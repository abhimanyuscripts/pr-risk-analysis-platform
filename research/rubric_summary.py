"""Phase 11, Task 5: summarise the filled-in rating sheet."""
from pathlib import Path

import pandas as pd

SHEET = Path(__file__).resolve().parent / "rubric" / "llm_prompt_v1_rubric.xlsx"
SCORES = ["Relevance (1-3)", "Specificity (1-3)", "Actionability (1-3)"]
INVENTED = "Invented something? (yes/no)"

df = pd.read_excel(SHEET, sheet_name="Rate these")
missing = df[df[SCORES + [INVENTED]].isna().any(axis=1)]["PR"].tolist()
if missing:
    raise SystemExit(f"Not rated yet: PRs {missing}. Fill every rating cell, save, and run again.")

df["group"] = df["LLM level"].map(lambda lvl: "LLM said low" if lvl == "low" else "LLM said medium/high")
df["invented"] = df[INVENTED].astype(str).str.strip().str.lower().eq("yes")

print(f"Rated answers: {len(df)}")
print("\nAVERAGE RATING (1 = poor, 3 = good)")
summary = df.groupby("group")[SCORES].mean().round(2)
summary.loc["all"] = df[SCORES].mean().round(2)
print(summary.to_string())
print(f"\nInvented something: {df.invented.sum()} of {len(df)} ({df.invented.mean():.0%})")
print("  by group:", df.groupby("group")["invented"].sum().to_dict())
print("\nShare rated 3 (good):")
for col in SCORES:
    print(f"  {col:22} {(df[col] == 3).mean():.0%}")
