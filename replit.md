# AOS Discover - AutonomOS Discovery Module

## Overview
AOS Discover is the discovery module of AutonomOS, an enterprise operating system. Its primary function is to ingest raw enterprise evidence to generate an Asset Catalog, a Run Log, and Explainable Findings. The system is designed to be deterministic, evidence-only, and fully explainable, rejecting pre-adjudicated labels to accurately identify and classify enterprise assets. This provides a clear, auditable view of an organization's digital footprint, supporting robust asset management and risk mitigation.

## User Preferences
Preferred communication style: Simple, everyday language.

## System Architecture

AOS Discover follows a strict architectural design based on several core principles:
- **No ground truth ingestion**: Rejects fields like `is_shadow_it` or `ground_truth`.
- **No ML/anomaly scores**: Relies solely on deterministic rules and explainable correlation.
- **Deterministic**: Ensures identical outputs for the same snapshot and configuration.
- **Evidence-only decisions**: Admission and findings are derived exclusively from plane evidence.
- **Assets vs. Artifacts**: Distinguishes between actual assets and artifacts (dashboards, reports), preventing inflation of asset counts.

The system uses a 7-stage sequential pipeline for processing:
1. **Validation**: Schema validation of input snapshots.
2. **Normalization**: Standardizing names and domains.
3. **Indexing**: Building plane indexes for efficient lookups.
4. **Correlation**: Three-pass correlation of entities.
5. **Admission**: Applying criteria for asset inclusion.
6. **Artifact Handling**: Processing non-asset related data.
7. **Findings Generation**: Producing explainable findings.

**Governance Trinity (Dec 2025):**
Shadow IT is defined by the absence of explicit sanctioning, not by malicious intent or utility. Any asset that fails the Governance Trinity is Shadow:
- **Visibility**: Registered in CMDB
- **Validation**: Present in IdP (sanctioned/SSO)
- **Control**: Managed lifecycle tied to owner

Finance presence does NOT equal governance. You can pay for unsanctioned tools. There is no "Grey IT" - binary classification only.

**Derived Classifications:**
- **Activity Status**: Classifies assets as RECENT (active within 90 days), STALE (inactive beyond 90 days), or NONE (no activity timestamps).
- **Anchored Predicate**: An asset is "anchored" if it has an IdP, CMDB, finance, or cloud resource match. Used for zombie eligibility.
- **Shadow Asset**: Ungoverned (no IdP/CMDB) AND RECENT activity. Finance does NOT exempt from shadow.
- **Financial Anchor Governance Gap**: Shadow asset with ongoing finance - needs governance review despite being paid for.
- **Zombie Asset**: Anchored AND STALE activity.
- **Parked Asset**: Not anchored AND STALE activity.

**Traffic Light Provisioning**: A fail-closed system for asset provisioning, controlling flow to DCL with statuses like ACTIVE (Green), REVIEW (Amber), QUARANTINE (Red), BLOCKED, RETIRED, and IGNORED.

**UI Design**: Adheres to the AutonomOS palette, featuring cyan and purple accents, a dark slate foundation, and the Quicksand font.

**Quality Guardrails**: Emphasizes semantic preservation, avoidance of "cheating" (overwrites, silent fallbacks), real-world proof via before/after outputs, and negative test inclusion. The system is designed to "fail loudly" with explicit error statuses.

## External Dependencies
- **Python 3.11**
- **FastAPI** with **Pydantic v2**
- **PostgreSQL** persistence via **asyncpg**
- **Uvicorn** server
- **httpx** for async HTTP communication with Farm
- **Farm Integration**: Integrates with Farm for snapshot ingestion and reconciliation, acting as the source of raw evidence.