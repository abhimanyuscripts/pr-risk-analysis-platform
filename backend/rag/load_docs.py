"""Phase 12: load a fixed snapshot of a repository's docs into repo_documents.

Run from backend/:  python -m rag.load_docs

Leakage rule: the docs come from ONE commit made before the test period starts,
so no test PR is ever shown documentation written after it. The CHANGELOG is
excluded because it lists later bug fixes, which would hand the LLM the answers.
Safe to re-run: existing rows for the same file and commit are updated.
"""
import httpx

from database.connection import SessionLocal
from database.models import RepoDocument, Repository

REPO = "encode/httpx"
# Last master commit before the test period (2022-05-26): "Version 0.23.0 (#2214)", 2022-05-23.
SNAPSHOT_COMMIT = "89cdd903b2f339c6ae319773c31b8c9352bd9cd8"

DOC_PATHS = [
    "README.md",
    ".github/PULL_REQUEST_TEMPLATE.md",
    "docs/index.md",
    "docs/quickstart.md",
    "docs/advanced.md",
    "docs/async.md",
    "docs/api.md",
    "docs/compatibility.md",
    "docs/contributing.md",
    "docs/environment_variables.md",
    "docs/exceptions.md",
    "docs/http2.md",
    "docs/troubleshooting.md",
]
# Left out on purpose: CHANGELOG.md (future fixes = leakage), README_chinese.md (translation),
# .github/CONTRIBUTING.md (near-copy of docs/contributing.md), LICENSE.md, code_of_conduct.md,
# issue template, third_party_packages.md (no guidance on how httpx code should be written).

RAW_URL = "https://raw.githubusercontent.com/{repo}/{sha}/{path}"


def main():
    db = SessionLocal()
    try:
        owner, name = REPO.split("/")
        repo = db.query(Repository).filter(Repository.owner == owner, Repository.name == name).one()
        total = 0
        with httpx.Client(timeout=15.0) as client:
            for path in DOC_PATHS:
                response = client.get(RAW_URL.format(repo=REPO, sha=SNAPSHOT_COMMIT, path=path))
                response.raise_for_status()
                content = response.text
                doc = db.query(RepoDocument).filter_by(
                    repository_id=repo.id, path=path, commit_sha=SNAPSHOT_COMMIT).first()
                if doc is None:
                    doc = RepoDocument(repository_id=repo.id, path=path, commit_sha=SNAPSHOT_COMMIT)
                    db.add(doc)
                doc.content = content
                total += len(content)
                print(f"{len(content):7,} chars  {path}")
        db.commit()
        print(f"\n{len(DOC_PATHS)} documents, {total:,} characters, commit {SNAPSHOT_COMMIT[:7]}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
