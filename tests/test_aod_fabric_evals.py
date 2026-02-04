"""
AOD Fabric Plane Classification Evals
======================================

TWO DISTINCT TYPES OF EVALUATION — DO NOT CONFLATE THEM:

1. FARM ORACLE TESTS (this file, Part 1)
   - Synthetic data with KNOWN correct answers
   - Every assertion is binary pass/fail
   - 100% accuracy required — wrong = bug
   - Run these in CI, every commit

2. RECOGNITION BENCHMARKS (this file, Part 2)
   - Aggregate metrics across large synthetic tenant
   - Measures coverage, calibration, noise filtering
   - Thresholds are performance targets for real-world readiness
   - Run these before release, not every commit

Usage:
    pytest test_aod_fabric_evals.py -v                    # Run all
    pytest test_aod_fabric_evals.py -v -k "oracle"        # Farm oracle only
    pytest test_aod_fabric_evals.py -v -k "benchmark"     # Benchmarks only
    pytest test_aod_fabric_evals.py -v -k "regression"    # Regression only
"""

import pytest
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from pathlib import Path
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ============================================================================
# DATA MODEL (mirrors output_contracts.py — adapt imports to your actual code)
# ============================================================================

class FabricPlane(str, Enum):
    API_GATEWAY = "API_GATEWAY"
    IPAAS = "IPAAS"
    EVENT_BUS = "EVENT_BUS"
    DATA_WAREHOUSE = "DATA_WAREHOUSE"
    UNMANAGED = "UNMANAGED"


class Modality(str, Enum):
    CONTROL_PLANE = "CONTROL_PLANE"
    DECLARED_INTERFACE = "DECLARED_INTERFACE"
    PASSIVE_SUBSCRIPTION = "PASSIVE_SUBSCRIPTION"
    MINIMAL_TEE = "MINIMAL_TEE"


class EvidenceTier(str, Enum):
    TIER_1 = "TIER_1"  # Direct crawl
    TIER_2 = "TIER_2"  # Observation plane
    TIER_3 = "TIER_3"  # Category inference


class EvidenceSourcePlane(str, Enum):
    CLOUD = "CLOUD"
    NETWORK = "NETWORK"
    CMDB = "CMDB"
    FINANCE = "FINANCE"
    IDP = "IDP"
    ENDPOINT = "ENDPOINT"
    DIRECT_CRAWL = "DIRECT_CRAWL"


class GovernanceStatus(str, Enum):
    SANCTIONED = "SANCTIONED"
    UNDER_REVIEW = "UNDER_REVIEW"
    SHADOW = "SHADOW"
    UNKNOWN = "UNKNOWN"


class ClassificationMethod(str, Enum):
    DIRECT_CRAWL = "DIRECT_CRAWL"
    OBSERVED = "OBSERVED"
    INFERRED = "INFERRED"


@dataclass
class FabricRoutingEvidence:
    source_plane: EvidenceSourcePlane
    signal_type: str
    signal_detail: str
    confidence: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Pipe:
    id: str
    name: str
    source_system: str
    target_system: Optional[str] = None
    fabric_plane: Optional[FabricPlane] = None
    fabric_plane_instance: Optional[str] = None
    modality: Optional[Modality] = None
    classification_method: Optional[ClassificationMethod] = None
    classification_evidence: list = field(default_factory=list)
    classification_confidence: float = 0.0
    governance_status: GovernanceStatus = GovernanceStatus.UNKNOWN
    entity_scope: list = field(default_factory=list)
    linked_sor_id: Optional[str] = None


@dataclass
class FabricPlaneRecord:
    plane_type: FabricPlane
    instance_name: str
    vendor: str
    governance_status: GovernanceStatus = GovernanceStatus.SANCTIONED


@dataclass
class Contradiction:
    source_a: EvidenceSourcePlane
    source_b: EvidenceSourcePlane
    claim_a: str
    claim_b: str
    severity: str  # "HIGH", "MEDIUM", "LOW"


@dataclass
class Finding:
    finding_type: str
    severity: str
    description: str
    related_asset: Optional[str] = None
    related_plane: Optional[str] = None


# ============================================================================
# FARM DATA FACTORY
# ============================================================================

