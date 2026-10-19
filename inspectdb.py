import sys
from collections import Counter

import chromadb

from config import CHROMA_DIR

client = chromadb.PersistentClient(path=CHROMA_DIR)
collection = client.get_or_create_collection("competitor_pages")

total = collection.count()
print(f"Total chunks stored: {total}")
if total == 0:
    print("Database is empty. Scrape some competitors first.")
    sys.exit(0)

data = collection.get(include=["metadatas", "documents"])

chunks_per_competitor = Counter(m["competitor"] for m in data["metadatas"])
pages_per_competitor = {}
for m in data["metadatas"]:
    pages_per_competitor.setdefault(m["competitor"], set()).add(m["url"])

print("\nPer competitor:")
for name, count in chunks_per_competitor.items():
    print(f"  {name}: {count} chunks from {len(pages_per_competitor[name])} pages")

# Optional: python inspect_db.py Acme  -> prints sample chunks for that competitor
if len(sys.argv) > 1:
    wanted = sys.argv[1]
    print(f"\nSample chunks for {wanted}:")
    shown = 0
    for doc, meta in zip(data["documents"], data["metadatas"]):
        if meta["competitor"] == wanted:
            print(f"\n[{meta['url']}]\n{doc[:300]}")
            shown += 1
            if shown >= 5:
                break