import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

from src.kb.store import KBStore

async def main():
    kb = KBStore(chroma_path="./data/chroma", sqlite_path="./data/bot.db")
    results = kb._collection.get(
        where={"source": "user_fact"},
        include=["documents", "metadatas"]
    )
    print("User facts in DB:")
    if results["ids"]:
        for doc, meta in zip(results["documents"], results["metadatas"]):
            print(f"Place: {meta.get('place_id')} | Fact: {doc}")
    else:
        print("None found")

if __name__ == "__main__":
    asyncio.run(main())
