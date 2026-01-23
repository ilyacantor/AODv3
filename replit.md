# AOD - AutonomOS Discovery Module

## Overview
AOD (AutonomOS Discovery) is the front-end entry point to the AutonomOS (AOS) platform. Its primary purpose is to discover all SaaS applications, cloud services, and software assets within an organization, preparing them for integration into the broader AOS data stack. AOD plays a crucial role in the AOS data flow, preceding connection (AAM), unification (DCL), and agent-driven actions.

AOD's key capabilities include:
- **Asset Discovery**: Identifies assets from various data sources (browser logs, network scans, SSO logs, expense reports).
- **Preparation for AAM**: Pinpoints assets requiring connectors for AAM integration.
- **Asset Classification**: Categorizes assets by governance status (governed, shadow, zombie).
- **Issue Identification**: Surfaces critical findings like identity gaps, finance gaps, and data conflicts that need resolution before AAM connection.
- **Triage**: Enables teams to prioritize assets for connection based on identified issues.
- **Autonomous Handshake**: Supports automatic provisioning to DCL's Ingest Sidecar, streamlining the data ingestion process.
- **System of Record (SOR) Identification**: Utilizes a signal-based scoring engine to identify potential Systems of Record, categorizing them by data domain and confidence level. This classification is orthogonal to governance status.

## User Preferences
I prefer simple language and detailed explanations when new concepts are introduced. I want iterative development with clear communication at each step. Ask before making major architectural changes or introducing new dependencies. I prefer to review code changes before they are applied to the main branch. Do not make changes to the `docs/` folder.

## System Architecture

### Core Architecture
AOD processes raw observations through a 7-stage sequential **DiscoveryScan**: Validation, Normalization, Indexing, Correlation, Admission, Artifact Handling, and Output. This DiscoveryScan transforms raw data into a catalog of discovered assets, complete with classifications and findings.

**Terminology Note**: AOD uses "DiscoveryScan" terminology (not "Pipeline") to distinguish from DCL ingestion pipelines. Each scan execution is tracked by a `scan_session_id` (aliased as `run_id` for backward compatibility).

### Data Flow
The system's data flow begins with fetching snapshot data from Farm (a test data generator), which then moves through the DiscoveryScan, ultimately populating a Catalog and enabling interaction via the Triage UI. Snapshots include discovery observations, IdP records, CMDB records, finance transactions, and cloud inventory.

### Key Features and Specifications
- **Classifications**: Determines asset status (Shadow IT, Zombie, Governed) based on governance signals.
- **Findings**: Generates actionable insights for each asset, categorized as Red (blocking), Yellow (review), or Green (informational). Examples include `identity_gap`, `finance_gap`, and `data_conflict`.
- **Policy Switchboard**: A central configuration (`config/policy_master.json`) that governs admission, classification logic, activity windows, finance thresholds, and custom exclusions.
- **Governance Trinity**: Defines an asset as governed if it possesses Visibility (CMDB), Validation (IdP/SSO), or Control (vendor-governed lifecycle).
- **Alias Collapsing**: Consolidates technical infrastructure domains to their canonical vendor domain (e.g., `office365.com` to `microsoft.com`).
- **SOR Identification**: Assets are scored based on signals like CMDB authoritative status, known SOR vendors, middleware exporter presence, and SSO/SCIM enablement. Confidence bands (high, medium, low) indicate the likelihood of an asset being an SOR. SOR scoring runs as a DiscoveryScan stage after vendor governance propagation, populating `sor_tagging` on each asset with likelihood, confidence, evidence, domain, and signals_matched.
- **Policy Manifest Export**: PolicyManifestBuilder compiles governance rules into a versioned JSON manifest (`GET /policy/manifest`) that AAM consumes during handshake for connection gating.
- **IdP Governance Policy**: Configurable policy (`Strict` or `Loose`) to control how IdP matches assert governance, balancing between detecting shadow IT and reducing noise.
- **Fabric Plane Detection**: FabricPlaneDetector identifies Control Planes (motherships) that aggregate data. AAM connects to Fabric Planes, not individual apps.
- **Enterprise Preset Inference**: PresetInferenceEngine classifies organizational integration patterns (iPaaS-centric, Warehouse-centric, Event-driven, etc.) to determine AAM connection strategy.

### Fabric Planes Architecture
AOD prioritizes discovering **Fabric Control Planes** over individual endpoints. Finding 500 APIs is useless if they're all managed by one MuleSoft instance.

**The 4 Fabric Planes:**
1. **IPAAS**: Workato, MuleSoft - Control plane for integration flows
2. **API_GATEWAY**: Kong, Apigee - Direct managed API access
3. **EVENT_BUS**: Kafka, EventBridge - Streaming backbone
4. **DATA_WAREHOUSE**: Snowflake, BigQuery - Source of Truth storage

