"""Phase 13: cut a markdown document into chunks for embedding.

Rules:
- Split at markdown headings, so each chunk is about one topic.
- Ignore '#' lines inside ``` code blocks: in Python code '# ...' is a comment,
  not a heading.
- Long sections are cut into ~MAX_CHARS pieces at paragraph breaks, with a
  small overlap so a sentence near a cut still appears with its context.
- Each chunk keeps its heading path (file > section > subsection) so the LLM,
  and a person reading the logs, knows where the text came from.
"""
import re

MAX_CHARS = 1_200
OVERLAP_CHARS = 150
MIN_CHARS = 80
HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")


def split_sections(text: str) -> list[tuple[list[str], str]]:
    """Return (heading path, body) for each heading-delimited section."""
    sections, path, body, in_code = [], [], [], False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_code = not in_code
        match = None if in_code else HEADING.match(line)
        if match:
            if "".join(body).strip():
                sections.append((list(path), "\n".join(body).strip()))
            level, title = len(match.group(1)), match.group(2)
            path = path[: level - 1] + [title]
            body = []
        else:
            body.append(line)
    if "".join(body).strip():
        sections.append((list(path), "\n".join(body).strip()))
    return sections


def split_long(body: str) -> list[str]:
    """Cut a long section at paragraph breaks into pieces of about MAX_CHARS."""
    if len(body) <= MAX_CHARS:
        return [body]
    paragraphs = re.split(r"\n\s*\n", body)
    pieces, current = [], ""
    for para in paragraphs:
        if current and len(current) + len(para) + 2 > MAX_CHARS:
            pieces.append(current)
            current = current[-OVERLAP_CHARS:] + "\n\n" + para  # carry a little context over
        else:
            current = f"{current}\n\n{para}" if current else para
        while len(current) > MAX_CHARS * 2:      # one giant paragraph (e.g. a long code block)
            pieces.append(current[:MAX_CHARS])
            current = current[MAX_CHARS - OVERLAP_CHARS:]
    if current.strip():
        pieces.append(current)
    return pieces


def chunk_document(path: str, text: str) -> list[dict]:
    """Return [{'heading': ..., 'content': ...}] ready to embed and store."""
    chunks = []
    for heading_path, body in split_sections(text):
        heading = " > ".join([path, *heading_path])
        for piece in split_long(body):
            if len(piece.strip()) < MIN_CHARS and chunks and chunks[-1]["heading"] == heading:
                chunks[-1]["content"] += "\n\n" + piece  # tiny leftover: glue to previous
            elif len(piece.strip()) >= MIN_CHARS:
                chunks.append({"heading": heading, "content": piece.strip()})
    return chunks
