"""Catalog routes for AOD API"""

import re
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from typing import Optional

from ..schemas import CatalogResponse, ProvisioningActionRequest, ProvisioningActionResponse
from ...db.database import get_db_direct
from ...models.output_contracts import ProvisioningStatus

router = APIRouter(prefix="/catalog")

ACTION_TO_STATUS = {
    "SANCTION": ProvisioningStatus.ACTIVE,
    "BAN": ProvisioningStatus.BLOCKED,
    "DEPROVISION": ProvisioningStatus.RETIRED,
    "ACKNOWLEDGE": ProvisioningStatus.ACTIVE,
    "DISMISS_RISK": ProvisioningStatus.ACTIVE,
}


@router.get("", response_model=CatalogResponse)
async def get_catalog(
    run_id: str,
    provisioning_status: Optional[str] = Query(None, description="Filter by provisioning status (active, review, quarantine)")
):
    """
    Get assets for a run.
    
    Optional filter by provisioning_status:
    - active: Only ACTIVE assets (trusted, flows to DCL)
    - review: Only REVIEW assets (needs cleanup)
    - quarantine: Only QUARANTINE assets (shadow IT, blocked from DCL)
    """
    db = await get_db_direct()
    
    run = await db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    assets = await db.get_assets_by_run(run_id)
    
    # Apply provisioning status filter if provided
    if provisioning_status:
        status_filter = provisioning_status.upper()
        assets = [a for a in assets if a.provisioning_status.value.upper() == status_filter]
    
    return CatalogResponse(
        run_id=run_id,
        assets=[
            {
                "asset_id": str(a.asset_id),
                "name": a.name,
                "asset_type": a.asset_type.value,
                "vendor": a.vendor,
                "environment": a.environment.value,
                "identifiers": a.identifiers.model_dump(),
                "lens_status": a.lens_status.model_dump(),
                "lens_coverage": a.lens_coverage.model_dump(),
                "tags": a.tags,
                "admission_reason": a.admission_reason,
                "evidence_refs": a.evidence_refs,
                "provisioning_status": a.provisioning_status.value,
                "owner": a.owner,
                "has_critical_gap": a.has_critical_gap,
                "created_at": a.created_at.isoformat()
            }
            for a in assets
        ],
        count=len(assets)
    )


@router.get("/dcl", response_model=CatalogResponse)
async def get_dcl_export(run_id: str):
    """
    DCL (Discovery Control Layer) Export - Only ACTIVE provisioned assets.
    
    This is the guardrail endpoint that ONLY returns assets with provisioning_status=ACTIVE.
    These are trusted assets (IdP or CMDB governed) that flow to the DCL.
    
    QUARANTINE assets (Shadow IT) are blocked from this export.
    REVIEW assets (zombie candidates) are blocked until cleaned up.
    """
    db = await get_db_direct()
    
    run = await db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    all_assets = await db.get_assets_by_run(run_id)
    
    # GUARDRAIL: Only ACTIVE assets flow to DCL
    active_assets = [a for a in all_assets if a.provisioning_status == ProvisioningStatus.ACTIVE]
    
    return CatalogResponse(
        run_id=run_id,
        assets=[
            {
                "asset_id": str(a.asset_id),
                "name": a.name,
                "asset_type": a.asset_type.value,
                "vendor": a.vendor,
                "environment": a.environment.value,
                "identifiers": a.identifiers.model_dump(),
                "lens_status": a.lens_status.model_dump(),
                "lens_coverage": a.lens_coverage.model_dump(),
                "tags": a.tags,
                "admission_reason": a.admission_reason,
                "evidence_refs": a.evidence_refs,
                "provisioning_status": a.provisioning_status.value,
                "owner": a.owner,
                "created_at": a.created_at.isoformat()
            }
            for a in active_assets
        ],
        count=len(active_assets)
    )


