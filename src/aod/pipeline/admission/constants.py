"""Constants used throughout the admission module."""

from ..correlate_entities import HEURISTIC_MATCH_METHODS, CROSS_TLD_MATCH_METHODS

# Match methods that allow domain promotion into primary identity (Jan 2026)
# Only authoritative matches from correlated planes can add domains to identifiers
PROMOTION_ALLOWED_MATCH_METHODS = {
    "domain", "uri", "canonical_name",  # Original authoritative from correlate_entities
    "verified_alias_domain",   # Explicit alias mapping (hipchat.com → atlassian.com)
    "foreign_key",             # Explicit foreign key (idp_app_id, cmdb_ci_id)
    "explicit_id",             # Explicit ID match
    "cmdb_domains_array",      # CMDB record.domains[] exact match
    "cmdb_canonical_domain",   # CMDB record.canonical_domain exact match
    "IDP_APP_MATCH", "CMDB_CI_MATCH", "FINANCE_CONTRACT_MATCH", "EXPLICIT_ALIAS_MAP"
}

# Match methods that BLOCK domain promotion (enrichment only)
PROMOTION_BLOCKED_MATCH_METHODS = HEURISTIC_MATCH_METHODS | CROSS_TLD_MATCH_METHODS

# Valid CI types for CMDB admission
VALID_CI_TYPES = {"app", "application", "service", "database", "infra", "infrastructure", "server", "system"}

# Valid lifecycles for CMDB admission
VALID_LIFECYCLES = {"prod", "production", "staging", "stage", "live", "active"}

# Valid cloud resource types
VALID_CLOUD_RESOURCE_TYPES = {
    "compute", "ec2", "vm", "instance", "container", "ecs", "eks", "kubernetes",
    "database", "rds", "dynamodb", "aurora", "redis", "elasticache",
    "storage", "s3", "bucket", "ebs",
    "lambda", "function", "serverless",
    "api", "gateway", "load_balancer", "elb", "alb",
    "queue", "sqs", "sns", "eventbridge",
    "service", "ecs_service", "app_runner"
}

# SSO provider domains
SSO_PROVIDER_DOMAINS: set[str] = {
    "okta.com", "oktapreview.com",
    "auth0.com",
    "onelogin.com",
    "pingidentity.com", "pingone.com",
    "duo.com", "duosecurity.com",
    "jumpcloud.com",
}

# Non-canonical IdP tokens (indicating legacy/dev/staging apps)
NON_CANONICAL_IDP_TOKENS = [
    "(legacy)", "legacy",
    "(deprecated)", "deprecated",
    "-prod", " prod", "production", "-production",
    "-dev", " dev", "-development",
    "-staging", " staging",
    "-test", " test", "-qa",
]

# Source to plane mapping
SOURCE_TO_PLANE = {
    "dns": "network",
    "proxy": "network",
    "web_filter": "network",
    "firewall": "network",
    "netflow": "network",
    "packet_capture": "network",
    "casb": "network",
    "swg": "network",
    "dlp": "network",
    "siem": "network",
    "zscaler": "network",
    "zscaler_proxy": "network",
    "zscaler_zia": "network",
    "zscaler_gre": "network",
    "paloalto": "network",
    "paloalto_panorama": "network",
    "netskope": "network",
    "netskope_casb": "network",
    "symantec_proxy": "network",
    "bluecoat": "network",
    "fortigate": "network",
    "cisco_umbrella": "network",
    "cato": "network",
    "cloudflare_gateway": "network",
    "menlo": "network",
    "iboss": "network",
    "browser": "network",
    "network_scan": "network",
    "edr": "endpoint",
    "mdm": "endpoint",
    "av": "endpoint",
    "agent": "endpoint",
    "endpoint": "endpoint",
    "endpoint_protection": "endpoint",
    "crowdstrike": "endpoint",
    "sentinelone": "endpoint",
    "carbonblack": "endpoint",
    "defender": "endpoint",
    "jamf": "endpoint",
    "intune": "endpoint",
    "workspace_one": "endpoint",
    "kandji": "endpoint",
    "sso": "idp",
    "oauth": "idp",
    "saml": "idp",
    "directory": "idp",
    "ldap": "idp",
    "okta": "idp",
    "azure_ad": "idp",
    "entra_id": "idp",
    "onelogin": "idp",
    "ping": "idp",
    "jumpcloud": "idp",
    "cloud_trail": "cloud",
    "cloudtrail": "cloud",
    "aws_config": "cloud",
    "azure_monitor": "cloud",
    "gcp_audit": "cloud",
    "aws": "cloud",
    "azure": "cloud",
    "gcp": "cloud",
    "cloud_api": "cloud",
    "saas_audit_log": "discovery",
    "contract": "finance",
    "invoice": "finance",
    "expense": "finance",
    "purchase_order": "finance",
    "procurement": "finance",
    "finance": "finance",
    "finance_coupa": "finance",
    "finance_netsuite": "finance",
    "finance_sap": "finance",
    "finance_ariba": "finance",
    "finance_concur": "finance",
    "coupa": "finance",
    "netsuite": "finance",
    "sap_ariba": "finance",
    "concur": "finance",
    "workday": "finance",
    "spend": "finance",
    "cmdb": "cmdb",
    "servicenow": "cmdb",
    "discovery": "discovery",
    "simulation": "discovery",
    "generator": "discovery",
    "farm_dns": "network",
    "farm_proxy": "network",
    "farm_network": "network",
    "farm_endpoint": "endpoint",
    "farm_idp": "idp",
    "farm_sso": "idp",
    "farm_cloud": "cloud",
    "farm_finance": "finance",
    "farm_cmdb": "cmdb",
    "simulated_dns": "network",
    "simulated_proxy": "network",
    "simulated_network": "network",
    "simulated_endpoint": "endpoint",
    "simulated_idp": "idp",
    "simulated_sso": "idp",
    "simulated_cloud": "cloud",
    "simulated_finance": "finance",
    "simulated_cmdb": "cmdb",
    "test_dns": "network",
    "test_proxy": "network",
    "test_network": "network",
    "test_endpoint": "endpoint",
    "test_idp": "idp",
    "test_cloud": "cloud",
    "synthetic_dns": "network",
    "synthetic_proxy": "network",
    "synthetic_network": "network",
    "synthetic_endpoint": "endpoint",
    "synthetic_idp": "idp",
    "synthetic_cloud": "cloud",
    "network": "network",
    "endpoint": "endpoint",
    "idp": "idp",
    "cloud": "cloud",
}

