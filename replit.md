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
AOD processes raw observations through a 7-stage sequential pipeline: Validation, Normalization, Indexing, Correlation, Admission, Artifact Handling, and Output. This pipeline transforms raw data into a catalog of discovered assets, complete with classifications and findings.

### Data Flow
The system's data flow begins with fetching snapshot data from Farm (a test data generator), which then moves through the Pipeline, ultimately populating a Catalog and enabling interaction via the Triage UI. Snapshots include discovery observations, IdP records, CMDB records, finance transactions, and cloud inventory.

### Key Features and Specifications
- **Classifications**: Determines asset status (Shadow IT, Zombie, Governed) based on governance signals.
- **Findings**: Generates actionable insights for each asset, categorized as Red (blocking), Yellow (review), or Green (informational). Examples include `identity_gap`, `finance_gap`, and `data_conflict`.
- **Policy Switchboard**: A central configuration (`config/policy_master.json`) that governs admission, classification logic, activity windows, finance thresholds, and custom exclusions.
- **Governance Trinity**: Defines an asset as governed if it possesses Visibility (CMDB), Validation (IdP/SSO), or Control (vendor-governed lifecycle).
- **Alias Collapsing**: Consolidates technical infrastructure domains to their canonical vendor domain (e.g., `office365.com` to `microsoft.com`).
- **SOR Identification**: Assets are scored based on signals like CMDB authoritative status, known SOR vendors, middleware exporter presence, and SSO/SCIM enablement. Confidence bands (high, medium, low) indicate the likelihood of an asset being an SOR.
- **IdP Governance Policy**: Configurable policy (`Strict` or `Loose`) to control how IdP matches assert governance, balancing between detecting shadow IT and reducing noise.

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