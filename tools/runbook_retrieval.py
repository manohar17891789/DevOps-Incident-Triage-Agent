"""FAISS similarity search over the runbook markdown docs.

Embeddings come from OpenAI (text-embedding-3-small). The index is built
once from data/runbooks/*.md and cached to disk under data/faiss_index/ so
repeated agent runs don't re-embed the corpus every time.
"""
from __future__ import annotations

from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

from config import settings
from tools.schemas import RunbookMatch, RunbookRetrievalInput, RunbookRetrievalOutput

RUNBOOKS_DIR = Path(__file__).resolve().parent.parent / "data" / "runbooks"
INDEX_DIR = Path(__file__).resolve().parent.parent / "data" / "faiss_index"

_VECTORSTORE: FAISS | None = None


def _load_runbook_documents() -> list[Document]:
    documents = []
    for path in sorted(RUNBOOKS_DIR.glob("*.md")):
        content = path.read_text()
        title = next((line.lstrip("# ").strip() for line in content.splitlines() if line.startswith("#")), path.stem)
        documents.append(Document(page_content=content, metadata={"doc_id": path.stem, "title": title}))
    return documents


def _get_vectorstore() -> FAISS:
    global _VECTORSTORE
    if _VECTORSTORE is not None:
        return _VECTORSTORE

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small", api_key=settings.openai_api_key)

    if INDEX_DIR.exists():
        _VECTORSTORE = FAISS.load_local(str(INDEX_DIR), embeddings, allow_dangerous_deserialization=True)
    else:
        documents = _load_runbook_documents()
        _VECTORSTORE = FAISS.from_documents(documents, embeddings)
        INDEX_DIR.mkdir(parents=True, exist_ok=True)
        _VECTORSTORE.save_local(str(INDEX_DIR))

    return _VECTORSTORE


def run_runbook_retrieval(input: RunbookRetrievalInput) -> RunbookRetrievalOutput:
    vectorstore = _get_vectorstore()
    results = vectorstore.similarity_search_with_score(input.query, k=input.top_k)

    matches = [
        RunbookMatch(
            doc_id=doc.metadata["doc_id"],
            title=doc.metadata["title"],
            content=doc.page_content,
            score=float(score),
        )
        for doc, score in results
    ]

    return RunbookRetrievalOutput(success=True, matches=matches)