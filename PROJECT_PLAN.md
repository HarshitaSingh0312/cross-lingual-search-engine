# Cross-Lingual Search Engine — Build Plan

**Owner:** Harshita Singh
**Goal:** Convert the existing Streamlit cross-lingual IR demo into a full-stack project (HTML+CSS+Javascript+React + FastAPI + PostgreSQL) that is strong enough — on the backend specifically, keep frontend easy and simple — to carry a college placement interview.
**Scope decision:** breadth is intentional, not padding. Every feature below must be built deep enough to defend in an interview (why this design, what breaks, what's the tradeoff) — depth of understanding matters more than checkbox count. See "How we'll work" at the bottom.

---

## 1. What's being kept from the current project

Location: `cross_lingual_retrieval/` (existing folder, kept as-is, reused as the ML core — not rewritten from scratch).

- `src/dense_retrieval.py` — `DenseRetriever` class (LaBSE/XLM-R/mBERT + FAISS). Becomes the thing the FastAPI service wraps, not a standalone script.
- `src/baseline.py` — BM25 + translate-test baselines. Reused for hybrid search (Tier 2).
- `src/evaluation.py` — MRR/Recall/nDCG metrics. Reused for the online (feedback-driven) eval loop.
- `src/preprocessing.py`, `src/data_collection.py` — reused and extended for corpus expansion (Section 4).
- `web_app/streamlit_app.py` — retired once the React frontend + FastAPI search endpoint reach parity.

## 2. Tech stack

| Layer | Choice | Notes |
|---|---|---|
| Frontend | React (+ HTML+CSS+javascript) | kept simple on purpose — this project is backend-focused |
| Backend | FastAPI (async) | wraps the existing ML core as services |
| Primary DB | PostgreSQL + `pgvector` extension | relational data + vector search in one place |
| Cache / broker | Redis | query caching + Celery broker |
| Background jobs | Celery (Redis broker) | reindexing, ingestion, batch encoding |
| Vector search | `pgvector` (HNSW/IVFFlat) in production; FAISS benchmarked offline on a dev machine only | FAISS+PyTorch has a known segfault bug on ARM (see Section 10) — production runs on an ARM VM, so pgvector is the deployed backend, FAISS is a documented comparison, not a live dependency |
| Migrations | Alembic | |
| Auth | JWT (`python-jose` + `passlib`) | RBAC: user / admin |
| Observability | `structlog`, `prometheus-fastapi-instrumentator`, Grafana | |
| Testing | `pytest`, `pytest-asyncio`, `httpx.TestClient`, Hypothesis | |
| Containers | Docker + docker-compose | built early (Phase 2), not bolted on at the end |
| CI/CD | GitHub Actions | lint + test on push; build/push/deploy on merge to main |
| Deployment | Oracle Cloud "Always Free" VM (Ampere A1, ARM) — Docker Compose + nginx/TLS, provisioned via Terraform (OCI provider) | switched from AWS to avoid real ongoing cost (ALB/Fargate/ElastiCache/NAT Gateway all bill from day one); see Section 10 for known gotchas |
| Load testing | Locust or k6 | produces real p50/p95/p99 numbers |
| RAG / LLM | Anthropic API, Claude Haiku 4.5, prepaid credits ($2 loaded, auto-reload **off**) | ~$0.002-0.003/search at this model+prompt size (~830 searches on $2) — plenty for dev/demo; see Phase 7 and Section 10 |

## 3. Repo layout (target)

```
cross_lingual_retrieval_project/
├── cross_lingual_retrieval/          # existing ML core, reused as a library
│   └── src/                          # dense_retrieval.py, baseline.py, evaluation.py, ...
├── backend/
│   ├── app/
│   │   ├── main.py                   # FastAPI app + lifespan (load model/index once)
│   │   ├── core/                     # config (pydantic-settings), security, logging
│   │   ├── api/v1/                   # routers: auth, search, feedback, history, bookmarks,
│   │   │                             #   analytics, api_keys, admin, health
│   │   ├── db/                       # SQLAlchemy models, session, alembic/
│   │   ├── services/                 # retrieval_service, hybrid_search, rag, cache_service,
│   │   │                             #   ingestion_service, recommendation_service
│   │   ├── workers/                  # celery app + tasks: encode_documents, reindex, ingest
│   │   └── schemas/                  # pydantic request/response models
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/                          # pages, components, api client, auth context
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml                # fastapi + postgres(pgvector) + redis + celery worker
├── .github/workflows/ci.yml
├── docs/
│   └── system_design.md              # written tradeoff doc (FAISS vs pgvector, scaling, consistency)
└── PROJECT_PLAN.md                   # this file
```

## 4. Corpus expansion plan

- **Languages:** expand beyond EN/ES/FR — add languages already supported by LaBSE/XLM-R/mBERT (e.g., Hindi, German, Arabic). This is a data-collection change, not a modeling change.
- **Domains:** mix in news articles alongside Wikipedia so retrieval is evaluated on heterogeneous text, not just clean encyclopedic content.
- **Benchmark:** evaluate against an established multilingual IR dataset (MIRACL) in addition to the self-scraped test set, so results are comparable to published numbers.
- **Scale:** target 100K+ documents — large enough that a flat FAISS/pgvector index stops being viable and IVF/HNSW indexing becomes a real requirement, not a demo flag.
- **Ingestion:** move from a one-time scrape script to a scheduled pipeline (Celery beat) that periodically pulls new documents and incrementally updates the index (ties into index versioning in Phase 11).

## 5. Dropped ideas (for the record)

- **Multi-tenant "bring your own corpus"** — dropped. This project stays a shared-corpus search engine (all users search the same expanding dataset), not a per-user SaaS search platform. Revisit only if we explicitly decide to pivot the product.

## 6. Database schema (initial entities)

- `users` — id, email, hashed_password, role (user/admin), created_at
- `documents` — id, title, summary, url, language, domain (wikipedia/news), source_metadata, created_at
- `embeddings` — document_id FK, model_name, vector (pgvector column), index_version
- `search_queries` — id, user_id FK (nullable for anon), query_text, detected_language, model_used, created_at
- `search_results` — search_query_id FK, document_id FK, rank, score
- `feedback` — search_result_id FK, user_id FK, is_relevant (bool), created_at
- `saved_searches` / `bookmarks` — user_id FK, document_id or query_text, created_at
- `api_keys` — user_id FK, key_hash, tier, quota, usage_count
- `index_versions` — id, model_name, index_type (faiss/pgvector), status, created_at, activated_at
- `analytics_rollups` — date, metric_name, value (populated by scheduled aggregation job)

Exact columns/types get finalized in Phase 1 as an Alembic migration, not fully locked here.

## 7. API surface (initial, grouped)

- **Auth:** `POST /auth/signup`, `POST /auth/login`, `POST /auth/refresh`
- **Search:** `GET /search?q=&model=&top_k=` (dense), `/search/hybrid`, `POST /search/rag` (answer synthesis — **on-demand only**, not fired automatically on every search: frontend shows a "Get AI answer" button under the results, since each call costs LLM API tokens; ordinary search stays free/instant)
- **Feedback:** `POST /feedback` (thumbs up/down on a result)
- **History/Bookmarks:** `GET /me/history`, `POST /me/bookmarks`, `GET /me/bookmarks`
- **Recommendations:** `GET /me/related-searches`
- **Admin:** `POST /admin/ingest` (trigger corpus ingestion job), `GET /admin/jobs/{id}` (status), `GET /admin/analytics`
- **API keys:** `POST /me/api-keys`, `GET /me/api-keys`
- **Ops:** `GET /health`, `GET /ready`, `GET /metrics`

## 8. Build roadmap (ordered by dependency, not by date)

Each phase should end with something runnable/testable before moving to the next — plumbing (Phase 1–3) has to exist before things that build on it (caching needs endpoints, event-driven ingestion needs background jobs, etc).

- [ ] **Phase 0 — Setup**: init git repo, initial commit of existing project as-is, repo layout scaffolding, branch strategy (`feat/*` branches, incremental commits/pushes).
- [ ] **Phase 1 — Backend foundation**: FastAPI skeleton, Postgres + pgvector schema (Alembic), wrap `DenseRetriever` as a service loaded once at startup, working `/search` endpoint against real data.
- [ ] **Phase 2 — Dockerize local dev**: docker-compose (FastAPI + Postgres/pgvector + Redis), env-based config (`pydantic-settings`), no hardcoded paths.
- [ ] **Phase 3 — Auth**: JWT signup/login, password hashing, RBAC (user/admin), protected routes.
- [ ] **Phase 4 — Core relational features**: search history logging, feedback (thumbs up/down), bookmarks/saved searches.
- [ ] **Phase 5 — Caching + background jobs**: Redis query caching, Celery for reindexing/batch encoding, job-status endpoint.
- [ ] **Phase 6 — Hybrid search**: BM25 + dense fusion (Reciprocal Rank Fusion), cross-encoder re-ranking on top-k.
- [ ] **Phase 7 — RAG layer**: LLM-based answer synthesis over retrieved cross-lingual docs, with clickable `[1] [2] [3]` citations linking to the matching result card. Triggered by an explicit "Get AI answer" button (opt-in, not automatic) to control LLM API cost; answer box is labeled "Generated by AI" for transparency.
  - [ ] 7a. Anthropic account set up with **prepaid credits** ($2 to start) — this is a pay-as-you-go balance deducted per call, not a per-click card charge; card is only touched again if we manually reload or explicitly turn on auto-reload (left **off** for now, so the feature just stops working at $0 instead of surprise-billing).
  - [ ] 7b. Model: Claude Haiku 4.5 — cheap enough for this task (short synthesis + citations over already-retrieved docs, not deep reasoning) and $2 covers ~800+ searches during dev/demo.
  - [ ] 7c. API key stored as a backend secret/env var, never in frontend code or committed to git.
- [ ] **Phase 8 — Corpus expansion**: more languages, news domain, MIRACL benchmark integration, scheduled ingestion pipeline, IVF/HNSW indexing at scale.
- [ ] **Phase 9 — Personalization & API access**: related-searches recommendations, API keys with tiered quotas.
- [ ] **Phase 10 — Observability**: structured logging, Prometheus metrics, Grafana dashboard, health/readiness checks.
- [ ] **Phase 11 — Event-driven ingestion + index versioning**: Redis Streams event on document upload, background consumer, zero-downtime index swap.
- [ ] **Phase 12 — Load testing**: Locust/k6 script, record real p50/p95/p99 latency numbers.
- [ ] **Phase 13 — Testing + CI**: pytest unit/integration coverage, property-based tests on ranking logic, GitHub Actions running lint+test on every push.
- [ ] **Phase 14 — Frontend**: React app — search, auth, history, bookmarks, model-comparison toggle, admin analytics dashboard.
- [ ] **Phase 15 — CI/CD to live deployment on Oracle Cloud** (first deployment, no prior experience — see Section 10 before starting):
  - [ ] 15a. Confirm signup card is eligible (real credit/debit, not prepaid/virtual/PIN-debit); create OCI account.
  - [ ] 15b. Launch the Always Free Ampere A1 VM (2 OCPU/12GB) in a 3-availability-domain region; have a capacity-retry approach ready in case of "out of host capacity."
  - [ ] 15c. Harden + configure the VM: open ports at *both* the OCI Security List and the OS-level firewall (iptables/ufw); SSH hardening.
  - [ ] 15d. Run the full stack via Docker Compose on the VM (FastAPI + Postgres/pgvector + Redis + Celery worker); nginx as reverse proxy; TLS via certbot/Let's Encrypt.
  - [ ] 15e. Set up a free external uptime monitor (e.g., UptimeRobot) pinging the API — doubles as reclaim-prevention and as an observability feature.
  - [ ] 15f. Provision the above with Terraform using the OCI provider, so it's reproducible instead of console-clicked.
  - [ ] 15g. GitHub Actions: build/push Docker images, auto-deploy on merge to main; project stays live at a public URL, redeployed continuously.
- [ ] **Phase 16 — System design doc**: written tradeoff doc (FAISS vs pgvector, scaling, consistency model for index swap) + resume bullet points pulled from real, measured numbers.

## 10. Deployment prerequisites & known gotchas (Oracle Cloud)

Researched before starting Phase 15 specifically to avoid getting stuck mid-deployment. Revisit this section if anything below turns out to have changed by the time we deploy.

- **Free tier was cut in June 2026, no announcement.** Always Free Ampere A1 is now **2 OCPU / 12GB RAM** (was 4/24) — still enough for FastAPI + Postgres + Redis + Celery together, but with less headroom than typical Oracle write-ups describe. Oracle has shown it can change "Always Free" terms without warning; not a monetary risk, but a reliability one to keep in mind.
- **Signup requires a qualifying card.** Real credit/debit only — no prepaid, virtual/single-use, or PIN-based debit cards accepted. A temporary (non-charging) authorization hold appears during verification; some users hit "Error Processing Transaction" even with a valid card and need Oracle support to resolve it. **Confirm card eligibility before starting Phase 15.**
- **"Out of host capacity" errors are common** for free Ampere A1 instances, especially in busy regions — can take hours to days to get an instance in the worst case. Pick a region with **3 availability domains** (not 1) to reduce this, and have a retry approach ready rather than manually refreshing.
- **Idle instances can be reclaimed.** If CPU, network, *and* memory utilization all stay under 20% (95th percentile) for 7 straight days, Oracle can reclaim the A1 instance. The uptime-monitor step (15e) prevents this as a side effect.
- **Two independent firewalls, not one.** Opening a port in the OCI console (Security List) is not sufficient — the VM's own OS-level firewall (iptables, or UFW if enabled) blocks it separately, by default. Both layers need explicit rules when we set up nginx/TLS. If `tcpdump` on the box shows packets arriving, it's the OS firewall; if it shows nothing, it's the OCI Security List/NSG.
- **FAISS + PyTorch has a known segfault bug on ARM** (conflicting OpenMP runtimes between the two libraries — open PyTorch issue). Since Oracle's free VM is ARM (aarch64), not x86, this directly affects `dense_retrieval.py`, which imports both. **Resolution baked into the plan:** production on the VM runs `pgvector` for ANN search (it executes inside Postgres, sidestepping the FAISS/PyTorch-in-one-process conflict entirely); FAISS stays as an offline benchmark run on a dev machine, feeding the FAISS-vs-pgvector comparison in the system design doc (Phase 16) without ever running live on the ARM box.

## 11. How we'll work

- **Git:** commit and push incrementally per feature/phase, not one final dump at the end. Feature branches (`feat/pgvector-schema`, `feat/hybrid-search`, etc.), merged to main as each piece works.
- **Docker:** local docker-compose set up in Phase 2, early — not deferred. CI/CD + cloud deployment layered in around Phase 15, but can go live earlier with a partial feature set and get redeployed continuously.
- **Oracle Cloud:** no prior deployment experience, chosen specifically to avoid AWS's from-day-one costs (ALB/Fargate/ElastiCache/NAT Gateway). Section 10's gotchas get handled proactively (card check, region choice, dual firewall, uptime monitor, pgvector-not-FAISS-in-production) rather than discovered mid-build.
- **Depth over breadth:** every phase should end with the ability to explain *why* it was built that way and what the alternative tradeoffs were — that's the actual interview bar, not the feature count.
- **This file is the source of truth** for scope. Update it (don't create a second planning doc) when scope changes.