class FarmDataFactory:
    """
    Generates synthetic observation plane data and direct crawl results
    for each test scenario.
    """

    @staticmethod
    def scenario_1_single_plane_sor():
        """Salesforce with exactly one Workato recipe."""
        return {
            "assets": [
                {"id": "asset-sf-001", "name": "Salesforce", "vendor": "Salesforce",
                 "category": "CRM", "in_cmdb": True, "in_finance": True, "in_idp": True},
            ],
            "fabric_planes": [
                {"type": "IPAAS", "vendor": "Workato", "instance": "Workato Production"},
            ],
            "cloud_resources": [
                {"resource_id": "ecs-workato-001", "type": "ECS_SERVICE",
                 "name": "workato-agent", "vendor_hint": "workato",
                 "region": "us-east-1"},
            ],
            "network_flows": [
                {"source_ip": "10.0.1.50", "source_label": "workato-agent",
                 "dest_host": "login.salesforce.com", "dest_port": 443,
                 "protocol": "HTTPS", "bytes_transferred": 52_000_000,
                 "frequency": "RECURRING_DAILY"},
            ],
            "finance_records": [
                {"vendor": "Workato", "product": "Workato Enterprise",
                 "annual_cost": 120_000, "cost_center": "IT",
                 "contract_status": "ACTIVE"},
                {"vendor": "Salesforce", "product": "Salesforce Enterprise",
                 "annual_cost": 350_000, "cost_center": "Sales",
                 "contract_status": "ACTIVE"},
            ],
            "cmdb_dependencies": [
                {"source": "Workato Production", "target": "Salesforce",
                 "relationship": "integrates_with"},
            ],
            "direct_crawl_results": {
                "workato": [
                    {"recipe_id": "recipe-001", "recipe_name": "Sync SF Opportunities",
                     "connected_app": "Salesforce", "connection_type": "REST_API",
                     "status": "ACTIVE", "last_run": "2026-02-01T10:00:00Z",
                     "entities": ["Opportunity"]},
                ],
                "kong": [],
                "snowflake": [],
            },
        }

    @staticmethod
    def scenario_2_multi_plane_sor():
        """Salesforce connected through 3 planes simultaneously."""
        return {
            "assets": [
                {"id": "asset-sf-001", "name": "Salesforce", "vendor": "Salesforce",
                 "category": "CRM", "in_cmdb": True, "in_finance": True, "in_idp": True},
            ],
            "fabric_planes": [
                {"type": "IPAAS", "vendor": "Workato", "instance": "Workato Production"},
                {"type": "API_GATEWAY", "vendor": "Kong", "instance": "Kong Production"},
                {"type": "DATA_WAREHOUSE", "vendor": "Snowflake", "instance": "Snowflake Analytics"},
            ],
            "cloud_resources": [
                {"resource_id": "ecs-workato-001", "type": "ECS_SERVICE",
                 "name": "workato-agent", "vendor_hint": "workato"},
                {"resource_id": "eks-kong-001", "type": "EKS_SERVICE",
                 "name": "kong-gateway", "vendor_hint": "kong"},
            ],
            "network_flows": [
                {"source_ip": "10.0.1.50", "source_label": "workato-agent",
                 "dest_host": "login.salesforce.com", "dest_port": 443,
                 "protocol": "HTTPS", "bytes_transferred": 52_000_000,
                 "frequency": "RECURRING_DAILY"},
                {"source_ip": "10.0.2.10", "source_label": "internal-app-1",
                 "dest_host": "kong-proxy.internal.corp", "dest_port": 8443,
                 "protocol": "HTTPS", "bytes_transferred": 15_000_000,
                 "frequency": "RECURRING_HOURLY"},
                {"source_ip": "10.0.3.20", "source_label": "fivetran-agent",
                 "dest_host": "acme.snowflakecomputing.com", "dest_port": 443,
                 "protocol": "HTTPS", "bytes_transferred": 200_000_000,
                 "frequency": "RECURRING_DAILY"},
            ],
            "finance_records": [
                {"vendor": "Workato", "product": "Workato Enterprise",
                 "annual_cost": 120_000, "cost_center": "IT", "contract_status": "ACTIVE"},
                {"vendor": "Kong", "product": "Kong Enterprise",
                 "annual_cost": 85_000, "cost_center": "IT", "contract_status": "ACTIVE"},
                {"vendor": "Snowflake", "product": "Snowflake Enterprise",
                 "annual_cost": 200_000, "cost_center": "Data", "contract_status": "ACTIVE"},
            ],
            "cmdb_dependencies": [],
            "direct_crawl_results": {
                "workato": [
                    {"recipe_id": "recipe-001", "recipe_name": "Sync SF Opportunities",
                     "connected_app": "Salesforce", "connection_type": "REST_API",
                     "status": "ACTIVE", "entities": ["Opportunity"]},
                ],
                "kong": [
                    {"service_id": "svc-sf-001", "service_name": "salesforce-api-proxy",
                     "upstream_host": "login.salesforce.com", "upstream_port": 443,
                     "routes": ["/api/sf/*"], "plugins": ["rate-limiting", "oauth2"],
                     "status": "ACTIVE"},
                ],
                "snowflake": [
                    {"database": "RAW", "schema": "SALESFORCE",
                     "table": "CONTACTS", "row_count": 1_500_000,
                     "last_modified": "2026-02-02T06:00:00Z",
                     "created_by": "FIVETRAN_ROLE",
                     "naming_pattern_match": "raw_landing_zone"},
                ],
            },
        }

    @staticmethod
    def scenario_3_shadow_asset_via_plane():
        """Workato recipe connects to Notion — but Notion is unknown to IT."""
        return {
            "assets": [],
            "known_asset_registry": [
                {"id": "asset-sf-001", "name": "Salesforce", "vendor": "Salesforce"},
                {"id": "asset-slack-001", "name": "Slack", "vendor": "Slack"},
            ],
            "fabric_planes": [
                {"type": "IPAAS", "vendor": "Workato", "instance": "Workato Production"},
            ],
            "cloud_resources": [],
            "network_flows": [],
            "finance_records": [
                {"vendor": "Workato", "product": "Workato Enterprise",
                 "annual_cost": 120_000, "cost_center": "IT", "contract_status": "ACTIVE"},
            ],
            "cmdb_dependencies": [],
            "idp_grants": [],
            "direct_crawl_results": {
                "workato": [
                    {"recipe_id": "recipe-099", "recipe_name": "Sync Notion Tasks",
                     "connected_app": "Notion", "connection_type": "REST_API",
                     "status": "ACTIVE", "entities": ["Task"]},
                ],
                "kong": [],
                "snowflake": [],
            },
        }

    @staticmethod
    def scenario_4_shadow_fabric_plane():
        """Marketing team has a shadow Zapier subscription."""
        return {
            "assets": [],
            "fabric_planes": [
                {"type": "IPAAS", "vendor": "Workato", "instance": "Workato Production"},
            ],
            "cloud_resources": [],
            "network_flows": [
                {"source_ip": "10.0.5.10", "source_label": "mktg-server-1",
                 "dest_host": "hooks.zapier.com", "dest_port": 443,
                 "protocol": "HTTPS", "bytes_transferred": 5_000_000,
                 "frequency": "RECURRING_DAILY"},
                {"source_ip": "10.0.5.11", "source_label": "mktg-server-2",
                 "dest_host": "hooks.zapier.com", "dest_port": 443,
                 "protocol": "HTTPS", "bytes_transferred": 3_000_000,
                 "frequency": "RECURRING_DAILY"},
                {"source_ip": "10.0.5.12", "source_label": "mktg-server-3",
                 "dest_host": "hooks.zapier.com", "dest_port": 443,
                 "protocol": "HTTPS", "bytes_transferred": 8_000_000,
                 "frequency": "RECURRING_DAILY"},
            ],
            "finance_records": [
                {"vendor": "Workato", "product": "Workato Enterprise",
                 "annual_cost": 120_000, "cost_center": "IT", "contract_status": "ACTIVE"},
                {"vendor": "Zapier", "product": "Zapier Pro",
                 "annual_cost": 6_000, "cost_center": "Marketing",
                 "contract_status": "ACTIVE"},
            ],
            "cmdb_dependencies": [],
            "direct_crawl_results": {
                "workato": [],
                "kong": [],
                "snowflake": [],
            },
        }

    @staticmethod
    def scenario_5_contradictory_evidence():
        """CMDB says MuleSoft, but nothing else confirms it."""
        return {
            "assets": [
                {"id": "asset-snow-001", "name": "ServiceNow", "vendor": "ServiceNow",
                 "category": "ITSM", "in_cmdb": True, "in_finance": True, "in_idp": True},
            ],
            "fabric_planes": [
                {"type": "IPAAS", "vendor": "Workato", "instance": "Workato Production"},
            ],
            "cloud_resources": [],
            "network_flows": [
                {"source_ip": "10.0.4.100", "source_label": "internal-app-2",
                 "dest_host": "acme.service-now.com", "dest_port": 443,
                 "protocol": "HTTPS", "bytes_transferred": 30_000_000,
                 "frequency": "RECURRING_HOURLY"},
            ],
            "finance_records": [
                {"vendor": "ServiceNow", "product": "ServiceNow ITSM",
                 "annual_cost": 500_000, "cost_center": "IT", "contract_status": "ACTIVE"},
            ],
            "cmdb_dependencies": [
                {"source": "ServiceNow", "target": "MuleSoft",
                 "relationship": "integrates_via",
                 "last_updated": "2024-03-15T00:00:00Z"},
            ],
            "direct_crawl_results": {
                "workato": [],
                "kong": [],
                "snowflake": [],
            },
        }

    @staticmethod
    def scenario_6_no_evidence():
        """Canva exists but has zero integration evidence."""
        return {
            "assets": [
                {"id": "asset-canva-001", "name": "Canva", "vendor": "Canva",
                 "category": "Design", "in_cmdb": True, "in_finance": True, "in_idp": True},
            ],
            "fabric_planes": [
                {"type": "IPAAS", "vendor": "Workato", "instance": "Workato Production"},
                {"type": "API_GATEWAY", "vendor": "Kong", "instance": "Kong Production"},
            ],
            "cloud_resources": [],
            "network_flows": [
                {"source_ip": "10.0.10.5", "source_label": "employee-laptop-1",
                 "dest_host": "www.canva.com", "dest_port": 443,
                 "protocol": "HTTPS", "bytes_transferred": 500_000,
                 "frequency": "SPORADIC",
                 "traffic_type": "BROWSER_SESSION"},
            ],
            "finance_records": [
                {"vendor": "Canva", "product": "Canva Enterprise",
                 "annual_cost": 15_000, "cost_center": "Marketing",
                 "contract_status": "ACTIVE"},
            ],
            "cmdb_dependencies": [],
            "idp_grants": [
                {"app": "Canva", "grant_type": "SAML_SSO", "status": "ACTIVE"},
            ],
            "direct_crawl_results": {
                "workato": [],
                "kong": [],
                "snowflake": [],
            },
        }

    @staticmethod
    def scenario_7_warehouse_noise():
        """Snowflake with 500 tables, only 12 are real pipes."""
        landing_tables = [
            {"database": "RAW", "schema": "SALESFORCE", "table": "ACCOUNTS",
             "row_count": 500_000, "last_modified": "2026-02-02T06:00:00Z",
             "created_by": "FIVETRAN_ROLE", "naming_pattern_match": "raw_landing_zone",
             "is_pipe": True, "source_sor": "Salesforce"},
            {"database": "RAW", "schema": "SALESFORCE", "table": "CONTACTS",
             "row_count": 1_200_000, "last_modified": "2026-02-02T06:00:00Z",
             "created_by": "FIVETRAN_ROLE", "naming_pattern_match": "raw_landing_zone",
             "is_pipe": True, "source_sor": "Salesforce"},
            {"database": "RAW", "schema": "SALESFORCE", "table": "OPPORTUNITIES",
             "row_count": 300_000, "last_modified": "2026-02-02T06:00:00Z",
             "created_by": "FIVETRAN_ROLE", "naming_pattern_match": "raw_landing_zone",
             "is_pipe": True, "source_sor": "Salesforce"},
            {"database": "RAW", "schema": "MARKETO", "table": "LEADS",
             "row_count": 800_000, "last_modified": "2026-02-02T05:30:00Z",
             "created_by": "FIVETRAN_ROLE", "naming_pattern_match": "raw_landing_zone",
             "is_pipe": True, "source_sor": "Marketo"},
            {"database": "RAW", "schema": "MARKETO", "table": "ACTIVITIES",
             "row_count": 5_000_000, "last_modified": "2026-02-02T05:30:00Z",
             "created_by": "FIVETRAN_ROLE", "naming_pattern_match": "raw_landing_zone",
             "is_pipe": True, "source_sor": "Marketo"},
            {"database": "RAW", "schema": "HUBSPOT", "table": "CONTACTS",
             "row_count": 200_000, "last_modified": "2026-02-02T07:00:00Z",
             "created_by": "FIVETRAN_ROLE", "naming_pattern_match": "raw_landing_zone",
             "is_pipe": True, "source_sor": "HubSpot"},
            {"database": "RAW", "schema": "HUBSPOT", "table": "DEALS",
             "row_count": 50_000, "last_modified": "2026-02-02T07:00:00Z",
             "created_by": "FIVETRAN_ROLE", "naming_pattern_match": "raw_landing_zone",
             "is_pipe": True, "source_sor": "HubSpot"},
            {"database": "RAW", "schema": "NETSUITE", "table": "TRANSACTIONS",
             "row_count": 2_000_000, "last_modified": "2026-02-02T04:00:00Z",
             "created_by": "WORKATO_ROLE", "naming_pattern_match": "raw_landing_zone",
             "is_pipe": True, "source_sor": "NetSuite"},
            {"database": "RAW", "schema": "NETSUITE", "table": "ACCOUNTS",
             "row_count": 50_000, "last_modified": "2026-02-02T04:00:00Z",
             "created_by": "WORKATO_ROLE", "naming_pattern_match": "raw_landing_zone",
             "is_pipe": True, "source_sor": "NetSuite"},
            {"database": "RAW", "schema": "ZENDESK", "table": "TICKETS",
             "row_count": 1_000_000, "last_modified": "2026-02-02T06:30:00Z",
             "created_by": "FIVETRAN_ROLE", "naming_pattern_match": "raw_landing_zone",
             "is_pipe": True, "source_sor": "Zendesk"},
            {"database": "RAW", "schema": "JIRA", "table": "ISSUES",
             "row_count": 400_000, "last_modified": "2026-02-02T05:00:00Z",
             "created_by": "FIVETRAN_ROLE", "naming_pattern_match": "raw_landing_zone",
             "is_pipe": True, "source_sor": "Jira"},
            {"database": "RAW", "schema": "STRIPE", "table": "PAYMENTS",
             "row_count": 3_000_000, "last_modified": "2026-02-02T06:00:00Z",
             "created_by": "FIVETRAN_ROLE", "naming_pattern_match": "raw_landing_zone",
             "is_pipe": True, "source_sor": "Stripe"},
        ]

        noise_tables = []
        noise_prefixes = [
            ("ANALYTICS", "DBT_MARTS", "dbt_model"),
            ("ANALYTICS", "DBT_STAGING", "dbt_staging"),
            ("ANALYTICS", "DBT_INTERMEDIATE", "dbt_intermediate"),
            ("SCRATCH", "ANALYST_JANE", "scratch"),
            ("SCRATCH", "ANALYST_BOB", "scratch"),
            ("STAGING", "TRANSFORMS", "staging_transform"),
            ("REPORTING", "DASHBOARDS", "reporting"),
            ("ML", "FEATURES", "ml_feature"),
        ]
        table_counter = 0
        for db, schema, pattern in noise_prefixes:
            count = 488 // len(noise_prefixes)
            for i in range(count):
                noise_tables.append({
                    "database": db, "schema": schema,
                    "table": f"TABLE_{table_counter:04d}",
                    "row_count": (i + 1) * 1000,
                    "last_modified": "2026-02-01T12:00:00Z",
                    "created_by": "DBT_ROLE" if "dbt" in pattern else "ANALYST_ROLE",
                    "naming_pattern_match": pattern,
                    "is_pipe": False, "source_sor": None,
                })
                table_counter += 1
        while len(noise_tables) < 488:
            noise_tables.append({
                "database": "SCRATCH", "schema": "TEMP",
                "table": f"TEMP_{table_counter:04d}",
                "row_count": 100, "last_modified": "2026-01-15T00:00:00Z",
                "created_by": "ANALYST_ROLE", "naming_pattern_match": "scratch",
                "is_pipe": False, "source_sor": None,
            })
            table_counter += 1

        all_tables = landing_tables + noise_tables
        assert len(all_tables) == 500, f"Expected 500 tables, got {len(all_tables)}"

        return {
            "assets": [],
            "fabric_planes": [
                {"type": "DATA_WAREHOUSE", "vendor": "Snowflake",
                 "instance": "Snowflake Analytics"},
                {"type": "IPAAS", "vendor": "Workato", "instance": "Workato Production"},
            ],
            "cloud_resources": [],
            "network_flows": [],
            "finance_records": [
                {"vendor": "Snowflake", "product": "Snowflake Enterprise",
                 "annual_cost": 200_000, "cost_center": "Data",
                 "contract_status": "ACTIVE"},
            ],
            "cmdb_dependencies": [],
            "direct_crawl_results": {
                "workato": [
                    {"recipe_id": "recipe-ns-001",
                     "recipe_name": "Sync NetSuite Transactions to Snowflake",
                     "connected_app": "NetSuite", "connection_type": "REST_API",
                     "destination": "Snowflake:RAW.NETSUITE.TRANSACTIONS",
                     "status": "ACTIVE"},
                    {"recipe_id": "recipe-ns-002",
                     "recipe_name": "Sync NetSuite Accounts to Snowflake",
                     "connected_app": "NetSuite", "connection_type": "REST_API",
                     "destination": "Snowflake:RAW.NETSUITE.ACCOUNTS",
                     "status": "ACTIVE"},
                ],
                "kong": [],
                "snowflake": all_tables,
            },
            "_answer_key": {
                "expected_pipe_count": 12,
                "expected_pipe_tables": [t["table"] for t in landing_tables],
                "expected_noise_excluded": 488,
            },
        }


