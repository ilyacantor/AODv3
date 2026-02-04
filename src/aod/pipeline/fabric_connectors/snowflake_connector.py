"""
Snowflake INFORMATION_SCHEMA Connector

Crawls Snowflake data warehouse to discover data access patterns.
This is Tier 1 evidence - authoritative data from the warehouse itself.

What Snowflake reveals:
- ACCESS_HISTORY: Which users/roles queried which tables
- QUERY_HISTORY: SQL queries executed (can extract source app patterns)
- TABLES/VIEWS: Database objects
- STAGES: External stages for data loading (S3, Azure, etc.)
- PIPE_USAGE_HISTORY: Snowpipe ingestion sources

CRITICAL: Snowflake ACCESS_HISTORY is noisy. Needs filtering:
- Include: ETL service accounts, known integration users
- Exclude: Analyst queries, BI tool exploration, one-off queries
- Focus: Recurring patterns, high-volume access, programmatic access

From this we can build:
- Pipes: ETL job → Snowflake table relationships
- Assets: Tables/views with data lineage
- Traffic metadata: Query volumes, access patterns
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set

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


# Known ETL/integration service account patterns (higher confidence)
ETL_SERVICE_ACCOUNT_PATTERNS = [
    r"fivetran",
    r"airbyte",
    r"stitch",
    r"matillion",
    r"dbt[_-]?cloud",
    r"airflow",
    r"dagster",
    r"prefect",
    r"etl[_-]?",
    r"data[_-]?pipeline",
    r"integration[_-]?",
    r"sync[_-]?",
    r"load[_-]?",
    r"ingest[_-]?",
]

# Analyst/BI patterns to exclude or reduce confidence
ANALYST_PATTERNS = [
    r"analyst",
    r"@.*\.(com|org|io)$",  # Email-like usernames (human users)
    r"looker",
    r"tableau",
    r"powerbi",
    r"metabase",
    r"mode",
    r"sigma",
    r"preset",
    r"superset",
]

# Minimum query count for recurring pattern detection
MIN_RECURRING_QUERIES = 5

# Lookback period for access history
DEFAULT_LOOKBACK_DAYS = 30


class SnowflakeConnector(FabricPlaneConnector):
    """
    Snowflake INFORMATION_SCHEMA connector for Data Warehouse fabric plane crawl.

    Queries Snowflake metadata to discover:
    - Tables and views with access patterns
    - Query history to identify integration sources
    - External stages for data loading

    Snowflake docs: https://docs.snowflake.com/en/sql-reference/info-schema
    """

    @property
    def plane_type(self) -> FabricPlaneType:
        return FabricPlaneType.DATA_WAREHOUSE

    @property
    def vendor(self) -> str:
        return "snowflake"

    def _validate_config(self) -> None:
        """Validate Snowflake connector config."""
        if not self.config.connection_string:
            # Check for individual components
            account = self.config.extra_config.get("account")
            if not account:
                raise ValueError(
                    "Snowflake connector requires connection_string or account in extra_config"
                )

        if not self.config.username:
            raise ValueError("Snowflake connector requires username")

        if not self.config.password and not self.config.extra_config.get("private_key"):
            raise ValueError(
                "Snowflake connector requires password or private_key in extra_config"
            )

    def test_connection(self) -> bool:
        """Test connection to Snowflake."""
        try:
            result = self._execute_query("SELECT CURRENT_VERSION()")
            return result is not None
        except Exception as e:
            logger.error("snowflake_connector.connection_test_failed", extra={
                "instance": self.config.instance_name,
                "error": str(e)
            })
            return False

    def crawl(self) -> DirectCrawlResult:
        """
        Execute Snowflake metadata crawl.

        Crawls in order:
        1. Tables/Views (database objects)
        2. Access history (who queries what)
        3. External stages (data sources)
        4. Snowpipe usage (streaming ingestion)

        Builds pipes from access patterns with noise filtering.
        """
        self._log_crawl_start()
        result = self._create_result()

        try:
            # Get databases and schemas to crawl
            databases = self._get_accessible_databases()

            # Crawl tables and views
            tables = self._crawl_tables(result, databases)

            # Crawl access history (with noise filtering)
            access_patterns = self._crawl_access_history(result)

            # Crawl external stages
            stages = self._crawl_stages(result, databases)

            # Crawl Snowpipe usage
            pipes = self._crawl_snowpipes(result)

            # Build pipes from access patterns
            self._build_pipes(result, access_patterns, tables)

            result.status = ConnectorStatus.SUCCESS
            result.crawl_completed_at = datetime.utcnow()

        except Exception as e:
            result.status = ConnectorStatus.FAILED
            result.error_message = str(e)
            logger.error("snowflake_connector.crawl_failed", extra={
                "instance": self.config.instance_name,
                "error": str(e)
            })

        self._log_crawl_complete(result)
        return result

    def _execute_query(
        self,
        query: str,
        params: Optional[Dict] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Execute a query against Snowflake.

        In production, this would use snowflake-connector-python.
        For now, returns simulated data for testing.
        """
        logger.debug("snowflake_connector.query", extra={
            "query_preview": query[:100],
            "instance": self.config.instance_name
        })

        # TODO: Replace with actual Snowflake connector
        # Example implementation:
        # import snowflake.connector
        # conn = snowflake.connector.connect(
        #     account=self.config.extra_config.get("account"),
        #     user=self.config.username,
        #     password=self.config.password,
        #     warehouse=self.config.extra_config.get("warehouse"),
        # )
        # cursor = conn.cursor(snowflake.connector.DictCursor)
        # cursor.execute(query)
        # return cursor.fetchall()

        return None

    def _get_accessible_databases(self) -> List[str]:
        """Get list of databases we can access."""
        result = self._execute_query("SHOW DATABASES")
        if not result:
            # Use configured database or default
            db = self.config.extra_config.get("database", "SNOWFLAKE")
            return [db]

        return [row.get("name") for row in result if row.get("name")]

    def _crawl_tables(
        self,
        result: DirectCrawlResult,
        databases: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """Crawl tables and views from INFORMATION_SCHEMA."""
        tables_by_fqn: Dict[str, Dict[str, Any]] = {}

        for database in databases:
            if not self._should_include(database):
                continue

            query = f"""
            SELECT
                TABLE_CATALOG as database_name,
                TABLE_SCHEMA as schema_name,
                TABLE_NAME as table_name,
                TABLE_TYPE as table_type,
                ROW_COUNT as row_count,
                BYTES as bytes,
                CREATED as created_at,
                LAST_ALTERED as updated_at,
                COMMENT as description
            FROM {database}.INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA != 'INFORMATION_SCHEMA'
            """

            tables = self._execute_query(query)
            if not tables:
                continue

            for table in tables:
                table_name = table.get("table_name")
                schema_name = table.get("schema_name")
                db_name = table.get("database_name", database)

                fqn = f"{db_name}.{schema_name}.{table_name}"

                if not self._should_include(fqn):
                    result.items_filtered += 1
                    continue

                # Create crawled asset for the table
                asset = CrawledAsset(
                    asset_id=fqn,
                    asset_name=table_name,
                    asset_type=f"snowflake_{table.get('table_type', 'table').lower()}",
                    domain=f"{db_name}.{schema_name}",
                    uri=fqn,
                    created_at=self._parse_timestamp(table.get("created_at")),
                    updated_at=self._parse_timestamp(table.get("updated_at")),
                    raw_data=table
                )
                result.assets.append(asset)
                result.total_items_crawled += 1

                # Evidence for table discovery
                result.add_evidence(
                    signal_type="snowflake_table",
                    signal_detail=f"Snowflake {table.get('table_type', 'TABLE')} '{fqn}' "
                                 f"({table.get('row_count', 0):,} rows)",
                    asset_key=fqn,
                    raw_data={
                        "fqn": fqn,
                        "table_type": table.get("table_type"),
                        "row_count": table.get("row_count"),
                        "bytes": table.get("bytes")
                    }
                )

                tables_by_fqn[fqn] = table

        logger.info("snowflake_connector.tables_crawled", extra={
            "instance": self.config.instance_name,
            "count": len(tables_by_fqn)
        })

        return tables_by_fqn

    def _crawl_access_history(
        self,
        result: DirectCrawlResult
    ) -> List[Dict[str, Any]]:
        """
        Crawl ACCESS_HISTORY with noise filtering.

        This is where we identify which systems are reading/writing to Snowflake.
        Critical to filter out analyst queries and focus on integration patterns.
        """
        lookback_days = self.config.extra_config.get("lookback_days", DEFAULT_LOOKBACK_DAYS)

        # Query aggregated access patterns
        query = f"""
        SELECT
            USER_NAME as user_name,
            QUERY_TYPE as query_type,
            DIRECT_OBJECTS_ACCESSED as objects_accessed,
            COUNT(*) as query_count,
            SUM(ROWS_PRODUCED) as total_rows,
            MIN(QUERY_START_TIME) as first_access,
            MAX(QUERY_START_TIME) as last_access
        FROM SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY
        WHERE QUERY_START_TIME >= DATEADD('day', -{lookback_days}, CURRENT_TIMESTAMP())
        GROUP BY USER_NAME, QUERY_TYPE, DIRECT_OBJECTS_ACCESSED
        HAVING COUNT(*) >= {MIN_RECURRING_QUERIES}
        ORDER BY query_count DESC
        LIMIT 1000
        """

        access_records = self._execute_query(query)
        if not access_records:
            return []

        filtered_patterns = []

        for record in access_records:
            user_name = record.get("user_name", "").lower()
            query_count = record.get("query_count", 0)

            # Classify the access pattern
            is_etl = self._is_etl_service_account(user_name)
            is_analyst = self._is_analyst_pattern(user_name)

            # Skip analyst patterns unless they have very high volume
            if is_analyst and query_count < 100:
                result.items_filtered += 1
                continue

            # Include ETL patterns
            if is_etl or query_count >= MIN_RECURRING_QUERIES:
                # Parse objects accessed
                objects = record.get("objects_accessed", [])
                if isinstance(objects, str):
                    try:
                        import json
                        objects = json.loads(objects)
                    except (json.JSONDecodeError, TypeError):
                        objects = []

                for obj in objects:
                    if isinstance(obj, dict):
                        obj_name = obj.get("objectName", "")
                        obj_domain = obj.get("objectDomain", "")
                    else:
                        obj_name = str(obj)
                        obj_domain = ""

                    pattern = {
                        "user_name": record.get("user_name"),
                        "query_type": record.get("query_type"),
                        "object_name": obj_name,
                        "object_domain": obj_domain,
                        "query_count": query_count,
                        "total_rows": record.get("total_rows"),
                        "first_access": record.get("first_access"),
                        "last_access": record.get("last_access"),
                        "is_etl": is_etl,
                        "confidence_boost": 0.1 if is_etl else 0.0
                    }
                    filtered_patterns.append(pattern)

                    # Evidence for access pattern
                    access_type = "ETL" if is_etl else "programmatic"
                    result.add_evidence(
                        signal_type="snowflake_access_pattern",
                        signal_detail=f"{access_type} access by '{record.get('user_name')}' to "
                                     f"'{obj_name}' ({query_count:,} queries)",
                        asset_key=obj_name,
                        raw_data=pattern
                    )

        logger.info("snowflake_connector.access_history_crawled", extra={
            "instance": self.config.instance_name,
            "patterns_found": len(filtered_patterns),
            "patterns_filtered": result.items_filtered
        })

        return filtered_patterns

    def _crawl_stages(
        self,
        result: DirectCrawlResult,
        databases: List[str]
    ) -> List[Dict[str, Any]]:
        """Crawl external stages (data loading sources)."""
        all_stages = []

        for database in databases:
            if not self._should_include(database):
                continue

            query = f"""
            SELECT
                STAGE_CATALOG as database_name,
                STAGE_SCHEMA as schema_name,
                STAGE_NAME as stage_name,
                STAGE_TYPE as stage_type,
                STAGE_URL as stage_url,
                CREATED as created_at
            FROM {database}.INFORMATION_SCHEMA.STAGES
            WHERE STAGE_TYPE = 'External'
            """

            stages = self._execute_query(query)
            if not stages:
                continue

            for stage in stages:
                stage_name = stage.get("stage_name")
                stage_url = stage.get("stage_url", "")
                stage_type = stage.get("stage_type")

                fqn = f"{database}.{stage.get('schema_name')}.{stage_name}"

                if not self._should_include(fqn):
                    result.items_filtered += 1
                    continue

                # Extract external source (S3, Azure, GCS)
                external_source = self._parse_stage_url(stage_url)

                # Create crawled asset for the stage
                asset = CrawledAsset(
                    asset_id=fqn,
                    asset_name=stage_name,
                    asset_type="snowflake_external_stage",
                    domain=external_source.get("bucket") if external_source else None,
                    uri=stage_url,
                    created_at=self._parse_timestamp(stage.get("created_at")),
                    raw_data=stage
                )
                result.assets.append(asset)
                result.total_items_crawled += 1

                # Evidence for external stage
                result.add_evidence(
                    signal_type="snowflake_stage",
                    signal_detail=f"Snowflake stage '{stage_name}' loads from {stage_url}",
                    asset_key=external_source.get("bucket", stage_name) if external_source else stage_name,
                    raw_data={
                        "fqn": fqn,
                        "stage_url": stage_url,
                        "stage_type": stage_type,
                        "external_source": external_source
                    }
                )

                all_stages.append({**stage, "_external_source": external_source})

        logger.info("snowflake_connector.stages_crawled", extra={
            "instance": self.config.instance_name,
            "count": len(all_stages)
        })

        return all_stages

    def _crawl_snowpipes(
        self,
        result: DirectCrawlResult
    ) -> List[Dict[str, Any]]:
        """Crawl Snowpipe streaming ingestion."""
        query = """
        SELECT
            PIPE_CATALOG as database_name,
            PIPE_SCHEMA as schema_name,
            PIPE_NAME as pipe_name,
            DEFINITION as definition,
            CREATED as created_at
        FROM SNOWFLAKE.ACCOUNT_USAGE.PIPES
        """

        pipes = self._execute_query(query)
        if not pipes:
            return []

        all_pipes = []

        for pipe in pipes:
            pipe_name = pipe.get("pipe_name")
            definition = pipe.get("definition", "")

            fqn = f"{pipe.get('database_name')}.{pipe.get('schema_name')}.{pipe_name}"

            if not self._should_include(fqn):
                result.items_filtered += 1
                continue

            # Parse definition for source and target
            source_stage, target_table = self._parse_pipe_definition(definition)

            # Create crawled asset
            asset = CrawledAsset(
                asset_id=fqn,
                asset_name=pipe_name,
                asset_type="snowflake_pipe",
                domain=pipe.get("database_name"),
                uri=fqn,
                created_at=self._parse_timestamp(pipe.get("created_at")),
                raw_data=pipe
            )
            result.assets.append(asset)
            result.total_items_crawled += 1

            # Evidence for Snowpipe
            result.add_evidence(
                signal_type="snowflake_pipe",
                signal_detail=f"Snowpipe '{pipe_name}' ingests from {source_stage} to {target_table}",
                asset_key=target_table or pipe_name,
                raw_data={
                    "fqn": fqn,
                    "source_stage": source_stage,
                    "target_table": target_table,
                    "definition": definition[:200]  # Truncate
                }
            )

            all_pipes.append({
                **pipe,
                "_source_stage": source_stage,
                "_target_table": target_table
            })

        logger.info("snowflake_connector.snowpipes_crawled", extra={
            "instance": self.config.instance_name,
            "count": len(all_pipes)
        })

        return all_pipes

    def _build_pipes(
        self,
        result: DirectCrawlResult,
        access_patterns: List[Dict[str, Any]],
        tables: Dict[str, Dict[str, Any]]
    ) -> None:
        """Build pipes from access patterns."""
        # Group patterns by user (source) and object (target)
        pipe_map: Dict[str, CrawledPipe] = {}

        for pattern in access_patterns:
            user_name = pattern.get("user_name", "unknown")
            object_name = pattern.get("object_name", "unknown")
            query_type = pattern.get("query_type", "SELECT")

            # Determine source and target based on query type
            if query_type in ("INSERT", "COPY", "PUT", "MERGE"):
                # Data flowing INTO Snowflake
                source = user_name
                target = object_name
            else:
                # Data flowing OUT of Snowflake
                source = object_name
                target = user_name

            pipe_key = f"{source}_{target}"

            if pipe_key not in pipe_map:
                pipe = CrawledPipe(
                    pipe_id=f"snowflake_{pipe_key}",
                    pipe_name=f"{source} → {target}",
                    source_identifier=source,
                    target_identifier=target,
                    modality=ConnectivityModality.DB,
                    is_active=True,
                    request_count=pattern.get("query_count", 0),
                    last_activity=self._parse_timestamp(pattern.get("last_access")),
                    source_domain=self._extract_domain(source),
                    target_domain=self._extract_domain(target),
                    raw_data={
                        "query_type": query_type,
                        "is_etl": pattern.get("is_etl", False),
                        "total_rows": pattern.get("total_rows", 0)
                    }
                )
                pipe_map[pipe_key] = pipe
            else:
                # Aggregate counts
                existing = pipe_map[pipe_key]
                existing.request_count = (existing.request_count or 0) + pattern.get("query_count", 0)

        result.pipes.extend(pipe_map.values())

        logger.info("snowflake_connector.pipes_built", extra={
            "instance": self.config.instance_name,
            "count": len(pipe_map)
        })

    def _is_etl_service_account(self, username: str) -> bool:
        """Check if username matches ETL service account patterns."""
        for pattern in ETL_SERVICE_ACCOUNT_PATTERNS:
            if re.search(pattern, username, re.IGNORECASE):
                return True
        return False

    def _is_analyst_pattern(self, username: str) -> bool:
        """Check if username matches analyst patterns (noise)."""
        for pattern in ANALYST_PATTERNS:
            if re.search(pattern, username, re.IGNORECASE):
                return True
        return False

    def _parse_stage_url(self, url: str) -> Optional[Dict[str, str]]:
        """Parse external stage URL to extract source info."""
        if not url:
            return None

        # S3: s3://bucket/path
        if url.startswith("s3://"):
            parts = url[5:].split("/", 1)
            return {"type": "s3", "bucket": parts[0], "path": parts[1] if len(parts) > 1 else ""}

        # Azure: azure://account.blob.core.windows.net/container
        if url.startswith("azure://"):
            parts = url[8:].split("/", 1)
            return {"type": "azure", "bucket": parts[0], "path": parts[1] if len(parts) > 1 else ""}

        # GCS: gcs://bucket/path
        if url.startswith("gcs://"):
            parts = url[6:].split("/", 1)
            return {"type": "gcs", "bucket": parts[0], "path": parts[1] if len(parts) > 1 else ""}

        return None

    def _parse_pipe_definition(self, definition: str) -> tuple[Optional[str], Optional[str]]:
        """Parse Snowpipe definition to extract source and target."""
        if not definition:
            return None, None

        # Pattern: COPY INTO table FROM @stage
        copy_match = re.search(
            r"COPY\s+INTO\s+([^\s]+)\s+FROM\s+@([^\s]+)",
            definition,
            re.IGNORECASE
        )
        if copy_match:
            return copy_match.group(2), copy_match.group(1)

        return None, None

    def _extract_domain(self, identifier: str) -> Optional[str]:
        """Extract domain-like string from identifier."""
        if "." in identifier:
            # Could be FQN like DB.SCHEMA.TABLE
            parts = identifier.split(".")
            if len(parts) >= 2:
                return f"{parts[0]}.{parts[1]}"
        return None

    def _parse_timestamp(self, ts: Any) -> Optional[datetime]:
        """Parse Snowflake timestamp."""
        if ts is None:
            return None

        if isinstance(ts, datetime):
            return ts

        if isinstance(ts, str):
            try:
                return datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

        return None
