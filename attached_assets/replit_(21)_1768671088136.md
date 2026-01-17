# AutonomOS - Multi-Tenant AI Orchestration Platform

## Overview
AutonomOS (AOS) is an AI-native "operating system" for the enterprise data/agent stack. It sits between chaotic source systems and domain agents, providing:
1. **Discover & classify** everything that runs in your estate (AOD)
2. **Connect & normalize** business data into a canonical ontology (AAM + DCL)
3. **Feed agents & humans** clean, persona-specific streams of information (FinOps, RevOps, etc.)

The platform is structured into three architectural layers:
-   **Operational Infrastructure (Production Ready):**
    -   **AOD (Asset & Observability Discovery):** Component that discovers, catalogs, and scores everything running in the environment. Ingests infrastructure and SaaS telemetry, builds the Asset Graph, and flags shadow IT, risky assets, and anomalies.
    -   **AAM (Adaptive API Mesh):** The connection and auth layer between AOS and external systems. Manages connectors (Salesforce, NetSuite, Stripe, etc.), mediates authentication, and exposes a uniform API for DCL, AOD, and Agents.
    -   **DCL (Data Connectivity Layer):** The unification and ontology engine. Maintains the ontology (Account, Opportunity, Revenue, Cost, Usage), maps source fields to canonical fields, performs entity resolution, and produces canonical streams.
-   **Platform Services (In Development):**
    -   **AOA (Agentic Orchestration Architecture):** High-level workflow orchestration engine for cross-domain playbooks and business process automation.
    -   **NLP / Intent (Control Center):** Natural language interface with persona classification and query routing.
-   **Tailored Applications (In Development):**
    -   **Pre-Built Agents:** Domain-specific AI agents (FinOps, RevOps) that consume DCL's canonical streams, combine domain rules with LLM/RAG reasoning, and produce recommendations, alerts, and actions.

The platform ensures complete data isolation through JWT authentication and user management. Data flow: AOD (discover) → AAM (connect) → DCL (intelligence) → Agents (action).

## Canonical Glossary

### Core Concepts

| Term | Definition |
|------|------------|
| **Asset** | Anything that RUNS: has a runtime/process, can be up or down, consumes CPU/RAM/IO, has blast radius. NOT Assets: CSV files, table definitions, GitHub repos, docs. |
| **Source** | Logical system-of-record for one or more ontology entities in DCL. About business meaning, not infrastructure. |
| **Ontology** | Formal definition of business entities (Account, Opportunity, Revenue, Cost, Usage, Health) and their relationships. |
| **Canonical Entity** | Unified, deduplicated representation of a real-world thing across multiple Sources. |
| **Canonical Stream** | Time-ordered stream of canonical entities produced by DCL for Agents and dashboards. |

### Source Types

| Type | Role | Is DCL Source? |
|------|------|----------------|
| SYSTEM_OF_RECORD | Where events originate (Salesforce, Stripe) | Yes |
| CURATED | Cleaned/modeled warehouse tables (dim_customer) | Yes |
| AGGREGATED | Rollups for reporting (MRR by segment) | Usually No |
| CONSUMER_ONLY | Read-only visualization (Tableau, Looker) | No |

### Personas

| Persona | Primary Entities |
|---------|-----------------|
| CFO | Revenue, Cost, Margin, Cash, Risk |
| CRO | Account, Opportunity, Pipeline, Churn |
| COO | Usage, Health, SLAs, Incidents |
| CTO | Assets, CloudResources, Cost, Risk, TechDebt |

## User Preferences

**🚨 MOST CRITICAL PREFERENCE - READ THIS FIRST:**
**FOUNDATIONAL/FUNDAMENTAL FIXES ONLY** - When facing issues or bugs, ALWAYS choose fundamental/root-cause fixes over workarounds. No band-aids, no quick patches, no shortcuts. Fix the underlying architecture, data model, or type system properly. User explicitly demands "Fundamental fix required always".

**Communication & Development:**
- Clear, concise explanations and direct answers
- Iterative development with frequent, small updates
- Ask for approval before major architectural changes or significant feature additions
- Detailed explanations for complex concepts, brevity for straightforward ones
- Do not make changes to folder `Z` and file `Y`

**CRITICAL: Task Planning Guidelines**
- NEVER reference duration/time estimates in task descriptions or plans
- NEVER organize plans around time-based phases (Week 1, Week 2, etc.)
- Organize by logical phases, dependencies, and priorities only
- Use priority levels (P0/Critical, High, Medium, Low) instead of timelines

## System Architecture
AutonomOS is a full-stack SaaS platform featuring a multi-tenant architecture with UUID-based `tenant_id` scoping and JWT authentication.

**UI/UX Decisions:**
The frontend utilizes React 18 and TypeScript, featuring a responsive design with Quicksand typography, a Green, Blue, Purple color scheme, and dark mode. It includes pages for platform guidance, AOS overview (embedding a standalone discovery demo), data discovery (AOD), API mesh connections (AAM with an embedded mesh app), ontology graph visualization (DCL), agentic orchestration (AOA), and a control center. Live status indicators differentiate real backend data from mock data. Navigation is structured: Platform Guide → AOS Overview → Control Center → Discovery → Connections → Ontology → Orchestration → Agents → Help. Enterprise reporting views include tabular lineage, hierarchical tree, and evaluation dashboards. Embedded applications leverage simple iframe patterns with aspect-ratio containers for consistent and fast loading.

