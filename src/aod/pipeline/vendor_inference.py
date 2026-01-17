"""
Vendor Hypothesis Inference - Domain-based vendor identification.

Design Principle: Inference decorates reality; it does not redefine it.

INVARIANT: vendor_hypothesis is NON-DECISIONABLE metadata.
It MUST NOT be referenced by:
- admission.py (admission logic)
- derived_classifications.py (classify_shadow, classify_zombie functions)
- findings_engine.py (finding generation)
- any policy, scoring, or automation logic

Constraints:
- This is decorative only - never affects admission or shadow logic
- Max confidence from policy.VENDOR_HYPOTHESIS_MAX_CONFIDENCE - never authoritative
- Based on curated domain mappings only (no ML, no NLP)
- UI displays as suggestion: "Likely MongoDB (90% confidence)"
"""

import functools
from dataclasses import dataclass
from typing import Optional
import re

from ..core.policy import get_current_config


@dataclass
class VendorHypothesisResult:
    """Result of vendor inference"""
    value: str
    confidence: float
    basis: str


DOMAIN_TO_VENDOR: dict[str, str] = {
    "mongodb.com": "MongoDB",
    "mongodb.org": "MongoDB",
    "salesforce.com": "Salesforce",
    "force.com": "Salesforce",
    "slack.com": "Slack",
    "slackb2b.com": "Slack",
    "atlassian.com": "Atlassian",
    "atlassian.net": "Atlassian",
    "jira.com": "Atlassian",
    "trello.com": "Atlassian",
    "bitbucket.org": "Atlassian",
    "confluence.com": "Atlassian",
    "hipchat.com": "Atlassian",  # Jan 2026: HipChat was Atlassian product (deprecated)
    "github.com": "GitHub",
    "github.io": "GitHub",
    "githubusercontent.com": "GitHub",
    "gitlab.com": "GitLab",
    "gitlab.io": "GitLab",
    "zoom.us": "Zoom",
    "zoom.com": "Zoom",
    "zoom-video.com": "Zoom",
    "zoom-meetings.net": "Zoom",
    "zoomapp.io": "Zoom",
    "dropbox.com": "Dropbox",
    "dropboxapi.com": "Dropbox",
    "box.com": "Box",
    "boxcdn.net": "Box",
    "google.com": "Google",
    "googleapis.com": "Google",
    "gstatic.com": "Google",
    "googleusercontent.com": "Google",
    "microsoft.com": "Microsoft",
    "microsoftonline.com": "Microsoft",
    "azure.com": "Microsoft",
    "office.com": "Microsoft",
    "office365.com": "Microsoft",
    "sharepoint.com": "Microsoft",
    "live.com": "Microsoft",
    "outlook.com": "Microsoft",
    "onedrive.com": "Microsoft",
    "yammer.com": "Microsoft",  # Jan 2026: Yammer is Microsoft product
    "aws.amazon.com": "Amazon Web Services",
    "amazonaws.com": "Amazon Web Services",
    "cloudfront.net": "Amazon Web Services",
    "awsstatic.com": "Amazon Web Services",
    "okta.com": "Okta",
    "oktapreview.com": "Okta",
    "auth0.com": "Auth0",
    "twilio.com": "Twilio",
    "sendgrid.net": "Twilio",
    "stripe.com": "Stripe",
    "stripe.network": "Stripe",
    "zendesk.com": "Zendesk",
    "zdassets.com": "Zendesk",
    "hubspot.com": "HubSpot",
    "hubspotusercontent.com": "HubSpot",
    "intercom.io": "Intercom",
    "intercom.com": "Intercom",
    "segment.io": "Segment",
    "segment.com": "Segment",
    "datadog.com": "Datadog",
    "datadoghq.com": "Datadog",
    "splunk.com": "Splunk",
    "splunkcloud.com": "Splunk",
    "newrelic.com": "New Relic",
    "pagerduty.com": "PagerDuty",
    "opsgenie.com": "Atlassian",
    "servicenow.com": "ServiceNow",
    "workday.com": "Workday",
    "notion.so": "Notion",
    "notion.com": "Notion",
    "airtable.com": "Airtable",
    "asana.com": "Asana",
    "monday.com": "monday.com",
    "clickup.com": "ClickUp",
    "figma.com": "Figma",
    "miro.com": "Miro",
    "canva.com": "Canva",
    "docusign.com": "DocuSign",
    "docusign.net": "DocuSign",
    "adobe.com": "Adobe",
    "adobelogin.com": "Adobe",
    "typeform.com": "Typeform",
    "surveymonkey.com": "SurveyMonkey",
    "calendly.com": "Calendly",
    "loom.com": "Loom",
    "grammarly.com": "Grammarly",
    "1password.com": "1Password",
    "lastpass.com": "LastPass",
    "bitwarden.com": "Bitwarden",
    "sentry.io": "Sentry",
    "cloudflare.com": "Cloudflare",
    "workers.dev": "Cloudflare",
    "fastly.com": "Fastly",
    "vercel.com": "Vercel",
    "netlify.com": "Netlify",
    "heroku.com": "Heroku",
    "digitalocean.com": "DigitalOcean",
    "linode.com": "Linode",
    "snowflake.com": "Snowflake",
    "databricks.com": "Databricks",
    "looker.com": "Google",
    "tableau.com": "Salesforce",
    "powerbi.com": "Microsoft",
    "mixpanel.com": "Mixpanel",
    "amplitude.com": "Amplitude",
    "heap.io": "Heap",
    "fullstory.com": "FullStory",
    "hotjar.com": "Hotjar",
    "linear.app": "Linear",
    "shortcut.com": "Shortcut",
    "productboard.com": "Productboard",
    "launchdarkly.com": "LaunchDarkly",
    "optimizely.com": "Optimizely",
    "zapier.com": "Zapier",
    "make.com": "Make",
    "ifttt.com": "IFTTT",
    "postman.com": "Postman",
    "insomnia.rest": "Insomnia",
    "swagger.io": "SmartBear",
    "circleci.com": "CircleCI",
    "travis-ci.com": "Travis CI",
    "jenkins.io": "Jenkins",
    "teamcity.com": "JetBrains",
    "jetbrains.com": "JetBrains",
    "docker.com": "Docker",
    "docker.io": "Docker",
    "kubernetes.io": "Kubernetes",
    "hashicorp.com": "HashiCorp",
    "terraform.io": "HashiCorp",
    "vault.hashicorp.com": "HashiCorp",
    "elastic.co": "Elastic",
    "elasticsearch.com": "Elastic",
    "redis.com": "Redis",
    "redis.io": "Redis",
    "postgresql.org": "PostgreSQL",
    "mysql.com": "MySQL",
    "mariadb.com": "MariaDB",
    "oracle.com": "Oracle",
    "sap.com": "SAP",
    "ibm.com": "IBM",
    "cisco.com": "Cisco",
    "webex.com": "Webex",
    "vmware.com": "VMware",
    "citrix.com": "Citrix",
    "basecamp.com": "Basecamp",
    "evernote.com": "Evernote",
    "surveymonkey.com": "Momentive",
    "getfeedback.com": "Momentive",
    "pivotaltracker.com": "Pivotal",
    "broadcom.com": "CA Technologies",
    "apache.org": "Apache",
    "teamsuite.cloud": "TeamSuite",
    "teamsuite.ai": "TeamSuite",
    "teamsuite.org": "TeamSuite",
    "corelabs.tech": "CoreLabs",
    "corelabs.app": "CoreLabs",
    "teamdesk.net": "TeamDesk",
    "probox.co": "Probox",
}