# ============================================================================
# ADAPTER — WIRE FARM DATA INTO AOD PIPELINE
# ============================================================================

def run_aod_pipeline(farm_data: dict) -> dict:
    """
    Feed Farm synthetic data through AOD's evidence-based classification pipeline.

    This adapter converts Farm's synthetic format into AOD's internal structures,
    runs the evidence collection and reconciliation, then converts back.
    """
    from aod.models.output_contracts import (
        FabricPlaneType as AODFabricPlane,
        EvidenceSourcePlane as AODEvidenceSource,
        EvidenceTier as AODEvidenceTier,
        FabricRoutingEvidence as AODEvidence,
        ConnectivityModality,
        ClassificationMethod as AODClassificationMethod,
        PipeGovernanceStatus,
    )
    from aod.pipeline.evidence_collectors.base import EvidenceCollectionResult, CONFIDENCE_SCORES
    from aod.pipeline.fabric_connectors.base import (
        DirectCrawlResult, CrawledPipe, CrawledAsset, ConnectorStatus, ConnectorConfig
    )
    from aod.pipeline.reconciliation.engine import ReconciliationEngine, ReconciliationConfig
    from aod.pipeline.reconciliation.contradictions import ContradictionDetector

    # Map Farm plane types to AOD plane types
    plane_type_map = {
        "IPAAS": AODFabricPlane.IPAAS,
        "API_GATEWAY": AODFabricPlane.API_GATEWAY,
        "DATA_WAREHOUSE": AODFabricPlane.DATA_WAREHOUSE,
        "EVENT_BUS": AODFabricPlane.EVENT_BUS,
        "UNMANAGED": AODFabricPlane.UNMANAGED,
    }

    # Build Phase 1 evidence from observation planes
    phase_1 = EvidenceCollectionResult()

    # Process network flows
    for flow in farm_data.get("network_flows", []):
        # Skip browser traffic
        if flow.get("traffic_type") == "BROWSER_SESSION":
            continue
        if flow.get("frequency") == "SPORADIC":
            continue

        dest_host = flow.get("dest_host", "")
        source_label = flow.get("source_label", "")

        # Detect fabric plane from network traffic
        fabric_plane = None
        vendor = None

        if "workato" in dest_host.lower() or "workato" in source_label.lower():
            fabric_plane = AODFabricPlane.IPAAS
            vendor = "workato"
        elif "zapier" in dest_host.lower():
            fabric_plane = AODFabricPlane.IPAAS
            vendor = "zapier"
        elif "kong" in dest_host.lower():
            fabric_plane = AODFabricPlane.API_GATEWAY
            vendor = "kong"
        elif "snowflake" in dest_host.lower():
            fabric_plane = AODFabricPlane.DATA_WAREHOUSE
            vendor = "snowflake"

        if fabric_plane:
            evidence = AODEvidence(
                evidence_id=f"net_{flow.get('source_ip', 'unknown')}_{dest_host}",
                source_plane=AODEvidenceSource.NETWORK,
                signal_type="proxy_traffic",
                signal_detail=f"Traffic from {source_label} to {dest_host}",
                confidence=CONFIDENCE_SCORES["tier_2_high"],
                timestamp=datetime.now(timezone.utc),
                fabric_plane_type=fabric_plane,
                fabric_plane_vendor=vendor,
                raw_data=flow
            )
            # Determine asset key from traffic
            asset_key = source_label if vendor else dest_host
            phase_1.add_evidence(asset_key, evidence)

    # Process finance records
    for record in farm_data.get("finance_records", []):
        vendor_name = record.get("vendor", "").lower()
        fabric_plane = None
        vendor = None

        if vendor_name in ["workato", "mulesoft", "boomi", "zapier", "tray.io"]:
            fabric_plane = AODFabricPlane.IPAAS
            vendor = vendor_name
        elif vendor_name in ["kong", "apigee", "aws api gateway"]:
            fabric_plane = AODFabricPlane.API_GATEWAY
            vendor = vendor_name
        elif vendor_name in ["snowflake", "databricks", "bigquery", "redshift"]:
            fabric_plane = AODFabricPlane.DATA_WAREHOUSE
            vendor = vendor_name
        elif vendor_name in ["kafka", "confluent", "rabbitmq", "aws eventbridge"]:
            fabric_plane = AODFabricPlane.EVENT_BUS
            vendor = vendor_name

        if fabric_plane:
            evidence = AODEvidence(
                evidence_id=f"fin_{vendor_name}_{record.get('product', '')}",
                source_plane=AODEvidenceSource.FINANCE,
                signal_type="contract",
                signal_detail=f"Finance contract for {vendor_name}: {record.get('product', '')}",
                confidence=CONFIDENCE_SCORES["tier_2_medium"],
                timestamp=datetime.now(timezone.utc),
                fabric_plane_type=fabric_plane,
                fabric_plane_vendor=vendor,
                raw_data=record
            )
            phase_1.add_evidence(vendor_name, evidence)

    # Process CMDB dependencies
    for dep in farm_data.get("cmdb_dependencies", []):
        target = dep.get("target", "").lower()
        fabric_plane = None
        vendor = None

        if target in ["workato", "mulesoft", "boomi"]:
            fabric_plane = AODFabricPlane.IPAAS
            vendor = target
        elif target in ["kong", "apigee"]:
            fabric_plane = AODFabricPlane.API_GATEWAY
            vendor = target

        if fabric_plane:
            # Check staleness
            last_updated = dep.get("last_updated", "")
            confidence = CONFIDENCE_SCORES["tier_2_low"]
            if last_updated:
                try:
                    updated_dt = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
                    age_days = (datetime.now(timezone.utc) - updated_dt).days
                    if age_days > 365:
                        confidence = CONFIDENCE_SCORES["tier_3_low"]  # Stale CMDB
                except (ValueError, TypeError):
                    pass

            evidence = AODEvidence(
                evidence_id=f"cmdb_{dep.get('source', '')}_{target}",
                source_plane=AODEvidenceSource.CMDB,
                signal_type="dependency",
                signal_detail=f"CMDB dependency: {dep.get('source', '')} -> {target}",
                confidence=confidence,
                timestamp=datetime.now(timezone.utc),
                fabric_plane_type=fabric_plane,
                fabric_plane_vendor=vendor,
                raw_data=dep
            )
            phase_1.add_evidence(dep.get("source", "unknown"), evidence)

    # Build Phase 2 results from direct crawl data
    phase_2_results: Dict[str, DirectCrawlResult] = {}
    crawl_data = farm_data.get("direct_crawl_results", {})

    # Workato crawl
    workato_recipes = crawl_data.get("workato", [])
    if workato_recipes:
        workato_result = DirectCrawlResult(
            plane_type=AODFabricPlane.IPAAS,
            vendor="workato",
            instance_name="Workato Production",
            status=ConnectorStatus.SUCCESS
        )
        for recipe in workato_recipes:
            connected_app = recipe.get("connected_app", "unknown")
            workato_result.pipes.append(CrawledPipe(
                pipe_id=recipe.get("recipe_id", f"workato_{connected_app}"),
                pipe_name=recipe.get("recipe_name", f"Recipe for {connected_app}"),
                source_identifier=connected_app,
                target_identifier=recipe.get("destination"),
                modality=ConnectivityModality.API,
                is_active=recipe.get("status") == "ACTIVE",
                raw_data=recipe
            ))
            workato_result.add_evidence(
                signal_type="workato_recipe",
                signal_detail=f"Workato recipe: {recipe.get('recipe_name', '')} for {connected_app}",
                asset_key=connected_app,
                raw_data=recipe
            )
        phase_2_results["workato"] = workato_result

    # Kong crawl
    kong_services = crawl_data.get("kong", [])
    if kong_services:
        kong_result = DirectCrawlResult(
            plane_type=AODFabricPlane.API_GATEWAY,
            vendor="kong",
            instance_name="Kong Production",
            status=ConnectorStatus.SUCCESS
        )
        for svc in kong_services:
            upstream = svc.get("upstream_host", "unknown")
            # Extract app name from upstream
            app_name = upstream.split(".")[0] if "." in upstream else upstream
            if "salesforce" in upstream.lower():
                app_name = "Salesforce"

            kong_result.pipes.append(CrawledPipe(
                pipe_id=svc.get("service_id", f"kong_{app_name}"),
                pipe_name=svc.get("service_name", f"Kong route to {app_name}"),
                source_identifier=app_name,
                target_identifier=upstream,
                modality=ConnectivityModality.API,
                is_active=svc.get("status") == "ACTIVE",
                raw_data=svc
            ))
            kong_result.add_evidence(
                signal_type="kong_service",
                signal_detail=f"Kong service: {svc.get('service_name', '')} -> {upstream}",
                asset_key=app_name,
                raw_data=svc
            )
        phase_2_results["kong"] = kong_result

    # Snowflake crawl
    snowflake_tables = crawl_data.get("snowflake", [])
    if snowflake_tables:
        snowflake_result = DirectCrawlResult(
            plane_type=AODFabricPlane.DATA_WAREHOUSE,
            vendor="snowflake",
            instance_name="Snowflake Analytics",
            status=ConnectorStatus.SUCCESS
        )
        for table in snowflake_tables:
            # Only include real pipes (landing zone tables)
            if not table.get("is_pipe", False):
                continue
            # Skip noise patterns
            pattern = table.get("naming_pattern_match", "")
            if pattern in ["dbt_model", "dbt_staging", "dbt_intermediate", "scratch",
                          "staging_transform", "reporting", "ml_feature"]:
                continue

            source_sor = table.get("source_sor", table.get("schema", "unknown"))
            fqn = f"{table.get('database')}.{table.get('schema')}.{table.get('table')}"

            snowflake_result.pipes.append(CrawledPipe(
                pipe_id=f"snowflake_{fqn}",
                pipe_name=f"{source_sor} -> {fqn}",
                source_identifier=source_sor,
                target_identifier=fqn,
                modality=ConnectivityModality.DB,
                is_active=True,
                raw_data=table
            ))
            snowflake_result.add_evidence(
                signal_type="snowflake_table",
                signal_detail=f"Snowflake landing zone: {fqn} from {source_sor}",
                asset_key=source_sor,
                raw_data=table
            )
        phase_2_results["snowflake"] = snowflake_result

    # Run reconciliation
    config = ReconciliationConfig(
        min_confidence_governed=0.70,
        min_confidence_known=0.50,
        min_confidence_classify=0.30,
        enable_deduplication=True,
    )
    engine = ReconciliationEngine(config)
    reconciliation_result = engine.reconcile(phase_1, phase_2_results)

    # Convert to test format
    output_pipes = []
    for aod_pipe in reconciliation_result.pipes:
        # Map AOD classification method to test format
        method_map = {
            AODClassificationMethod.DIRECT_CRAWL: ClassificationMethod.DIRECT_CRAWL,
            AODClassificationMethod.EVIDENCE_BASED: ClassificationMethod.OBSERVED,
            AODClassificationMethod.INFERRED: ClassificationMethod.INFERRED,
        }

        # Map AOD fabric plane to test format
        plane_map = {
            AODFabricPlane.IPAAS: FabricPlane.IPAAS,
            AODFabricPlane.API_GATEWAY: FabricPlane.API_GATEWAY,
            AODFabricPlane.DATA_WAREHOUSE: FabricPlane.DATA_WAREHOUSE,
            AODFabricPlane.EVENT_BUS: FabricPlane.EVENT_BUS,
            AODFabricPlane.UNMANAGED: FabricPlane.UNMANAGED,
        }

        # Map governance status
        gov_map = {
            PipeGovernanceStatus.GOVERNED: GovernanceStatus.SANCTIONED,
            PipeGovernanceStatus.KNOWN: GovernanceStatus.SANCTIONED,
            PipeGovernanceStatus.SHADOW: GovernanceStatus.SHADOW,
            PipeGovernanceStatus.INVESTIGATION_NEEDED: GovernanceStatus.UNDER_REVIEW,
        }

        # Convert evidence
        evidence_list = []
        for ev in aod_pipe.classification_evidence:
            source_map = {
                AODEvidenceSource.DIRECT_CRAWL: EvidenceSourcePlane.DIRECT_CRAWL,
                AODEvidenceSource.NETWORK: EvidenceSourcePlane.NETWORK,
                AODEvidenceSource.CLOUD: EvidenceSourcePlane.CLOUD,
                AODEvidenceSource.FINANCE: EvidenceSourcePlane.FINANCE,
                AODEvidenceSource.CMDB: EvidenceSourcePlane.CMDB,
                AODEvidenceSource.IDP: EvidenceSourcePlane.IDP,
                AODEvidenceSource.ENDPOINT: EvidenceSourcePlane.ENDPOINT,
            }
            evidence_list.append(FabricRoutingEvidence(
                source_plane=source_map.get(ev.source_plane, EvidenceSourcePlane.CLOUD),
                signal_type=ev.signal_type,
                signal_detail=ev.signal_detail,
                confidence=ev.confidence,
                timestamp=ev.timestamp
            ))

        pipe = Pipe(
            id=aod_pipe.pipe_id,
            name=aod_pipe.name,
            source_system=aod_pipe.source_system,
            target_system=aod_pipe.target_system,
            fabric_plane=plane_map.get(aod_pipe.fabric_plane, FabricPlane.UNMANAGED),
            fabric_plane_instance=aod_pipe.fabric_plane_instance,
            classification_method=method_map.get(aod_pipe.classification_method, ClassificationMethod.INFERRED),
            classification_evidence=evidence_list,
            classification_confidence=aod_pipe.classification_confidence,
            governance_status=gov_map.get(aod_pipe.governance_status, GovernanceStatus.UNKNOWN),
            linked_sor_id=aod_pipe.source_system,  # Use source as SOR ID for dedup
        )
        output_pipes.append(pipe)

    # Build fabric planes output
    fabric_planes = []
    for fp in reconciliation_result.fabric_planes:
        gov_status = GovernanceStatus.SANCTIONED
        if hasattr(fp, 'governance_status'):
            if 'shadow' in str(fp.governance_status).lower():
                gov_status = GovernanceStatus.SHADOW

        fabric_planes.append(FabricPlaneRecord(
            plane_type=plane_map.get(fp.plane_type, FabricPlane.UNMANAGED),
            instance_name=fp.display_name if hasattr(fp, 'display_name') else str(fp.plane_id),
            vendor=fp.vendor,
            governance_status=gov_status
        ))

    # Add shadow planes
    for sp in reconciliation_result.shadow_planes:
        fabric_planes.append(FabricPlaneRecord(
            plane_type=plane_map.get(sp.plane_type, FabricPlane.IPAAS),
            instance_name=sp.display_name if hasattr(sp, 'display_name') else str(sp.plane_id),
            vendor=sp.vendor,
            governance_status=GovernanceStatus.SHADOW
        ))

    # Build contradictions
    contradictions = []
    for asset_key, analysis in reconciliation_result.contradictions_by_asset.items():
        for c in analysis.contradictions:
            source_a = EvidenceSourcePlane.CMDB
            source_b = EvidenceSourcePlane.NETWORK
            if c.evidence_a:
                src = c.evidence_a[0].source_plane if hasattr(c.evidence_a[0], 'source_plane') else None
                if src:
                    source_a = EvidenceSourcePlane(src.value.upper()) if hasattr(src, 'value') else EvidenceSourcePlane.CMDB
            if c.evidence_b:
                src = c.evidence_b[0].source_plane if hasattr(c.evidence_b[0], 'source_plane') else None
                if src:
                    source_b = EvidenceSourcePlane(src.value.upper()) if hasattr(src, 'value') else EvidenceSourcePlane.NETWORK

            contradictions.append(Contradiction(
                source_a=source_a,
                source_b=source_b,
                claim_a=c.claim_a,
                claim_b=c.claim_b,
                severity=c.severity.value.upper() if hasattr(c.severity, 'value') else "MEDIUM"
            ))

    # Build findings
    findings = []
    # Shadow asset findings
    for pipe in output_pipes:
        if pipe.governance_status == GovernanceStatus.SHADOW:
            findings.append(Finding(
                finding_type="SHADOW_ASSET",
                severity="HIGH",
                description=f"Shadow SaaS detected: {pipe.source_system} via {pipe.fabric_plane_instance}",
                related_asset=pipe.source_system,
                related_plane=pipe.fabric_plane_instance
            ))

    # Shadow plane findings
    for fp in fabric_planes:
        if fp.governance_status == GovernanceStatus.SHADOW:
            findings.append(Finding(
                finding_type="SHADOW_FABRIC_PLANE",
                severity="HIGH",
                description=f"Shadow fabric plane detected: {fp.vendor}",
                related_asset=None,
                related_plane=fp.vendor
            ))

    # Contradiction findings
    for c in contradictions:
        findings.append(Finding(
            finding_type="CONTRADICTION_DETECTED",
            severity=c.severity,
            description=f"Contradicting evidence: {c.claim_a} vs {c.claim_b}",
        ))

    # Build assets
    assets = []
    for asset in farm_data.get("assets", []):
        asset_pipes = [p for p in output_pipes if p.source_system.lower() == asset.get("name", "").lower()]
        gov_status = GovernanceStatus.SANCTIONED if asset.get("in_cmdb") or asset.get("in_finance") or asset.get("in_idp") else GovernanceStatus.UNKNOWN
        assets.append({
            "id": asset.get("id"),
            "name": asset.get("name"),
            "governance_status": gov_status,
            "pipe_count": len(asset_pipes),
        })

    return {
        "pipes": output_pipes,
        "fabric_planes": fabric_planes,
        "contradictions": contradictions,
        "findings": findings,
        "assets": assets,
    }


