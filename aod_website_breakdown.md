# AOD — Website Service Breakdown
> Source: AOS Constitution v7.0, MASTER RACI v8.6, AOD repo state. Eight dimensions: tech, uniqueness, governance/security, AI, RAG/learning, speed/performance, enterprise-grade, Farm validation.

## What AOD Owns
Discovery, classification, SOR detection, ConnectionCandidate generation. Step 1 of the AOS pipeline (AOD → AAM → Farm → triple conversion → PG). Does NOT own pipe blueprints (AAM), data extraction, or semantic mapping (DCL).

## Technologies Deployed
FastAPI / Python backend (port 8001); React 18 + Vite frontend (port 3001); Supabase Postgres (tenant-scoped). Core engines: classification, SOR detector, ConnectionCandidate generator, Discovery layout/topology UI, triage de-duplication. Ops: pm2, render.yaml deploy, Makefile-driven local workflows.

## Uniqueness
- Auto-discovers Systems of Record across a messy enterprise stack without rules-based config — vendors, domains, IDPs, governance touchpoints inferred from observed signals, not pre-declared.
- Emits canonical `ConnectionCandidate` objects that downstream AAM consumes directly — no manual blueprint authoring step.
- Discovery delivered in days, not the 12–18 months of traditional integration approaches.
- Free-axis drag topology surface lets operators reshape the discovered graph without losing provenance.

## Governance & Security Posture (Production)
- **Tenant isolation:** Postgres row-level security keyed on `tenant_id`; namespace-scoped storage and run identifiers; one canonical `AOS_TENANT_ID` per workload, no cross-tenant data path.
- **AuthN / AuthZ:** SSO via SAML 2.0 and OIDC (Okta, Azure AD, Google Workspace); RBAC roles scoped to engagement + persona; service-to-service mTLS with short-lived workload identities.
- **Audit & compliance:** Immutable audit log of every discovery action (operator, timestamp, `run_name`, payload hash); SOC 2 Type II controls; GDPR/CCPA data-residency tagging; PII redaction at ingest.
- **Cryptography:** KMS-managed AES-256 at rest, TLS 1.3 in transit, rotated DB credentials, signed inter-service calls.
- **Network:** VPC isolation, private endpoints to AAM/Farm/DCL, WAF on the Console edge, per-tenant rate limits on public APIs.
- **Secrets & code integrity:** Vault-backed secrets, no plaintext credentials in repo; pre-commit hook bans unnamespaced run identifiers, seed UUIDs, hardcoded entity names, references to the deprecated demo-data file, and silent-fallback patterns; `--no-verify` is banned.

## Use of AI
**Status: scaffolded, not yet active in the live pipeline.** `llm_facts` table + `LLMFactOperations` CRUD layer are in place (`src/aod/db/operations/llm_facts.py`, schema at `src/aod/db/schema.py:160`) with provider/model fields ready for vendor-identity, governance-domain, and IDP-domain inference. `openai==2.13.0` is wired into `requirements.txt`. Current classification, vendor-matching, and triage engines run on rule/heuristic logic; LLM-backed inference is the next build phase, not current behavior. When activated, AI will be bounded — control flow code-driven, LLM steps inside discrete nodes.

## Use of Learning / RAG
**Status: not in place at the AOD layer.** No vector store, embeddings, or retrieval layer in AOD source. AOD performs structured inventory lookups (ConnectionCandidate registry, governance/IDP context tables) — these are not RAG. Semantic retrieval is delegated to DCL downstream (Pinecone + triple graph). AOD's role is to produce the canonical candidates DCL resolves; if AOD-side RAG is needed for grounded LLM inference, it is deferred work.

## Speed / Performance
Sub-second discovery surfaces; React 18 + Vite delivers a fast operator loop. Lazy graph rendering and free-axis drag keep large topologies interactive. B18 latency budget: 5% regression on any endpoint is blocking; hard ceilings stated in prompts are absolute. Latency means the operation **completes** in time — timeouts are not performance fixes (C10).

## Enterprise-Grade — Resilience & Scale
- **Resilience patterns:** Idempotent stage execution keyed on `aod_discovery_id` — replays produce identical state. Loud-fail on identity drift (422, never silent fallback). HTTP retries with exponential backoff and circuit breakers on AAM and Farm calls. Stage manifests are replayable; pipeline restarts from the last successful step without re-discovering.
- **Observability:** Structured per-stage telemetry; canonical `run_name` (`{entity_id}-{short_hash}`) traces any candidate from the operator UI back to the originating crawl. Operators never type IDs (I4) — dropdown-only from what exists.
- **Scale-tested via Farm:** Farm is the proof harness. It parameterizes synthetic enterprise fixtures — vendors, IDPs, governance domains, multi-entity tenants — at controllable scale, then runs end-to-end through AOD → AAM → Farm → DCL with reconciliation against ground truth (B10/B15). Determinism enforced: two consecutive runs must produce identical results (B14).
- **Validated scale envelopes:** Multi-tenant fixture runs across the SaaS-consultancy and BPM-services reference entities; thousands of ConnectionCandidates per discovery; sustained drift-event injection for AAM self-heal validation. Production scale targets (10k+ vendors per tenant, 100+ concurrent tenants) are exercised through Farm scale-run profiles before each release.

## Farm Validation
- **Ground truth at runtime:** Reconciliation tests fetch expected values from Farm's ground-truth endpoint at test time (B10) — no hardcoded expecteds.
- **Pipeline before harness:** Farm seeds synthetic vendor/system/governance fixtures → AOD discovers → AAM consumes → harness runs (B15).
- **User-facing assertion:** Tests hit user-facing endpoints with natural-language input (B2); a correct API response that doesn't render is not a pass (B17).
- **Playwright is the gate:** Real UI events — `locator.click()`, `selectOption()`, file pickers — drive the operator path. Backend POSTs from the test runner are API tests, not acceptance.
- **Source check on every test:** `source=Ingest` or `source=dcl` asserted on every data response (B12); demo data is never a pass (B9).
- **Negative tests paired** with every visible failure surface; harness is deterministic — runs twice with identical results (B14).
