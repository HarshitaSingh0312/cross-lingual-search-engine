# Built with the project root as context, not backend/ — see PROJECT_PLAN.md Section 3.
# `cross_lingual_retrieval/` and `backend/` are siblings on disk; backend imports from the
# former, so both need to be copied into the same image.
FROM python:3.11-slim

WORKDIR /code

COPY backend/requirements.txt backend/requirements.txt

# CPU-only torch first: satisfies requirements.txt's torch>=2.0.0 so the next install
# doesn't pull the default GPU build (CUDA/cuDNN/cuBLAS add several GB for no benefit —
# this container, and Render's free tier, have no GPU).
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY cross_lingual_retrieval/ cross_lingual_retrieval/
COPY backend/ backend/

WORKDIR /code/backend

EXPOSE 8000

CMD ["sh", "docker-entrypoint.sh"]
