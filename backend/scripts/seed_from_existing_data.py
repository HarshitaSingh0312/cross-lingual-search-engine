"""One-time seed: loads the existing Wikipedia corpus + its cached LaBSE embeddings
(from cross_lingual_retrieval/) into a freshly migrated Postgres database.

Run once, after `alembic upgrade head`:
    python scripts/seed_from_existing_data.py

Idempotent: truncates documents/embeddings first, then bulk-inserts in small batches
(a handful of round trips instead of thousands) so it finishes quickly and isn't sitting
in one long-lived transaction that a serverless Postgres connection (Neon) can drop.
"""

import pickle
import sys
import uuid
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, insert, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.db.models import Document, Embedding  # noqa: E402

settings = get_settings()
ML_CORE = Path(__file__).resolve().parents[2] / "cross_lingual_retrieval"
BATCH_SIZE = 250


def chunked(items, size):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def main() -> None:
    docs_df = pd.read_csv(ML_CORE / "data" / "processed" / "all_train.csv")
    embeddings_path = ML_CORE / "data" / "embeddings" / "doc_embeddings_sentence-transformers_LaBSE.pkl"
    with open(embeddings_path, "rb") as f:
        embeddings = pickle.load(f)

    assert len(docs_df) == len(embeddings), "row count mismatch between CSV and cached embeddings"

    document_rows = [
        {
            "id": row["doc_id"],
            "title": row["title"],
            "summary": row["summary"],
            "url": row["url"] if pd.notna(row["url"]) else None,
            "language": row["language"],
            "domain": "wikipedia",
        }
        for _, row in docs_df.iterrows()
    ]
    embedding_rows = [
        {
            "id": uuid.uuid4(),
            "document_id": row["doc_id"],
            "model_name": settings.embedding_model_name,
            "vector": vector.tolist(),
        }
        for (_, row), vector in zip(docs_df.iterrows(), embeddings)
    ]

    engine = create_engine(settings.sync_database_url)
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE embeddings, documents RESTART IDENTITY CASCADE"))

    for batch in chunked(document_rows, BATCH_SIZE):
        with engine.begin() as conn:
            conn.execute(insert(Document), batch)

    for batch in chunked(embedding_rows, BATCH_SIZE):
        with engine.begin() as conn:
            conn.execute(insert(Embedding), batch)

    print(f"Seeded {len(document_rows)} documents + {len(embedding_rows)} embeddings.")


if __name__ == "__main__":
    main()
