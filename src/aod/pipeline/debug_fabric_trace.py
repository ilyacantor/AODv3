"""
Fabric Routing Debug Trace

Traces the complete journey of a specific asset (e.g., Salesforce) through
the fabric routing pipeline to identify where data drops occur.

Usage:
    from aod.pipeline.debug_fabric_trace import FabricRoutingTracer

    tracer = FabricRoutingTracer("salesforce")
    tracer.trace_cmdb_ingestion(snapshot)
    tracer.trace_normalization(candidates)
    tracer.trace_correlation(correlations, indexes)
    tracer.trace_evidence_collection(planes, evidence_result)
    tracer.trace_fabric_tagging(assets)
    tracer.print_report()
"""

import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class TraceStep:
    """Single step in the trace"""
    stage: str
    found: bool
    details: Dict[str, Any] = field(default_factory=dict)
    raw_data: Optional[Any] = None


class FabricRoutingTracer:
    """
    Traces fabric routing for a specific asset through all pipeline stages.
    """

    def __init__(self, target_name: str):
        """
        Args:
            target_name: Asset name to trace (case-insensitive partial match)
        """
        self.target_name = target_name.lower()
        self.steps: List[TraceStep] = []
        self.final_result: Optional[str] = None

    def _matches(self, name: str) -> bool:
        """Check if name matches target (case-insensitive partial match)"""
        return self.target_name in (name or "").lower()

    def trace_cmdb_ingestion(self, snapshot) -> None:
        """
        Stage 1: Check if CMDB CI exists after Farm adapter ingestion.
        """
        cis = []
        if hasattr(snapshot, 'planes') and hasattr(snapshot.planes, 'cmdb'):
            cis = snapshot.planes.cmdb.cis or []
        elif isinstance(snapshot, dict):
            cis = snapshot.get('planes', {}).get('cmdb', {}).get('cis', [])

        matching_cis = []
        for ci in cis:
            ci_name = ci.name if hasattr(ci, 'name') else ci.get('name', '')
            if self._matches(ci_name):
                ci_data = {
                    'ci_id': ci.ci_id if hasattr(ci, 'ci_id') else ci.get('ci_id'),
                    'name': ci_name,
                    'domain': ci.domain if hasattr(ci, 'domain') else ci.get('domain'),
                    'integrates_via': getattr(ci, 'integrates_via', None) or ci.get('integrates_via'),
                    'fabric_vendor': getattr(ci, 'fabric_vendor', None) or ci.get('fabric_vendor'),
                    'vendor': ci.vendor if hasattr(ci, 'vendor') else ci.get('vendor'),
                }
                matching_cis.append(ci_data)

        self.steps.append(TraceStep(
            stage="1. CMDB Ingestion",
            found=len(matching_cis) > 0,
            details={
                'total_cis': len(cis),
                'matching_cis_count': len(matching_cis),
                'matching_cis': matching_cis,
                'has_integrates_via': any(c.get('integrates_via') for c in matching_cis),
            },
            raw_data=matching_cis[0] if matching_cis else None
        ))

    def trace_normalization(self, candidates) -> None:
        """
        Stage 2: Check normalized candidate/observation.
        """
        matching = []
        for c in candidates:
            name = c.original_name if hasattr(c, 'original_name') else c.get('original_name', '')
            if self._matches(name):
                matching.append({
                    'entity_id': c.entity_id if hasattr(c, 'entity_id') else c.get('entity_id'),
                    'original_name': name,
                    'domain': c.domain if hasattr(c, 'domain') else c.get('domain'),
                    'source': c.source if hasattr(c, 'source') else c.get('source'),
                })

        self.steps.append(TraceStep(
            stage="2. Normalization",
            found=len(matching) > 0,
            details={
                'total_candidates': len(candidates),
                'matching_count': len(matching),
                'matching_candidates': matching,
            },
            raw_data=matching[0] if matching else None
        ))

    def trace_correlation(self, correlations, indexes) -> None:
        """
        Stage 3: Check correlation results - does asset match CMDB CI?
        """
        matching = []
        for corr in correlations:
            entity_name = ''
            if hasattr(corr, 'entity'):
                entity_name = corr.entity.original_name if hasattr(corr.entity, 'original_name') else ''

            if self._matches(entity_name):
                cmdb_match = None
                cmdb_match_method = None

                if hasattr(corr, 'cmdb') and corr.cmdb:
                    cmdb_match = {
                        'ci_id': corr.cmdb.ci_id if hasattr(corr.cmdb, 'ci_id') else None,
                        'name': corr.cmdb.name if hasattr(corr.cmdb, 'name') else None,
                        'integrates_via': getattr(corr.cmdb, 'integrates_via', None),
                        'fabric_vendor': getattr(corr.cmdb, 'fabric_vendor', None),
                    }
                    # Try to determine match method
                    if hasattr(corr, 'cmdb_match_method'):
                        cmdb_match_method = corr.cmdb_match_method
                    elif hasattr(corr, 'match_details'):
                        cmdb_match_method = corr.match_details.get('cmdb_method')

                matching.append({
                    'entity_id': corr.entity.entity_id if hasattr(corr.entity, 'entity_id') else None,
                    'entity_name': entity_name,
                    'has_cmdb_match': cmdb_match is not None,
                    'cmdb_match': cmdb_match,
                    'cmdb_match_method': cmdb_match_method,
                    'has_idp': corr.idp is not None if hasattr(corr, 'idp') else False,
                    'has_finance': corr.finance is not None if hasattr(corr, 'finance') else False,
                })

        self.steps.append(TraceStep(
            stage="3. Correlation",
            found=len(matching) > 0,
            details={
                'total_correlations': len(correlations),
                'matching_count': len(matching),
                'matching_correlations': matching,
                'cmdb_matched': any(m.get('has_cmdb_match') for m in matching),
                'cmdb_has_integrates_via': any(
                    m.get('cmdb_match', {}).get('integrates_via')
                    for m in matching if m.get('cmdb_match')
                ),
            },
            raw_data=matching[0] if matching else None
        ))

    def trace_evidence_collection(self, planes, evidence_result) -> None:
        """
        Stage 4: Check if CMDBEvidenceCollector processed this asset.
        """
        # Check what CIs CMDBEvidenceCollector would process
        cis = planes.cmdb.cis if hasattr(planes, 'cmdb') else []

        matching_cis_with_integrates = []
        matching_cis_without_integrates = []

        for ci in cis:
            ci_name = ci.name if hasattr(ci, 'name') else ''
            if self._matches(ci_name):
                integrates_via = getattr(ci, 'integrates_via', None)
                ci_data = {
                    'ci_id': ci.ci_id if hasattr(ci, 'ci_id') else None,
                    'name': ci_name,
                    'integrates_via': integrates_via,
                    'fabric_vendor': getattr(ci, 'fabric_vendor', None),
                }
                if integrates_via:
                    matching_cis_with_integrates.append(ci_data)
                else:
                    matching_cis_without_integrates.append(ci_data)

        # Check evidence result for this asset
        matching_evidence = []
        if evidence_result and hasattr(evidence_result, 'by_asset'):
            for asset_key, evidence_list in evidence_result.by_asset.items():
                if self._matches(asset_key):
                    for ev in evidence_list:
                        matching_evidence.append({
                            'asset_key': asset_key,
                            'signal_type': ev.signal_type if hasattr(ev, 'signal_type') else None,
                            'source_plane': ev.source_plane.value if hasattr(ev, 'source_plane') and hasattr(ev.source_plane, 'value') else str(getattr(ev, 'source_plane', None)),
                            'fabric_plane_type': ev.fabric_plane_type.value if hasattr(ev, 'fabric_plane_type') and ev.fabric_plane_type and hasattr(ev.fabric_plane_type, 'value') else str(getattr(ev, 'fabric_plane_type', None)),
                            'confidence': ev.confidence if hasattr(ev, 'confidence') else None,
                        })

        self.steps.append(TraceStep(
            stage="4. Evidence Collection",
            found=len(matching_evidence) > 0 or len(matching_cis_with_integrates) > 0,
            details={
                'cis_with_integrates_via': matching_cis_with_integrates,
                'cis_without_integrates_via': matching_cis_without_integrates,
                'evidence_records': matching_evidence,
                'evidence_count': len(matching_evidence),
                'would_produce_evidence': len(matching_cis_with_integrates) > 0,
                'reason_no_evidence': (
                    "CI found but no integrates_via field" if matching_cis_without_integrates and not matching_cis_with_integrates
                    else "No matching CI found" if not matching_cis_with_integrates and not matching_cis_without_integrates
                    else None
                ),
            }
        ))

    def trace_fabric_tagging(self, assets) -> None:
        """
        Stage 5: Check if asset received FabricPlaneTag.
        """
        matching = []
        for asset in assets:
            asset_name = asset.name if hasattr(asset, 'name') else asset.get('name', '')
            if self._matches(asset_name):
                tag = asset.fabric_plane_tag if hasattr(asset, 'fabric_plane_tag') else asset.get('fabric_plane_tag')
                tag_data = None
                if tag:
                    tag_data = {
                        'plane_type': tag.plane_type.value if hasattr(tag, 'plane_type') and hasattr(tag.plane_type, 'value') else str(getattr(tag, 'plane_type', None)),
                        'controller_vendor': tag.controller_vendor if hasattr(tag, 'controller_vendor') else None,
                        'confidence': tag.confidence if hasattr(tag, 'confidence') else None,
                        'evidence': tag.evidence if hasattr(tag, 'evidence') else None,
                    }

                matching.append({
                    'asset_id': str(asset.asset_id) if hasattr(asset, 'asset_id') else asset.get('asset_id'),
                    'name': asset_name,
                    'has_fabric_plane_tag': tag is not None,
                    'fabric_plane_tag': tag_data,
                })

        has_tag = any(m.get('has_fabric_plane_tag') for m in matching)

        self.steps.append(TraceStep(
            stage="5. Fabric Plane Tagging",
            found=has_tag,
            details={
                'matching_assets': matching,
                'has_fabric_plane_tag': has_tag,
            },
            raw_data=matching[0] if matching else None
        ))

        # Set final result
        if matching:
            if has_tag:
                self.final_result = "ROUTED"
            else:
                self.final_result = "NOT_ROUTED"
        else:
            self.final_result = "NOT_FOUND"

    def get_report(self) -> str:
        """Generate a text report of the trace."""
        lines = [
            "=" * 80,
            f"FABRIC ROUTING TRACE: {self.target_name.upper()}",
            "=" * 80,
            "",
        ]

        for step in self.steps:
            status = "✓ FOUND" if step.found else "✗ NOT FOUND"
            lines.append(f"\n{step.stage}: {status}")
            lines.append("-" * 60)

            for key, value in step.details.items():
                if isinstance(value, list) and len(value) > 0:
                    lines.append(f"  {key}:")
                    for item in value[:3]:  # Limit to 3 items
                        if isinstance(item, dict):
                            lines.append(f"    - {item}")
                        else:
                            lines.append(f"    - {item}")
                    if len(value) > 3:
                        lines.append(f"    ... and {len(value) - 3} more")
                elif value is not None:
                    lines.append(f"  {key}: {value}")

        lines.append("")
        lines.append("=" * 80)
        lines.append(f"FINAL RESULT: {self.final_result}")
        lines.append("=" * 80)

        # Diagnosis
        lines.append("\nDIAGNOSIS:")
        lines.append("-" * 60)

        if self.final_result == "NOT_FOUND":
            lines.append("Asset was not found in the pipeline output.")
            lines.append("Check if it was rejected during admission.")
        elif self.final_result == "NOT_ROUTED":
            # Find where it dropped
            for step in self.steps:
                if not step.found:
                    lines.append(f"Data dropped at: {step.stage}")
                    if 'reason_no_evidence' in step.details and step.details['reason_no_evidence']:
                        lines.append(f"Reason: {step.details['reason_no_evidence']}")
                    break
            else:
                # All steps found but no tag
                cmdb_step = next((s for s in self.steps if 'CMDB' in s.stage), None)
                if cmdb_step and not cmdb_step.details.get('has_integrates_via'):
                    lines.append("CMDB CI exists but lacks integrates_via field")
                    lines.append("Fix: Add integrates_via to CMDB record in Farm")
        else:
            lines.append("Asset successfully routed through fabric plane!")

        return "\n".join(lines)

    def print_report(self) -> None:
        """Print the trace report to stdout and logger."""
        report = self.get_report()
        print(report)
        logger.info(f"Fabric routing trace for {self.target_name}:\n{report}")


def trace_asset_fabric_routing(
    target_name: str,
    snapshot,
    candidates,
    correlations,
    indexes,
    planes,
    evidence_result,
    assets
) -> str:
    """
    Convenience function to run full trace and return report.
    """
    tracer = FabricRoutingTracer(target_name)
    tracer.trace_cmdb_ingestion(snapshot)
    tracer.trace_normalization(candidates)
    tracer.trace_correlation(correlations, indexes)
    tracer.trace_evidence_collection(planes, evidence_result)
    tracer.trace_fabric_tagging(assets)
    return tracer.get_report()
