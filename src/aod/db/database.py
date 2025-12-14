"""SQLite persistence layer for AOD - structured for future PostgreSQL migration"""

import aiosqlite
import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import UUID

from ..models.output_contracts import (
    Asset, Artifact, Finding, RunLog, RunStatus, RunCounts,
    AssetType, Environment, LensStatus, LensStatuses, LensCoverage,
    AssetIdentifiers, FindingType, Severity, ArtifactType
)

DB_PATH = Path("aod.db")

_db_instance: Optional["Database"] = None


async def get_db() -> "Database":
    """Get or create database instance"""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database(DB_PATH)
        await _db_instance.initialize()
    return _db_instance


class Database:
    """SQLite database for AOD persistence"""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None
    
    async def get_connection(self) -> aiosqlite.Connection:
        """Get database connection"""
        if self._conn is None:
            self._conn = await aiosqlite.connect(self.db_path)
            self._conn.row_factory = aiosqlite.Row
        return self._conn
    
    async def close(self):
        """Close database connection"""
        if self._conn:
            await self._conn.close()
            self._conn = None
    
    async def initialize(self):
        """Initialize database schema"""
        conn = await self.get_connection()
        
        await conn.executescript("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                input_meta TEXT NOT NULL DEFAULT '{}',
                counts TEXT NOT NULL DEFAULT '{}',
                failure_reasons TEXT NOT NULL DEFAULT '[]'
            );
            
            CREATE TABLE IF NOT EXISTS assets (
                asset_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                name TEXT NOT NULL,
                asset_type TEXT NOT NULL,
                identifiers TEXT NOT NULL DEFAULT '{}',
                vendor TEXT,
                environment TEXT NOT NULL,
                evidence_refs TEXT NOT NULL DEFAULT '[]',
                lens_status TEXT NOT NULL DEFAULT '{}',
                lens_coverage TEXT NOT NULL DEFAULT '{}',
                tags TEXT NOT NULL DEFAULT '[]',
                admission_reason TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES runs(run_id)
            );
            
            CREATE TABLE IF NOT EXISTS artifacts (
                artifact_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                parent_asset_id TEXT,
                name TEXT NOT NULL,
                artifact_type TEXT NOT NULL,
                source TEXT NOT NULL,
                evidence_ref TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES runs(run_id),
                FOREIGN KEY (parent_asset_id) REFERENCES assets(asset_id)
            );
            
            CREATE TABLE IF NOT EXISTS findings (
                finding_id TEXT PRIMARY KEY,
                asset_id TEXT,
                tenant_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                finding_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                explanation TEXT NOT NULL,
                evidence_refs TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES runs(run_id),
                FOREIGN KEY (asset_id) REFERENCES assets(asset_id)
            );
            
            CREATE INDEX IF NOT EXISTS idx_assets_run_id ON assets(run_id);
            CREATE INDEX IF NOT EXISTS idx_artifacts_run_id ON artifacts(run_id);
            CREATE INDEX IF NOT EXISTS idx_findings_run_id ON findings(run_id);
            CREATE INDEX IF NOT EXISTS idx_findings_asset_id ON findings(asset_id);
            
            CREATE TABLE IF NOT EXISTS observation_samples (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                name TEXT NOT NULL,
                domain TEXT,
                source TEXT NOT NULL,
                category TEXT,
                raw_preview TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES runs(run_id)
            );
            
            CREATE TABLE IF NOT EXISTS ambiguous_matches (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                entity_key TEXT NOT NULL,
                entity_name TEXT NOT NULL,
                plane TEXT NOT NULL,
                candidate_ids TEXT NOT NULL DEFAULT '[]',
                candidate_names TEXT NOT NULL DEFAULT '[]',
                match_keys TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES runs(run_id)
            );
            
            CREATE TABLE IF NOT EXISTS rejections (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                entity_key TEXT NOT NULL,
                entity_name TEXT NOT NULL,
                reason_code TEXT NOT NULL,
                reason_detail TEXT NOT NULL,
                evidence_summary TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES runs(run_id)
            );
            
            CREATE INDEX IF NOT EXISTS idx_observation_samples_run_id ON observation_samples(run_id);
            CREATE INDEX IF NOT EXISTS idx_ambiguous_matches_run_id ON ambiguous_matches(run_id);
            CREATE INDEX IF NOT EXISTS idx_rejections_run_id ON rejections(run_id);
        """)
        
        await conn.commit()
    
    async def create_run(self, run: RunLog) -> RunLog:
        """Create a new run log entry"""
        conn = await self.get_connection()
        
        await conn.execute(
            """
            INSERT INTO runs (run_id, tenant_id, status, started_at, completed_at, input_meta, counts, failure_reasons)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run.run_id,
                run.tenant_id,
                run.status.value,
                run.started_at.isoformat(),
                run.completed_at.isoformat() if run.completed_at else None,
                json.dumps(run.input_meta),
                run.counts.model_dump_json(),
                json.dumps(run.failure_reasons)
            )
        )
        await conn.commit()
        return run
    
    async def update_run(self, run: RunLog) -> RunLog:
        """Update an existing run log entry"""
        conn = await self.get_connection()
        
        await conn.execute(
            """
            UPDATE runs SET
                status = ?,
                completed_at = ?,
                counts = ?,
                failure_reasons = ?
            WHERE run_id = ?
            """,
            (
                run.status.value,
                run.completed_at.isoformat() if run.completed_at else None,
                run.counts.model_dump_json(),
                json.dumps(run.failure_reasons),
                run.run_id
            )
        )
        await conn.commit()
        return run
    
    async def get_run(self, run_id: str) -> Optional[RunLog]:
        """Get a run log entry by ID"""
        conn = await self.get_connection()
        
        cursor = await conn.execute(
            "SELECT * FROM runs WHERE run_id = ?",
            (run_id,)
        )
        row = await cursor.fetchone()
        
        if not row:
            return None
        
        return RunLog(
            run_id=row["run_id"],
            tenant_id=row["tenant_id"],
            status=RunStatus(row["status"]),
            started_at=datetime.fromisoformat(row["started_at"]),
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            input_meta=json.loads(row["input_meta"]),
            counts=RunCounts.model_validate_json(row["counts"]),
            failure_reasons=json.loads(row["failure_reasons"])
        )
    
    async def get_all_runs(self) -> list[RunLog]:
        """Get all run logs"""
        conn = await self.get_connection()
        
        cursor = await conn.execute(
            "SELECT * FROM runs ORDER BY started_at DESC"
        )
        rows = await cursor.fetchall()
        
        return [
            RunLog(
                run_id=row["run_id"],
                tenant_id=row["tenant_id"],
                status=RunStatus(row["status"]),
                started_at=datetime.fromisoformat(row["started_at"]),
                completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
                input_meta=json.loads(row["input_meta"]),
                counts=RunCounts.model_validate_json(row["counts"]),
                failure_reasons=json.loads(row["failure_reasons"])
            )
            for row in rows
        ]
    
    async def create_asset(self, asset: Asset) -> Asset:
        """Create a new asset"""
        conn = await self.get_connection()
        
        await conn.execute(
            """
            INSERT INTO assets (
                asset_id, tenant_id, run_id, name, asset_type, identifiers,
                vendor, environment, evidence_refs, lens_status, lens_coverage,
                tags, admission_reason, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(asset.asset_id),
                asset.tenant_id,
                asset.run_id,
                asset.name,
                asset.asset_type.value,
                asset.identifiers.model_dump_json(),
                asset.vendor,
                asset.environment.value,
                json.dumps(asset.evidence_refs),
                asset.lens_status.model_dump_json(),
                asset.lens_coverage.model_dump_json(),
                json.dumps(asset.tags),
                asset.admission_reason,
                asset.created_at.isoformat()
            )
        )
        await conn.commit()
        return asset
    
    async def get_assets_by_run(self, run_id: str) -> list[Asset]:
        """Get all assets for a run"""
        conn = await self.get_connection()
        
        cursor = await conn.execute(
            "SELECT * FROM assets WHERE run_id = ? ORDER BY name",
            (run_id,)
        )
        rows = await cursor.fetchall()
        
        return [
            Asset(
                asset_id=UUID(row["asset_id"]),
                tenant_id=row["tenant_id"],
                run_id=row["run_id"],
                name=row["name"],
                asset_type=AssetType(row["asset_type"]),
                identifiers=AssetIdentifiers.model_validate_json(row["identifiers"]),
                vendor=row["vendor"],
                environment=Environment(row["environment"]),
                evidence_refs=json.loads(row["evidence_refs"]),
                lens_status=LensStatuses.model_validate_json(row["lens_status"]),
                lens_coverage=LensCoverage.model_validate_json(row["lens_coverage"]),
                tags=json.loads(row["tags"]),
                admission_reason=row["admission_reason"],
                created_at=datetime.fromisoformat(row["created_at"])
            )
            for row in rows
        ]
    
    async def create_artifact(self, artifact: Artifact) -> Artifact:
        """Create a new artifact"""
        conn = await self.get_connection()
        
        await conn.execute(
            """
            INSERT INTO artifacts (
                artifact_id, tenant_id, run_id, parent_asset_id, name,
                artifact_type, source, evidence_ref, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(artifact.artifact_id),
                artifact.tenant_id,
                artifact.run_id,
                str(artifact.parent_asset_id) if artifact.parent_asset_id else None,
                artifact.name,
                artifact.artifact_type.value,
                artifact.source,
                artifact.evidence_ref,
                artifact.created_at.isoformat()
            )
        )
        await conn.commit()
        return artifact
    
    async def get_artifacts_by_run(self, run_id: str) -> list[Artifact]:
        """Get all artifacts for a run"""
        conn = await self.get_connection()
        
        cursor = await conn.execute(
            "SELECT * FROM artifacts WHERE run_id = ? ORDER BY name",
            (run_id,)
        )
        rows = await cursor.fetchall()
        
        return [
            Artifact(
                artifact_id=UUID(row["artifact_id"]),
                tenant_id=row["tenant_id"],
                run_id=row["run_id"],
                parent_asset_id=UUID(row["parent_asset_id"]) if row["parent_asset_id"] else None,
                name=row["name"],
                artifact_type=ArtifactType(row["artifact_type"]),
                source=row["source"],
                evidence_ref=row["evidence_ref"],
                created_at=datetime.fromisoformat(row["created_at"])
            )
            for row in rows
        ]
    
    async def create_finding(self, finding: Finding) -> Finding:
        """Create a new finding"""
        conn = await self.get_connection()
        
        await conn.execute(
            """
            INSERT INTO findings (
                finding_id, asset_id, tenant_id, run_id, finding_type,
                severity, explanation, evidence_refs, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(finding.finding_id),
                str(finding.asset_id) if finding.asset_id else None,
                finding.tenant_id,
                finding.run_id,
                finding.finding_type.value,
                finding.severity.value,
                finding.explanation,
                json.dumps(finding.evidence_refs),
                finding.created_at.isoformat()
            )
        )
        await conn.commit()
        return finding
    
    async def get_findings_by_run(self, run_id: str) -> list[Finding]:
        """Get all findings for a run"""
        conn = await self.get_connection()
        
        cursor = await conn.execute(
            "SELECT * FROM findings WHERE run_id = ? ORDER BY severity DESC, finding_type",
            (run_id,)
        )
        rows = await cursor.fetchall()
        
        return [
            Finding(
                finding_id=UUID(row["finding_id"]),
                asset_id=UUID(row["asset_id"]) if row["asset_id"] else None,
                tenant_id=row["tenant_id"],
                run_id=row["run_id"],
                finding_type=FindingType(row["finding_type"]),
                severity=Severity(row["severity"]),
                explanation=row["explanation"],
                evidence_refs=json.loads(row["evidence_refs"]),
                created_at=datetime.fromisoformat(row["created_at"])
            )
            for row in rows
        ]
    
    async def create_observation_sample(
        self,
        sample_id: str,
        run_id: str,
        name: str,
        domain: Optional[str],
        source: str,
        category: Optional[str],
        raw_preview: str,
        created_at: datetime
    ) -> None:
        """Create an observation sample record"""
        conn = await self.get_connection()
        await conn.execute(
            """
            INSERT INTO observation_samples (id, run_id, name, domain, source, category, raw_preview, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (sample_id, run_id, name, domain, source, category, raw_preview, created_at.isoformat())
        )
        await conn.commit()
    
    async def create_ambiguous_match(
        self,
        match_id: str,
        run_id: str,
        entity_key: str,
        entity_name: str,
        plane: str,
        candidate_ids: list[str],
        candidate_names: list[str],
        match_keys: list[str],
        created_at: datetime
    ) -> None:
        """Create an ambiguous match record"""
        conn = await self.get_connection()
        await conn.execute(
            """
            INSERT INTO ambiguous_matches (id, run_id, entity_key, entity_name, plane, candidate_ids, candidate_names, match_keys, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                match_id, run_id, entity_key, entity_name, plane,
                json.dumps(candidate_ids), json.dumps(candidate_names), json.dumps(match_keys),
                created_at.isoformat()
            )
        )
        await conn.commit()
    
    async def create_rejection(
        self,
        rejection_id: str,
        run_id: str,
        entity_key: str,
        entity_name: str,
        reason_code: str,
        reason_detail: str,
        evidence_summary: dict,
        created_at: datetime
    ) -> None:
        """Create a rejection record"""
        conn = await self.get_connection()
        await conn.execute(
            """
            INSERT INTO rejections (id, run_id, entity_key, entity_name, reason_code, reason_detail, evidence_summary, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rejection_id, run_id, entity_key, entity_name, reason_code, reason_detail,
                json.dumps(evidence_summary), created_at.isoformat()
            )
        )
        await conn.commit()
    
    async def get_observation_samples_by_run(self, run_id: str, limit: int = 100, offset: int = 0) -> tuple[list[dict], int]:
        """Get observation samples for a run with pagination"""
        conn = await self.get_connection()
        
        count_cursor = await conn.execute(
            "SELECT COUNT(*) as total FROM observation_samples WHERE run_id = ?",
            (run_id,)
        )
        count_row = await count_cursor.fetchone()
        total = count_row["total"] if count_row else 0
        
        cursor = await conn.execute(
            "SELECT * FROM observation_samples WHERE run_id = ? ORDER BY name LIMIT ? OFFSET ?",
            (run_id, limit, offset)
        )
        rows = await cursor.fetchall()
        
        items = [
            {
                "id": row["id"],
                "name": row["name"],
                "domain": row["domain"],
                "source": row["source"],
                "category": row["category"],
                "raw_preview": row["raw_preview"],
                "created_at": row["created_at"]
            }
            for row in rows
        ]
        return items, total
    
    async def get_ambiguous_matches_by_run(self, run_id: str, limit: int = 100, offset: int = 0) -> tuple[list[dict], int]:
        """Get ambiguous matches for a run with pagination"""
        conn = await self.get_connection()
        
        count_cursor = await conn.execute(
            "SELECT COUNT(*) as total FROM ambiguous_matches WHERE run_id = ?",
            (run_id,)
        )
        count_row = await count_cursor.fetchone()
        total = count_row["total"] if count_row else 0
        
        cursor = await conn.execute(
            "SELECT * FROM ambiguous_matches WHERE run_id = ? ORDER BY entity_name LIMIT ? OFFSET ?",
            (run_id, limit, offset)
        )
        rows = await cursor.fetchall()
        
        items = [
            {
                "id": row["id"],
                "entity_key": row["entity_key"],
                "entity_name": row["entity_name"],
                "plane": row["plane"],
                "candidate_ids": json.loads(row["candidate_ids"]),
                "candidate_names": json.loads(row["candidate_names"]),
                "match_keys": json.loads(row["match_keys"]),
                "created_at": row["created_at"]
            }
            for row in rows
        ]
        return items, total
    
    async def get_rejections_by_run(self, run_id: str, limit: int = 100, offset: int = 0) -> tuple[list[dict], int]:
        """Get rejections for a run with pagination"""
        conn = await self.get_connection()
        
        count_cursor = await conn.execute(
            "SELECT COUNT(*) as total FROM rejections WHERE run_id = ?",
            (run_id,)
        )
        count_row = await count_cursor.fetchone()
        total = count_row["total"] if count_row else 0
        
        cursor = await conn.execute(
            "SELECT * FROM rejections WHERE run_id = ? ORDER BY entity_name LIMIT ? OFFSET ?",
            (run_id, limit, offset)
        )
        rows = await cursor.fetchall()
        
        items = [
            {
                "id": row["id"],
                "entity_key": row["entity_key"],
                "entity_name": row["entity_name"],
                "reason_code": row["reason_code"],
                "reason_detail": row["reason_detail"],
                "evidence_summary": json.loads(row["evidence_summary"]),
                "created_at": row["created_at"]
            }
            for row in rows
        ]
        return items, total
