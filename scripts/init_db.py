"""Tao bang PostgreSQL va collection Qdrant (khong can load model)."""
from pathlib import Path

from rag.config import load_settings
from rag.factory import build_stores

SCHEMA = Path(__file__).resolve().parent.parent / "sql" / "schema.sql"


def main() -> None:
    s = load_settings()
    metadata, vectors = build_stores(s)
    metadata.apply_schema(SCHEMA)
    vectors.ensure_collection(s.dense_dim)
    print(f"OK: schema PostgreSQL + collection '{s.qdrant_collection}' (dim={s.dense_dim})")


if __name__ == "__main__":
    main()
