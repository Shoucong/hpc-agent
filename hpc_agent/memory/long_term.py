"""Long-term memory — ChromaDB-based knowledge accumulation."""

from pathlib import Path

DB_DIR = Path(__file__).parent.parent.parent / "data" / "chromadb"


class LongTermMemory:
    """Store and retrieve diagnostic patterns via semantic search."""

    def __init__(self, db_dir: str = None):
        self.db_dir = db_dir or str(DB_DIR)
        Path(self.db_dir).mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        import chromadb
        self.client = chromadb.PersistentClient(path=self.db_dir)
        self.collection = self.client.get_or_create_collection(
            name="hpc_knowledge",
            metadata={"description": "HPC cluster diagnostic patterns"},
        )

    def save(self, text: str, metadata: dict = None):
        """Save a knowledge entry. Deduplicates by text content."""
        import hashlib
        doc_id = hashlib.md5(text.encode()).hexdigest()[:12]

        existing = self.collection.get(ids=[doc_id])
        if existing and existing["ids"]:
            # Update frequency count
            old_meta = existing["metadatas"][0] if existing["metadatas"] else {}
            freq = old_meta.get("frequency", 1) + 1
            new_meta = {**(metadata or {}), "frequency": freq}
            self.collection.update(ids=[doc_id], documents=[text], metadatas=[new_meta])
        else:
            self.collection.add(
                ids=[doc_id],
                documents=[text],
                metadatas=[{**(metadata or {}), "frequency": 1}],
            )

    def search(self, query: str, n_results: int = 3, skill: str = None) -> list[dict]:
        """Semantic search for similar knowledge entries."""
        where = {"skill": skill} if skill else None
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where,
            )
        except Exception:
            # If where filter fails (no matching metadata), search without filter
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
            )

        entries = []
        for i, doc in enumerate(results["documents"][0]):
            entries.append({
                "text": doc,
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                "distance": results["distances"][0][i] if results["distances"] else None,
            })
        return entries

    def count(self) -> int:
        return self.collection.count()