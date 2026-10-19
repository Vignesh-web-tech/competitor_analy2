import json
import os
import threading

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

import analyzer
import rag
from cache import cache
from config import COMPETITORS_FILE, STATIC_DIR
from scraper import crawl_site, normalize_url

app = FastAPI(title="Competitor Analyzer")

_store_lock = threading.Lock()
ingest_status: dict = {}


# ---------- competitor store (simple JSON file) ----------
def load_competitors() -> list:
    if not os.path.exists(COMPETITORS_FILE):
        return []
    with open(COMPETITORS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_competitors(items: list) -> None:
    with open(COMPETITORS_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)


# ---------- models ----------
class CompetitorIn(BaseModel):
    name: str
    url: str


class SearchIn(BaseModel):
    query: str
    top_k: int = 5
    with_analysis: bool = True


# ---------- background ingestion ----------
def run_ingest(names: list, force: bool) -> None:
    competitors = {c["name"]: c for c in load_competitors()}
    for name in names:
        comp = competitors.get(name)
        if not comp:
            continue
        ingest_status[name] = {"state": "running", "pages": 0, "chunks": 0, "error": None}
        try:
            pages = crawl_site(comp["url"], force=force)
            chunks = rag.index_pages(name, comp["url"], pages)
            ingest_status[name] = {
                "state": "done",
                "pages": len(pages),
                "chunks": chunks,
                "error": None,
            }
        except Exception as exc:
            ingest_status[name] = {
                "state": "error",
                "pages": 0,
                "chunks": 0,
                "error": str(exc),
            }


# ---------- routes ----------
@app.get("/")
def home():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/api/health")
def health():
    return {"status": "ok", "rag": rag.stats(), "cache": cache.stats()}


@app.get("/api/competitors")
def list_competitors():
    return load_competitors()


@app.post("/api/competitors")
def add_competitor(body: CompetitorIn):
    with _store_lock:
        items = load_competitors()
        name = body.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Name is required")
        if any(c["name"].lower() == name.lower() for c in items):
            raise HTTPException(status_code=409, detail="Competitor already exists")
        items.append({"name": name, "url": normalize_url(body.url.strip())})
        save_competitors(items)
    return {"ok": True}


@app.delete("/api/competitors/{name}")
def remove_competitor(name: str):
    with _store_lock:
        items = [c for c in load_competitors() if c["name"] != name]
        save_competitors(items)
    rag.delete_competitor(name)
    ingest_status.pop(name, None)
    return {"ok": True}


@app.post("/api/ingest")
def ingest(background_tasks: BackgroundTasks, name: str | None = None, force: bool = False):
    """Scrape and index one competitor (?name=...) or all of them. Use force=true to bypass the cache."""
    all_names = [c["name"] for c in load_competitors()]
    if name:
        if name not in all_names:
            raise HTTPException(status_code=404, detail="Competitor not found")
        names = [name]
    else:
        names = all_names
    if not names:
        raise HTTPException(status_code=400, detail="Add at least one competitor first")

    for n in names:
        ingest_status[n] = {"state": "queued", "pages": 0, "chunks": 0, "error": None}
    background_tasks.add_task(run_ingest, names, force)
    return {"started": names, "force": force}


@app.get("/api/ingest/status")
def get_ingest_status():
    return ingest_status


@app.post("/api/search")
def search(body: SearchIn):
    query = body.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query is required")

    ranked = analyzer.rank_competitors(query)[: body.top_k]
    analysis = None
    if body.with_analysis:
        try:
            analysis = analyzer.generate_analysis(query, ranked)
        except Exception as exc:
            analysis = f"Analysis failed: {exc}"

    return {"query": query, "competitors": ranked, "analysis": analysis}


@app.get("/api/cache/stats")
def cache_stats():
    return cache.stats()


@app.post("/api/cache/purge-expired")
def cache_purge():
    return {"removed": cache.purge_expired()}


@app.post("/api/cache/clear")
def cache_clear():
    return {"removed": cache.clear()}