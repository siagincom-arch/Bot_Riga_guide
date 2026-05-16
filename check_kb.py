from src.rag.singleton import get_kb_store
import asyncio
from src.config import settings

def main():
    kb = get_kb_store()
    results = kb._collection.get(
        where={"source": "user_fact"},
        include=["documents", "metadatas"]
    )
    print("User facts in KB:", results["ids"])
    if results["ids"]:
        for doc, meta in zip(results["documents"], results["metadatas"]):
            print(meta, "->", doc)

if __name__ == "__main__":
    main()