**Technical Implementations:**
-   **Task Orchestration:** Asynchronous job processing with Python RQ and Redis Queue.
-   **Authentication & Security:** JWT-based authentication using Argon2 hashing.
-   **AOA (Agentic Orchestration Architecture):** High-level orchestration for DCL engine operations.
-   **End-to-End Pipeline Demo:** Admin APIs manage AAM production connectors vs. legacy sources, and demo APIs simulate the full AOD→AAM→DCL→Agent flow.
-   **DCL Engine (Data Connection Layer):** AI-driven, in-process engine for data orchestration, using DuckDB for materialized views and Redis for concurrent access. It supports multiple connectors, AI-powered entity mapping, graph generation, and idempotent operations. LLM Telemetry tracks usage, and intelligence services provide LLM proposals, RAG lookup, confidence scoring, drift repair, and mapping approval.
-   **Adaptive API Mesh (AAM):** Provides self-healing data connectivity with production connectors (Salesforce, FileSource, Supabase, MongoDB). Features canonical event normalization (Pydantic), schema fingerprinting for drift detection, LLM-powered auto-repair, RAG intelligence, and an auto-onboarding system with Safe Mode. Integrates with DCL via Redis Streams and includes Airbyte Sync Monitoring.
-   **NLP Gateway Service:** Dedicated service for persona-based routing with context-specific prompts, tenant-scoped RAG knowledge base (Postgres + pgvector), hybrid retrieval, JWT auth, and PII redaction.
-   **Event Streaming System:** Real-time event delivery via Server-Sent Events (SSE) and WebSockets, using Redis Pub/Sub.
-   **API Endpoints:** Organized by domain with OpenAPI/Swagger documentation.
-   **Data Quality Intelligence Layer:** Implements canonical event processing, schema drift detection (fingerprinting with Redis), LLM/RAG-powered auto-repair, and Human-in-the-Loop (HITL) workflows.
-   **Resilience Infrastructure:** Async circuit breaker, retry, timeout, and bulkhead decorators for intelligence services.
-   **Live Flow Telemetry:** Real-time data flow monitoring dashboard with Redis Streams (aam:flow, dcl:flow, agent:flow) for tracking entity lifecycle events across the AAM → DCL → Agent pipeline. Features include event publishing, REST snapshot API, WebSocket live streaming, and a React dashboard with tenant-scoped filtering.

**System Design Choices:**
The platform employs a "Strangler Fig" pattern with feature flags for zero downtime. Data flows as: Data Sources → AAM → DCL → Agents. A single Supabase PostgreSQL database is used for development and production, managed with Alembic for schema versioning.
-   **Database Connection Architecture:** Centralized session factories ensure PgBouncer compatibility. Connection pool sizes are optimized for Supabase Session mode (pool_size=2, max_overflow=3).
-   **Production Database Override:** `SUPABASE_DATABASE_URL` is prioritized over Replit's `DATABASE_URL`.
-   **AAM Production Connections:** Four operational AAM connectors (Salesforce, FileSource, Supabase, MongoDB) use real credentials from Replit Secrets.
-   **Redis Infrastructure:** All Redis connections (sync, async, RQ worker) use TLS encryption with full certificate validation. A shared Redis client prevents connection pool exhaustion, with graceful degradation, watchdog processes, and retry logic.
-   **Feature Flags:** Frontend (`VITE_CONNECTIONS_V2`) and backend (`USE_AAM_AS_SOURCE`, `USE_DCL_INTELLIGENCE_API`) feature flags are managed via `.env.local` and Redis, respectively. The `USE_AAM_AS_SOURCE` flag is Redis-backed with multi-worker support, async pub/sub broadcasting, and persistence.
-   **Data Ingestion:** A script populates `mapping_registry` from CSV files.
-   **DCL Graph Structure:** Simplified graph with a consolidated "from AAM" parent node and source names on entity node labels.

## External Dependencies
-   **FastAPI:** Web framework.
-   **uvicorn:** ASGI server.
-   **SQLAlchemy:** ORM.
-   **Alembic:** Database migration tool.
-   **psycopg2-binary, psycopg-binary:** PostgreSQL adapters.
-   **redis:** Python client for Redis.
-   **rq (Redis Queue):** Background job processing.
-   **pydantic:** Data validation.
-   **python-dotenv:** Environment variable management.
-   **httpx:** HTTP client.
-   **duckdb:** Embedded SQL database.
-   **pandas:** Data manipulation.
-   **pyyaml:** YAML parsing.
-   **google-generativeai:** Gemini AI integration.
-   **openai:** OpenAI API integration.
-   **Supabase PostgreSQL:** Primary database service.
-   **Upstash Redis:** External Redis for production.
-   **Slack Incoming Webhooks:** For notifications.
-   **AOS Discover (AOD):** External microservice for asset discovery.
-   **pgvector:** PostgreSQL extension for vector embeddings.

## Documentation Files

| File | Purpose |
|------|---------|
| `README.md` | Platform overview, quick start, features, architecture |
| `replit.md` | Project state, user preferences, system architecture (this file) |
| `SECURITY.md` | Security architecture, implemented controls, compliance roadmap |
| `color_palette.md` | UI color system, navigation styling, component patterns |
| `DCL_REMOVAL_ASSESSMENT.md` | Impact analysis for DCL decommission (assessment only, no action) |
| `DOCUMENTATION_INDEX.md` | Complete documentation directory with all file paths |

### Frontend Help Resources
- **FAQ Page** (`/faq`): Searchable FAQ with category filters
- **Glossary Tab**: 30+ canonical terms across 7 categories (Core Concepts, Components, Data Types, Personas, Source Types, Technical Terms, AI/ML)
- Both accessible via Help navigation item