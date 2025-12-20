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
- Max confidence is 0.9 - never authoritative
- Based on curated domain mappings only (no ML, no NLP)
- UI displays as suggestion: "Likely MongoDB (90% confidence)"
"""

from dataclasses import dataclass
from typing import Optional
import re


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
    "aws.amazon.com": "Amazon Web Services",
    "amazonaws.com": "Amazon Web Services",
    "cloudfront.net": "Amazon Web Services",
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
}


def extract_registered_domain(domain: str) -> Optional[str]:
    """
    Extract the registered domain from a full domain.
    
    Examples:
        docs.mongodb.com -> mongodb.com
        api.stripe.com -> stripe.com
        sub.sub.example.com -> example.com
    """
    if not domain:
        return None
    
    domain = domain.lower().strip()
    domain = domain.removeprefix("www.")
    
    parts = domain.split(".")
    if len(parts) < 2:
        return None
    
    if len(parts) == 2:
        return domain
    
    tld = parts[-1]
    sld = parts[-2]
    
    if tld in ("com", "net", "org", "io", "co", "app", "dev", "so", "us"):
        return f"{sld}.{tld}"
    
    if len(parts) >= 3 and parts[-2] == "co":
        return f"{parts[-3]}.{parts[-2]}.{parts[-1]}"
    
    return f"{sld}.{tld}"


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
    
    if registered in DOMAIN_TO_VENDOR:
        return VendorHypothesisResult(
            value=DOMAIN_TO_VENDOR[registered],
            confidence=0.9,
            basis=f"domain:{registered}"
        )
    
    if domain in DOMAIN_TO_VENDOR:
        return VendorHypothesisResult(
            value=DOMAIN_TO_VENDOR[domain],
            confidence=0.9,
            basis=f"domain:{domain}"
        )
    
    return None
