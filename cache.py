import hashlib
import json
import os
import threading
import time

from config import CACHE_DIR, CACHE_TTL_SECONDS


class FileCache:
    """Simple file-based cache with TTL, hit/miss stats and clear support."""

    def __init__(self, directory: str, ttl_seconds: int):
        self.directory = directory
        self.ttl = ttl_seconds
        self.hits = 0
        self.misses = 0
        self._lock = threading.Lock()
        os.makedirs(self.directory, exist_ok=True)

    def _path(self, key: str) -> str:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return os.path.join(self.directory, f"{digest}.json")

    def get(self, key: str):
        path = self._path(key)
        if not os.path.exists(path):
            with self._lock:
                self.misses += 1
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                entry = json.load(f)
        except (json.JSONDecodeError, OSError):
            with self._lock:
                self.misses += 1
            return None

        if time.time() - entry["created_at"] > self.ttl:
            try:
                os.remove(path)
            except OSError:
                pass
            with self._lock:
                self.misses += 1
            return None

        with self._lock:
            self.hits += 1
        return entry["value"]

    def set(self, key: str, value) -> None:
        entry = {"key": key, "created_at": time.time(), "value": value}
        with open(self._path(key), "w", encoding="utf-8") as f:
            json.dump(entry, f, ensure_ascii=False)

    def purge_expired(self) -> int:
        removed = 0
        now = time.time()
        for name in os.listdir(self.directory):
            if not name.endswith(".json"):
                continue
            path = os.path.join(self.directory, name)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    entry = json.load(f)
                if now - entry["created_at"] > self.ttl:
                    os.remove(path)
                    removed += 1
            except (json.JSONDecodeError, OSError, KeyError):
                try:
                    os.remove(path)
                    removed += 1
                except OSError:
                    pass
        return removed

    def clear(self) -> int:
        removed = 0
        for name in os.listdir(self.directory):
            if name.endswith(".json"):
                try:
                    os.remove(os.path.join(self.directory, name))
                    removed += 1
                except OSError:
                    pass
        return removed

    def stats(self) -> dict:
        files = [n for n in os.listdir(self.directory) if n.endswith(".json")]
        size = sum(os.path.getsize(os.path.join(self.directory, n)) for n in files)
        total = self.hits + self.misses
        return {
            "entries": len(files),
            "size_kb": round(size / 1024, 1),
            "ttl_seconds": self.ttl,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(self.hits / total, 3) if total else 0.0,
        }


cache = FileCache(CACHE_DIR, CACHE_TTL_SECONDS)