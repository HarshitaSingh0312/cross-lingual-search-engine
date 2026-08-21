import torch
from sentence_transformers import SentenceTransformer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import Document, Embedding

settings = get_settings()


class RetrievalService:
    """Encodes queries with the same multilingual model/normalization used to build the
    stored document embeddings (see cross_lingual_retrieval/src/dense_retrieval.py), then
    searches via pgvector cosine distance instead of that module's in-memory FAISS index —
    FAISS stays an offline benchmarking tool per PROJECT_PLAN.md Section 2; pgvector is what
    runs in production so vector search lives next to the relational data, one fewer moving part.

    DenseRetriever itself isn't instantiated here: its __init__ has script-oriented side effects
    (creates a `data/embeddings/` dir relative to cwd) that don't fit a long-running server process.
    """

    def __init__(self) -> None:
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model: SentenceTransformer | None = None

    def load(self) -> None:
        self.model = SentenceTransformer(settings.embedding_model_name).to(self.device)

    def encode_query(self, query: str) -> list[float]:
        # No manual L2-normalization: pgvector's cosine_distance operator computes true
        # cosine similarity from the raw vectors, unlike the original FAISS IndexFlatIP
        # setup which needed pre-normalized vectors to approximate cosine via inner product.
        embedding = self.model.encode([query], convert_to_numpy=True, device=self.device)[0]
        return embedding.tolist()

    async def search(self, db: AsyncSession, query: str, top_k: int = 10) -> list[dict]:
        query_vector = self.encode_query(query)
        distance = Embedding.vector.cosine_distance(query_vector)
        stmt = (
            select(Document, distance.label("distance"))
            .join(Embedding, Embedding.document_id == Document.id)
            .order_by(distance)
            .limit(top_k)
        )
        rows = (await db.execute(stmt)).all()
        return [
            {
                "doc_id": doc.id,
                "title": doc.title,
                "summary": doc.summary,
                "language": doc.language,
                "url": doc.url,
                "score": 1 - dist,
            }
            for doc, dist in rows
        ]


retrieval_service = RetrievalService()