def build_vendor_to_domain_map() -> dict[str, str]:
    """
    Build reverse mapping from vendor name to canonical domain.

    Uses DOMAIN_TO_VENDOR from vendor_inference.py.
    When a vendor has multiple domains, prefer the primary one (.com, .so, .io).

    Returns:
        Dictionary mapping lowercase vendor names to their canonical domains
    """
    vendor_to_domain: dict[str, str] = {}

    for domain, vendor in DOMAIN_TO_VENDOR.items():
        vendor_key = vendor.lower().strip()
        if vendor_key not in vendor_to_domain:
            vendor_to_domain[vendor_key] = domain
        else:
            current = vendor_to_domain[vendor_key]
            if domain.endswith(('.com', '.so', '.io', '.us')) and not current.endswith(('.com', '.so', '.io', '.us')):
                vendor_to_domain[vendor_key] = domain

    return vendor_to_domain


# Build and export VENDOR_TO_DOMAIN as single source of truth
VENDOR_TO_DOMAIN = build_vendor_to_domain_map()


def build_vendor_domain_sets() -> dict[str, set[str]]:
    """
    Build mapping from vendor name to all its domains.
    
    Farm-style mapping used for vendor governance propagation.
    Example: "Microsoft" -> {"microsoft.com", "office.com", "sharepoint.com", "outlook.com", ...}
    
    Returns:
        Dictionary mapping lowercase vendor names to sets of their domains
    """
    vendor_sets: dict[str, set[str]] = {}
    
    for domain, vendor in DOMAIN_TO_VENDOR.items():
        vendor_key = vendor.lower().strip()
        if vendor_key not in vendor_sets:
            vendor_sets[vendor_key] = set()
        vendor_sets[vendor_key].add(domain.lower().strip())
    
    return vendor_sets