@router.get("/view", response_class=HTMLResponse)
async def view_catalog(run_id: str):
    """Display catalog as HTML page"""
    db = await get_db_direct()
    
    run = await db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    assets = await db.get_assets_by_run(run_id)
    
    triage_actions = await db.get_triage_actions_by_run(run_id)
    findings = await db.get_findings_by_run(run_id)
    
    finding_to_asset = {str(f.finding_id): str(f.asset_id) for f in findings if f.asset_id}
    
    triage_by_asset = {}
    for action in triage_actions:
        item_id = action.get('item_id')
        item_type = action.get('item_type')
        
        if item_type in ('asset', 'shadow', 'zombie', 'governance'):
            if item_id not in triage_by_asset:
                triage_by_asset[item_id] = action
            else:
                existing = triage_by_asset[item_id]
                existing_priority = {'approved': 5, 'banned': 5, 'deprovisioned': 5, 'deferred': 3, 'assigned': 2, 'acknowledged': 2, 'ignored': 1}.get(existing.get('state', ''), 0)
                new_priority = {'approved': 5, 'banned': 5, 'deprovisioned': 5, 'deferred': 3, 'assigned': 2, 'acknowledged': 2, 'ignored': 1}.get(action.get('state', ''), 0)
                if new_priority > existing_priority:
                    triage_by_asset[item_id] = action
        elif item_type == 'finding':
            asset_id = finding_to_asset.get(item_id)
            if asset_id and asset_id not in triage_by_asset:
                triage_by_asset[asset_id] = action
    
    def get_tag(asset, key):
        """Get tag value from asset, handling both dict and list formats"""
        if not asset.tags:
            return None
        if isinstance(asset.tags, dict):
            return asset.tags.get(key)
        return None
    
    def get_triage_badge(asset_id):
        """Get triage disposition badge for an asset"""
        action = triage_by_asset.get(str(asset_id))
        if not action:
            return ''
        
        action_type = action.get('action_type', '') or action.get('action', '')
        state = action.get('state', '')
        owner = action.get('owner', '') or action.get('metadata', {}).get('assigned_to', '')
        
        if state == 'approved':
            return f'<span style="background: #10b981; color: #fff; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: 500;">Approved for AAM{" by " + owner if owner else ""}</span>'
        elif state == 'banned':
            return f'<span style="background: #1e293b; color: #ef4444; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: 500; border: 1px solid #ef4444;">Banned{" by " + owner if owner else ""}</span>'
        elif state == 'deprovisioned':
            return f'<span style="background: #374151; color: #9ca3af; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: 500;">Deprovisioned{" by " + owner if owner else ""}</span>'
        elif action_type == 'assign':
            return f'<span style="background: #3b82f6; color: #fff; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: 500;">Assigned to: {owner}</span>'
        elif action_type == 'defer':
            days = action.get('metadata', {}).get('defer_days', '')
            return f'<span style="background: #8b5cf6; color: #fff; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: 500;">Deferred {days}d</span>'
        elif action_type == 'ignore':
            return '<span style="background: #64748b; color: #fff; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: 500;">Ignored</span>'
        elif state == 'acknowledged':
            return f'<span style="background: #0ea5e9; color: #fff; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: 500;">Assigned to: {owner if owner else "team"}</span>'
        return ''
    
    shadow_count = sum(1 for a in assets if get_tag(a, 'shadow_actual') == True)
    zombie_count = sum(1 for a in assets if get_tag(a, 'zombie_actual') == True)
    governed_count = sum(1 for a in assets if a.lens_status and (a.lens_status.cmdb or a.lens_status.idp))
    
    triage_stats = {'approved': 0, 'banned': 0, 'deprovisioned': 0, 'assigned': 0, 'deferred': 0, 'ignored': 0, 'pending': 0}
    triaged_asset_ids = set()
    for action in triage_actions:
        action_type = action.get('action_type', '') or action.get('action', '')
        state = action.get('state', '')
        item_id = action.get('item_id', '')
        
        if state == 'approved':
            triage_stats['approved'] += 1
        elif state == 'banned':
            triage_stats['banned'] += 1
        elif state == 'deprovisioned':
            triage_stats['deprovisioned'] += 1
        elif action_type == 'assign' or state == 'acknowledged':
            triage_stats['assigned'] += 1
        elif action_type == 'defer' or state == 'deferred':
            triage_stats['deferred'] += 1
        elif action_type == 'ignore':
            triage_stats['ignored'] += 1
        triaged_asset_ids.add(item_id)
    triage_stats['pending'] = len(assets) - len(triaged_asset_ids.intersection({str(a.asset_id) for a in assets}))
    
    triaged_finding_ids = {action['item_id'] for action in triage_actions if action.get('item_type') == 'finding'}
    orphan_findings = [f for f in findings if not f.asset_id and str(f.finding_id) in triaged_finding_ids]
    
    def get_finding_triage_badge(finding_id):
        """Get triage disposition badge for a finding"""
        for action in triage_actions:
            if action.get('item_id') == str(finding_id):
                action_type = action.get('action', '')
                state = action.get('state', '')
                owner = action.get('owner', '')
                
                if action_type == 'assign':
                    return f'<span style="background: #3b82f6; color: #fff; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: 500;">Assigned to: {owner}</span>'
                elif action_type == 'defer':
                    return '<span style="background: #8b5cf6; color: #fff; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: 500;">Deferred</span>'
                elif action_type == 'ignore':
                    return '<span style="background: #64748b; color: #fff; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: 500;">Ignored</span>'
                elif action_type == 'acknowledge' or state == 'acknowledged':
                    return f'<span style="background: #0ea5e9; color: #fff; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: 500;">Assigned to: {owner if owner else "team"}</span>'
        return ''
    
    def get_provisioning_badge(asset):
        """Get provisioning status badge for an asset"""
        status = asset.provisioning_status.value if asset.provisioning_status else 'QUARANTINE'
        is_shadow = get_tag(asset, 'shadow_actual') == True
        is_zombie = get_tag(asset, 'zombie_actual') == True
        
        if status == 'ACTIVE' and (is_shadow or is_zombie):
            return '<span style="background: #10b981; color: #fff; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: 500;">Approved for AAM</span>'
        elif status == 'BLOCKED':
            return '<span style="background: #1e293b; color: #ef4444; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: 500; border: 1px solid #ef4444;">Banned</span>'
        elif status == 'RETIRED':
            return '<span style="background: #374151; color: #9ca3af; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: 500;">Deprovisioned</span>'
        elif status == 'QUARANTINE':
            return '<span style="background: #7f1d1d; color: #fca5a5; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: 500;">Quarantined</span>'
        elif status == 'REVIEW':
            return '<span style="background: #78350f; color: #fcd34d; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: 500;">Under Review</span>'
        return ''
    
    orphan_rows_html = ""
    for f in orphan_findings:
        vendor_match = None
        if f.explanation:
            match = re.search(r"Vendor '([^']+)'", f.explanation)
            if match:
                vendor_match = match.group(1)
        
        finding_type_display = f.finding_type.value.replace('_', ' ').title() if f.finding_type else '-'
        triage_badge = get_finding_triage_badge(f.finding_id)
        
        orphan_rows_html += f'''
        <tr style="border-bottom: 1px solid #334155;" data-type="finding" data-name="{vendor_match or 'Unknown'}">
            <td style="padding: 0.75rem; color: #f59e0b; font-weight: 500;">{vendor_match or 'Unknown Vendor'}</td>
            <td style="padding: 0.75rem; color: #94a3b8;">{finding_type_display}</td>
            <td style="padding: 0.75rem; color: #64748b; font-size: 0.8rem; max-width: 400px; overflow: hidden; text-overflow: ellipsis;">{f.explanation[:100] + '...' if f.explanation and len(f.explanation) > 100 else f.explanation or '-'}</td>
            <td style="padding: 0.75rem;">{triage_badge}</td>
        </tr>'''
    
    rows_html = ""
    for a in assets:
        is_shadow = get_tag(a, 'shadow_actual') == True
        is_zombie = get_tag(a, 'zombie_actual') == True
        
        status_badges = []
        if is_shadow:
            status_badges.append('<span style="background: #f59e0b; color: #000; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: 600;">SHADOW</span>')
        if is_zombie:
            status_badges.append('<span style="background: #ef4444; color: #fff; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: 600;">ZOMBIE</span>')
        if not is_shadow and not is_zombie:
            status_badges.append('<span style="background: #22c55e; color: #000; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: 600;">GOVERNED</span>')
        
        lens_parts = []
        if a.lens_coverage:
            if a.lens_coverage.discovery: lens_parts.append('Discovery')
            if a.lens_coverage.idp: lens_parts.append('IdP')
            if a.lens_coverage.cmdb: lens_parts.append('CMDB')
            if a.lens_coverage.cloud: lens_parts.append('Cloud')
            if a.lens_coverage.finance: lens_parts.append('Finance')
        
        triage_badge = get_triage_badge(a.asset_id)
        provisioning_badge = get_provisioning_badge(a)
        
        rows_html += f'''
        <tr style="border-bottom: 1px solid #334155;">
            <td style="padding: 0.75rem; color: #06b6d4; font-weight: 500;">{a.name or 'Unknown'}</td>
            <td style="padding: 0.75rem; color: #94a3b8;">{a.vendor or '-'}</td>
            <td style="padding: 0.75rem; color: #94a3b8;">{a.asset_type.value if a.asset_type else '-'}</td>
            <td style="padding: 0.75rem; color: #94a3b8;">{a.environment.value if a.environment else '-'}</td>
            <td style="padding: 0.75rem;">{' '.join(status_badges)}</td>
            <td style="padding: 0.75rem;">{provisioning_badge or '<span style="color: #475569; font-size: 0.75rem;">-</span>'}</td>
            <td style="padding: 0.75rem; color: #64748b; font-size: 0.8rem;">{', '.join(lens_parts) or '-'}</td>
            <td style="padding: 0.75rem; color: #64748b; font-size: 0.75rem;">{a.admission_reason or '-'}</td>
            <td style="padding: 0.75rem;">{triage_badge or '<span style="color: #475569; font-size: 0.75rem;">-</span>'}</td>
        </tr>'''
    
    orphan_section = ""
    if orphan_rows_html:
        sort_icon = "&#8597;"
        orphan_section = f'''
            <div class="section-header">
                <div class="section-title">Triaged Findings (No Asset)</div>
                <div class="section-subtitle">{len(orphan_findings)} finding(s) triaged for vendors without a corresponding cataloged asset</div>
            </div>
            <table id="findingsTable">
                <thead>
                    <tr>
                        <th onclick="sortTable('findingsTable', 0)">Vendor <span class="sort-icon">{sort_icon}</span></th>
                        <th onclick="sortTable('findingsTable', 1)">Finding Type <span class="sort-icon">{sort_icon}</span></th>
                        <th>Description</th>
                        <th onclick="sortTable('findingsTable', 3)">Triage <span class="sort-icon">{sort_icon}</span></th>
                    </tr>
                </thead>
                <tbody>
                    {orphan_rows_html}
                </tbody>
            </table>
        '''
    
    triage_summary_section = f'''
        <div id="triageSummary" class="section-header" style="border-left-color: #06b6d4;">
            <div class="section-title" style="color: #06b6d4;">Triage Summary</div>
            <div class="section-subtitle">Overview of triage actions taken on assets in this run</div>
        </div>
        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 1rem;">
            <div class="stat">
                <div class="stat-value" style="color: #10b981;">{triage_stats['approved']}</div>
                <div class="stat-label">Approved for AAM</div>
            </div>
            <div class="stat">
                <div class="stat-value" style="color: #ef4444;">{triage_stats['banned']}</div>
                <div class="stat-label">Banned</div>
            </div>
            <div class="stat">
                <div class="stat-value" style="color: #9ca3af;">{triage_stats['deprovisioned']}</div>
                <div class="stat-label">Deprovisioned</div>
            </div>
            <div class="stat">
                <div class="stat-value" style="color: #3b82f6;">{triage_stats['assigned']}</div>
                <div class="stat-label">Assigned</div>
            </div>
        </div>
        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; margin-bottom: 2rem;">
            <div class="stat">
                <div class="stat-value" style="color: #8b5cf6;">{triage_stats['deferred']}</div>
                <div class="stat-label">Deferred</div>
            </div>
            <div class="stat">
                <div class="stat-value" style="color: #64748b;">{triage_stats['ignored']}</div>
                <div class="stat-label">Ignored</div>
            </div>
            <div class="stat">
                <div class="stat-value" style="color: #f59e0b;">{triage_stats['pending']}</div>
                <div class="stat-label">Pending Review</div>
            </div>
        </div>
    '''
    
    sort_icon = "&#8597;"
    html = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Asset Catalog - Run {run_id[:8]}</title>
        <link href="https://fonts.googleapis.com/css2?family=Quicksand:wght@400;500;600;700&display=swap" rel="stylesheet">
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{ 
                font-family: 'Quicksand', sans-serif; 
                background: #0f172a; 
                color: #e2e8f0; 
                padding: 2rem;
                min-height: 100vh;
            }}
            .container {{ max-width: 1400px; margin: 0 auto; }}
            .header {{ 
                display: flex; 
                justify-content: space-between; 
                align-items: center; 
                margin-bottom: 2rem;
                padding-bottom: 1rem;
                border-bottom: 1px solid #334155;
            }}
            .title {{ font-size: 1.5rem; font-weight: 700; color: #06b6d4; }}
            .subtitle {{ font-size: 0.9rem; color: #64748b; margin-top: 0.25rem; }}
            .stats {{ display: flex; gap: 1.5rem; }}
            .stat {{ 
                background: #1e293b; 
                padding: 0.75rem 1.25rem; 
                border-radius: 8px;
                text-align: center;
            }}
            .stat-value {{ font-size: 1.25rem; font-weight: 700; color: #06b6d4; }}
            .stat-label {{ font-size: 0.75rem; color: #64748b; }}
            .export-btn {{
                background: #334155;
                color: #e2e8f0;
                padding: 0.5rem 1rem;
                border-radius: 6px;
                text-decoration: none;
                font-size: 0.85rem;
                display: inline-flex;
                align-items: center;
                gap: 0.5rem;
            }}
            .export-btn:hover {{ background: #475569; }}
            table {{ 
                width: 100%; 
                border-collapse: collapse; 
                background: #1e293b; 
                border-radius: 8px;
                overflow: hidden;
            }}
            th {{ 
                background: #334155; 
                padding: 0.75rem; 
                text-align: left; 
                font-weight: 600;
                color: #94a3b8;
                font-size: 0.8rem;
                text-transform: uppercase;
                letter-spacing: 0.05em;
                cursor: pointer;
                user-select: none;
            }}
            th:hover {{ background: #3f5165; }}
            th .sort-icon {{ opacity: 0.5; margin-left: 0.25rem; }}
            th.sorted .sort-icon {{ opacity: 1; }}
            tr:hover {{ background: #263445; }}
            .section-header {{ 
                margin-top: 2rem; 
                margin-bottom: 1rem; 
                padding: 0.75rem 1rem;
                background: #1e293b;
                border-radius: 8px;
                border-left: 4px solid #f59e0b;
            }}
            .section-title {{ font-size: 1rem; font-weight: 600; color: #f59e0b; }}
            .section-subtitle {{ font-size: 0.8rem; color: #64748b; margin-top: 0.25rem; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div>
                    <div class="title">Asset Catalog</div>
                    <div class="subtitle">
                        Run: {run_id[:8]}... | 
                        Tenant: {run.tenant_id} | 
                        {run.completed_at.strftime('%Y-%m-%d %H:%M') if run.completed_at else 'In Progress'}
                    </div>
                </div>
                <div style="display: flex; align-items: center; gap: 1rem;">
                    <div class="stats">
                        <div class="stat">
                            <div class="stat-value">{len(assets)}</div>
                            <div class="stat-label">Total Assets</div>
                        </div>
                        <div class="stat">
                            <div class="stat-value" style="color: #f59e0b;">{shadow_count}</div>
                            <div class="stat-label">Shadow</div>
                        </div>
                        <div class="stat">
                            <div class="stat-value" style="color: #ef4444;">{zombie_count}</div>
                            <div class="stat-label">Zombie</div>
                        </div>
                        <div class="stat">
                            <div class="stat-value" style="color: #22c55e;">{governed_count}</div>
                            <div class="stat-label">Governed</div>
                        </div>
                    </div>
                    <a href="/api/catalog?run_id={run_id}" class="export-btn" target="_blank">
                        Export JSON ↗
                    </a>
                </div>
            </div>
            <table id="assetsTable">
                <thead>
                    <tr>
                        <th onclick="sortTable('assetsTable', 0)">Asset Name <span class="sort-icon">{sort_icon}</span></th>
                        <th onclick="sortTable('assetsTable', 1)">Vendor <span class="sort-icon">{sort_icon}</span></th>
                        <th onclick="sortTable('assetsTable', 2)">Type <span class="sort-icon">{sort_icon}</span></th>
                        <th onclick="sortTable('assetsTable', 3)">Environment <span class="sort-icon">{sort_icon}</span></th>
                        <th onclick="sortTable('assetsTable', 4)">Status <span class="sort-icon">{sort_icon}</span></th>
                        <th onclick="sortTable('assetsTable', 5)">Provisioning <span class="sort-icon">{sort_icon}</span></th>
                        <th onclick="sortTable('assetsTable', 6)">Data Sources <span class="sort-icon">{sort_icon}</span></th>
                        <th onclick="sortTable('assetsTable', 7)">Admission Reason <span class="sort-icon">{sort_icon}</span></th>
                        <th onclick="scrollToTriageSummary()" style="color: #06b6d4; cursor: pointer;" title="Click to view triage summary">Triage ↓</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html if rows_html else '<tr><td colspan="9" style="padding: 2rem; text-align: center; color: #64748b;">No assets in catalog</td></tr>'}
                </tbody>
            </table>
            
            {orphan_section}
            
            {triage_summary_section}
        </div>
        <script>
            function scrollToTriageSummary() {{
                const el = document.getElementById('triageSummary');
                if (el) {{
                    el.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
                }}
            }}
            let sortDirections = {{}};
            function sortTable(tableId, colIndex) {{
                const table = document.getElementById(tableId);
                const tbody = table.querySelector('tbody');
                const rows = Array.from(tbody.querySelectorAll('tr'));
                
                const dir = sortDirections[tableId + '_' + colIndex] === 'asc' ? 'desc' : 'asc';
                sortDirections[tableId + '_' + colIndex] = dir;
                
                rows.sort((a, b) => {{
                    const aText = a.cells[colIndex]?.textContent?.trim() || '';
                    const bText = b.cells[colIndex]?.textContent?.trim() || '';
                    const cmp = aText.localeCompare(bText);
                    return dir === 'asc' ? cmp : -cmp;
                }});
                
                rows.forEach(row => tbody.appendChild(row));
                
                table.querySelectorAll('th').forEach((th, i) => {{
                    th.classList.toggle('sorted', i === colIndex);
                }});
            }}
        </script>
    </body>
    </html>
    '''
    return HTMLResponse(content=html)


@router.post("/assets/{asset_id}/provisioning", response_model=ProvisioningActionResponse)
async def update_asset_provisioning(
    asset_id: str,
    request: ProvisioningActionRequest
):
    """
    Update an asset's provisioning status via state transition actions.
    
    Actions:
    - SANCTION: Approve shadow IT → ACTIVE (flows to DCL)
    - BAN: Reject asset → BLOCKED (permanently blocked)
    - DEPROVISION: Retire zombie → RETIRED (removed from active use)
    
    This is the "Sanction Button" that allows users to approve or reject
    quarantined assets, giving them control over what flows to the DCL.
    """
    action = request.action.upper()
    
    if action not in ACTION_TO_STATUS:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid action '{action}'. Valid actions: SANCTION, BAN, DEPROVISION, ACKNOWLEDGE, DISMISS_RISK"
        )
    
    db = await get_db_direct()
    
    asset = await db.get_asset_by_id(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail=f"Asset {asset_id} not found")
    
    previous_status = asset.provisioning_status
    new_status = ACTION_TO_STATUS[action]
    
    valid_transitions = {
        "SANCTION": [ProvisioningStatus.QUARANTINE, ProvisioningStatus.REVIEW, ProvisioningStatus.BLOCKED],
        "BAN": [ProvisioningStatus.QUARANTINE, ProvisioningStatus.REVIEW, ProvisioningStatus.ACTIVE],
        "DEPROVISION": [ProvisioningStatus.REVIEW, ProvisioningStatus.ACTIVE],
        "ACKNOWLEDGE": [ProvisioningStatus.ACTIVE, ProvisioningStatus.REVIEW],
        "DISMISS_RISK": [ProvisioningStatus.ACTIVE, ProvisioningStatus.REVIEW],
    }
    
    if previous_status not in valid_transitions[action]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot {action} an asset with status '{previous_status.value}'. Valid source statuses: {[s.value for s in valid_transitions[action]]}"
        )
    
    success = await db.update_asset_provisioning_status(
        asset_id=asset_id,
        new_status=new_status.value,
        reason=request.reason,
        actor=request.actor
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update asset status")
    
    action_to_triage_state = {
        "SANCTION": "approved",
        "BAN": "banned",
        "DEPROVISION": "deprovisioned",
        "ACKNOWLEDGE": "acknowledged",
        "DISMISS_RISK": "dismissed",
    }
    
    tenant_id = "unknown"
    if asset.tags and isinstance(asset.tags, dict):
        tenant_id = asset.tags.get("tenant_id", "unknown")
    
    await db.save_triage_action(
        tenant_id=tenant_id,
        run_id=asset.run_id,
        item_id=asset_id,
        item_type="asset",
        action=action.lower(),
        state=action_to_triage_state[action],
        owner=request.actor,
        defer_until=None,
        ignore_reason=request.reason
    )
    
    action_messages = {
        "SANCTION": f"Asset '{asset.name}' sanctioned - now eligible for AAM",
        "BAN": f"Asset '{asset.name}' banned - permanently blocked from AAM",
        "DEPROVISION": f"Asset '{asset.name}' deprovisioned - retired from active use",
        "ACKNOWLEDGE": f"Asset '{asset.name}' acknowledged - data governance gap noted, awaiting remediation",
        "DISMISS_RISK": f"Asset '{asset.name}' risk dismissed - acknowledged as acceptable",
    }
    
    return ProvisioningActionResponse(
        success=True,
        asset_id=asset_id,
        asset_name=asset.name,
        previous_status=previous_status.value,
        new_status=new_status.value,
        action=action,
        reason=request.reason,
        actor=request.actor,
        message=action_messages[action]
    )
