document.addEventListener('DOMContentLoaded', function() {
    const ingestForm = document.getElementById('ingestForm');
    if (ingestForm) {
        ingestForm.addEventListener('submit', handleIngest);
    }
});

async function handleIngest(e) {
    e.preventDefault();
    
    const btn = document.getElementById('ingestBtn');
    const status = document.getElementById('ingestStatus');
    const archetype = document.getElementById('archetype').value;
    const scale = document.getElementById('scale').value;
    
    btn.disabled = true;
    btn.textContent = 'Pulling...';
    status.innerHTML = '<div class="status-message loading">Connecting to Farm and ingesting assets...</div>';
    
    try {
        const response = await fetch('/api/farm/ingest', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ archetype, scale })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            status.innerHTML = `<div class="status-message success">
                Successfully ingested ${data.total_assets} assets from ${data.company_name || 'enterprise'}.
                Shadow IT: ${data.shadow_it_count}, Parked: ${data.parked_count}
            </div>`;
            setTimeout(() => location.reload(), 2000);
        } else {
            status.innerHTML = `<div class="status-message error">Error: ${data.detail || 'Ingestion failed'}</div>`;
        }
    } catch (err) {
        status.innerHTML = `<div class="status-message error">Error: ${err.message}</div>`;
    } finally {
        btn.disabled = false;
        btn.textContent = 'Pull from Farm';
    }
}

async function showAssets(type, value) {
    const container = document.getElementById('assetListContainer');
    let url;
    let displayValue = value;
    
    switch(type) {
        case 'lifecycle':
            url = `/api/assets/lifecycle/${value}`;
            break;
        case 'parked':
            url = `/api/assets/parked/${encodeURIComponent(value)}`;
            break;
        case 'finding':
            url = `/api/assets/finding/${value}`;
            break;
        case 'shadow':
            url = `/api/assets/shadow-it`;
            break;
        case 'inventory':
            url = `/api/assets/inventory/${value}`;
            displayValue = value.split('/').pop();
            break;
        case 'shadow_inventory':
            url = `/api/assets/shadow-it/${value}`;
            displayValue = 'Shadow IT - ' + value.split('/').pop();
            break;
        default:
            return;
    }
    
    try {
        const response = await fetch(url);
        const data = await response.json();
        
        if (data.assets.length === 0) {
            container.innerHTML = `<div class="empty-state"><h3>No Assets Found</h3></div>`;
            return;
        }
        
        let html = `
            <h3 class="section-title" style="margin-top: 24px;">${displayValue} (${data.count} assets)</h3>
            <div class="asset-list">
                <div class="asset-list-header">
                    <div>Name</div>
                    <div>Vendor</div>
                    <div>Kind</div>
                    <div>State</div>
                    <div>Owner</div>
                </div>
        `;
        
        for (const asset of data.assets) {
            const stateClass = asset.lifecycle_state === 'CATALOGED' ? 'cataloged' : 
                              asset.lifecycle_state === 'PARKED' ? 'parked' : 'discovered';
            html += `
                <div class="asset-row" onclick="showAssetDetail('${asset.id}')">
                    <div class="asset-name">${asset.name}</div>
                    <div>${asset.vendor || '-'}</div>
                    <div>${asset.asset_kind || '-'}</div>
                    <div>
                        <span class="badge badge-${stateClass}">${asset.lifecycle_state}</span>
                        ${asset.is_shadow_it ? '<span class="badge badge-shadow">Shadow</span>' : ''}
                    </div>
                    <div>${asset.owner || asset.owner_team || '-'}</div>
                </div>
            `;
        }
        
        html += '</div>';
        container.innerHTML = html;
        container.scrollIntoView({ behavior: 'smooth' });
        
    } catch (err) {
        container.innerHTML = `<div class="status-message error">Error loading assets: ${err.message}</div>`;
    }
}

