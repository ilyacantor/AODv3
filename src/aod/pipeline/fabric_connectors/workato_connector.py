"""
Workato Platform API Connector

Crawls Workato iPaaS to discover recipes, connections, and data flows.
This is Tier 1 evidence - authoritative data from the iPaaS platform itself.

What Workato reveals:
- Recipes: Automated workflows connecting applications
- Connections: OAuth/API credentials to external systems
- Folders: Organizational structure
- Jobs: Execution history (traffic metadata)

From this we can build:
- Pipes: Recipe connections showing App A → Workato → App B flows
- Assets: The connected applications
- Traffic metadata: Job counts, success rates
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse

from ...models.output_contracts import (
    FabricPlaneType,
    ConnectivityModality,
)
from .base import (
    FabricPlaneConnector,
    ConnectorConfig,
    DirectCrawlResult,
    CrawledAsset,
    CrawledPipe,
    ConnectorStatus,
    TIER_1_CONFIDENCE,
)

logger = logging.getLogger(__name__)


# Known Workato connector types that indicate modality
CONNECTOR_MODALITY_MAP = {
    "salesforce": ConnectivityModality.API,
    "netsuite": ConnectivityModality.API,
    "workday": ConnectivityModality.API,
    "jira": ConnectivityModality.API,
    "slack": ConnectivityModality.API,
    "mysql": ConnectivityModality.DB,
    "postgresql": ConnectivityModality.DB,
    "snowflake": ConnectivityModality.DB,
    "redshift": ConnectivityModality.DB,
    "s3": ConnectivityModality.FILE,
    "sftp": ConnectivityModality.FILE,
    "google_sheets": ConnectivityModality.FILE,
    "http": ConnectivityModality.API,
    "webhook": ConnectivityModality.API,
}


class WorkatoConnector(FabricPlaneConnector):
    """
    Workato Platform API connector for iPaaS fabric plane crawl.

    Queries Workato Platform API to discover:
    - Recipes (automated workflows)
    - Connections (app integrations)
    - Job history (execution metadata)

    Workato API reference: https://docs.workato.com/workato-api.html
    """

    @property
    def plane_type(self) -> FabricPlaneType:
        return FabricPlaneType.IPAAS

    @property
    def vendor(self) -> str:
        return "workato"

    def _validate_config(self) -> None:
        """Validate Workato connector config."""
        if not self.config.base_url:
            # Default to Workato's API endpoint
            self.config.base_url = "https://www.workato.com/api"

        if not self.config.api_key:
            raise ValueError("Workato connector requires api_key (API token)")

    def test_connection(self) -> bool:
        """Test connection to Workato API."""
        try:
            response = self._make_request("GET", "/users/me")
            return response is not None and "id" in response
        except Exception as e:
            logger.error("workato_connector.connection_test_failed", extra={
                "instance": self.config.instance_name,
                "error": str(e)
            })
            return False

    def crawl(self) -> DirectCrawlResult:
        """
        Execute Workato Platform API crawl.

        Crawls in order:
        1. Connections (app credentials)
        2. Recipes (workflows that use connections)
        3. Recent jobs (execution metadata)

        Builds pipes from recipe trigger→action relationships.
        """
        self._log_crawl_start()
        result = self._create_result()

        try:
            # Crawl connections first (recipes reference them)
            connections = self._crawl_connections(result)

            # Crawl recipes (the integration workflows)
            recipes = self._crawl_recipes(result, connections)

            # Build pipes from recipe trigger→action flows
            self._build_pipes(result, recipes, connections)

            result.status = ConnectorStatus.SUCCESS
            result.crawl_completed_at = datetime.utcnow()

        except Exception as e:
            result.status = ConnectorStatus.FAILED
            result.error_message = str(e)
            logger.error("workato_connector.crawl_failed", extra={
                "instance": self.config.instance_name,
                "error": str(e)
            })

        self._log_crawl_complete(result)
        return result

    def _make_request(
        self,
        method: str,
        path: str,
        params: Optional[Dict] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Make a request to Workato Platform API.

        In production, this would use httpx or requests.
        For now, returns simulated data for testing.
        """
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.config.api_key}"
        }

        # TODO: Replace with actual HTTP client
        logger.debug("workato_connector.request", extra={
            "method": method,
            "path": path,
            "base_url": self.config.base_url
        })

        return None

    def _paginate(
        self,
        path: str,
        key: str = "result"
    ) -> List[Dict[str, Any]]:
        """
        Paginate through Workato API results.

        Workato uses page-based pagination.
        """
        all_items = []
        page = 1

        while True:
            params = {"per_page": self.config.page_size, "page": page}

            response = self._make_request("GET", path, params)
            if not response:
                break

            items = response.get(key, [])
            if not items:
                break

            all_items.extend(items)

            # Check if more pages
            if len(items) < self.config.page_size:
                break

            page += 1

        return all_items

    def _crawl_connections(
        self,
        result: DirectCrawlResult
    ) -> Dict[str, Dict[str, Any]]:
        """Crawl Workato connections (app integrations)."""
        connections_by_id: Dict[str, Dict[str, Any]] = {}

        connections = self._paginate("/connections")
        for conn in connections:
            conn_id = conn.get("id")
            conn_name = conn.get("name", str(conn_id))
            provider = conn.get("provider", "unknown")

            if not self._should_include(conn_name):
                result.items_filtered += 1
                continue

            # Determine modality from provider
            modality = CONNECTOR_MODALITY_MAP.get(
                provider.lower(),
                ConnectivityModality.API
            )

            # Extract connection metadata
            is_connected = conn.get("authorization_status") == "success"
            auth_type = conn.get("auth_type", "unknown")

            # Create crawled asset for the connection
            asset = CrawledAsset(
                asset_id=str(conn_id),
                asset_name=conn_name,
                asset_type=f"workato_connection_{provider}",
                domain=self._extract_domain_from_connection(conn),
                created_at=self._parse_timestamp(conn.get("created_at")),
                updated_at=self._parse_timestamp(conn.get("updated_at")),
                owner=conn.get("user", {}).get("email"),
                raw_data=conn
            )
            result.assets.append(asset)
            result.total_items_crawled += 1

            # Create Tier 1 evidence for connection discovery
            result.add_evidence(
                signal_type="workato_connection",
                signal_detail=f"Workato connection '{conn_name}' to {provider} "
                             f"({'active' if is_connected else 'inactive'})",
                asset_key=conn_name,
                raw_data={
                    "connection_id": conn_id,
                    "connection_name": conn_name,
                    "provider": provider,
                    "auth_type": auth_type,
                    "is_connected": is_connected,
                    "modality": modality.value
                }
            )

            connections_by_id[str(conn_id)] = {
                **conn,
                "_modality": modality
            }

        logger.info("workato_connector.connections_crawled", extra={
            "instance": self.config.instance_name,
            "count": len(connections_by_id)
        })

        return connections_by_id

    def _crawl_recipes(
        self,
        result: DirectCrawlResult,
        connections: Dict[str, Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Crawl Workato recipes (integration workflows)."""
        all_recipes = []

        recipes = self._paginate("/recipes")
        for recipe in recipes:
            recipe_id = recipe.get("id")
            recipe_name = recipe.get("name", str(recipe_id))

            if not self._should_include(recipe_name):
                result.items_filtered += 1
                continue

            # Recipe status
            is_running = recipe.get("running", False)
            is_active = recipe.get("active", False)

            # Extract trigger and actions
            trigger_app = self._extract_trigger_app(recipe)
            action_apps = self._extract_action_apps(recipe)

            # Job statistics (if available)
            job_count = recipe.get("job_succeeded_count", 0) + recipe.get("job_failed_count", 0)
            success_rate = None
            if job_count > 0:
                success_rate = recipe.get("job_succeeded_count", 0) / job_count

            # Create crawled asset for the recipe
            asset = CrawledAsset(
                asset_id=str(recipe_id),
                asset_name=recipe_name,
                asset_type="workato_recipe",
                created_at=self._parse_timestamp(recipe.get("created_at")),
                updated_at=self._parse_timestamp(recipe.get("updated_at")),
                owner=recipe.get("user", {}).get("email"),
                raw_data=recipe
            )
            result.assets.append(asset)
            result.total_items_crawled += 1

            # Create Tier 1 evidence for recipe discovery
            all_apps = set([trigger_app] + action_apps) - {None, "unknown"}
            result.add_evidence(
                signal_type="workato_recipe",
                signal_detail=f"Workato recipe '{recipe_name}' connects: {', '.join(all_apps) or 'unknown'}",
                asset_key=recipe_name,
                raw_data={
                    "recipe_id": recipe_id,
                    "recipe_name": recipe_name,
                    "trigger_app": trigger_app,
                    "action_apps": action_apps,
                    "is_running": is_running,
                    "is_active": is_active,
                    "job_count": job_count,
                    "success_rate": success_rate
                }
            )

            all_recipes.append({
                **recipe,
                "_trigger_app": trigger_app,
                "_action_apps": action_apps,
                "_job_count": job_count,
                "_success_rate": success_rate
            })

        logger.info("workato_connector.recipes_crawled", extra={
            "instance": self.config.instance_name,
            "count": len(all_recipes)
        })

        return all_recipes

    def _build_pipes(
        self,
        result: DirectCrawlResult,
        recipes: List[Dict[str, Any]],
        connections: Dict[str, Dict[str, Any]]
    ) -> None:
        """Build pipes from recipe trigger→action flows."""
        for recipe in recipes:
            recipe_id = recipe.get("id")
            recipe_name = recipe.get("name", str(recipe_id))
            trigger_app = recipe.get("_trigger_app", "unknown")
            action_apps = recipe.get("_action_apps", [])

            is_active = recipe.get("active", False)
            job_count = recipe.get("_job_count", 0)

            # Build a pipe for each trigger→action relationship
            for action_app in action_apps:
                if action_app == trigger_app:
                    continue  # Skip self-loops

                pipe = CrawledPipe(
                    pipe_id=f"workato_{recipe_id}_{trigger_app}_{action_app}",
                    pipe_name=f"{recipe_name}: {trigger_app} → {action_app}",
                    source_identifier=trigger_app,
                    target_identifier=action_app,
                    modality=self._infer_modality(trigger_app, action_app, connections),
                    is_active=is_active,
                    request_count=job_count,
                    error_rate=1 - recipe.get("_success_rate", 1.0) if recipe.get("_success_rate") else None,
                    source_domain=None,  # Would need connection details
                    target_domain=None,
                    raw_data={
                        "recipe_id": recipe_id,
                        "recipe_name": recipe_name,
                        "trigger_app": trigger_app,
                        "action_app": action_app,
                        "is_active": is_active
                    }
                )
                result.pipes.append(pipe)

        logger.info("workato_connector.pipes_built", extra={
            "instance": self.config.instance_name,
            "count": len(result.pipes)
        })

    def _extract_trigger_app(self, recipe: Dict[str, Any]) -> str:
        """Extract the trigger application from a recipe."""
        # Workato recipes have a 'code' field with the recipe definition
        code = recipe.get("code", {})
        if isinstance(code, dict):
            trigger = code.get("trigger", {})
            if isinstance(trigger, dict):
                return trigger.get("application", trigger.get("provider", "unknown"))

        # Fallback: check recipe-level metadata
        trigger_application = recipe.get("trigger_application")
        if trigger_application:
            return trigger_application

        return "unknown"

    def _extract_action_apps(self, recipe: Dict[str, Any]) -> List[str]:
        """Extract action applications from a recipe."""
        apps = []

        # Parse recipe code for actions
        code = recipe.get("code", {})
        if isinstance(code, dict):
            actions = code.get("actions", [])
            for action in actions:
                if isinstance(action, dict):
                    app = action.get("application", action.get("provider"))
                    if app and app not in apps:
                        apps.append(app)

        # Fallback: check recipe-level metadata
        if not apps:
            applications = recipe.get("applications", [])
            trigger_app = self._extract_trigger_app(recipe)
            apps = [app for app in applications if app != trigger_app]

        return apps if apps else ["unknown"]

    def _infer_modality(
        self,
        trigger_app: str,
        action_app: str,
        connections: Dict[str, Dict[str, Any]]
    ) -> ConnectivityModality:
        """Infer modality from app types."""
        # Check known modality mappings
        trigger_modality = CONNECTOR_MODALITY_MAP.get(
            trigger_app.lower(),
            ConnectivityModality.API
        )
        action_modality = CONNECTOR_MODALITY_MAP.get(
            action_app.lower(),
            ConnectivityModality.API
        )

        # If either is DB/FILE, that takes precedence
        if trigger_modality in (ConnectivityModality.DB, ConnectivityModality.FILE):
            return trigger_modality
        if action_modality in (ConnectivityModality.DB, ConnectivityModality.FILE):
            return action_modality

        return ConnectivityModality.API

    def _extract_domain_from_connection(self, conn: Dict[str, Any]) -> Optional[str]:
        """Extract domain from connection settings."""
        # Check for instance URL in settings
        settings = conn.get("settings", {}) or {}
        for key in ["instance_url", "domain", "host", "url", "base_url"]:
            value = settings.get(key)
            if value:
                try:
                    parsed = urlparse(value)
                    if parsed.netloc:
                        return parsed.netloc
                    return value
                except Exception:
                    return value

        return None

    def _parse_timestamp(self, ts: Optional[str]) -> Optional[datetime]:
        """Parse Workato ISO timestamp."""
        if ts:
            try:
                # Handle various ISO formats
                ts = ts.replace("Z", "+00:00")
                return datetime.fromisoformat(ts)
            except (ValueError, AttributeError):
                pass
        return None
