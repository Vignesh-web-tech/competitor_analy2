import hashlib

import chromadb

from config import CHROMA_DIR, CHUNK_OVERLAP, CHUNK_SIZE

_client = chromadb.PersistentClient(path=CHROMA_DIR)
_collection = _client.get_or_create_collection(
    name="competitor_pages",
    metadata={"hnsw:space": "cosine"},
)


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list:
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            # try to cut at a sentence boundary
            boundary = text.rfind(". ", start + size // 2, end)
            if boundary != -1:
                end = boundary + 1
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


def delete_competitor(name: str) -> None:
    _collection.delete(where={"competitor": name})


def index_pages(competitor: str, website: str, pages: list) -> int:
    """Replace everything stored for this competitor with freshly chunked pages."""
    delete_competitor(competitor)

    ids, documents, metadatas = [], [], []
    for page in pages:
        url_hash = hashlib.md5(page["url"].encode("utf-8")).hexdigest()[:10]
        for i, chunk in enumerate(chunk_text(page["text"])):
            ids.append(f"{competitor}::{url_hash}::{i}")
            documents.append(chunk)
            metadatas.append(
                {
                    "competitor": competitor,
                    "website": website,
                    "url": page["url"],
                    "title": page["title"],
                }
            )

    batch = 200
    for i in range(0, len(ids), batch):
        _collection.add(
            ids=ids[i : i + batch],
            documents=documents[i : i + batch],
            metadatas=metadatas[i : i + batch],
        )
    return len(ids)


def search(query: str, n_results: int = 30, competitor: str | None = None) -> list:
    total = _collection.count()
    if total == 0:
        return []

    kwargs = {"query_texts": [query], "n_results": min(n_results, total)}
    if competitor:
        kwargs["where"] = {"competitor": competitor}
    result = _collection.query(**kwargs)

    hits = []
    for doc, meta, dist in zip(
        result["documents"][0], result["metadatas"][0], result["distances"][0]
    ):
        hits.append(
            {
                "competitor": meta["competitor"],
                "website": meta["website"],
                "url": meta["url"],
                "title": meta["title"],
                "text": doc,
                "similarity": round(1 - dist, 4),
            }
        )
    return hits


def stats() -> dict:
    return {"total_chunks": _collection.count()}