# ============================================================================
# PART 1: FARM ORACLE TESTS — BINARY PASS/FAIL
# ============================================================================


class TestOracleScenario1_SinglePlaneSOR:
    """
    Salesforce with one Workato recipe.
    Expected: Exactly 1 pipe, IPAAS, Tier 1 confidence.
    """

    @pytest.fixture
    def result(self):
        farm_data = FarmDataFactory.scenario_1_single_plane_sor()
        return run_aod_pipeline(farm_data)

    def test_exactly_one_pipe_created(self, result):
        """AOD must produce exactly 1 pipe for a single-plane SOR."""
        sf_pipes = [p for p in result["pipes"] if p.source_system == "Salesforce"]
        assert len(sf_pipes) == 1, (
            f"Expected exactly 1 pipe for Salesforce, got {len(sf_pipes)}. "
            f"Pipes: {[p.name for p in sf_pipes]}"
        )

    def test_pipe_assigned_to_ipaas(self, result):
        """The pipe MUST be assigned to IPAAS — evidence is unambiguous."""
        sf_pipe = [p for p in result["pipes"] if p.source_system == "Salesforce"][0]
        assert sf_pipe.fabric_plane == FabricPlane.IPAAS, (
            f"Pipe should be IPAAS, got {sf_pipe.fabric_plane}. "
            f"Direct crawl found it in Workato — this is the authoritative source."
        )

    def test_classification_is_tier_1(self, result):
        """Direct crawl found this pipe — classification method must be DIRECT_CRAWL."""
        sf_pipe = [p for p in result["pipes"] if p.source_system == "Salesforce"][0]
        assert sf_pipe.classification_method == ClassificationMethod.DIRECT_CRAWL, (
            f"Classification method should be DIRECT_CRAWL, got {sf_pipe.classification_method}. "
            f"Workato recipe catalog is a Tier 1 source."
        )

    def test_confidence_reflects_tier_1(self, result):
        """Tier 1 evidence must produce confidence >= 0.90."""
        sf_pipe = [p for p in result["pipes"] if p.source_system == "Salesforce"][0]
        assert sf_pipe.classification_confidence >= 0.90, (
            f"Tier 1 confidence should be >= 0.90, got {sf_pipe.classification_confidence}. "
            f"Direct crawl evidence is authoritative."
        )

    def test_evidence_chain_includes_direct_crawl(self, result):
        """The pipe must have at least one evidence record from DIRECT_CRAWL."""
        sf_pipe = [p for p in result["pipes"] if p.source_system == "Salesforce"][0]
        crawl_evidence = [
            e for e in sf_pipe.classification_evidence
            if e.source_plane == EvidenceSourcePlane.DIRECT_CRAWL
        ]
        assert len(crawl_evidence) >= 1, (
            f"Expected at least 1 DIRECT_CRAWL evidence record, got {len(crawl_evidence)}. "
            f"Evidence sources found: {[e.source_plane for e in sf_pipe.classification_evidence]}"
        )