# Planes that count for discovery corroboration
DISCOVERY_CORROBORATION_PLANES = {"network", "endpoint", "idp", "cloud", "discovery"}

# Sources that Farm recognizes as "hard discovery"
FARM_CREDITED_DISCOVERY_SOURCES = {
    # Network hard discovery (not user activity)
    "dns", "network_scan", "firewall", "netflow", "packet_capture",
    "zscaler_gre", "paloalto_panorama",
    # Endpoint agents
    "edr", "mdm", "av", "agent", "endpoint", "endpoint_protection",
    "crowdstrike", "sentinelone", "carbonblack", "defender",
    "jamf", "intune", "workspace_one", "kandji",
    # Cloud API discovery
    "cloud_api", "cloud_trail", "cloudtrail", "aws_config", "azure_monitor", "gcp_audit",
    "aws", "azure", "gcp",
    # IdP (for SSO discovery)
    "sso", "oauth", "saml", "directory", "ldap", "okta", "azure_ad", "entra_id",
    "onelogin", "ping", "jumpcloud",
    # Explicit discovery sources
    "discovery",
    # Simulated/test variants
    "simulated_dns", "simulated_endpoint", "simulated_cloud", "simulated_idp",
    "farm_dns", "farm_endpoint", "farm_cloud", "farm_idp",
    "synthetic_dns", "synthetic_endpoint", "synthetic_cloud", "synthetic_idp",
    "test_dns", "test_endpoint", "test_cloud", "test_idp",
}

# User activity exhaust sources (Farm ignores these)
USER_ACTIVITY_EXHAUST = {
    "proxy", "browser", "saas_audit_log", "casb", "swg", "dlp", "siem",
    "web_filter", "zscaler", "zscaler_proxy", "zscaler_zia", "netskope",
    "netskope_casb", "symantec_proxy", "bluecoat", "fortigate",
    "cisco_umbrella", "cato", "cloudflare_gateway", "menlo", "iboss",
    "simulated_proxy", "farm_proxy", "synthetic_proxy", "test_proxy",
    "simulated_network", "farm_network", "synthetic_network", "test_network",
    "network",  # Generic "network" is too ambiguous
}

# Known database domains
KNOWN_DATABASE_DOMAINS = {
    "postgresql.org", "postgres.org", "mysql.com", "mysql.org",
    "mariadb.org", "mariadb.com", "mongodb.com", "mongodb.org",
    "redis.io", "redis.com", "cassandra.apache.org", "couchbase.com",
    "neo4j.com", "influxdata.com", "timescale.com", "cockroachlabs.com",
    "planetscale.com", "supabase.com", "supabase.io", "neon.tech",
    "fauna.com", "arangodb.com", "dgraph.io", "singlestore.com"
}

# Known database names
KNOWN_DATABASE_NAMES = {
    "postgresql", "postgres", "mysql", "mariadb", "mongodb", "mongo",
    "redis", "cassandra", "couchbase", "neo4j", "influxdb", "timescaledb",
    "cockroachdb", "planetscale", "supabase", "neon", "fauna", "arangodb",
    "dgraph", "singlestore", "dynamodb", "aurora", "rds"
}
