"""Phase 13: find the doc chunks closest in meaning to a piece of text.

Run from backend/ to try it:  python -m rag.retrieve "how do I set a timeout"
"""
import sys

from sqlalchemy.orm import Session

from database.models import DocumentChunk
from rag.embed import EMBEDDING_MODEL, embed


def search(db: Session, text: str, k: int = 4) -> list[tuple[DocumentChunk, float]]:
    """Return the k closest chunks with their cosine distance (0 = same meaning)."""
    query_vector = embed([text])[0]
    distance = DocumentChunk.embedding.cosine_distance(query_vector)  # pgvector's <=> operator
    rows = (
        db.query(DocumentChunk, distance.label("distance"))
        .filter(DocumentChunk.embedding_model == EMBEDDING_MODEL)
        .order_by(distance)
        .limit(k)
        .all()
    )
    return [(chunk, float(dist)) for chunk, dist in rows]


if __name__ == "__main__":
    from database.connection import SessionLocal

    question = " ".join(sys.argv[1:]) or "how do I set a timeout"
    db = SessionLocal()
    try:
        print(f"Query: {question}\n")
        for chunk, dist in search(db, question):
            print(f"distance {dist:.3f}  {chunk.heading}")
            print("   " + chunk.content[:160].replace("\n", " ") + " ...\n")
    finally:
        db.close()