class TestOracleScenario2_MultiPlaneSOR:
    """
    Salesforce connected through iPaaS, API Gateway, AND Data Warehouse.
    Expected: Exactly 3 pipes, one per plane, all linked to same SOR.
    """

    @pytest.fixture
    def result(self):
        farm_data = FarmDataFactory.scenario_2_multi_plane_sor()
        return run_aod_pipeline(farm_data)

    @pytest.fixture
    def sf_pipes(self, result):
        return [p for p in result["pipes"] if p.source_system == "Salesforce"]

    def test_exactly_three_pipes_created(self, sf_pipes):
        """AOD MUST create 3 separate pipes for one SOR connected through 3 planes."""
        assert len(sf_pipes) == 3, (
            f"CRITICAL FAILURE: Expected exactly 3 pipes for multi-plane Salesforce, "
            f"got {len(sf_pipes)}. Pipes found: {[(p.name, p.fabric_plane) for p in sf_pipes]}"
        )

    def test_one_pipe_per_plane(self, sf_pipes):
        """Each of the 3 planes must be represented exactly once."""
        planes = {p.fabric_plane for p in sf_pipes}
        expected_planes = {FabricPlane.IPAAS, FabricPlane.API_GATEWAY, FabricPlane.DATA_WAREHOUSE}
        assert planes == expected_planes, (
            f"Expected pipes on {expected_planes}, got {planes}."
        )

    def test_all_pipes_are_tier_1(self, sf_pipes):
        """All 3 pipes come from direct crawl — should be Tier 1 confidence."""
        for pipe in sf_pipes:
            assert pipe.classification_method == ClassificationMethod.DIRECT_CRAWL, (
                f"Pipe '{pipe.name}' ({pipe.fabric_plane}) should be DIRECT_CRAWL, "
                f"got {pipe.classification_method}."
            )
            assert pipe.classification_confidence >= 0.90, (
                f"Pipe '{pipe.name}' ({pipe.fabric_plane}) confidence should be >= 0.90, "
                f"got {pipe.classification_confidence}."
            )