**Enterprise Presets:**
- PRESET_6_SCRAPPY: Direct app connections (no fabric planes)
- PRESET_8_IPAAS: >50% assets via iPaaS
- PRESET_9_EVENT_DRIVEN: Kafka is primary integration bus
- PRESET_10_API_GATEWAY: API Gateway-centric
- PRESET_11_WAREHOUSE: Warehouse holds canonical data

**ConnectionCandidate.connected_via_plane**: Assets include connection routing (e.g., "Connect via MuleSoft") so AAM knows to use the fabric plane, not direct connection.

### UI/UX Decisions
The user interface features a dark slate foundation with cyan and purple accents. The 'Quicksand' font is used. Notifications are minimal, primarily using cyan toast messages for loading states.

### Technical Implementation
The project is built using FastAPI for the backend, with a structured `src/` directory containing API routes, pipeline logic, database models, and client integrations. Frontend assets (JS, CSS, HTML templates) are located in `static/` and `templates/`.

## External Dependencies

- **Farm**: A test data generator providing snapshots of discovery observations, IdP records, CMDB entries, and finance transactions. This is a critical component for testing and reconciliation.
- **PostgreSQL**: Used as the primary database for storing application data, configured via `DATABASE_URL`.
- **DCL (Data Connectivity Layer)**: AOD integrates with DCL for provisioning connectors and ingesting data through its Ingest Sidecar.
- **AAM (Adaptive API Mesh)**: AOD prepares assets for connection to AAM, which serves as the connection and authentication layer for the broader AOS platform.
- **Uvicorn**: Used to run the FastAPI application locally.

## Important Files

- `src/aod/pipeline/pipeline_executor.py` - Main DiscoveryScan orchestrator (also exports `execute_scan`, `ScanResult` aliases)
- `src/aod/pipeline/sor_scoring.py` - SOR signal-based scoring engine
- `src/aod/models/output_contracts.py` - Data models including SORTagging, RunLog (with `scan_session_id` alias)
- `src/aod/core/policy/schema.py` - Policy configuration schema
- `src/aod/core/policy/manifest.py` - PolicyManifestBuilder for AAM governance export
- `config/policy_master.json` - Central policy switchboard configuration
- `docs/FARM_SOR_INSTRUCTIONS.md` - Farm test data generation instructions
- `docs/TEST_HARNESS.md` - Test harness documentation

## AAM Integration

AOD emits ConnectionCandidates to AAM (Adaptive API Mesh). AAM handles connectivity decisions.

**Architecture:**
- AOD discovers and classifies assets
- AOD exports ConnectionCandidates via `POST /handoff/aam/candidates`
- AAM receives candidates and determines how to connect
- AOD does NOT provision connectors or talk directly to DCL

**ConnectionCandidate fields:**
- `asset_key`: Canonical identifier (domain/vendor)
- `governance_status`: governed | shadow | zombie | edge
- `sor_tagging`: SOR likelihood, domain, evidence
- `findings`: List of finding codes, severities, messages
- `signals_summary`: Thin summary (has_idp, has_cmdb, etc.)
- `priority_score`: Score for connection ordering

**Deprecated endpoints:**
- `POST /handoff/provision-connector` - Returns 410 Gone
- `GET /handoff/targeting-package` - Returns 410 Gone

## Recent Changes

- **2026-01-23**: Execution signaling added - ConnectionCandidate now includes `execution_allowed` and `action_type` fields. Blocking findings (critical severity) set execution_allowed=false, action_type="inventory_only". Clear candidates get execution_allowed=true, action_type="provision". AAM receives complete inventory but knows which candidates require triage resolution before auto-provisioning.
- **2026-01-23**: Nomenclature refactoring - "Pipeline" → "DiscoveryScan" terminology with backward-compatible aliases
- **2026-01-23**: PolicyManifestBuilder created - GET /policy/manifest exports governance rules for AAM consumption
- **2026-01-23**: scan_session_id added to AAM handoff responses (aliases run_id for lineage tracking)
- **2026-01-22**: ConnectionCandidate output contract implemented - AAM handoff via POST /handoff/aam/candidates
- **2026-01-22**: DCL provisioning endpoints deprecated - AOD no longer talks directly to DCL
- **2026-01-22**: SOR Phase 2 complete - Pipeline integration with evidence_refs-derived entity_id correlation
- **2026-01-21**: SOR Phase 1 complete - Signal-based scoring engine with 8 weighted signals
- **2026-01-21**: Guided tour enhanced with "Legacy Stack" section (8 total stops)
- **2026-01-20**: Phase 4 Autonomous Handshake operational (99.3-99.8% accuracy)