# Farm-style mapping: vendor -> all domains for that vendor
VENDOR_DOMAIN_SETS = build_vendor_domain_sets()

# Add product name aliases that don't match vendor names exactly
VENDOR_TO_DOMAIN.update({
    "microsoft 365": "microsoft.com",
    "office 365": "microsoft.com",
    "office365": "microsoft.com",
    "ms 365": "microsoft.com",
    "google workspace": "google.com",
    "g suite": "google.com",
    "gsuite": "google.com",
    "google apps": "google.com",
    "aws": "amazon.com",
    "amazon web services": "amazon.com",
    "cloudflare workers": "workers.dev",
    # Jan 2026: Explicit canonical domain overrides per Farm contract
    "zoom": "zoom.com",  # Farm uses zoom.com as canonical (not zoom.us)
    "atlassian": "atlassian.com",  # Ensure atlassian.com is canonical
})


@functools.lru_cache(maxsize=10000)
def extract_registered_domain(domain: str) -> Optional[str]:
    """
    Extract the registered domain (eTLD+1) from a full domain using PSL.
    
    Uses tldextract for proper Public Suffix List parsing, ensuring accurate
    extraction for all TLDs including .app, .cloud, .io, etc.
    
    Examples:
        docs.mongodb.com -> mongodb.com
        api.stripe.com -> stripe.com
        observability.prod.elasticcloud.app -> elasticcloud.app
        tooling.dev.meraki.io -> meraki.io
        cache01.use1.redis.com -> redis.com
    """
    if not domain:
        return None
    
    domain = domain.lower().strip()
    
    try:
        from .domain_cache import extract_domain
        extracted = extract_domain(domain)
        if extracted.domain and extracted.suffix:
            return f"{extracted.domain}.{extracted.suffix}"
        return None
    except Exception:
        domain = domain.removeprefix("www.")
        parts = domain.split(".")
        if len(parts) < 2:
            return None
        if len(parts) == 2:
            return domain
        return f"{parts[-2]}.{parts[-1]}"


def infer_vendor_from_domain(domain: Optional[str]) -> Optional[VendorHypothesisResult]:
    """
    Infer vendor from domain using curated mapping.
    
    Returns None if no confident match found.
    """
    if not domain:
        return None
    
    registered = extract_registered_domain(domain)
    if not registered:
        return None
    
    confidence = get_current_config().vendor_inference.max_confidence

    if registered in DOMAIN_TO_VENDOR:
        return VendorHypothesisResult(
            value=DOMAIN_TO_VENDOR[registered],
            confidence=confidence,
            basis=f"domain:{registered}"
        )

    if domain in DOMAIN_TO_VENDOR:
        return VendorHypothesisResult(
            value=DOMAIN_TO_VENDOR[domain],
            confidence=confidence,
            basis=f"domain:{domain}"
        )
    
    return None