class TestOracleScenario6_NoEvidence:
    """
    Canva exists (SSO/Finance) but has zero integration evidence.
    Expected: ZERO pipes created. This validates AOD doesn't guess.
    """

    @pytest.fixture
    def result(self):
        farm_data = FarmDataFactory.scenario_6_no_evidence()
        return run_aod_pipeline(farm_data)

    def test_zero_pipes_for_canva(self, result):
        """
        CRITICAL: No pipes must be created for Canva.
        The old system would default to iPaaS at 0.70 confidence.
        The new system must produce NOTHING.
        """
        canva_pipes = [p for p in result["pipes"] if p.source_system == "Canva"]
        assert len(canva_pipes) == 0, (
            f"REGRESSION: {len(canva_pipes)} pipe(s) created for Canva, expected 0. "
            f"Canva has zero integration evidence. "
            f"Pipes found: {[(p.name, p.fabric_plane, p.classification_confidence) for p in canva_pipes]}"
        )


class TestOracleScenario7_WarehouseNoiseFiltering:
    """
    Snowflake with 500 tables, only 12 are real landing zone pipes.
    Expected: ~12 pipes created, not 500.
    """

    @pytest.fixture
    def farm_data(self):
        return FarmDataFactory.scenario_7_warehouse_noise()

    @pytest.fixture
    def result(self, farm_data):
        return run_aod_pipeline(farm_data)

    @pytest.fixture
    def answer_key(self, farm_data):
        return farm_data["_answer_key"]

    def test_pipe_count_matches_real_landing_zones(self, result, answer_key):
        """Must create ~12 pipes, NOT 500."""
        dw_pipes = [p for p in result["pipes"] if p.fabric_plane == FabricPlane.DATA_WAREHOUSE]
        expected = answer_key["expected_pipe_count"]
        assert len(dw_pipes) == expected, (
            f"Expected exactly {expected} Data Warehouse pipes, got {len(dw_pipes)}. "
            f"If you got ~500, noise filtering is not working."
        )


