"""Phase 11, Task 5: export a fixed sample of LLM answers for manual rating.

AUC says how well the LLM's scores rank PRs; it says nothing about whether the
explanations are any good. This writes 25 answers to an Excel sheet that a person
rates on relevance, specificity, actionability and invented content.

Sample: 10 PRs the LLM rated medium/high + 15 it rated low (stratified, so the
rare flagged answers are not missed), drawn with a fixed seed and shuffled.
The risk label is NOT shown, so it cannot bias the rating.
"""
import os
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation
from sqlalchemy import create_engine, text

from load_dataset import load_training_table
from split import chronological_split

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
PROMPT_VERSION = 1
SEED = 42
OUT = Path(__file__).resolve().parent / "rubric" / f"llm_prompt_v{PROMPT_VERSION}_rubric.xlsx"
RATING_COLUMNS = ["Relevance (1-3)", "Specificity (1-3)", "Actionability (1-3)", "Invented something? (yes/no)"]

QUERY = text("""
    SELECT pr.github_pr_number, pr.title, a.risk_score, a.risk_level, a.result
    FROM llm_analyses a
    JOIN pull_requests pr ON pr.id = a.pull_request_id
    JOIN repositories r ON r.id = pr.repository_id
    WHERE r.full_name = 'encode/httpx' AND a.model = :model
      AND a.prompt_version = :pv AND a.use_rag = false
""")

HOW_TO_RATE = [
    ("What you do", "For each row: open the PR link, read the 'Files changed' tab, then rate the LLM's summary and concerns."),
    ("Relevance", "1 = about something the PR does not really do · 2 = partly on target · 3 = describes what the PR actually changes"),
    ("Specificity", "1 = generic ('this could have bugs') · 2 = some detail · 3 = names concrete files, functions or behaviour"),
    ("Actionability", "1 = a reviewer learns nothing to check · 2 = vague hint · 3 = a reviewer knows exactly what to look at"),
    ("Invented something?", "yes = mentions a file, function or behaviour that is NOT in the PR · no = everything it mentions is real"),
    ("Notes", "Optional: anything notable (good catch, wrong reasoning, missed risk)."),
    ("Ignore", "Whether the PR was 'risky' is deliberately hidden. Rate the explanation, not the score."),
]


def concerns_text(result: dict) -> str:
    items = (result or {}).get("concerns") or []
    return "\n".join(f"• [{c['category']}] {c['file']}: {c['explanation']}" for c in items) or "(none)"


if __name__ == "__main__":
    if OUT.exists():
        raise SystemExit(f"{OUT} already exists; not overwriting your ratings. Delete it first to re-export.")

    df = load_training_table()
    _, test = chronological_split(df)
    with create_engine(os.getenv("DATABASE_URL")).connect() as conn:
        llm = pd.read_sql(QUERY, conn, params={"model": MODEL, "pv": PROMPT_VERSION})
    llm = llm[llm["github_pr_number"].isin(test["github_pr_number"])]

    flagged = llm[llm["risk_level"] != "low"]
    sample = pd.concat([
        flagged.sample(n=min(10, len(flagged)), random_state=SEED),
        llm[llm["risk_level"] == "low"].sample(n=15, random_state=SEED),
    ]).sample(frac=1, random_state=SEED)       # shuffle so the order gives nothing away

    sheet = pd.DataFrame({
        "PR": sample["github_pr_number"],
        "Link": "https://github.com/encode/httpx/pull/" + sample["github_pr_number"].astype(str) + "/files",
        "Title": sample["title"],
        "LLM score": sample["risk_score"],
        "LLM level": sample["risk_level"],
        "LLM summary": sample["result"].map(lambda r: (r or {}).get("summary", "")),
        "LLM concerns": sample["result"].map(concerns_text),
        **{col: "" for col in RATING_COLUMNS},
        "Notes": "",
    })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(OUT, engine="openpyxl") as writer:
        sheet.to_excel(writer, sheet_name="Rate these", index=False)
        pd.DataFrame(HOW_TO_RATE, columns=["Item", "Meaning"]).to_excel(writer, sheet_name="How to rate", index=False)

    # Make it pleasant to fill in: widths, wrapping, frozen header, dropdowns, links.
    wb = load_workbook(OUT)
    ws = wb["Rate these"]
    widths = {"A": 7, "B": 14, "C": 34, "D": 9, "E": 9, "F": 55, "G": 60, "H": 12, "I": 12, "J": 13, "K": 14, "L": 30}
    for col, w in widths.items():
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "D2"
    header_fill = PatternFill("solid", start_color="DCE6F2")
    rate_fill = PatternFill("solid", start_color="FFF4CC")
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = header_fill
        cell.alignment = Alignment(wrap_text=True, vertical="top")
    one_to_three = DataValidation(type="list", formula1='"1,2,3"', allow_blank=True)
    yes_no = DataValidation(type="list", formula1='"yes,no"', allow_blank=True)
    ws.add_data_validation(one_to_three)
    ws.add_data_validation(yes_no)
    last = ws.max_row
    one_to_three.add(f"H2:J{last}")
    yes_no.add(f"K2:K{last}")
    for row in ws.iter_rows(min_row=2, max_row=last):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
        link = row[1]
        link.hyperlink = link.value
        link.value = "open diff"
        link.font = Font(color="0563C1", underline="single")
        for cell in row[7:11]:
            cell.fill = rate_fill
    guide = wb["How to rate"]
    guide.column_dimensions["A"].width = 22
    guide.column_dimensions["B"].width = 110
    for row in guide.iter_rows():
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    wb.save(OUT)

    print(f"Wrote {len(sheet)} answers to {OUT}")
    print(f"  {min(10, len(flagged))} rated medium/high by the LLM, 15 rated low (seed {SEED}, shuffled)")
