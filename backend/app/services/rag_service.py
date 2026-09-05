import re

import anthropic

from app.core.config import get_settings

settings = get_settings()

SYSTEM_PROMPT = (
    "You are a search assistant. Answer the user's query using only the numbered documents "
    "below, which may be in different languages than the query or each other. Write a concise "
    "answer (2-4 sentences) in the same language as the query. Every claim must cite the "
    "document it came from using its bracketed number, e.g. [1] or [2][3]. Never cite a number "
    "that isn't listed, and never use outside knowledge. If the documents don't actually answer "
    "the query, say so instead of guessing."
)


def extract_cited_numbers(answer: str, doc_count: int) -> list[int]:
    # The model is instructed not to invent citation numbers, but it's an LLM output, not a
    # guarantee - out-of-range numbers get silently dropped rather than trusted as valid ids.
    cited = {int(n) for n in re.findall(r"\[(\d+)\]", answer)}
    return sorted(n for n in cited if 1 <= n <= doc_count)


class RagService:
    """Synthesizes an answer over documents the caller already retrieved - this service never
    runs a search itself. Only called on an explicit "Get AI answer" click (see Phase 7 in
    PROJECT_PLAN.md), never automatically per search, since every call spends real API credit."""

    def __init__(self) -> None:
        self._client: anthropic.AsyncAnthropic | None = None

    def _get_client(self) -> anthropic.AsyncAnthropic:
        if self._client is None:
            self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        return self._client

    async def synthesize(self, query: str, docs: list[dict]) -> str:
        """docs: ordered list of {"title", "summary", "language"} dicts, numbered [1..len(docs)]
        in the order given. That order must match the caller's own numbering (search rank order
        from the frontend), since the returned citations reference documents by that position."""
        context = "\n\n".join(
            f"[{i}] ({doc['language']}) {doc['title']}\n{doc['summary']}"
            for i, doc in enumerate(docs, start=1)
        )
        message = await self._get_client().messages.create(
            model=settings.rag_model_name,
            max_tokens=settings.rag_max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"Documents:\n\n{context}\n\nQuery: {query}"}],
        )
        return message.content[0].text

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()


rag_service = RagService()