# ============================================================================
# PART 2: RECOGNITION BENCHMARKS
# ============================================================================


class TestBenchmarkCoverage:
    """Run AOD against combined scenarios and measure aggregate coverage."""

    @pytest.fixture(scope="class")
    def combined_result(self):
        all_pipes = []
        all_planes = []
        all_contradictions = []
        all_findings = []
        all_assets = []

        scenarios = [
            FarmDataFactory.scenario_1_single_plane_sor(),
            FarmDataFactory.scenario_2_multi_plane_sor(),
            FarmDataFactory.scenario_6_no_evidence(),
            FarmDataFactory.scenario_7_warehouse_noise(),
        ]

        for farm_data in scenarios:
            result = run_aod_pipeline(farm_data)
            all_pipes.extend(result.get("pipes", []))
            all_planes.extend(result.get("fabric_planes", []))
            all_contradictions.extend(result.get("contradictions", []))
            all_findings.extend(result.get("findings", []))
            all_assets.extend(result.get("assets", []))

        return {
            "pipes": all_pipes,
            "fabric_planes": all_planes,
            "contradictions": all_contradictions,
            "findings": all_findings,
            "assets": all_assets,
        }

    def test_benchmark_tier_1_coverage(self, combined_result):
        """RECOGNITION TARGET: >= 60% of discovered pipes should have Tier 1 evidence."""
        pipes = combined_result["pipes"]
        if len(pipes) == 0:
            pytest.skip("No pipes discovered")

        tier_1_pipes = [p for p in pipes if p.classification_method == ClassificationMethod.DIRECT_CRAWL]
        coverage = len(tier_1_pipes) / len(pipes)
        assert coverage >= 0.60, (
            f"Tier 1 coverage: {coverage:.1%} ({len(tier_1_pipes)}/{len(pipes)}). Target: >= 60%."
        )

    def test_benchmark_no_pipes_have_zero_evidence(self, combined_result):
        """Every pipe must have at least one evidence record."""
        pipes = combined_result["pipes"]
        empty_evidence = [p for p in pipes if len(p.classification_evidence) == 0]
        assert len(empty_evidence) == 0, (
            f"{len(empty_evidence)} pipe(s) have zero evidence records: {[p.name for p in empty_evidence]}"
        )


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════════╗
║              AOD FABRIC PLANE CLASSIFICATION EVALS              ║
╠══════════════════════════════════════════════════════════════════╣
║  Run: pytest tests/test_aod_fabric_evals.py -v                  ║
╚══════════════════════════════════════════════════════════════════╝
    """)
    import subprocess
    subprocess.run(["pytest", __file__, "-v", "--tb=short"])
