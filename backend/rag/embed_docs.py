"""Phase 13: chunk the stored docs and save each chunk with its embedding.

Run from backend/:  python -m rag.embed_docs
Re-running replaces the chunks for the same documents and embedding model,
so changing the chunker and running again is safe.
"""
from collections import Counter

from database.connection import SessionLocal
from database.models import DocumentChunk, RepoDocument, Repository
from rag.chunker import chunk_document
from rag.embed import EMBEDDING_MODEL, embed
from rag.load_docs import REPO, SNAPSHOT_COMMIT


def main():
    db = SessionLocal()
    try:
        owner, name = REPO.split("/")
        repo = db.query(Repository).filter(Repository.owner == owner, Repository.name == name).one()
        docs = db.query(RepoDocument).filter_by(repository_id=repo.id, commit_sha=SNAPSHOT_COMMIT).all()
        if not docs:
            raise SystemExit("No documents found. Run: python -m rag.load_docs")

        rows = []  # (document, index, heading, content)
        for doc in docs:
            for i, chunk in enumerate(chunk_document(doc.path, doc.content)):
                rows.append((doc, i, chunk["heading"], chunk["content"]))
        print(f"{len(docs)} documents -> {len(rows)} chunks. Embedding with {EMBEDDING_MODEL} ...")

        # The heading goes into the embedded text too: "Timeout Configuration" says a lot about meaning.
        vectors = embed([f"{heading}\n{content}" for _, _, heading, content in rows])

        db.query(DocumentChunk).filter(
            DocumentChunk.document_id.in_([d.id for d in docs]),
            DocumentChunk.embedding_model == EMBEDDING_MODEL,
        ).delete(synchronize_session=False)
        for (doc, i, heading, content), vector in zip(rows, vectors):
            db.add(DocumentChunk(document_id=doc.id, chunk_index=i, heading=heading,
                                 content=content, embedding_model=EMBEDDING_MODEL, embedding=vector))
        db.commit()

        per_doc = Counter(doc.path for doc, *_ in rows)
        for path, n in sorted(per_doc.items()):
            print(f"{n:4} chunks  {path}")
        print(f"\nSaved {len(rows)} chunks, {len(vectors[0])} numbers each.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