async function showAssetDetail(assetId) {
    const modal = document.getElementById('assetModal');
    const title = document.getElementById('modalTitle');
    const body = document.getElementById('modalBody');
    
    try {
        const response = await fetch(`/api/assets/${assetId}`);
        const data = await response.json();
        const asset = data.asset;
        const findings = data.findings || [];
        
        title.textContent = asset.name;
        
        let metadata = {};
        try {
            metadata = typeof asset.metadata === 'string' ? JSON.parse(asset.metadata) : asset.metadata || {};
        } catch(e) {}
        
        let lensCoverage = {};
        try {
            lensCoverage = typeof asset.lens_coverage === 'string' ? JSON.parse(asset.lens_coverage) : asset.lens_coverage || {};
        } catch(e) {}
        
        body.innerHTML = `
            <div class="modal-tabs">
                <button class="modal-tab active" onclick="showTab(this, 'catalog')">Catalog View</button>
                <button class="modal-tab" onclick="showTab(this, 'findings')">Findings (${findings.length})</button>
            </div>
            
            <div id="catalogTab">
                <h4 style="margin-bottom: 16px; color: var(--cyan-400);">Core Identity</h4>
                <div class="detail-grid">
                    <div class="detail-item">
                        <div class="detail-label">Asset ID</div>
                        <div class="detail-value">${asset.id}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Name</div>
                        <div class="detail-value">${asset.name}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Vendor</div>
                        <div class="detail-value">${asset.vendor || '-'}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Environment</div>
                        <div class="detail-value">${asset.environment || '-'}</div>
                    </div>
                </div>
                
                <h4 style="margin: 24px 0 16px; color: var(--purple-400);">Classification</h4>
                <div class="detail-grid">
                    <div class="detail-item">
                        <div class="detail-label">Asset Kind</div>
                        <div class="detail-value">${asset.asset_kind || '-'}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Business Domain</div>
                        <div class="detail-value">${asset.business_domain || '-'}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Tech Domain</div>
                        <div class="detail-value">${asset.tech_domain || '-'}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">System Role</div>
                        <div class="detail-value">${asset.system_role || '-'}</div>
                    </div>
                </div>
                
                <h4 style="margin: 24px 0 16px; color: var(--green-400);">Governance</h4>
                <div class="detail-grid">
                    <div class="detail-item">
                        <div class="detail-label">Lifecycle State</div>
                        <div class="detail-value">${asset.lifecycle_state}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Parked Reason</div>
                        <div class="detail-value">${asset.parked_reason || 'N/A'}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Shadow IT</div>
                        <div class="detail-value">${asset.is_shadow_it ? 'Yes' : 'No'}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Data Conflicts</div>
                        <div class="detail-value">${asset.has_data_conflicts ? 'Yes' : 'No'}</div>
                    </div>
                </div>
                
                <h4 style="margin: 24px 0 16px; color: var(--blue-400);">Ownership</h4>
                <div class="detail-grid">
                    <div class="detail-item">
                        <div class="detail-label">Owner</div>
                        <div class="detail-value">${asset.owner || '-'}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Email</div>
                        <div class="detail-value">${asset.owner_email || '-'}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Team</div>
                        <div class="detail-value">${asset.owner_team || '-'}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Lens Coverage</div>
                        <div class="detail-value">${Object.entries(lensCoverage).filter(([k,v]) => v).map(([k]) => k).join(', ') || 'None'}</div>
                    </div>
                </div>
            </div>
            
            <div id="findingsTab" style="display: none;">
                ${findings.length > 0 ? `
                    <div class="findings-list">
                        ${findings.map(f => `
                            <div class="finding-item ${f.severity}">
                                <div class="finding-header">
                                    <span class="finding-type">${f.finding_type.replace('_', ' ').toUpperCase()}</span>
                                    <span class="badge badge-${f.severity === 'critical' ? 'parked' : f.severity === 'warn' ? 'shadow' : 'discovered'}">${f.severity}</span>
                                </div>
                                <div class="finding-description">${f.description}</div>
                                ${f.rule_id ? `<div style="margin-top: 8px; font-size: 12px; color: var(--slate-500);">Rule: ${f.rule_id}</div>` : ''}
                            </div>
                        `).join('')}
                    </div>
                ` : '<div class="empty-state"><h3>No Findings</h3><p>This asset has no open findings.</p></div>'}
            </div>
        `;
        
        modal.classList.add('active');
        
    } catch (err) {
        body.innerHTML = `<div class="status-message error">Error loading asset: ${err.message}</div>`;
        modal.classList.add('active');
    }
}

function showTab(btn, tabName) {
    document.querySelectorAll('.modal-tab').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
    
    document.getElementById('catalogTab').style.display = tabName === 'catalog' ? 'block' : 'none';
    document.getElementById('findingsTab').style.display = tabName === 'findings' ? 'block' : 'none';
}

function closeModal() {
    document.getElementById('assetModal').classList.remove('active');
}

document.getElementById('assetModal').addEventListener('click', function(e) {
    if (e.target === this) {
        closeModal();
    }
});

document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        closeModal();
    }
});
