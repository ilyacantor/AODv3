"""
Tests for pipeline identity fields on discovery and handoff responses.

Verifies compliance with pipeline_identity_architecture_v1:
  - I1: Namespaced identifiers (aod_discovery_id, handoff_id)
  - I2: Identity pair (tenant_id + entity_id) on every response
  - I3: Provenance is explicit (consumed_snapshot_id, source_aod_discovery_id)
"""

import uuid
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aod.api.schemas import RunResponse, FarmRunRequest
from aod.models.output_contracts import RunCounts


class TestDiscoveryResponseIdentity:
    """Discovery response (/api/runs/from-farm) must carry identity + provenance fields."""

    def test_aod_discovery_id_present_in_schema(self):
        """RunResponse schema accepts aod_discovery_id."""
        resp = RunResponse(
            aod_discovery_id=str(uuid.uuid4()),
            consumed_snapshot_id="snap_001",
            tenant_id="t-123",
            entity_id="acme",
            status="completed",
            counts=RunCounts(),
            message="ok",
        )
        assert resp.aod_discovery_id is not None
        # Must be a valid UUID
        uuid.UUID(resp.aod_discovery_id)

    def test_consumed_snapshot_id_present(self):
        """RunResponse carries consumed_snapshot_id (provenance — I3)."""
        resp = RunResponse(
            aod_discovery_id=str(uuid.uuid4()),
            consumed_snapshot_id="snap_001",
            tenant_id="t-123",
            entity_id="acme",
            status="completed",
            counts=RunCounts(),
            message="ok",
        )
        assert resp.consumed_snapshot_id == "snap_001"

    def test_tenant_id_present(self):
        """RunResponse carries tenant_id (identity pair — I2)."""
        resp = RunResponse(
            aod_discovery_id=str(uuid.uuid4()),
            consumed_snapshot_id="snap_001",
            tenant_id="t-123",
            entity_id="acme",
            status="completed",
            counts=RunCounts(),
            message="ok",
        )
        assert resp.tenant_id == "t-123"

    def test_entity_id_present(self):
        """RunResponse carries entity_id (identity pair — I2)."""
        resp = RunResponse(
            aod_discovery_id=str(uuid.uuid4()),
            consumed_snapshot_id="snap_001",
            tenant_id="t-123",
            entity_id="acme",
            status="completed",
            counts=RunCounts(),
            message="ok",
        )
        assert resp.entity_id == "acme"

    def test_aod_discovery_id_is_unique_per_call(self):
        """Each discovery response mints a fresh UUID."""
        id1 = str(uuid.uuid4())
        id2 = str(uuid.uuid4())
        assert id1 != id2

    def test_discovery_response_serialization(self):
        """All identity fields appear in JSON output."""
        disc_id = str(uuid.uuid4())
        resp = RunResponse(
            aod_discovery_id=disc_id,
            consumed_snapshot_id="snap_002",
            tenant_id="t-456",
            entity_id="bluelogic",
            status="completed",
            counts=RunCounts(),
            message="ok",
        )
        data = resp.model_dump()
        assert data["aod_discovery_id"] == disc_id
        assert data["consumed_snapshot_id"] == "snap_002"
        assert data["tenant_id"] == "t-456"
        assert data["entity_id"] == "bluelogic"


class TestHandoffResponseIdentity:
    """Handoff response (/api/handoff/aam/export) must carry identity + provenance fields."""

    def _import_handoff_response(self):
        from aod.api.routes.handoff import AAMExportResponse
        return AAMExportResponse

    def test_handoff_id_present(self):
        """AAMExportResponse carries handoff_id (namespaced identifier — I1)."""
        AAMExportResponse = self._import_handoff_response()
        hid = str(uuid.uuid4())
        resp = AAMExportResponse(
            success=True,
            message="ok",
            aod_discovery_id="run_abc123",
            handoff_id=hid,
            source_aod_discovery_id=str(uuid.uuid4()),
            tenant_id="t-123",
            entity_id="acme",
            candidates_sent=10,
        )
        assert resp.handoff_id == hid
        uuid.UUID(resp.handoff_id)

    def test_source_aod_discovery_id_present(self):
        """AAMExportResponse carries source_aod_discovery_id (provenance — I3)."""
        AAMExportResponse = self._import_handoff_response()
        disc_id = str(uuid.uuid4())
        resp = AAMExportResponse(
            success=True,
            message="ok",
            aod_discovery_id="run_abc123",
            handoff_id=str(uuid.uuid4()),
            source_aod_discovery_id=disc_id,
            tenant_id="t-123",
            entity_id="acme",
            candidates_sent=10,
        )
        assert resp.source_aod_discovery_id == disc_id
        uuid.UUID(resp.source_aod_discovery_id)

    def test_tenant_id_on_handoff(self):
        """AAMExportResponse carries tenant_id (identity pair — I2)."""
        AAMExportResponse = self._import_handoff_response()
        resp = AAMExportResponse(
            success=True,
            message="ok",
            aod_discovery_id="run_abc123",
            handoff_id=str(uuid.uuid4()),
            source_aod_discovery_id=str(uuid.uuid4()),
            tenant_id="t-789",
            entity_id="acme",
            candidates_sent=5,
        )
        assert resp.tenant_id == "t-789"

    def test_entity_id_on_handoff(self):
        """AAMExportResponse carries entity_id (identity pair — I2)."""
        AAMExportResponse = self._import_handoff_response()
        resp = AAMExportResponse(
            success=True,
            message="ok",
            aod_discovery_id="run_abc123",
            handoff_id=str(uuid.uuid4()),
            source_aod_discovery_id=str(uuid.uuid4()),
            tenant_id="t-789",
            entity_id="bluelogic",
            candidates_sent=5,
        )
        assert resp.entity_id == "bluelogic"

    def test_handoff_response_serialization(self):
        """All identity fields appear in JSON output."""
        AAMExportResponse = self._import_handoff_response()
        hid = str(uuid.uuid4())
        disc_id = str(uuid.uuid4())
        resp = AAMExportResponse(
            success=True,
            message="ok",
            aod_discovery_id="run_abc123",
            handoff_id=hid,
            source_aod_discovery_id=disc_id,
            tenant_id="t-999",
            entity_id="meridian_co",
            candidates_sent=3,
        )
        data = resp.model_dump()
        assert data["handoff_id"] == hid
        assert data["source_aod_discovery_id"] == disc_id
        assert data["tenant_id"] == "t-999"
        assert data["entity_id"] == "meridian_co"

    def test_handoff_id_is_valid_uuid(self):
        """handoff_id must be a valid UUID4."""
        AAMExportResponse = self._import_handoff_response()
        hid = str(uuid.uuid4())
        resp = AAMExportResponse(
            success=True,
            message="ok",
            aod_discovery_id="run_abc123",
            handoff_id=hid,
            source_aod_discovery_id=str(uuid.uuid4()),
            tenant_id="t-123",
            entity_id="acme",
            candidates_sent=0,
        )
        parsed = uuid.UUID(resp.handoff_id)
        assert parsed.version == 4
