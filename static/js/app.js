        let currentRunId = null, catalogData = null, loadedSnapshots = [];
        let drillStack = [];
        let normalizedData = { assets: [], security_risks: [], governance_hygiene: [], artifacts: [], observations: [], validated: [], ambiguous: [], rejections: [], shadow: [], zombie: [] };
        let detailPagination = { page: 0, pageSize: 25, items: [], rootType: null, itemIndex: 0 };
        
        let decisionTracesCache = null;
        let decisionTraceFilter = 'all';
        let decisionMismatches = {};
        
        let farmWakingToast = null;
        let farmWakeCheckInterval = null;
        
        window.farmLiveMode = true;

        // Check Farm status and update light indicator (binary: green=online, grey=offline)
        // farmLiveMode is true if farm OR cache is available (allows tenant loading)
        async function checkFarmStatus() {
            const light = document.getElementById('farmStatusBadge');
            if (!light) return;

            try {
                const res = await fetch('/api/farm/status');
                const data = await res.json();

                if (data.farm_available) {
                    light.className = 'farm-status-light online';
                    light.title = 'Farm Online';
                    window.farmLiveMode = true;
                } else {
                    light.className = 'farm-status-light';
                    light.title = 'Farm Offline';
                    window.farmLiveMode = data.cache_available || false;
                }
            } catch (e) {
                light.className = 'farm-status-light';
                light.title = 'Farm Offline';
                window.farmLiveMode = false;
            }
        }

        function loadObservationPlaneCounts(snapshotData) {
            if (!snapshotData || !snapshotData.planes) {
                document.getElementById('planeCountDiscovery').textContent = '-';
                document.getElementById('planeCountIdp').textContent = '-';
                document.getElementById('planeCountCmdb').textContent = '-';
                document.getElementById('planeCountCloud').textContent = '-';
                document.getElementById('planeCountEndpoint').textContent = '-';
                document.getElementById('planeCountNetwork').textContent = '-';
                document.getElementById('planeCountFinance').textContent = '-';
                if (typeof updateObsBars === 'function') updateObsBars();
                return;
            }
            
            const planes = snapshotData.planes;
            
            const discoveryCount = planes.discovery?.observations?.length || 0;
            const idpCount = planes.idp?.objects?.length || 0;
            const cmdbCount = planes.cmdb?.cis?.length || 0;
            const cloudCount = planes.cloud?.resources?.length || 0;
            const endpointCount = (planes.endpoint?.devices?.length || 0) + (planes.endpoint?.installed_apps?.length || 0);
            const networkCount = (planes.network?.dns?.length || 0) + (planes.network?.proxy?.length || 0) + (planes.network?.certs?.length || 0);
            const financeCount = (planes.finance?.vendors?.length || 0) + (planes.finance?.contracts?.length || 0);
            
            document.getElementById('planeCountDiscovery').textContent = discoveryCount;
            document.getElementById('planeCountIdp').textContent = idpCount;
            document.getElementById('planeCountCmdb').textContent = cmdbCount;
            document.getElementById('planeCountCloud').textContent = cloudCount;
            document.getElementById('planeCountEndpoint').textContent = endpointCount;
            document.getElementById('planeCountNetwork').textContent = networkCount;
            document.getElementById('planeCountFinance').textContent = financeCount;
            if (typeof updateObsBars === 'function') updateObsBars();
        }
        
        function toggleUserGuide(guideId) {
            const guide = document.getElementById(guideId);
            if (guide) {
                guide.classList.toggle('expanded');
            }
        }
        
        function showToast(message, type = 'error', persistent = false) {
            const existing = document.getElementById('app-toast');
            if (existing) existing.remove();
            
            const toast = document.createElement('div');
            toast.id = 'app-toast';
            toast.className = `app-toast ${type}`;
            
            if (persistent) {
                toast.innerHTML = `<span class="toast-spinner"></span><span>${message}</span>`;
            } else {
                toast.innerHTML = `<span>${message}</span><button onclick="this.parentElement.remove()">&times;</button>`;
            }
            document.body.appendChild(toast);
            
            setTimeout(() => toast.classList.add('visible'), 10);
            
            if (!persistent) {
                setTimeout(() => { toast.classList.remove('visible'); setTimeout(() => toast.remove(), 300); }, 4000);
            }
            
            return toast;
        }
        
        function dismissToast() {
            const toast = document.getElementById('app-toast');
            if (toast) {
                toast.classList.remove('visible');
                setTimeout(() => toast.remove(), 300);
            }
        }
        
        function showFarmWakingToast() {
            if (farmWakingToast) return; // Already showing
            
            farmWakingToast = showToast('Waking up Farm...', 'info', true);
            
            // Poll Farm until it responds
            farmWakeCheckInterval = setInterval(async () => {
                try {
                    const r = await fetch('/api/farm/tenants');
                    const data = await r.json();
                    if (data.ok !== false && !data.error) {
                        // Farm is awake!
                        clearInterval(farmWakeCheckInterval);
                        farmWakeCheckInterval = null;
                        dismissToast();
                        farmWakingToast = null;
                        loadTenants(); // Reload tenants
                    }
                } catch (e) {
                    // Still waking, keep polling
                }
            }, 3000);
        }
        
        function initMainTabs() {
            document.querySelectorAll('.header-nav-tab').forEach(tab => {
                tab.addEventListener('click', () => {
                    const targetTab = tab.dataset.tab;
                    document.querySelectorAll('.header-nav-tab').forEach(t => t.classList.remove('active'));
                    document.querySelectorAll('.main-tab-content').forEach(c => c.classList.remove('active'));
                    tab.classList.add('active');
                    document.getElementById(targetTab + 'TabContent').classList.add('active');
                    if (targetTab === 'triage') loadTriageRuns();
                    if (targetTab === 'handoff') loadHandoffRuns();
                });
            });
        }
        
        function initTriageTab() {
            const triageSelect = document.getElementById('triageRunSelect');
            triageSelect.addEventListener('change', loadTriageData);
            
            document.querySelectorAll('.triage-collapsible').forEach(header => {
                header.addEventListener('click', () => {
                    const targetId = header.dataset.target;
                    const content = document.getElementById(targetId);
                    if (content) {
                        header.classList.toggle('collapsed');
                        content.classList.toggle('collapsed');
                    }
                });
            });
            
            document.getElementById('openConnectionPolicy')?.addEventListener('click', (e) => {
                e.preventDefault();
                openConnectionPolicyModal();
            });
            
            document.getElementById('triageSections').addEventListener('click', async (e) => {
                if (e.target.closest('.triage-collapsible')) return;
                const btn = e.target.closest('[data-action]');
                if (!btn) return;
                
                const action = btn.dataset.action;
                const itemId = btn.dataset.itemId;
                const itemType = btn.dataset.itemType;
                const runId = document.getElementById('triageRunSelect').value;
                
                if (!runId || !itemId) return;
                
                if (action === 'revert') {
                    await revertTriageAction(runId, itemId, itemType);
                } else if (action === 'defer') {
                    showDeferModal(runId, itemId, itemType);
                } else if (action === 'ignore') {
                    showIgnoreModal(runId, itemId, itemType);
                } else if (action === 'assign') {
                    showAssignModal(runId, itemId, itemType);
                } else if (action === 'resolve_blocking') {
                    await submitProvisioningAction(itemId, 'RESOLVE');
                } else if (action === 'override_blocking') {
                    await submitTriageAction(runId, itemId, itemType, 'override', { override_reason: 'Manual override - warn only' });
                } else if (['sanction', 'ban', 'deprovision', 'dismiss_risk', 'resolve'].includes(action)) {
                    await submitProvisioningAction(itemId, action.toUpperCase());
                } else {
                    await submitTriageAction(runId, itemId, itemType, action);
                }
            });
        }
        
        async function revertTriageAction(runId, itemId, itemType) {
            try {
                const response = await fetch(`/api/triage/action/${runId}/${itemId}`, {
                    method: 'DELETE'
                });
                
                if (!response.ok) {
                    console.error('Revert action failed:', response.status, response.statusText);
                    return;
                }
                
                delete triageActionsMap[itemId];
                
                updateTriageItemInSections(itemId, itemType, {
                    triageState: null,
                    triageAction: null,
                    triageOwner: null,
                    triageDeferUntil: null,
                    triageIgnoreReason: null
                });
            } catch (err) {
                console.error('Revert action failed:', err);
            }
        }
        
        async function submitTriageAction(runId, itemId, itemType, action, extra = {}) {
            try {
                const response = await fetch('/api/triage/action', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ run_id: runId, item_id: itemId, item_type: itemType, action, ...extra })
                });
                
                if (!response.ok) {
                    console.error('Triage action failed:', response.status, response.statusText);
                    return;
                }
                
                const contentType = response.headers.get('content-type');
                if (!contentType || !contentType.includes('application/json')) {
                    console.warn('Triage action returned non-JSON response');
                    return;
                }
                
                let result;
                try {
                    result = await response.json();
                } catch (parseErr) {
                    console.error('Failed to parse triage response:', parseErr);
                    return;
                }
                
                const state = result.state || action;
                triageActionsMap[itemId] = {
                    item_id: itemId,
                    item_type: itemType,
                    action: action,
                    state: state,
                    owner: extra.owner || result.owner || null,
                    defer_until: result.defer_until || null,
                    ignore_reason: extra.ignore_reason || null
                };
                
                updateTriageItemInSections(itemId, itemType, {
                    triageState: state,
                    triageAction: action,
                    triageOwner: extra.owner || result.owner || null,
                    triageDeferUntil: result.defer_until || null,
                    triageIgnoreReason: extra.ignore_reason || null
                });
            } catch (err) {
                console.error('Triage action failed:', err);
            }
        }
        
        async function submitProvisioningAction(assetId, action) {
            try {
                let itemType = 'asset';
                for (const section of ['firewall', 'risk', 'hygiene']) {
                    const items = triageSectionData[section];
                    const idx = items.findIndex(item => (item.asset_id || item.id) === assetId);
                    if (idx !== -1) {
                        itemType = items[idx].itemType;
                        break;
                    }
                }
                
                const response = await fetch(`/api/catalog/assets/${assetId}/provisioning`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action: action, item_type: itemType })
                });
                
                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({}));
                    console.error('Provisioning action failed:', response.status, errorData.detail || response.statusText);
                    showToast(`Action failed: ${errorData.detail || 'Unknown error'}`, 'error');
                    return;
                }
                
                const result = await response.json();
                console.log('Provisioning action result:', result);
                
                const stateMap = { 'SANCTION': 'approved', 'BAN': 'banned', 'DEPROVISION': 'deprovisioned', 'DISMISS_RISK': 'dismissed', 'ACKNOWLEDGE': 'acknowledged', 'RESOLVE': 'approved' };
                const newState = stateMap[action] || action.toLowerCase();

                triageActionsMap[assetId] = {
                    item_id: assetId,
                    item_type: itemType,
                    action: action.toLowerCase(),
                    state: newState
                };
                
                updateTriageItemInSections(assetId, itemType, {
                    triageState: newState,
                    triageAction: action.toLowerCase()
                });
                
            } catch (err) {
                console.error('Provisioning action failed:', err);
                showToast('Action failed: ' + err.message, 'error');
            }
        }
        
        function removeItemFromTriage(assetId) {
            const sectionIds = {
                firewall: { countEl: 'triageFirewallCount', contentEl: 'triageFirewallContent' },
                risk: { countEl: 'triageRiskCount', contentEl: 'triageRiskContent' },
                hygiene: { countEl: 'triageHygieneCount', contentEl: 'triageHygieneContent' }
            };
            
            for (const [section, els] of Object.entries(sectionIds)) {
                const items = triageSectionData[section];
                const idx = items.findIndex(item => 
                    (item.asset_id || item.id) === assetId
                );
                if (idx !== -1) {
                    items.splice(idx, 1);
                    document.getElementById(els.countEl).textContent = items.length;
                    const container = document.getElementById(els.contentEl);
                    if (container) {
                        renderTriageSection(container, sortTriageItems(items, triageSortState[section], section), section);
                    }
                    break;
                }
            }
        }
        
        function updateTriageItemInSections(itemId, itemType, updates) {
            const sectionIds = {
                firewall: { contentEl: 'triageFirewallContent' },
                risk: { contentEl: 'triageRiskContent' },
                hygiene: { contentEl: 'triageHygieneContent' }
            };
            
            for (const [section, els] of Object.entries(sectionIds)) {
                const items = triageSectionData[section];
                const idx = items.findIndex(item => 
                    getTriageItemId(item) === itemId && getTriageItemType(item) === itemType
                );
                if (idx !== -1) {
                    Object.assign(items[idx], updates);
                    const container = document.getElementById(els.contentEl);
                    if (container) {
                        renderTriageSection(container, sortTriageItems(items, triageSortState[section], section), section);
                    }
                    break;
                }
            }
        }
        
        let triageModalContext = { runId: null, itemId: null, itemType: null };
        
        function showDeferModal(runId, itemId, itemType) {
            triageModalContext = { runId, itemId, itemType };
            document.querySelectorAll('#deferModal .triage-option-card').forEach(c => c.classList.remove('selected'));
            document.querySelector('#deferModal .triage-option-card[data-days="30"]').classList.add('selected');
            document.getElementById('deferModal').classList.add('active');
        }
        
        function showIgnoreModal(runId, itemId, itemType) {
            triageModalContext = { runId, itemId, itemType };
            document.querySelectorAll('#ignoreModal .triage-option-card').forEach(c => c.classList.remove('selected'));
            document.querySelector('#ignoreModal .triage-option-card').classList.add('selected');
            document.getElementById('ignoreModal').classList.add('active');
        }
        
        function showAssignModal(runId, itemId, itemType) {
            triageModalContext = { runId, itemId, itemType };
            document.getElementById('assignDepartment').value = '';
            document.getElementById('assignOwner').value = '';
            updateOwnerOptions();
            document.getElementById('assignModal').classList.add('active');
        }
        
        function closeTriageModal(modalId) {
            document.getElementById(modalId).classList.remove('active');
        }
        
        let connectionPolicy = {
            identity_gap: 'red',
            finance_gap: 'red',
            data_conflict: 'red',
            zombie_asset: 'yellow',
            duplication_risk: 'yellow',
            cmdb_gap: 'green',
            governance_gap: 'green'
        };
        
        async function loadConnectionPolicy() {
            try {
                const res = await fetch('/api/v1/policy/master');
                if (res.ok) {
                    const policy = await res.json();
                    if (policy.connection_policy) {
                        const cp = policy.connection_policy;
                        Object.keys(connectionPolicy).forEach(key => {
                            if (cp[key] && cp[key].value) {
                                connectionPolicy[key] = cp[key].value;
                            }
                        });
                    }
                }
            } catch (err) {
                console.warn('Failed to load connection policy:', err);
            }
        }
        
        loadConnectionPolicy();
        
        function openConnectionPolicyModal() {
            const findingTypes = ['identity_gap', 'finance_gap', 'data_conflict', 'zombie_asset', 'duplication_risk', 'cmdb_gap', 'governance_gap'];
            findingTypes.forEach(type => {
                const select = document.getElementById(`policy_${type}`);
                if (select) select.value = connectionPolicy[type] || 'green';
            });
            document.getElementById('connectionPolicyModal').classList.add('active');
        }
        
        async function saveConnectionPolicy() {
            const findingTypes = ['identity_gap', 'finance_gap', 'data_conflict', 'zombie_asset', 'duplication_risk', 'cmdb_gap', 'governance_gap'];
            const updates = {};
            
            findingTypes.forEach(type => {
                const select = document.getElementById(`policy_${type}`);
                if (select) {
                    connectionPolicy[type] = select.value;
                    updates[`connection_policy.${type}.value`] = select.value;
                }
            });
            
            try {
                await fetch('/api/v1/policy/master', {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(updates)
                });
            } catch (err) {
                console.warn('Policy save failed:', err);
            }
            
            closeTriageModal('connectionPolicyModal');
            
            const runId = document.getElementById('triageRunSelect').value;
            if (runId) loadTriageData();
        }
        
        function updateOwnerOptions() {
            const dept = document.getElementById('assignDepartment').value;
            const ownerSelect = document.getElementById('assignOwner');
            const owners = {
                '': [],
                'engineering': ['Alex Chen', 'Jordan Smith', 'Taylor Kim', 'Morgan Lee', 'Casey Wright'],
                'security': ['Sam Rodriguez', 'Riley Johnson', 'Jamie Park', 'Drew Martinez', 'Quinn Anderson'],
                'it_operations': ['Pat Thompson', 'Blake Wilson', 'Avery Davis', 'Cameron Brown', 'Skyler White'],
                'finance': ['Dana Miller', 'Jesse Garcia', 'Robin Taylor', 'Reese Jackson', 'Charlie Moore'],
                'compliance': ['Morgan Clark', 'Jordan Lewis', 'Alex Walker', 'Taylor Hall', 'Casey Young']
            };
            const deptOwners = owners[dept] || [];
            ownerSelect.innerHTML = '<option value="">Select an owner...</option>' + 
                deptOwners.map(o => `<option value="${o}">${o}</option>`).join('');
        }
        
        function submitDeferAction() {
            const selected = document.querySelector('#deferModal .triage-option-card.selected');
            if (selected) {
                const days = parseInt(selected.dataset.days);
                submitTriageAction(triageModalContext.runId, triageModalContext.itemId, triageModalContext.itemType, 'defer', { defer_days: days });
                closeTriageModal('deferModal');
            }
        }
        
        function submitIgnoreAction() {
            const selected = document.querySelector('#ignoreModal .triage-option-card.selected');
            if (selected) {
                const reason = selected.dataset.reason;
                submitTriageAction(triageModalContext.runId, triageModalContext.itemId, triageModalContext.itemType, 'ignore', { ignore_reason: reason });
                closeTriageModal('ignoreModal');
            }
        }
        
        function submitAssignAction() {
            const dept = document.getElementById('assignDepartment').value;
            const owner = document.getElementById('assignOwner').value;
            if (owner) {
                const ownerStr = `${owner} (${dept.replace('_', ' ')})`;
                submitTriageAction(triageModalContext.runId, triageModalContext.itemId, triageModalContext.itemType, 'assign', { owner: ownerStr });
                closeTriageModal('assignModal');
            }
        }
        
        window.submitDeferAction = submitDeferAction;
        window.submitIgnoreAction = submitIgnoreAction;
        window.submitAssignAction = submitAssignAction;
        window.closeTriageModal = closeTriageModal;
        window.updateOwnerOptions = updateOwnerOptions;
        
        async function loadTriageRuns() {
            const select = document.getElementById('triageRunSelect');
            try {
                const response = await fetch('/api/runs');
                const runs = await response.json();
                select.innerHTML = '<option value="">Select a run...</option>';
                const completedRuns = runs.filter(r => r.status === 'completed_with_results' || r.status === 'COMPLETED_WITH_RESULTS');
                completedRuns.sort((a, b) => new Date(b.started_at || b.created_at) - new Date(a.started_at || a.created_at));
                completedRuns.forEach((run, idx) => {
                    const opt = document.createElement('option');
                    opt.value = run.run_id;
                    const tenant = run.tenant_id || run.tenant_name || 'Unknown';
                    const dateStr = run.started_at || run.created_at;
                    const date = dateStr ? new Date(dateStr).toLocaleDateString() : '';
                    const latest = idx === 0 ? ' (Latest)' : '';
                    opt.textContent = `${tenant} - ${date}${latest}`;
                    select.appendChild(opt);
                });
                if (currentRunId && completedRuns.some(r => r.run_id === currentRunId)) {
                    select.value = currentRunId;
                    loadTriageData();
                } else if (completedRuns.length > 0) {
                    select.value = completedRuns[0].run_id;
                    loadTriageData();
                }
            } catch (err) {
                console.error('Failed to load triage runs:', err);
            }
        }
        
        let triageSectionData = { firewall: [], risk: [], hygiene: [] };
        let triageSortState = { firewall: 'name', risk: 'name', hygiene: 'name' };
        let triageActionsMap = {};
        
        async function loadTriageData() {
            const runId = document.getElementById('triageRunSelect').value;
            if (!runId) return;
            
            const firewallContent = document.getElementById('triageFirewallContent');
            const riskContent = document.getElementById('triageRiskContent');
            const hygieneContent = document.getElementById('triageHygieneContent');
            
            firewallContent.innerHTML = '<div class="triage-empty">Loading...</div>';
            riskContent.innerHTML = '<div class="triage-empty">Loading...</div>';
            hygieneContent.innerHTML = '<div class="triage-empty">Loading...</div>';
            
            try {
                const [findingsRes, derivedRes, actionsRes, catalogRes] = await Promise.all([
                    fetch(`/api/findings?run_id=${runId}`),
                    fetch(`/api/runs/${runId}/derived`),
                    fetch(`/api/triage/actions/${runId}`),
                    fetch(`/api/catalog?run_id=${runId}`)
                ]);
                
                const findingsData = await findingsRes.json();
                const derivedData = await derivedRes.json();
                const catalogAssets = catalogRes.ok ? await catalogRes.json() : [];
                
                triageActionsMap = {};
                if (actionsRes.ok) {
                    const actionsData = await actionsRes.json();
                    const actions = actionsData.actions || actionsData || [];
                    actions.forEach(a => {
                        // With UNIQUE(run_id, item_id) constraint, key by item_id only
                        triageActionsMap[a.item_id] = a;
                    });
                }
                
                const findings = findingsData.findings || [];
                const shadowAssets = derivedData.shadow_assets || [];
                const zombieAssets = derivedData.zombie_assets || [];
                const assets = catalogAssets.assets || catalogAssets || [];
                
                const assetStatusMap = {};
                const assetDataMap = {};
                assets.forEach(a => {
                    const id = a.asset_id || a.id;
                    assetStatusMap[id] = (a.provisioning_status || '').toUpperCase();
                    assetDataMap[id] = a;
                });
                
                const assetFindingsMap = {};
                findings.forEach(f => {
                    const assetId = f.asset_id || f.id;
                    if (!assetFindingsMap[assetId]) {
                        assetFindingsMap[assetId] = [];
                    }
                    assetFindingsMap[assetId].push(f);
                });
                
                const firewallItems = [];
                const riskItems = [];
                const hygieneItems = [];
                const processedAssetIds = new Set();
                
                const redTypes = Object.entries(connectionPolicy).filter(([k, v]) => v === 'red').map(([k]) => k);
                const yellowTypes = Object.entries(connectionPolicy).filter(([k, v]) => v === 'yellow').map(([k]) => k);
                const greenTypes = Object.entries(connectionPolicy).filter(([k, v]) => v === 'green').map(([k]) => k);
                
                const hasRedFinding = (findings) => findings.some(f => redTypes.includes(f.finding_type));
                const hasYellowFinding = (findings) => findings.some(f => yellowTypes.includes(f.finding_type));
                const hasOnlyGreenFindings = (findings) => findings.length > 0 && findings.every(f => greenTypes.includes(f.finding_type));
                
                shadowAssets.forEach(a => {
                    const assetId = a.asset_id || a.id;
                    const savedAction = triageActionsMap[assetId];
                    const provStatus = assetStatusMap[assetId] || (a.provisioning_status || '').toUpperCase();
                    const assetFindings = assetFindingsMap[assetId] || [];
                    
                    const item = { 
                        ...a, 
                        itemType: 'shadow',
                        sectionType: 'firewall',
                        provisioning_status: provStatus,
                        findings: assetFindings,
                        triageState: savedAction?.state || 'pending',
                        triageAction: savedAction?.action || null,
                        triageOwner: savedAction?.owner || null,
                        triageDeferUntil: savedAction?.defer_until || null,
                        triageIgnoreReason: savedAction?.ignore_reason || null
                    };
                    
                    firewallItems.push(item);
                    processedAssetIds.add(assetId);
                });
                
                assets.forEach(a => {
                    const assetId = a.asset_id || a.id;
                    if (processedAssetIds.has(assetId)) return;
                    
                    const provStatus = (a.provisioning_status || '').toUpperCase();
                    const assetFindings = assetFindingsMap[assetId] || [];
                    
                    if (provStatus === 'QUARANTINE' || provStatus === 'BLOCKED') {
                        const savedAction = triageActionsMap[assetId];
                        const item = { 
                            ...a, 
                            itemType: 'blocked',
                            sectionType: 'firewall',
                            provisioning_status: provStatus,
                            findings: assetFindings,
                            triageState: savedAction?.state || 'pending',
                            triageAction: savedAction?.action || null,
                            triageOwner: savedAction?.owner || null,
                            triageDeferUntil: savedAction?.defer_until || null,
                            triageIgnoreReason: savedAction?.ignore_reason || null
                        };
                        firewallItems.push(item);
                        processedAssetIds.add(assetId);
                    }
                });
                
                assets.forEach(a => {
                    const assetId = a.asset_id || a.id;
                    if (processedAssetIds.has(assetId)) return;
                    
                    const provStatus = (a.provisioning_status || '').toUpperCase();
                    const assetFindings = assetFindingsMap[assetId] || [];
                    
                    if (hasRedFinding(assetFindings)) {
                        const savedAction = triageActionsMap[assetId];
                        const item = { 
                            ...a, 
                            itemType: 'blocking',
                            sectionType: 'firewall',
                            provisioning_status: provStatus,
                            findings: assetFindings,
                            triageState: savedAction?.state || 'pending',
                            triageAction: savedAction?.action || null,
                            triageOwner: savedAction?.owner || null,
                            triageDeferUntil: savedAction?.defer_until || null,
                            triageIgnoreReason: savedAction?.ignore_reason || null
                        };
                        firewallItems.push(item);
                        processedAssetIds.add(assetId);
                    }
                });
                
                zombieAssets.forEach(a => {
                    const assetId = a.asset_id || a.id;
                    if (processedAssetIds.has(assetId)) return;

                    const savedAction = triageActionsMap[assetId];
                    const provStatus = assetStatusMap[assetId] || (a.provisioning_status || '').toUpperCase();
                    const assetFindings = assetFindingsMap[assetId] || [];
                    
                    const item = { 
                        ...a, 
                        itemType: 'zombie',
                        sectionType: 'risk',
                        provisioning_status: provStatus,
                        findings: assetFindings,
                        triageState: savedAction?.state || 'pending',
                        triageAction: savedAction?.action || null,
                        triageOwner: savedAction?.owner || null,
                        triageDeferUntil: savedAction?.defer_until || null,
                        triageIgnoreReason: savedAction?.ignore_reason || null
                    };
                    
                    riskItems.push(item);
                    processedAssetIds.add(assetId);
                });
                
                assets.forEach(a => {
                    const assetId = a.asset_id || a.id;
                    if (processedAssetIds.has(assetId)) return;
                    
                    const provStatus = (a.provisioning_status || '').toUpperCase();
                    const assetFindings = assetFindingsMap[assetId] || [];
                    
                    if (hasYellowFinding(assetFindings) && !hasRedFinding(assetFindings)) {
                        const savedAction = triageActionsMap[assetId];
                        const item = { 
                            ...a,
                            itemType: 'judgment',
                            sectionType: 'risk',
                            provisioning_status: provStatus,
                            findings: assetFindings,
                            triageState: savedAction?.state || 'pending',
                            triageAction: savedAction?.action || null,
                            triageOwner: savedAction?.owner || null,
                            triageDeferUntil: savedAction?.defer_until || null,
                            triageIgnoreReason: savedAction?.ignore_reason || null
                        };
                        riskItems.push(item);
                        processedAssetIds.add(assetId);
                    }
                });
                
                assets.forEach(a => {
                    const assetId = a.asset_id || a.id;
                    if (processedAssetIds.has(assetId)) return;
                    
                    const provStatus = (a.provisioning_status || '').toUpperCase();
                    const assetFindings = assetFindingsMap[assetId] || [];
                    
                    if (provStatus === 'ACTIVE' && hasOnlyGreenFindings(assetFindings)) {
                        const savedAction = triageActionsMap[assetId];
                        const item = { 
                            ...a,
                            itemType: 'hygiene',
                            sectionType: 'hygiene',
                            findings: assetFindings,
                            triageState: savedAction?.state || 'pending',
                            triageAction: savedAction?.action || null,
                            triageOwner: savedAction?.owner || null,
                            triageDeferUntil: savedAction?.defer_until || null,
                            triageIgnoreReason: savedAction?.ignore_reason || null
                        };
                        hygieneItems.push(item);
                        processedAssetIds.add(assetId);
                    }
                });
                
                triageSectionData = { firewall: firewallItems, risk: riskItems, hygiene: hygieneItems };
                
                document.getElementById('triageFirewallCount').textContent = firewallItems.length;
                document.getElementById('triageRiskCount').textContent = riskItems.length;
                document.getElementById('triageHygieneCount').textContent = hygieneItems.length;
                
                renderTriageSection(firewallContent, sortTriageItems(firewallItems, triageSortState.firewall, 'firewall'), 'firewall');
                renderTriageSection(riskContent, sortTriageItems(riskItems, triageSortState.risk, 'risk'), 'risk');
                renderTriageSection(hygieneContent, sortTriageItems(hygieneItems, triageSortState.hygiene, 'hygiene'), 'hygiene');
                
            } catch (err) {
                console.error('Failed to load triage data:', err);
                firewallContent.innerHTML = '<div class="triage-empty">Failed to load data</div>';
                riskContent.innerHTML = '<div class="triage-empty">Failed to load data</div>';
                hygieneContent.innerHTML = '<div class="triage-empty">Failed to load data</div>';
            }
        }
        
        function getTriageItemId(item) {
            return item.finding_id || item.asset_id || item.id || '';
        }
        
        function getTriageItemType(item) {
            return item.itemType || (item.finding_id ? 'finding' : 'shadow');
        }
        
        function getTriageKey(item) {
            return `${getTriageItemType(item)}:${getTriageItemId(item)}`;
        }
        
        function getItemName(item) {
            if (item.itemType === 'finding') {
                return item.asset_name || item.finding_type?.replace(/_/g, ' ') || '';
            }
            return item.name || item.asset_key || '';
        }
        
        function getItemType(item) {
            if (item.itemType === 'finding') return item.finding_type || '';
            return item.itemType || '';
        }
        
        function getItemCategory(item) {
            if (item.itemType === 'finding') return item.category || '';
            return item.asset_type || '';
        }
        
        function sortTriageItems(items, sortBy, sectionType = null) {
            const sorted = [...items];
            sorted.sort((a, b) => {
                if (sectionType === 'firewall') {
                    const aFinance = a.hasFinanceGap ? 0 : 1;
                    const bFinance = b.hasFinanceGap ? 0 : 1;
                    if (aFinance !== bFinance) return aFinance - bFinance;
                }
                
                let aVal = '', bVal = '';
                if (sortBy === 'name') {
                    aVal = getItemName(a);
                    bVal = getItemName(b);
                } else if (sortBy === 'type') {
                    aVal = getItemType(a);
                    bVal = getItemType(b);
                } else if (sortBy === 'category') {
                    aVal = getItemCategory(a);
                    bVal = getItemCategory(b);
                }
                return aVal.localeCompare(bVal);
            });
            return sorted;
        }
        
        
        function getCategoryLabel(category) {
            const labels = {
                'identity_access': 'Identity & Access',
                'shadow_it': 'Shadow IT',
                'data_integrity': 'Data Integrity',
                'governance': 'Governance',
                'visibility_gap': 'Governance',
                'governance_hygiene': 'Governance'
            };
            return labels[category] || category || '';
        }
        
        function generateTriageHeadline(item, itemType) {
            const name = item.name || item.asset_key || item.asset_name || 'Unknown asset';
            const agg = item.aggregated_evidence || {};
            const userCount = agg.user_count || item.user_count || null;
            const monthlySpend = agg.monthly_spend || item.monthly_spend || null;
            
            let headline = '', cause = '', consequence = '';
            const findings = item.findings || [];
            
            if (itemType === 'shadow' || itemType === 'blocking' || itemType === 'blocked') {
                const hasIdentity = findings.some(f => f.finding_type === 'identity_gap') || itemType === 'shadow';
                const hasFinance = findings.some(f => f.finding_type === 'finance_gap');
                const hasConflict = findings.some(f => f.finding_type === 'data_conflict');
                
                if (itemType === 'blocked') {
                    headline = `${name} cannot be connected until policy block is resolved`;
                    cause = 'Previously rejected or banned from catalog';
                    consequence = 'Requires manual approval to unblock';
                } else if (hasConflict) {
                    headline = `${name} cannot be connected until ownership conflict is resolved`;
                    cause = 'Sources disagree on identity or ownership';
                    consequence = 'Resolve data conflict before connecting';
                } else if (hasFinance && !hasIdentity) {
                    headline = `${name} cannot be connected until cost ownership is resolved`;
                    cause = 'Active charges without accountable owner';
                    consequence = 'Assign cost owner before connecting';
                } else if (hasIdentity) {
                    headline = `${name} cannot be connected until SSO is configured`;
                    cause = hasFinance ? `Active spend ($${monthlySpend?.toLocaleString() || '?'}/mo) without identity governance` : 'No identity provider integration';
                    consequence = 'Configure SSO to enable lifecycle control';
                } else {
                    headline = `${name} cannot be connected until identity context is resolved`;
                    cause = 'Missing required governance prerequisite';
                    consequence = 'Establish identity context before connecting';
                }
            } else if (itemType === 'zombie' || itemType === 'toxic' || itemType === 'judgment') {
                headline = `${name} has unresolved ambiguity that requires review before connecting`;
                if (itemType === 'zombie') {
                    cause = 'No logins or usage detected in 90+ days';
                    consequence = monthlySpend ? `Review: $${monthlySpend.toLocaleString()}/mo may be recoverable` : 'Review stale access credentials';
                } else if (itemType === 'judgment') {
                    const hasDupe = findings.some(f => f.finding_type === 'duplication_risk');
                    if (hasDupe) {
                        cause = 'Potential overlap with existing assets';
                        consequence = 'Confirm before connecting to avoid duplication';
                    } else {
                        cause = 'Classification requires human judgment';
                        consequence = 'Review context before proceeding';
                    }
                } else {
                    cause = 'Ambiguous governance data detected';
                    consequence = 'Clarify before connecting';
                }
            } else if (itemType === 'hygiene') {
                const hasCmdbGap = findings.some(f => f.finding_type === 'cmdb_gap');
                const hasGovGap = findings.some(f => f.finding_type === 'governance_gap');
                const hasDupe = findings.some(f => f.finding_type === 'duplication_risk');
                
                if (hasCmdbGap) {
                    headline = `${name} is not registered in the CMDB, but connection is not affected`;
                    cause = 'Missing from configuration management database';
                    consequence = 'Recommend adding to CMDB for tracking';
                } else if (hasGovGap) {
                    headline = `${name} has no data classification defined, but connection is not affected`;
                    cause = 'Governance metadata is incomplete';
                    consequence = 'Consider defining data classification';
                } else if (hasDupe) {
                    headline = `${name} has possible duplicate entries, but connection is not affected`;
                    cause = 'Similar assets detected in catalog';
                    consequence = 'Review for consolidation';
                } else if (!agg.has_cmdb) {
                    headline = `${name} is missing CMDB registration, but connection is not affected`;
                    cause = 'Not in configuration database';
                    consequence = 'Add to CMDB when convenient';
                } else {
                    headline = `${name} has no recorded technical owner, but connection is not affected`;
                    cause = 'Owner metadata is missing';
                    consequence = 'Assign owner for accountability';
                }
            } else {
                headline = `${name} has unresolved ambiguity that requires review before connecting`;
                cause = 'Classification pending';
                consequence = 'Manual review recommended';
            }
            
            return { headline, cause, consequence };
        }
        
        function buildEvidenceBySource(item) {
            const agg = item.aggregated_evidence || {};
            const sources = [];
            
            sources.push({
                name: 'IdP / SSO',
                icon: agg.has_idp ? '✅' : '❌',
                status: agg.has_idp ? 'Connected' : 'Not registered',
                detail: agg.idp_app_name || (agg.has_idp ? 'App found in IdP' : 'No matching app in identity provider'),
                hasData: agg.has_idp
            });
            
            sources.push({
                name: 'CMDB',
                icon: agg.has_cmdb ? '✅' : '❌',
                status: agg.has_cmdb ? 'Registered' : 'Not registered',
                detail: agg.cmdb_record_name || (agg.has_cmdb ? 'Found in CMDB' : 'No matching record in configuration database'),
                hasData: agg.has_cmdb
            });
            
            sources.push({
                name: 'Finance',
                icon: agg.has_finance ? '✅' : '➖',
                status: agg.has_finance ? `$${(agg.monthly_spend || 0).toLocaleString()}/mo` : 'No spend detected',
                detail: agg.finance_vendor || (agg.has_finance ? 'Active subscription' : 'No financial transactions found'),
                hasData: agg.has_finance
            });
            
            sources.push({
                name: 'Discovery',
                icon: agg.has_discovery ? '✅' : '➖',
                status: agg.has_discovery ? 'Active usage' : 'No usage detected',
                detail: agg.discovery_sources ? `Sources: ${agg.discovery_sources.join(', ')}` : (agg.has_discovery ? 'DNS/Browser activity detected' : 'No network activity observed'),
                hasData: agg.has_discovery
            });
            
            sources.push({
                name: 'Cloud',
                icon: agg.has_cloud ? '✅' : '➖',
                status: agg.has_cloud ? 'Cloud presence' : 'No cloud data',
                detail: agg.cloud_provider || (agg.has_cloud ? 'Found in cloud inventory' : 'Not found in cloud providers'),
                hasData: agg.has_cloud
            });
            
            return sources;
        }
        
        function buildDetailHtml(item, itemType) {
            const { headline, cause, consequence } = generateTriageHeadline(item, itemType);
            const evidenceSources = buildEvidenceBySource(item);
            
            const evidenceHtml = evidenceSources.map(s => `
                <div class="evidence-row ${s.hasData ? 'has-data' : 'no-data'}">
                    <span class="evidence-icon">${s.icon}</span>
                    <span class="evidence-source">${s.name}</span>
                    <span class="evidence-status">${s.status}</span>
                    <span class="evidence-detail">${s.detail}</span>
                </div>
            `).join('');
            
            const techDetailsHtml = `
                <div class="tech-details-toggle" onclick="this.parentElement.classList.toggle('show-tech')">
                    <span class="toggle-icon">▶</span> Show technical details
                </div>
                <div class="tech-details-content">
                    <pre>${JSON.stringify(item, null, 2)}</pre>
                </div>
            `;
            
            return `<div class="triage-detail-content triage-detail-v2">
                <div class="detail-block detail-summary">
                    <div class="detail-block-title">What's Wrong</div>
                    <div class="detail-headline">${headline}</div>
                    <div class="detail-cause"><strong>Cause:</strong> ${cause}</div>
                    <div class="detail-consequence"><strong>Impact:</strong> ${consequence}</div>
                </div>
                <div class="detail-block detail-evidence">
                    <div class="detail-block-title">Evidence by Source</div>
                    <div class="evidence-grid">${evidenceHtml}</div>
                </div>
                <div class="detail-block detail-tech">
                    ${techDetailsHtml}
                </div>
            </div>`;
        }
        
        function toggleTriageMenu(btn, event) {
            event.stopPropagation();
            const menu = btn.nextElementSibling;
            const wasOpen = menu.classList.contains('open');
            document.querySelectorAll('.triage-more-menu.open').forEach(m => m.classList.remove('open'));
            if (!wasOpen) menu.classList.add('open');
        }
        
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.triage-more')) {
                document.querySelectorAll('.triage-more-menu.open').forEach(m => m.classList.remove('open'));
            }
        });
        
        function renderTriageSection(container, items, sectionType) {
            if (!items || items.length === 0) {
                container.innerHTML = '<div class="triage-empty">No items in this section</div>';
                return;
            }
            
            const currentSort = triageSortState[sectionType] || 'name';
            const showCheckbox = sectionType === 'hygiene';
            const checkboxHeader = showCheckbox ? '<th style="width: 30px;"></th>' : '';
            
            let tableHtml = `<table class="triage-table">
                <thead>
                    <tr>
                        ${checkboxHeader}
                        <th data-sort="name" data-section="${sectionType}" class="${currentSort === 'name' ? 'sorted' : ''}">Asset <span class="sort-arrow">&#8597;</span></th>
                        <th data-sort="type" data-section="${sectionType}" class="${currentSort === 'type' ? 'sorted' : ''}">Issue <span class="sort-arrow">&#8597;</span></th>
                        <th style="width: 180px;">Actions</th>
                    </tr>
                </thead>
                <tbody>`;
            
            items.forEach((item, idx) => {
                const itemType = item.itemType || 'unknown';
                const itemId = item.finding_id || item.asset_id || item.id || '';
                const checkboxCell = showCheckbox ? `<td><input type="checkbox" class="triage-item-checkbox" data-item-id="${itemId}" data-item-type="${itemType}" onclick="event.stopPropagation()"></td>` : '';
                
                const triageState = item.triageState || 'pending';
                const isTriaged = triageState !== 'pending';
                const rowStateClass = isTriaged ? `triaged triaged-${triageState}` : '';
                
                const { headline } = generateTriageHeadline(item, itemType);
                const assetName = item.name || item.asset_key || item.asset_name || 'Unknown';
                const issue = headline;
                let categoryClass = itemType || 'governance';
                
                const dataAttrs = `data-item-id="${itemId}" data-item-type="${itemType}"`;
                let primaryBtn, secondaryBtn = '', moreOptions, statusBadge = '';
                
                if (isTriaged) {
                    const stateLabels = {
                        'approved': '✓ Approved for AAM',
                        'banned': '⊘ Banned',
                        'deprovisioned': '✗ Deprovisioned',
                        'acknowledged': '✓ Acknowledged',
                        'assigned': '→ Assigned',
                        'deferred': '⏳ Deferred',
                        'ignored': '✗ Ignored',
                        'dismissed': '✓ Risk Dismissed',
                        'acknowledged': '✓ Acknowledged'
                    };
                    const stateLabel = stateLabels[triageState] || triageState;
                    let extraInfo = '';
                    if (item.triageOwner) extraInfo = ` to ${item.triageOwner}`;
                    if (item.triageDeferUntil) extraInfo = ` until ${new Date(item.triageDeferUntil).toLocaleDateString()}`;
                    if (item.triageIgnoreReason) extraInfo = `: ${item.triageIgnoreReason}`;
                    
                    statusBadge = `<span class="triage-status-badge ${triageState}">${stateLabel}${extraInfo}</span>`;
                    primaryBtn = `<button class="triage-btn secondary" ${dataAttrs} data-action="revert">Undo</button>`;
                    moreOptions = `
                        <button class="triage-more-item" ${dataAttrs} data-action="assign">Reassign</button>
                        <button class="triage-more-item" ${dataAttrs} data-action="defer">Defer</button>`;
                } else if (sectionType === 'firewall') {
                    const provStatus = (item.provisioning_status || '').toUpperCase();
                    const isAlreadyBlocked = provStatus === 'BLOCKED';
                    
                    if (isAlreadyBlocked) {
                        statusBadge = `<span class="triage-status-badge banned">⊘ Banned</span>`;
                        primaryBtn = '';
                        secondaryBtn = '';
                        moreOptions = `
                            <button class="triage-more-item" ${dataAttrs} data-action="sanction">Unblock (Approve)</button>`;
                    } else {
                        statusBadge = `<span class="triage-status-badge warning">⚠ AAM Blocked</span>`;
                        primaryBtn = `<button class="triage-btn success" ${dataAttrs} data-action="resolve_blocking">Resolve & Connect</button>`;
                        secondaryBtn = `<button class="triage-btn danger" ${dataAttrs} data-action="ban">Ban</button>`;
                        moreOptions = `
                            <button class="triage-more-item" ${dataAttrs} data-action="override_blocking">Override (Warn Only)</button>
                            <button class="triage-more-item" ${dataAttrs} data-action="defer">Defer</button>
                            <button class="triage-more-item" ${dataAttrs} data-action="assign">Assign</button>`;
                    }
                } else if (sectionType === 'risk') {
                    primaryBtn = `<button class="triage-btn warning" ${dataAttrs} data-action="deprovision">Deprovision</button>`;
                    secondaryBtn = `<button class="triage-btn secondary" ${dataAttrs} data-action="dismiss_risk">Dismiss Risk</button>`;
                    moreOptions = `
                        <button class="triage-more-item" ${dataAttrs} data-action="defer">Defer</button>
                        <button class="triage-more-item" ${dataAttrs} data-action="assign">Assign</button>`;
                } else {
                    primaryBtn = `<button class="triage-btn primary" ${dataAttrs} data-action="acknowledge">Acknowledge Gap</button>`;
                    secondaryBtn = `<button class="triage-btn secondary" ${dataAttrs} data-action="assign">Assign Owner</button>`;
                    moreOptions = `
                        <button class="triage-more-item" ${dataAttrs} data-action="defer">Defer</button>`;
                }
                
                const actionBtns = `
                    ${statusBadge}
                    ${primaryBtn}
                    ${secondaryBtn}
                    <div class="triage-more">
                        <button class="triage-more-btn" onclick="toggleTriageMenu(this, event);">&#8942;</button>
                        <div class="triage-more-menu">${moreOptions}</div>
                    </div>`;
                
                const detailHtml = buildDetailHtml(item, itemType);
                const colSpan = showCheckbox ? 4 : 3;
                
                tableHtml += `
                    <tr class="triage-row ${rowStateClass}" data-item-idx="${idx}" data-section="${sectionType}">
                        ${checkboxCell}
                        <td class="triage-cell-asset">${assetName}</td>
                        <td class="triage-cell-issue"><span class="triage-tag ${categoryClass}">${issue}</span></td>
                        <td class="triage-cell-actions">${actionBtns}</td>
                    </tr>
                    <tr class="triage-detail-row" data-detail-for="${idx}">
                        <td colspan="${colSpan}">${detailHtml}</td>
                    </tr>`;
            });
            
            tableHtml += '</tbody></table>';
            container.innerHTML = tableHtml;
            
            container.querySelectorAll('.triage-table th[data-sort]').forEach(th => {
                th.onclick = function() {
                    const sortBy = this.dataset.sort;
                    const section = this.dataset.section;
                    triageSortState[section] = sortBy;
                    const sorted = sortTriageItems(triageSectionData[section], sortBy, section);
                    renderTriageSection(container, sorted, section);
                };
            });
            
            container.querySelectorAll('.triage-row').forEach(row => {
                row.onclick = function(e) {
                    if (e.target.closest('.triage-cell-actions') || e.target.closest('.triage-item-checkbox')) return;
                    const idx = this.dataset.itemIdx;
                    const detailRow = container.querySelector(`.triage-detail-row[data-detail-for="${idx}"]`);
                    if (detailRow) {
                        detailRow.classList.toggle('open');
                        this.classList.toggle('expanded');
                    }
                };
            });
            
            if (sectionType === 'hygiene') {
                initHygieneBatchSelection();
            }
        }
        
        function initHygieneBatchSelection() {
            const batchBar = document.getElementById('hygieneBatchBar');
            const selectAllCheckbox = document.getElementById('hygieneSelectAll');
            const batchCount = document.getElementById('hygieneBatchCount');
            const hygieneContent = document.getElementById('triageHygieneContent');
            const ackBtn = document.getElementById('hygieneBatchAck');
            
            const checkboxes = hygieneContent.querySelectorAll('.triage-item-checkbox');
            if (checkboxes.length === 0) {
                batchBar.classList.remove('show');
                return;
            }
            
            batchBar.classList.add('show');
            
            function updateBatchCount() {
                const checked = hygieneContent.querySelectorAll('.triage-item-checkbox:checked');
                const count = checked.length;
                batchCount.textContent = count === 0 ? '0 selected' : `${count} selected`;
                selectAllCheckbox.checked = count === checkboxes.length && count > 0;
                selectAllCheckbox.indeterminate = count > 0 && count < checkboxes.length;
            }
            
            selectAllCheckbox.onclick = function() {
                const isChecked = this.checked;
                hygieneContent.querySelectorAll('.triage-item-checkbox').forEach(cb => {
                    cb.checked = isChecked;
                });
                updateBatchCount();
            };
            
            checkboxes.forEach(cb => {
                cb.onclick = updateBatchCount;
            });
            
            ackBtn.onclick = async function() {
                const checked = hygieneContent.querySelectorAll('.triage-item-checkbox:checked');
                if (checked.length === 0) return;
                const runId = document.getElementById('triageRunSelect').value;
                if (!runId) return;
                
                this.disabled = true;
                this.textContent = 'Processing...';
                
                for (const cb of checked) {
                    const itemId = cb.dataset.itemId;
                    const itemType = cb.dataset.itemType;
                    await submitTriageAction(runId, itemId, itemType, 'acknowledge', {});
                }
                
                this.disabled = false;
                this.textContent = 'Acknowledge Selected';
                selectAllCheckbox.checked = false;
                updateBatchCount();
            };
            
            updateBatchCount();
        }
        
        function initTestTab() {
            async function loadDecisionTraceRuns() {
                const select = document.getElementById('decisionTraceRunId');
                try {
                    const response = await fetch('/api/runs');
                    const runs = await response.json();
                    select.innerHTML = '<option value="">Select a run...</option>';
                    runs.filter(r => r.status === 'completed_with_results' || r.status === 'COMPLETED_WITH_RESULTS')
                        .forEach(run => {
                            const opt = document.createElement('option');
                            opt.value = run.run_id;
                            const tenant = run.tenant_id || run.tenant_name || 'Unknown';
                            const dateStr = run.started_at || run.created_at;
                            const date = dateStr ? new Date(dateStr).toLocaleDateString() : '';
                            opt.textContent = `${tenant} - ${date}`;
                            select.appendChild(opt);
                        });
                } catch (err) {
                    console.error('Failed to load runs:', err);
                }
            }
            loadDecisionTraceRuns();
            
            document.querySelectorAll('.decision-filter').forEach(btn => {
                btn.addEventListener('click', () => {
                    document.querySelectorAll('.decision-filter').forEach(b => {
                        b.classList.remove('active');
                        b.classList.remove('btn-primary');
                        b.classList.add('btn-secondary');
                    });
                    btn.classList.add('active');
                    btn.classList.remove('btn-secondary');
                    btn.classList.add('btn-primary');
                    decisionTraceFilter = btn.dataset.filter;
                    if (decisionTracesCache) applyDecisionFilters();
                });
            });
            
            document.getElementById('runDecisionTrace').addEventListener('click', loadDecisionTraces);
            document.getElementById('decisionTraceRunId').addEventListener('change', loadDecisionTraces);
            
            document.getElementById('exportMismatches').addEventListener('click', exportMismatches);
            
            function exportMismatches() {
                if (!decisionTracesCache) {
                    showToast('Load traces first', 'error');
                    return;
                }
                
                const mismatchKeys = Object.keys(decisionMismatches).filter(k => decisionMismatches[k]);
                if (mismatchKeys.length === 0) {
                    showToast('No mismatches tracked. Compare assets with Farm traces first.', 'error');
                    return;
                }
                
                const exportData = mismatchKeys.map(key => ({
                    asset_key: key,
                    ...decisionTracesCache[key]
                }));
                
                const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `aod_mismatches_${new Date().toISOString().slice(0,10)}.json`;
                a.click();
                URL.revokeObjectURL(url);
            }
            
            async function loadDecisionTraces() {
                const runId = document.getElementById('decisionTraceRunId').value;
                const resultDiv = document.getElementById('decisionTraceResult');
                
                if (!runId) {
                    resultDiv.innerHTML = '<div style="padding:2rem;text-align:center;color:var(--slate-500);">Select a snapshot to load decision traces</div>';
                    return;
                }
                
                resultDiv.innerHTML = '<div style="padding:2rem;text-align:center;color:var(--cyan-400);"><div class="spinner"></div> Loading traces...</div>';
                
                try {
                    const response = await fetch('/api/debug/decision-trace', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ run_id: runId, activity_window_days: 90 })
                    });
                    const data = await response.json();
                    
                    if (data.detail) {
                        resultDiv.innerHTML = `<div style="padding:2rem;text-align:center;color:var(--red-400);">${data.detail}</div>`;
                        return;
                    }
                    
                    decisionTracesCache = data.traces;
                    applyDecisionFilters();
                } catch (err) {
                    resultDiv.innerHTML = `<div style="padding:2rem;text-align:center;color:var(--red-400);">Error: ${err.message}</div>`;
                }
            }
            
            document.getElementById('decisionTraceFilter').addEventListener('input', () => {
                if (decisionTracesCache) applyDecisionFilters();
            });
            
            function applyDecisionFilters() {
                const textFilter = document.getElementById('decisionTraceFilter').value.toLowerCase().trim();
                const filtered = {};
                
                for (const [key, trace] of Object.entries(decisionTracesCache)) {
                    if (textFilter && !key.toLowerCase().includes(textFilter)) continue;
                    if (decisionTraceFilter === 'shadow' && !trace.is_shadow) continue;
                    if (decisionTraceFilter === 'mismatch' && !decisionMismatches[key]) continue;
                    filtered[key] = trace;
                }
                
                renderDecisionTraces(filtered);
            }
            
            function renderDecisionTraces(traces) {
                const resultDiv = document.getElementById('decisionTraceResult');
                const countSpan = document.getElementById('decisionTraceCount');
                const total = Object.keys(traces).length;
                countSpan.textContent = `${total} traces`;
                
                let html = `<div style="max-height:500px;overflow-y:auto;">`;
                html += `<table style="width:100%;font-size:0.875rem;border-collapse:collapse;">`;
                html += `<thead><tr style="position:sticky;top:0;background:var(--slate-700);z-index:1;">`;
                html += `<th style="text-align:left;padding:0.75rem 1rem;font-weight:500;color:var(--slate-300);">Asset Key</th>`;
                html += `<th style="text-align:left;padding:0.75rem 0.5rem;font-weight:500;color:var(--slate-300);">Registered Domain</th>`;
                html += `<th style="text-align:center;padding:0.75rem 0.5rem;font-weight:500;color:var(--slate-300);">External</th>`;
                html += `<th style="text-align:center;padding:0.75rem 0.5rem;font-weight:500;color:var(--slate-300);">Active</th>`;
                html += `<th style="text-align:center;padding:0.75rem 0.5rem;font-weight:500;color:var(--slate-300);">IdP</th>`;
                html += `<th style="text-align:center;padding:0.75rem 0.5rem;font-weight:500;color:var(--slate-300);">CMDB</th>`;
                html += `<th style="text-align:center;padding:0.75rem 0.5rem;font-weight:500;color:var(--slate-300);">Infra</th>`;
                html += `<th style="text-align:center;padding:0.75rem 0.5rem;font-weight:500;color:var(--slate-300);">Shadow</th>`;
                html += `<th style="text-align:left;padding:0.75rem 1rem;font-weight:500;color:var(--slate-300);">Activity Source</th>`;
                html += `</tr></thead><tbody>`;
                
                const sortedKeys = Object.keys(traces).sort();
                
                for (const key of sortedKeys) {
                    const t = traces[key];
                    const escapedKey = key.replace(/'/g, "\\'");
                    html += `<tr style="border-bottom:1px solid var(--slate-700);cursor:pointer;" onclick="showDecisionDetail('${escapedKey}')" onmouseover="this.style.background='var(--slate-700)'" onmouseout="this.style.background=''">`;
                    html += `<td style="padding:0.5rem 1rem;color:var(--cyan-400);">${key}</td>`;
                    html += `<td style="padding:0.5rem;color:var(--slate-300);">${t.registered_domain || ''}</td>`;
                    html += `<td style="text-align:center;padding:0.5rem;color:${t.is_external ? 'var(--green-400)' : 'var(--slate-500)'};">${t.is_external ? 'Y' : '-'}</td>`;
                    html += `<td style="text-align:center;padding:0.5rem;color:${t.is_active ? 'var(--green-400)' : 'var(--slate-500)'};">${t.is_active ? 'Y' : '-'}</td>`;
                    html += `<td style="text-align:center;padding:0.5rem;color:${t.idp_present ? 'var(--green-400)' : 'var(--slate-500)'};">${t.idp_present ? 'Y' : '-'}</td>`;
                    html += `<td style="text-align:center;padding:0.5rem;color:${t.cmdb_present ? 'var(--green-400)' : 'var(--slate-500)'};">${t.cmdb_present ? 'Y' : '-'}</td>`;
                    html += `<td style="text-align:center;padding:0.5rem;color:${t.infra_excluded ? 'var(--purple-400)' : 'var(--slate-500)'};">${t.infra_excluded ? 'Y' : '-'}</td>`;
                    html += `<td style="text-align:center;padding:0.5rem;"><span style="color:${t.is_shadow ? 'var(--orange-400)' : 'var(--slate-500)'};">${t.is_shadow ? 'SHADOW' : '-'}</span></td>`;
                    html += `<td style="padding:0.5rem 1rem;color:var(--slate-400);">${t.activity_source || ''}</td>`;
                    html += `</tr>`;
                }
                
                html += `</tbody></table></div>`;
                resultDiv.innerHTML = html;
            }
            
        }
        
        function initHandoffTab() {
            const handoffSelect = document.getElementById('handoffRunSelect');
            const handoffStatusFilter = document.getElementById('handoffStatusFilter');
            const exportBtn = document.getElementById('exportToAAMBtn');
            const auditBtn = document.getElementById('viewFabricAuditBtn');
            const closeAuditBtn = document.getElementById('closeFabricAuditBtn');
            const downloadAuditBtn = document.getElementById('downloadAuditReportBtn');

            if (!handoffSelect) {
                console.error('Handoff tab elements not found');
                return;
            }

            handoffSelect.addEventListener('change', () => {
                const runId = handoffSelect.value;
                const statusFilter = handoffStatusFilter.value;
                if (runId) loadHandoffCandidates(runId, statusFilter);
            });

            exportBtn.addEventListener('click', exportToAAM);

            if (auditBtn) {
                auditBtn.addEventListener('click', () => {
                    const runId = handoffSelect.value;
                    if (runId) loadFabricAudit(runId);
                });
            }

            if (closeAuditBtn) {
                closeAuditBtn.addEventListener('click', hideFabricAudit);
            }

            if (downloadAuditBtn) {
                downloadAuditBtn.addEventListener('click', () => {
                    const runId = handoffSelect.value;
                    if (runId) downloadAuditReport(runId);
                });
            }

            handoffStatusFilter.addEventListener('change', () => {
                hideHandoffDrill();
                const runId = handoffSelect.value;
                const statusFilter = handoffStatusFilter.value;
                if (runId) loadHandoffCandidates(runId, statusFilter);
            });

            const backBtn = document.getElementById('handoffDrillBack');
            if (backBtn) {
                backBtn.addEventListener('click', hideHandoffDrill);
            }
        }
        
        async function loadHandoffRuns() {
            const select = document.getElementById('handoffRunSelect');
            if (!select) {
                console.error('handoffRunSelect element not found');
                return;
            }
            select.innerHTML = '<option value="">Loading runs...</option>';
            try {
                const response = await fetch('/api/runs');
                if (!response.ok) {
                    throw new Error(`API error: ${response.status}`);
                }
                const runs = await response.json();
                const currentVal = select.value;
                select.innerHTML = '<option value="">Select a run...</option>';
                const completedRuns = runs.filter(r => r.status === 'completed_with_results' || r.status === 'COMPLETED_WITH_RESULTS');
                completedRuns.sort((a, b) => new Date(b.started_at || b.created_at) - new Date(a.started_at || a.created_at));
                const displayRuns = completedRuns.slice(0, 20);
                console.log('Handoff: loaded', completedRuns.length, 'runs, showing', displayRuns.length);
                displayRuns.forEach((run, idx) => {
                    const opt = document.createElement('option');
                    opt.value = run.run_id;
                    const tenant = run.tenant_id || run.tenant_name || 'Unknown';
                    const dateStr = run.started_at || run.created_at;
                    const date = dateStr ? new Date(dateStr).toLocaleDateString() : '';
                    const latest = idx === 0 ? ' (Latest)' : '';
                    opt.textContent = `${tenant} - ${date}${latest}`;
                    select.appendChild(opt);
                });
                // Populate dropdown only — Console's selectRun() handles candidate loading
                if (currentRunId && displayRuns.some(r => r.run_id === currentRunId)) {
                    select.value = currentRunId;
                } else if (displayRuns.length > 0) {
                    select.value = displayRuns[0].run_id;
                }
            } catch (err) {
                console.error('Failed to load handoff runs:', err);
                select.innerHTML = '<option value="">Failed to load runs</option>';
            }
        }
        
        async function loadHandoffCandidates(runId, statusFilter) {
            const container = document.getElementById('handoffCandidatesContainer');
            const labelEl = document.getElementById('handoffCandidateLabel');
            const exportBtn = document.getElementById('exportToAAMBtn');
            const auditBtn = document.getElementById('viewFabricAuditBtn');

            container.innerHTML = '<div class="loading"><div class="spinner"></div> Loading candidates...</div>';
            exportBtn.disabled = true;
            if (auditBtn) auditBtn.disabled = true;
            
            try {
                const response = await fetch(`/api/handoff/aam/candidates?run_id=${runId}&status_filter=${statusFilter}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                
                if (!response.ok) {
                    throw new Error(`Failed to load candidates: ${response.status}`);
                }
                
                const data = await response.json();
                const candidates = data.candidates || [];
                const farmFabricPlanes = data.fabric_planes || [];
                const farmSORs = data.systems_of_record || [];
                
                window.farmFabricPlanes = farmFabricPlanes;
                window.farmSORs = farmSORs;
                
                const totalCount = candidates.length;
                const fabricCount = farmFabricPlanes.length;
                const sorCount = farmSORs.length;
                const findingsCount = candidates.filter(c => c.findings && c.findings.length > 0).length;
                
                const fabricCounts = {
                    ipaas: farmFabricPlanes.filter(p => p.plane_type === 'ipaas').length,
                    api_gateway: farmFabricPlanes.filter(p => p.plane_type === 'api_gateway').length,
                    warehouse: farmFabricPlanes.filter(p => p.plane_type === 'data_warehouse').length,
                    event_bus: farmFabricPlanes.filter(p => p.plane_type === 'event_bus').length
                };
                
                document.getElementById('handoffTotalCount').textContent = totalCount;
                document.getElementById('handoffFabricCount').textContent = fabricCount;
                document.getElementById('handoffSorCount').textContent = sorCount;
                document.getElementById('handoffFindingsCount').textContent = findingsCount;
                
                document.getElementById('fabricIpaasCount').textContent = fabricCounts.ipaas;
                document.getElementById('fabricApiGatewayCount').textContent = fabricCounts.api_gateway;
                document.getElementById('fabricWarehouseCount').textContent = fabricCounts.warehouse;
                document.getElementById('fabricEventBusCount').textContent = fabricCounts.event_bus;
                
                const fabricBreakdown = document.getElementById('fabricPlanesBreakdown');
                if (fabricCount > 0) {
                    fabricBreakdown.classList.remove('hidden');
                    renderFarmFabricPlanes(farmFabricPlanes);
                } else {
                    fabricBreakdown.classList.add('hidden');
                }
                
                renderFarmSORs(farmSORs);
                
                labelEl.textContent = `${totalCount} candidates from ${runId.substring(0, 16)}...`;
                
                if (totalCount > 0) {
                    exportBtn.disabled = false;
                    if (auditBtn) auditBtn.disabled = false;
                }

                renderHandoffCandidates(candidates);
                if (typeof updatePipelineStrip === 'function') updatePipelineStrip();
            } catch (err) {
                console.error('Failed to load handoff candidates:', err);
                container.innerHTML = `<div class="error-message">Failed to load candidates: ${err.message}</div>`;
                labelEl.textContent = 'Error loading candidates';
            }
        }

        let handoffCandidatesData = [];
        let handoffCandidatesFullData = [];
        
        const IPAAS_VENDORS = ['mulesoft', 'workato', 'boomi', 'tray', 'zapier', 'make', 'snaplogic', 'celigo'];
        const API_GATEWAY_VENDORS = ['kong', 'apigee', 'aws_api_gateway', 'azure_api', 'api gateway'];
        const WAREHOUSE_VENDORS = ['snowflake', 'bigquery', 'redshift', 'databricks', 'synapse'];
        const EVENT_BUS_VENDORS = ['kafka', 'confluent', 'eventbridge', 'eventhub', 'pubsub', 'kinesis'];
        
        let activeFabricFilter = null;
        
        function getFabricPlaneType(candidate) {
            if (!candidate.connected_via_plane && !candidate.fabric_plane_tag) return null;
            
            const planeStr = ((candidate.connected_via_plane || '') + ' ' + (candidate.fabric_plane_tag?.plane_type || '') + ' ' + (candidate.fabric_plane_tag?.controller_vendor || '')).toLowerCase();
            
            if (planeStr.includes('ipaas') || IPAAS_VENDORS.some(v => planeStr.includes(v))) {
                return 'ipaas';
            } else if (planeStr.includes('api_gateway') || planeStr.includes('gateway') || API_GATEWAY_VENDORS.some(v => planeStr.includes(v))) {
                return 'api_gateway';
            } else if (planeStr.includes('data_warehouse') || planeStr.includes('warehouse') || WAREHOUSE_VENDORS.some(v => planeStr.includes(v))) {
                return 'warehouse';
            } else if (planeStr.includes('event_bus') || planeStr.includes('event') || planeStr.includes('stream') || EVENT_BUS_VENDORS.some(v => planeStr.includes(v))) {
                return 'event_bus';
            }
            return null;
        }
        
        function countFabricPlaneTypes(candidates) {
            const counts = { ipaas: 0, api_gateway: 0, warehouse: 0, event_bus: 0 };
            
            for (const c of candidates) {
                const planeType = getFabricPlaneType(c);
                if (planeType) counts[planeType]++;
            }
            
            return counts;
        }
        
        function renderFarmFabricPlanes(planes) {
            const container = document.getElementById('farmFabricPlanesContainer');
            if (!container) return;
            
            if (!planes || planes.length === 0) {
                container.innerHTML = '<div class="empty-state">No fabric planes detected</div>';
                return;
            }
            
            const planeTypeLabels = {
                'ipaas': 'iPaaS',
                'api_gateway': 'API Gateway',
                'data_warehouse': 'Data Warehouse',
                'event_bus': 'Event Bus'
            };
            
            const html = planes.map(p => `
                <div class="fabric-plane-chip">
                    <span class="plane-type">${planeTypeLabels[p.plane_type] || p.plane_type}</span>
                    <span class="plane-vendor">${p.vendor.replace(/_/g, ' ')}</span>
                    ${p.is_healthy ? '<span class="health-badge healthy">Healthy</span>' : '<span class="health-badge unhealthy">Degraded</span>'}
                    <span class="source-badge">${p.source}</span>
                </div>
            `).join('');
            
            container.innerHTML = html;
        }
        
        function renderFarmSORs(sors) {
            const container = document.getElementById('farmSORsContainer');
            if (!container) return;
            
            if (!sors || sors.length === 0) {
                container.innerHTML = '<div class="empty-state">No Systems of Record detected</div>';
                return;
            }
            
            const html = sors.map(s => `
                <div class="sor-chip">
                    <span class="sor-domain">${s.domain.toUpperCase()}</span>
                    <span class="sor-name">${s.sor_name}</span>
                    <span class="sor-type">${s.sor_type}</span>
                    <span class="confidence-badge ${s.confidence}">${s.confidence}</span>
                    <span class="source-badge">${s.source}</span>
                </div>
            `).join('');
            
            container.innerHTML = html;
        }
        
        function filterByFabricPlane(planeType) {
            hideHandoffDrill();
            
            activeFabricFilter = planeType;
            
            document.querySelectorAll('.fabric-plane-item').forEach(el => el.classList.remove('active'));
            const activeItem = document.querySelector(`.fabric-plane-item.${planeType.replace('_', '-')}`);
            if (activeItem) activeItem.classList.add('active');
            
            const planeNames = { ipaas: 'iPaaS', api_gateway: 'API Gateway', warehouse: 'Warehouse', event_bus: 'Event Bus' };
            const planeTypeMapping = { warehouse: 'data_warehouse' };
            const farmPlaneType = planeTypeMapping[planeType] || planeType;
            
            const farmPlanes = window.farmFabricPlanes || [];
            const matchingPlanes = farmPlanes.filter(p => p.plane_type === farmPlaneType);
            const vendorPatterns = matchingPlanes.map(p => p.vendor.toLowerCase().replace(/_/g, ' '));
            
            const filtered = handoffCandidatesFullData.filter(c => {
                const connectedVia = (c.connected_via_plane || '').toLowerCase();
                const fabricTag = c.fabric_plane_tag;
                const tagVendor = fabricTag ? (fabricTag.controller_vendor || '').toLowerCase() : '';
                const tagType = fabricTag ? (fabricTag.plane_type || '').toLowerCase() : '';
                
                const fabricSummary = c.fabric_plane_summary;
                const summaryPlaneType = fabricSummary ? (fabricSummary.primary_plane_type || '').toLowerCase() : '';
                
                const pipes = c.pipes || [];
                const hasPipeWithPlaneType = pipes.some(p => 
                    (p.fabric_plane_type || '').toLowerCase() === farmPlaneType
                );
                
                return vendorPatterns.some(pattern => 
                    connectedVia.includes(pattern) || 
                    tagVendor.includes(pattern)
                ) || tagType === farmPlaneType || summaryPlaneType === farmPlaneType || hasPipeWithPlaneType;
            });
            
            const vendorLabel = matchingPlanes.length > 0 
                ? matchingPlanes.map(p => p.vendor.replace(/_/g, ' ')).join(', ')
                : planeNames[planeType];
            document.getElementById('fabricFilterLabel').textContent = `Filtering: ${planeNames[planeType]} (${vendorLabel})`;
            document.getElementById('fabricFilterActive').classList.remove('hidden');
            
            renderHandoffCandidates(filtered, true);
            
            document.getElementById('handoffCandidateLabel').textContent = `${filtered.length} ${planeNames[planeType]} candidates`;
        }
        
        function clearFabricFilter() {
            hideHandoffDrill();
            
            activeFabricFilter = null;
            
            document.querySelectorAll('.fabric-plane-item').forEach(el => el.classList.remove('active'));
            document.getElementById('fabricFilterActive').classList.add('hidden');
            
            renderHandoffCandidates(handoffCandidatesFullData, true);
            document.getElementById('handoffCandidateLabel').textContent = `${handoffCandidatesFullData.length} candidates`;
        }
        
        function renderHandoffCandidates(candidates, isFiltered = false) {
            const container = document.getElementById('handoffCandidatesContainer');
            if (!isFiltered) {
                handoffCandidatesFullData = candidates || [];
            }
            handoffCandidatesData = candidates || [];
            
            if (!candidates || candidates.length === 0) {
                container.innerHTML = '<div class="empty-state">No candidates found for this snapshot</div>';
                return;
            }
            
            let html = '';
            for (let i = 0; i < candidates.length; i++) {
                const candidate = candidates[i];
                const displayName = candidate.display_name || candidate.asset_key || 'Unknown';
                const vendorName = candidate.vendor_name || '';
                const assetKey = candidate.asset_key || '';
                const govStatus = candidate.governance_status || 'edge';
                const priorityScore = candidate.priority_score != null ? candidate.priority_score.toFixed(1) : '-';
                const connectedViaPlane = candidate.connected_via_plane;
                const sorTagging = candidate.sor_tagging;
                const findings = candidate.findings || [];
                
                const systemType = getSystemType(sorTagging);
                
                let badgesHtml = `<span class="handoff-badge ${govStatus}">${govStatus}</span>`;
                if (systemType !== 'unknown') {
                    badgesHtml += `<span class="handoff-badge ${systemType}">${systemType.toUpperCase()}</span>`;
                }
                if (connectedViaPlane) {
                    badgesHtml += `<span class="handoff-badge fabric-plane">⚡ ${connectedViaPlane}</span>`;
                }
                
                let sorHtml = '';
                if (sorTagging && sorTagging.domain) {
                    const confidence = sorTagging.confidence || 'unknown';
                    sorHtml = `
                        <div class="handoff-sor-tag">
                            <span class="handoff-sor-label">SOR Domain</span>
                            <span class="handoff-sor-value">${sorTagging.domain}</span>
                            <span class="handoff-sor-confidence">${confidence} confidence</span>
                        </div>`;
                }
                
                let findingsHtml = '';
                if (findings.length > 0) {
                    findingsHtml = '<div class="handoff-finding-list">';
                    for (const finding of findings.slice(0, 3)) {
                        const code = finding.code || finding.type || 'unknown';
                        const severity = (finding.severity || 'info').toLowerCase();
                        findingsHtml += `<span class="handoff-finding severity-${severity}">${code}</span>`;
                    }
                    if (findings.length > 3) {
                        findingsHtml += `<span class="handoff-finding severity-info">+${findings.length - 3} more</span>`;
                    }
                    findingsHtml += '</div>';
                }
                
                html += `
                    <div class="handoff-candidate-card" data-candidate-index="${i}" onclick="showHandoffDrill(${i})">
                        <div class="handoff-card-header">
                            <div>
                                <div class="handoff-card-title">${displayName}</div>
                                <div class="handoff-card-subtitle">${vendorName}${vendorName && assetKey ? ' • ' : ''}${assetKey}</div>
                            </div>
                            <div class="handoff-card-badges">
                                ${badgesHtml}
                                <span class="handoff-priority-score">Score: ${priorityScore}</span>
                            </div>
                        </div>
                        <div class="handoff-card-body">
                            ${sorHtml}
                            ${findingsHtml}
                        </div>
                    </div>`;
            }
            
            container.innerHTML = html;
        }
        
        function getSystemType(sorTagging) {
            if (!sorTagging) return 'unknown';
            const domain = (sorTagging.domain || '').toLowerCase();
            const confidence = (sorTagging.confidence || '').toLowerCase();
            
            if (domain && (confidence === 'high' || confidence === 'medium')) {
                return 'sor';
            }
            if (domain === 'customer' || domain === 'employee' || domain === 'finance') {
                return 'sor';
            }
            if (sorTagging.evidence && sorTagging.evidence.some(e => e.toLowerCase().includes('engagement'))) {
                return 'soe';
            }
            if (sorTagging.evidence && sorTagging.evidence.some(e => e.toLowerCase().includes('integration') || e.toLowerCase().includes('middleware'))) {
                return 'soi';
            }
            return 'unknown';
        }
        
        function showHandoffDrill(index) {
            const candidate = handoffCandidatesData[index];
            if (!candidate) return;
            
            const panel = document.getElementById('handoffDrillPanel');
            const title = document.getElementById('handoffDrillTitle');
            const content = document.getElementById('handoffDrillContent');
            const container = document.getElementById('handoffCandidatesContainer');
            
            container.classList.add('hidden');
            panel.classList.remove('hidden');
            
            const displayName = candidate.display_name || candidate.asset_key || 'Unknown';
            title.textContent = displayName;
            
            const sorTagging = candidate.sor_tagging || {};
            const systemType = getSystemType(sorTagging);
            const systemTypeLabel = systemType === 'sor' ? 'System of Record' : 
                                    systemType === 'soe' ? 'System of Engagement' :
                                    systemType === 'soi' ? 'System of Integration' : 'Unclassified';
            
            const signals = candidate.signals_summary || {};
            const findings = candidate.findings || [];
            const evidenceRefs = candidate.evidence_refs || [];
            
            let findingsHtml = '';
            if (findings.length > 0) {
                findingsHtml = '<ul class="handoff-evidence-list">';
                for (const f of findings) {
                    const code = f.code || f.type || 'Unknown';
                    const msg = f.message || f.explanation || '';
                    findingsHtml += `<li class="handoff-evidence-item">${code}: ${msg}</li>`;
                }
                findingsHtml += '</ul>';
            } else {
                findingsHtml = '<span style="color:var(--slate-500)">No findings</span>';
            }
            
            let evidenceHtml = '';
            if (sorTagging.evidence && sorTagging.evidence.length > 0) {
                evidenceHtml = '<ul class="handoff-evidence-list">';
                for (const e of sorTagging.evidence) {
                    evidenceHtml += `<li class="handoff-evidence-item">${e}</li>`;
                }
                evidenceHtml += '</ul>';
            } else {
                evidenceHtml = '<span style="color:var(--slate-500)">No evidence</span>';
            }
            
            content.innerHTML = `
                <div style="display:flex;gap:1rem;align-items:center;margin-bottom:1.5rem;">
                    <div class="handoff-system-type ${systemType}">
                        ${systemType === 'sor' ? '📊' : systemType === 'soe' ? '👥' : systemType === 'soi' ? '🔗' : '❓'}
                        ${systemTypeLabel}
                    </div>
                    <span class="handoff-badge ${candidate.governance_status || 'edge'}" style="font-size:0.8rem;">${candidate.governance_status || 'edge'}</span>
                    ${candidate.connected_via_plane ? `<span class="handoff-badge fabric-plane">⚡ ${candidate.connected_via_plane}</span>` : ''}
                </div>
                
                <div class="handoff-drill-grid">
                    <div class="handoff-drill-section">
                        <div class="handoff-drill-section-title">Asset Information</div>
                        <div class="handoff-drill-row">
                            <span class="handoff-drill-label">Asset Key</span>
                            <span class="handoff-drill-value">${candidate.asset_key || '-'}</span>
                        </div>
                        <div class="handoff-drill-row">
                            <span class="handoff-drill-label">Vendor</span>
                            <span class="handoff-drill-value">${candidate.vendor_name || '-'}</span>
                        </div>
                        <div class="handoff-drill-row">
                            <span class="handoff-drill-label">Priority Score</span>
                            <span class="handoff-drill-value">${candidate.priority_score != null ? candidate.priority_score.toFixed(1) : '-'}</span>
                        </div>
                        <div class="handoff-drill-row">
                            <span class="handoff-drill-label">Governance Status</span>
                            <span class="handoff-drill-value">${candidate.governance_status || '-'}</span>
                        </div>
                    </div>
                    
                    <div class="handoff-drill-section">
                        <div class="handoff-drill-section-title">Signal Summary</div>
                        <div class="handoff-drill-row">
                            <span class="handoff-drill-label">Has IdP</span>
                            <span class="handoff-drill-value" style="color:${signals.has_idp ? 'var(--green-400)' : 'var(--slate-500)'}">${signals.has_idp ? 'Yes' : 'No'}</span>
                        </div>
                        <div class="handoff-drill-row">
                            <span class="handoff-drill-label">Has CMDB</span>
                            <span class="handoff-drill-value" style="color:${signals.has_cmdb ? 'var(--green-400)' : 'var(--slate-500)'}">${signals.has_cmdb ? 'Yes' : 'No'}</span>
                        </div>
                        <div class="handoff-drill-row">
                            <span class="handoff-drill-label">Has Finance</span>
                            <span class="handoff-drill-value" style="color:${signals.has_finance ? 'var(--green-400)' : 'var(--slate-500)'}">${signals.has_finance ? 'Yes' : 'No'}</span>
                        </div>
                        <div class="handoff-drill-row">
                            <span class="handoff-drill-label">Discovery Sources</span>
                            <span class="handoff-drill-value">${signals.discovery_source_count || 0}</span>
                        </div>
                    </div>
                    
                    <div class="handoff-drill-section">
                        <div class="handoff-drill-section-title">SOR Classification</div>
                        <div class="handoff-drill-row">
                            <span class="handoff-drill-label">Domain</span>
                            <span class="handoff-drill-value">${sorTagging.domain || 'Not classified'}</span>
                        </div>
                        <div class="handoff-drill-row">
                            <span class="handoff-drill-label">Confidence</span>
                            <span class="handoff-drill-value">${sorTagging.confidence || '-'}</span>
                        </div>
                        <div style="margin-top:0.5rem;">
                            <span class="handoff-drill-label">Evidence</span>
                            ${evidenceHtml}
                        </div>
                    </div>
                    
                    <div class="handoff-drill-section">
                        <div class="handoff-drill-section-title">Findings (${findings.length})</div>
                        ${findingsHtml}
                    </div>
                </div>
            `;
        }
        
        function hideHandoffDrill() {
            const panel = document.getElementById('handoffDrillPanel');
            const container = document.getElementById('handoffCandidatesContainer');
            if (panel) panel.classList.add('hidden');
            if (container) container.classList.remove('hidden');
        }
        
        async function exportToAAM() {
            const runId = document.getElementById('handoffRunSelect').value;
            const statusFilter = document.getElementById('handoffStatusFilter').value;
            const exportBtn = document.getElementById('exportToAAMBtn');

            if (!runId) {
                showToast('Please select a snapshot first', 'error');
                return;
            }

            exportBtn.disabled = true;
            exportBtn.textContent = 'Exporting...';

            try {
                const response = await fetch(`/api/handoff/aam/export?run_id=${runId}&status_filter=${statusFilter}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });

                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.detail || `Export failed: ${response.status}`);
                }

                showToast(`Exported ${data.candidates_sent} candidates to AAM`, 'success');
                console.log('AAM export response:', data);
            } catch (err) {
                console.error('Failed to export to AAM:', err);
                showToast(`Export failed: ${err.message}`, 'error');
            } finally {
                exportBtn.disabled = false;
                exportBtn.textContent = 'Export to AAM';
            }
        }

        async function loadFabricAudit(runId) {
            const auditPanel = document.getElementById('fabricAuditPanel');
            const candidatesSection = document.getElementById('handoffCandidatesContainer').closest('.section');
            const farmMetadata = document.querySelector('.farm-metadata-section');
            const tableBody = document.getElementById('fabricAuditTableBody');

            if (!auditPanel || !tableBody) {
                console.error('Fabric audit elements not found');
                return;
            }

            // Show audit panel, hide other sections
            auditPanel.classList.remove('hidden');
            if (candidatesSection) candidatesSection.style.display = 'none';
            if (farmMetadata) farmMetadata.style.display = 'none';

            tableBody.innerHTML = '<tr><td colspan="6" class="loading"><div class="spinner"></div> Loading audit data...</td></tr>';

            try {
                const response = await fetch(`/api/handoff/fabric-allocation-audit/${runId}`);

                if (!response.ok) {
                    throw new Error(`Failed to load audit: ${response.status}`);
                }

                const data = await response.json();
                const summary = data.summary || {};
                const decisions = data.decisions || [];

                // Update summary stats
                document.getElementById('auditTotalScanned').textContent = summary.total_assets_scanned || 0;
                document.getElementById('auditRoutedTier1').textContent = summary.routed_tier_1 || 0;
                document.getElementById('auditRoutedTier2').textContent = summary.routed_tier_2 || 0;
                document.getElementById('auditRoutedTier3').textContent = summary.routed_tier_3 || 0;
                document.getElementById('auditNotRouted').textContent = summary.not_routed || 0;
                document.getElementById('auditShadow').textContent = summary.shadow_detected || 0;
                document.getElementById('auditContradictions').textContent = summary.contradictions_flagged || 0;
                document.getElementById('auditMultiPlane').textContent = summary.multi_plane_sors || 0;

                // Render decisions table
                if (decisions.length === 0) {
                    tableBody.innerHTML = '<tr><td colspan="6" class="empty-state">No allocation decisions found</td></tr>';
                    return;
                }

                tableBody.innerHTML = decisions.map(d => {
                    const decisionClass = {
                        'Routed': 'decision-routed',
                        'Not Routed': 'decision-not-routed',
                        'Shadow Detected': 'decision-shadow',
                        'Contradicted': 'decision-contradicted'
                    }[d.decision] || '';

                    const decisionColor = {
                        'Routed': 'var(--green-400)',
                        'Not Routed': 'var(--gray-400)',
                        'Shadow Detected': 'var(--purple-400)',
                        'Contradicted': 'var(--red-400)'
                    }[d.decision] || 'var(--slate-400)';

                    const tierColor = {
                        'Tier 1': 'var(--green-400)',
                        'Tier 2': 'var(--cyan-400)',
                        'Tier 3': 'var(--amber-400)'
                    }[d.evidence_tier] || 'var(--gray-400)';

                    const confidence = d.confidence !== null ? (d.confidence * 100).toFixed(0) + '%' : '—';

                    return `
                        <tr class="${decisionClass}">
                            <td><span style="color:${decisionColor};font-weight:500;">${d.decision}</span></td>
                            <td style="font-weight:500;">${d.asset_name}</td>
                            <td>${d.plane_assigned || '—'}</td>
                            <td><span style="color:${tierColor};">${d.evidence_tier || '—'}</span></td>
                            <td>${confidence}</td>
                            <td style="font-size:0.8rem;color:var(--slate-300);">${d.rationale}</td>
                        </tr>
                    `;
                }).join('');

            } catch (err) {
                console.error('Failed to load fabric audit:', err);
                tableBody.innerHTML = `<tr><td colspan="6" class="error-message">Failed to load audit: ${err.message}</td></tr>`;
            }
        }

        function hideFabricAudit() {
            const auditPanel = document.getElementById('fabricAuditPanel');
            const candidatesSection = document.getElementById('handoffCandidatesContainer').closest('.section');
            const farmMetadata = document.querySelector('.farm-metadata-section');

            if (auditPanel) auditPanel.classList.add('hidden');
            if (candidatesSection) candidatesSection.style.display = '';
            if (farmMetadata) farmMetadata.style.display = '';
        }

        async function downloadAuditReport(runId) {
            const downloadBtn = document.getElementById('downloadAuditReportBtn');
            if (downloadBtn) {
                downloadBtn.disabled = true;
                downloadBtn.textContent = 'Generating...';
            }

            try {
                const response = await fetch(`/api/handoff/fabric-allocation-audit/${runId}`);
                if (!response.ok) {
                    throw new Error(`Failed to fetch audit: ${response.status}`);
                }

                const data = await response.json();
                const summary = data.summary || {};
                const decisions = data.decisions || [];
                const timestamp = new Date().toISOString().split('T')[0];

                // Generate Plain English Report
                let plainEnglish = `FABRIC ALLOCATION AUDIT REPORT
Generated: ${new Date().toLocaleString()}
Run ID: ${runId}

═══════════════════════════════════════════════════════════════════════════════
EXECUTIVE SUMMARY
═══════════════════════════════════════════════════════════════════════════════

Total Assets Scanned: ${summary.total_assets_scanned || 0}

ROUTING BREAKDOWN:
  • Tier 1 (Direct Crawl):    ${summary.routed_tier_1 || 0} assets
    These were found directly in fabric plane admin APIs (Workato recipes,
    Kong services, Snowflake schemas). Highest confidence evidence.

  • Tier 2 (Observed):        ${summary.routed_tier_2 || 0} assets
    These have documented evidence from CMDB, network traffic, or cloud
    resource associations. Strong evidence but not directly verified.

  • Tier 3 (Inferred):        ${summary.routed_tier_3 || 0} assets
    These are inferred from indirect signals. Lower confidence, may need
    manual verification.

  • Not Routed:               ${summary.not_routed || 0} assets
    No fabric plane routing evidence found. These assets may use direct
    point-to-point connections or unmanaged integrations.

ISSUES DETECTED:
  • Shadow Assets:            ${summary.shadow_detected || 0}
    Found in fabric planes but NOT in IdP/CMDB. These are governance gaps.

  • Contradictions:           ${summary.contradictions_flagged || 0}
    Conflicting evidence from different sources. Requires investigation.

  • Multi-Plane SORs:         ${summary.multi_plane_sors || 0}
    Assets routed through multiple fabric planes simultaneously.

═══════════════════════════════════════════════════════════════════════════════
ALLOCATION DECISIONS
═══════════════════════════════════════════════════════════════════════════════

`;
                // Group decisions by type
                const routed = decisions.filter(d => d.decision === 'Routed');
                const notRouted = decisions.filter(d => d.decision === 'Not Routed');
                const shadow = decisions.filter(d => d.decision === 'Shadow Detected');
                const contradicted = decisions.filter(d => d.decision === 'Contradicted');

                if (routed.length > 0) {
                    plainEnglish += `\n--- ROUTED ASSETS (${routed.length}) ---\n\n`;
                    routed.forEach(d => {
                        plainEnglish += `  ${d.asset_name}\n`;
                        plainEnglish += `    → ${d.plane_assigned || 'Unknown'} | ${d.evidence_tier || 'N/A'} | ${d.confidence ? (d.confidence * 100).toFixed(0) + '%' : 'N/A'}\n`;
                        plainEnglish += `    ${d.rationale}\n\n`;
                    });
                }

                if (shadow.length > 0) {
                    plainEnglish += `\n--- SHADOW ASSETS (${shadow.length}) ---\n`;
                    plainEnglish += `These assets are routing through fabric planes but are NOT governed.\n\n`;
                    shadow.forEach(d => {
                        plainEnglish += `  ⚠ ${d.asset_name}\n`;
                        plainEnglish += `    → ${d.plane_assigned || 'Unknown'} | ${d.evidence_tier || 'N/A'}\n`;
                        plainEnglish += `    ${d.rationale}\n\n`;
                    });
                }

                if (contradicted.length > 0) {
                    plainEnglish += `\n--- CONTRADICTIONS (${contradicted.length}) ---\n`;
                    plainEnglish += `These assets have conflicting evidence. Manual review required.\n\n`;
                    contradicted.forEach(d => {
                        plainEnglish += `  ✗ ${d.asset_name}\n`;
                        plainEnglish += `    → ${d.plane_assigned || 'Unknown'}\n`;
                        plainEnglish += `    ${d.rationale}\n\n`;
                    });
                }

                if (notRouted.length > 0) {
                    plainEnglish += `\n--- NOT ROUTED (${notRouted.length}) ---\n`;
                    plainEnglish += `No fabric plane evidence found for these assets.\n\n`;
                    notRouted.forEach(d => {
                        plainEnglish += `  - ${d.asset_name}\n`;
                    });
                }

                // Generate Technical Report (JSON)
                const technicalReport = {
                    report_type: 'fabric_allocation_audit',
                    generated_at: new Date().toISOString(),
                    run_id: runId,
                    summary: summary,
                    decisions: decisions,
                    methodology: {
                        tier_1: {
                            name: 'Direct Crawl',
                            confidence_range: '0.90 - 0.95',
                            description: 'Evidence obtained directly from fabric plane admin APIs'
                        },
                        tier_2: {
                            name: 'Observed',
                            confidence_range: '0.60 - 0.89',
                            description: 'Evidence from CMDB, network traffic, or cloud resources'
                        },
                        tier_3: {
                            name: 'Inferred',
                            confidence_range: '0.30 - 0.59',
                            description: 'Evidence inferred from indirect signals'
                        }
                    }
                };

                // Combine both reports
                const fullReport = `${plainEnglish}

═══════════════════════════════════════════════════════════════════════════════
TECHNICAL DETAILS (JSON)
═══════════════════════════════════════════════════════════════════════════════

${JSON.stringify(technicalReport, null, 2)}
`;

                // Create and download file
                const blob = new Blob([fullReport], { type: 'text/plain' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `fabric-audit-${runId.substring(0, 8)}-${timestamp}.txt`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);

                showToast('Audit report downloaded', 'success');
            } catch (err) {
                console.error('Failed to download audit report:', err);
                showToast(`Download failed: ${err.message}`, 'error');
            } finally {
                if (downloadBtn) {
                    downloadBtn.disabled = false;
                    downloadBtn.textContent = 'Download Report';
                }
            }
        }

        function showDecisionDetail(assetKey) {
                const t = decisionTracesCache[assetKey];
                if (!t) return;
                
                const detailDiv = document.getElementById('decisionTraceDetail');
                detailDiv.style.display = 'block';
                
                const boolVal = (v) => `<span style="color:${v ? 'var(--cyan-400)' : 'var(--red-400)'};">${v ? 'true' : 'false'}</span>`;
                const tagColors = {
                    'HAS_DISCOVERY': 'var(--cyan-600)', 'NO_IDP': 'var(--red-500)', 'NO_CMDB': 'var(--red-500)',
                    'HAS_FINANCE': 'var(--green-600)', 'HAS_ONGOING_FINANCE': 'var(--green-600)',
                    'RECENT_ACTIVITY': 'var(--purple-600)', 'HAS_IDP': 'var(--green-600)', 'HAS_CMDB': 'var(--green-600)'
                };
                
                let reasonTags = (t.reason_codes || []).map(code => {
                    const bg = tagColors[code] || 'var(--slate-600)';
                    return `<span style="display:inline-block;padding:0.25rem 0.5rem;margin:0.125rem;border-radius:4px;background:${bg};color:white;font-size:0.75rem;">${code}</span>`;
                }).join('');
                
                let html = `
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem;">
                        <h3 style="margin:0;color:var(--cyan-400);font-size:1.25rem;">Decision Trace: ${assetKey}</h3>
                        <button onclick="document.getElementById('decisionTraceDetail').style.display='none'" style="background:none;border:none;color:var(--slate-400);cursor:pointer;font-size:1.25rem;">&times;</button>
                    </div>
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:2rem;">
                        <div>
                            <h4 style="color:var(--cyan-400);margin:0 0 1rem 0;font-size:1rem;">AOD Decision Trace</h4>
                            <table style="width:100%;font-size:0.875rem;">
                                <tr><td style="padding:0.5rem 0;color:var(--slate-400);">asset_key_used:</td><td style="color:white;text-align:right;">${t.asset_key_used}</td></tr>
                                <tr><td style="padding:0.5rem 0;color:var(--slate-400);">registered_domain:</td><td style="color:white;text-align:right;">${t.registered_domain || ''}</td></tr>
                                <tr><td style="padding:0.5rem 0;color:var(--slate-400);">raw_domains_seen:</td><td style="color:white;text-align:right;">${JSON.stringify(t.raw_domains_seen || [])}</td></tr>
                                <tr><td style="padding:0.5rem 0;color:var(--slate-400);">is_external:</td><td style="text-align:right;">${boolVal(t.is_external)}</td></tr>
                                <tr><td style="padding:0.5rem 0;color:var(--slate-400);">is_active:</td><td style="text-align:right;">${boolVal(t.is_active)}</td></tr>
                                <tr><td style="padding:0.5rem 0;color:var(--slate-400);">activity_window_days:</td><td style="color:white;text-align:right;">${t.activity_window_days}</td></tr>
                                <tr><td style="padding:0.5rem 0;color:var(--slate-400);">activity_source:</td><td style="color:white;text-align:right;">${t.activity_source || ''}</td></tr>
                                <tr><td style="padding:0.5rem 0;color:var(--slate-400);">latest_activity_at:</td><td style="color:white;text-align:right;font-size:0.75rem;">${t.latest_activity_at || ''}</td></tr>
                                <tr><td style="padding:0.5rem 0;color:var(--slate-400);">idp_present:</td><td style="text-align:right;">${boolVal(t.idp_present)}</td></tr>
                                <tr><td style="padding:0.5rem 0;color:var(--slate-400);">cmdb_present:</td><td style="text-align:right;">${boolVal(t.cmdb_present)}</td></tr>
                                <tr><td style="padding:0.5rem 0;color:var(--slate-400);">infra_excluded:</td><td style="text-align:right;">${boolVal(t.infra_excluded)}</td></tr>
                                <tr><td style="padding:0.5rem 0;color:var(--slate-400);">is_shadow:</td><td style="text-align:right;">${boolVal(t.is_shadow)}</td></tr>
                                <tr><td style="padding:0.5rem 0;color:var(--slate-400);vertical-align:top;">reason_codes:</td><td style="text-align:right;">${reasonTags}</td></tr>
                            </table>
                        </div>
                        <div>
                            <h4 style="color:var(--slate-400);margin:0 0 1rem 0;font-size:1rem;">Farm Decision Trace</h4>
                            <p style="color:var(--slate-500);font-size:0.875rem;">Paste Farm's trace JSON here for comparison</p>
                            <textarea id="farmTraceInput" style="width:100%;height:200px;background:var(--slate-900);border:1px solid var(--slate-600);border-radius:4px;color:var(--slate-300);padding:0.75rem;font-family:'Fira Code',monospace;font-size:0.75rem;resize:vertical;" placeholder='{"asset_key_used": "...", ...}'></textarea>
                            <button class="btn btn-primary" style="margin-top:0.75rem;" onclick="compareFarmTrace('${assetKey.replace(/'/g, "\\'")}')">Compare</button>
                            <div id="farmCompareResult"></div>
                        </div>
                    </div>
                `;
            detailDiv.innerHTML = html;
            detailDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
        
        function compareFarmTrace(assetKey) {
            const aod = decisionTracesCache[assetKey];
            const farmInput = document.getElementById('farmTraceInput').value.trim();
            const resultDiv = document.getElementById('farmCompareResult');
            
            if (!farmInput) {
                resultDiv.innerHTML = '<p style="color:var(--red-400);margin-top:0.5rem;">Paste Farm trace JSON first</p>';
                return;
            }
            
            try {
                const farm = JSON.parse(farmInput);
                const fields = ['asset_key_used','registered_domain','is_external','is_active','activity_window_days','activity_source','idp_present','cmdb_present','infra_excluded','is_shadow'];
                let diffs = [];
                
                for (const f of fields) {
                    const aodVal = JSON.stringify(aod[f]);
                    const farmVal = JSON.stringify(farm[f]);
                    if (aodVal !== farmVal) {
                        diffs.push(`<tr><td style="color:var(--red-400);">${f}</td><td>${farmVal}</td><td>${aodVal}</td></tr>`);
                    }
                }
                
                if (diffs.length === 0) {
                    decisionMismatches[assetKey] = false;
                    resultDiv.innerHTML = '<p style="color:var(--green-400);margin-top:0.75rem;">All fields match!</p>';
                } else {
                    decisionMismatches[assetKey] = true;
                    resultDiv.innerHTML = `<table style="width:100%;margin-top:0.75rem;font-size:0.8rem;"><tr style="color:var(--slate-400);"><th>Field</th><th>Farm</th><th>AOD</th></tr>${diffs.join('')}</table>`;
                }
            } catch (e) {
                resultDiv.innerHTML = `<p style="color:var(--red-400);margin-top:0.5rem;">Invalid JSON: ${e.message}</p>`;
            }
        }
        
        function safeStr(value, maxLen = 200) {
            if (value === null || value === undefined) return 'N/A';
            const str = String(value);
            if (str.length <= maxLen) return escapeHtml(str);
            return escapeHtml(str.slice(0, maxLen)) + '...';
        }
        
        function safeJsonPreview(obj, maxLen = 5000) {
            if (obj === null || obj === undefined) return 'null';
            try {
                const str = JSON.stringify(obj, null, 2);
                if (str.length <= maxLen) return escapeHtml(str);
                return escapeHtml(str.slice(0, maxLen)) + '\n... [truncated]';
            } catch (e) {
                return '[Error serializing object]';
            }
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        function formatDrillValue(value, field) {
            if (field === 'triage_priority') {
                if (!value || value === 'unknown' || value === null || value === undefined) {
                    return `<span class="priority-badge priority-p2">Unrated (Legacy)</span>`;
                }
                const priorityLabels = { 'p0': 'P0 - Critical', 'p1': 'P1 - High', 'p2': 'P2 - Medium' };
                const priorityClass = `priority-${value}`;
                return `<span class="priority-badge ${priorityClass}">${priorityLabels[value] || value.toUpperCase()}</span>`;
            }
            if (value === 'unknown' || value === null || value === undefined) {
                const fieldLabel = field.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                return `Unknown ${fieldLabel}`;
            }
            const friendlyLabels = {
                'identity_access': 'Identity & Access',
                'shadow_it': 'Shadow IT (Financial)',
                'data_integrity': 'Data Integrity',
                'visibility_gap': 'Visibility Gaps',
                'governance_hygiene': 'Governance Hygiene',
                'security_risk': 'Security Risks',
                'governance_finding': 'Governance & Data Quality',
                'identity_gap': 'Identity Gap',
                'finance_gap': 'Finance Gap',
                'data_conflict': 'Data Conflict',
                'cmdb_gap': 'CMDB Gap',
                'governance_gap': 'Governance Gap',
                'duplication_risk': 'Duplication Risk'
            };
            return friendlyLabels[value] || value;
        }
        
        function copyToClipboard(text) {
            navigator.clipboard.writeText(text).then(() => {
                const btn = document.querySelector('.copy-json-btn');
                if (btn) {
                    const original = btn.textContent;
                    btn.textContent = 'Copied!';
                    setTimeout(() => btn.textContent = original, 1500);
                }
            });
        }
        
        const DRILL_SCHEMA = {
            entities: {
                assets: {
                    fields: {
                        name: { default: 'unknown' },
                        asset_type: { default: 'unknown' },
                        vendor: { default: 'unknown' },
                        vendor_hypothesis: { default: null },
                        environment: { default: 'unknown' },
                        lens_status: { 
                            default: { idp: 'unmatched', cmdb: 'unmatched', cloud: 'unmatched', finance: 'unmatched' }
                        },
                        identifiers: { default: {} },
                        deterministic_id: { default: 'unknown' }
                    },
                    drillPaths: ['asset_type', 'vendor', 'environment'],
                    displayName: 'Assets'
                },
                security_risks: {
                    fields: {
                        finding_type: { default: 'unknown' },
                        category: { default: 'identity_access' },
                        severity: { default: 'unknown' },
                        explanation: { default: 'No explanation available' },
                        asset_id: { default: null },
                        created_at: { default: null }
                    },
                    drillPaths: ['finding_type'],
                    displayName: 'Security Risks'
                },
                governance_hygiene: {
                    fields: {
                        finding_type: { default: 'governance_gap' },
                        category: { default: 'governance_hygiene' },
                        explanation: { default: 'No explanation available' },
                        asset_id: { default: null },
                        created_at: { default: null }
                    },
                    drillPaths: ['finding_type'],
                    displayName: 'Governance'
                },
                artifacts: {
                    fields: {
                        artifact_type: { default: 'unknown' },
                        source_lens: { default: 'unknown' },
                        asset_id: { default: null },
                        data: { default: {} }
                    },
                    drillPaths: ['artifact_type', 'source_lens'],
                    displayName: 'Artifacts'
                },
                observations: {
                    fields: {
                        name: { default: 'unknown' },
                        domain: { default: null },
                        source: { default: 'unknown' },
                        category: { default: null }
                    },
                    drillPaths: ['source', 'category'],
                    displayName: 'Observations'
                },
                validated: {
                    fields: {
                        name: { default: 'unknown' },
                        domain: { default: null },
                        source: { default: 'unknown' },
                        category: { default: null }
                    },
                    drillPaths: ['source', 'category'],
                    displayName: 'Validated Observations'
                },
                ambiguous: {
                    fields: {
                        entity_name: { default: 'unknown' },
                        plane: { default: 'unknown' },
                        explanation: { default: 'No explanation available' },
                        candidate_names: { default: [] }
                    },
                    drillPaths: ['plane'],
                    displayName: 'Ambiguous Matches'
                },
                rejections: {
                    fields: {
                        entity_name: { default: 'unknown' },
                        reason_code: { default: 'unknown' },
                        reason_detail: { default: 'No details available' }
                    },
                    drillPaths: ['reason_code'],
                    displayName: 'Rejections'
                },
                shadow: {
                    fields: {
                        name: { default: 'unknown' },
                        vendor: { default: 'unknown' },
                        vendor_hypothesis: { default: null },
                        asset_type: { default: 'unknown' },
                        environment: { default: 'unknown' },
                        reason: { default: 'No reason available' },
                        evidence_summary: { default: [] }
                    },
                    drillPaths: ['asset_type', 'vendor'],
                    displayName: 'Shadow Assets'
                },
                zombie: {
                    fields: {
                        name: { default: 'unknown' },
                        vendor: { default: 'unknown' },
                        vendor_hypothesis: { default: null },
                        asset_type: { default: 'unknown' },
                        environment: { default: 'unknown' },
                        reason: { default: 'No reason available' },
                        evidence_summary: { default: [] }
                    },
                    drillPaths: ['asset_type', 'vendor'],
                    displayName: 'Zombie Assets'
                },
                fabric_planes: {
                    fields: {
                        plane_id: { default: 'unknown' },
                        plane_type: { default: 'unknown' },
                        vendor: { default: 'unknown' },
                        display_name: { default: 'Unknown Plane' },
                        managed_asset_count: { default: 0 },
                        sample_assets: { default: [] }
                    },
                    drillPaths: ['plane_type', 'vendor'],
                    displayName: 'Fabric Planes'
                },
                sor: {
                    fields: {
                        name: { default: 'unknown' },
                        vendor: { default: 'unknown' },
                        sor_likelihood: { default: 'unknown' },
                        sor_confidence: { default: 0 },
                        sor_domain: { default: null },
                        sor_evidence: { default: [] }
                    },
                    drillPaths: ['sor_likelihood', 'sor_domain'],
                    displayName: 'Systems of Record'
                }
            },
            summaryCardMappings: {
                statAssets: 'assets',
                statSecurityRisks: 'security_risks',
                statGovernanceHygiene: 'governance_hygiene',
                statObservations: 'observations',
                statRejected: 'rejections',
                statShadow: 'shadow',
                statZombie: 'zombie',
                statFabricPlanes: 'fabric_planes',
                statSOR: 'sor'
            }
        };
        
        function normalizeResponse(type, data) {
            const errors = [];
            const schema = DRILL_SCHEMA.entities[type];
            
            if (!schema) {
                errors.push(`Unknown entity type: ${type}`);
                return { data: [], errors };
            }
            
            if (!Array.isArray(data)) {
                errors.push(`Expected array for ${type}, got ${typeof data}`);
                return { data: [], errors };
            }
            
            const normalized = data.map((item, index) => {
                const result = {};
                try {
                    for (const [field, config] of Object.entries(schema.fields)) {
                        const value = item?.[field];
                        if (value === undefined || value === null || value === '') {
                            if (typeof config.default === 'object' && config.default !== null) {
                                result[field] = JSON.parse(JSON.stringify(config.default));
                            } else {
                                result[field] = config.default;
                            }
                        } else if (typeof config.default === 'object' && config.default !== null && typeof value === 'object') {
                            result[field] = { ...JSON.parse(JSON.stringify(config.default)), ...value };
                        } else {
                            result[field] = value;
                        }
                    }
                    Object.keys(item || {}).forEach(key => {
                        if (!(key in result)) result[key] = item[key];
                    });
                } catch (e) {
                    errors.push(`Error normalizing ${type}[${index}]: ${e.message}`);
                    for (const [field, config] of Object.entries(schema.fields)) {
                        result[field] = typeof config.default === 'object' && config.default !== null
                            ? JSON.parse(JSON.stringify(config.default))
                            : config.default;
                    }
                }
                return result;
            });
            
            return { data: normalized, errors };
        }
        
        function executeDrill({ rootType, filters = {}, level = 0 }) {
            const schema = DRILL_SCHEMA.entities[rootType];
            if (!schema) {
                return { items: [], nextDrillOptions: [], canDrillFurther: false, error: `Unknown type: ${rootType}` };
            }
            
            const sourceData = normalizedData[rootType] || [];
            let filtered = sourceData;
            
            for (const [key, value] of Object.entries(filters)) {
                filtered = filtered.filter(item => (item[key] ?? 'unknown') === value);
            }
            
            const drillPaths = schema.drillPaths || [];
            const usedFields = Object.keys(filters);
            const availablePaths = drillPaths.filter(p => !usedFields.includes(p));
            
            if (filtered.length <= 1 || availablePaths.length === 0) {
                return { items: filtered, nextDrillOptions: [], canDrillFurther: false };
            }
            
            const nextField = availablePaths[0];
            const groups = {};
            filtered.forEach(item => {
                const val = item[nextField] ?? 'unknown';
                groups[val] = groups[val] || [];
                groups[val].push(item);
            });
            
            const nextDrillOptions = Object.entries(groups).map(([value, items]) => ({
                field: nextField,
                value,
                count: items.length,
                canDrillDeeper: availablePaths.length > 1 || items.length > 1
            }));
            
            return {
                items: filtered,
                nextDrillOptions: nextDrillOptions.sort((a, b) => b.count - a.count),
                canDrillFurther: true,
                groupField: nextField
            };
        }
        
        function pushDrill(drillState) {
            drillStack.push(drillState);
            renderDrillPanel();
        }
        
        function popDrill() {
            if (drillStack.length > 0) {
                drillStack.pop();
                if (drillStack.length === 0) {
                    hideDrillPanel();
                } else {
                    renderDrillPanel();
                }
            }
        }
        
        function navigateToDrillLevel(level) {
            while (drillStack.length > level + 1) {
                drillStack.pop();
            }
            if (drillStack.length === 0) {
                hideDrillPanel();
            } else {
                renderDrillPanel();
            }
        }
        
        function hideDrillPanel() {
            drillStack = [];
            document.getElementById('drillPanel').classList.add('hidden');
        }
        
        function showDrillError(message) {
            const errorEl = document.getElementById('drillError');
            errorEl.textContent = message;
            errorEl.classList.remove('hidden');
        }
        
        function hideDrillError() {
            document.getElementById('drillError').classList.add('hidden');
        }
        
        function renderDrillPanel() {
            if (drillStack.length === 0) {
                hideDrillPanel();
                return;
            }
            
            hideDrillError();
            const panel = document.getElementById('drillPanel');
            const titleEl = document.getElementById('drillPanelTitle');
            const breadcrumbEl = document.getElementById('drillBreadcrumb');
            const contentEl = document.getElementById('drillContent');
            
            const currentState = drillStack[drillStack.length - 1];
            const schema = DRILL_SCHEMA.entities[currentState.rootType];
            const displayName = schema?.displayName || currentState.rootType;
            
            titleEl.textContent = `Drill Down: ${displayName}`;
            
            const catalogLinkEl = document.getElementById('drillCatalogLink');
            if (currentState.rootType === 'assets' && currentRunId) {
                catalogLinkEl.innerHTML = `
                    <a href="/api/catalog/view?run_id=${currentRunId}" target="_blank" 
                       style="font-size: 0.8rem; color: var(--cyan-400); text-decoration: none; display: flex; align-items: center; gap: 0.35rem;">
                        <span>View Full Catalog</span>
                        <span style="font-size: 0.7rem;">↗</span>
                    </a>`;
                catalogLinkEl.classList.remove('hidden');
            } else {
                catalogLinkEl.classList.add('hidden');
            }
            
            let breadcrumbHtml = `<span class="breadcrumb-item" onclick="navigateToDrillLevel(-1)">${displayName}</span>`;
            drillStack.forEach((state, index) => {
                if (Object.keys(state.filters).length > 0) {
                    const lastFilter = Object.entries(state.filters).pop();
                    const [filterField, filterValue] = lastFilter;
                    breadcrumbHtml += `<span class="breadcrumb-sep">›</span>`;
                    breadcrumbHtml += `<span class="breadcrumb-item${index === drillStack.length - 1 ? ' active' : ''}" onclick="navigateToDrillLevel(${index})">${formatDrillValue(filterValue, filterField)}</span>`;
                }
            });
            breadcrumbEl.innerHTML = breadcrumbHtml;
            
            const result = executeDrill(currentState);
            
            if (result.error) {
                showDrillError(result.error);
                contentEl.innerHTML = '';
                panel.classList.remove('hidden');
                return;
            }
            
            if (result.items.length === 0) {
                contentEl.innerHTML = '<div class="drill-no-data">No items found matching the current filters.</div>';
                panel.classList.remove('hidden');
                return;
            }
            
            let catalogBanner = '';
            if (currentState.rootType === 'assets' && drillStack.length === 1) {
                const runInfo = catalogData ? `Run: ${catalogData.tenant_id || 'Unknown'} • ${catalogData.completed_at ? new Date(catalogData.completed_at).toLocaleDateString() : ''}` : '';
                catalogBanner = `
                    <div style="background: rgba(6, 182, 212, 0.1); border: 1px solid var(--cyan-600); border-radius: 8px; padding: 0.75rem 1rem; margin-bottom: 1rem; display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <div style="font-size: 0.85rem; font-weight: 600; color: var(--cyan-400);">Asset Catalog for this Discovery Run</div>
                            <div style="font-size: 0.75rem; color: var(--slate-400);">${result.items.length} assets cataloged • ${runInfo}</div>
                        </div>
                        <div style="display: flex; gap: 0.5rem;">
                            <a href="/api/catalog/view?run_id=${currentRunId}" target="_blank" class="btn btn-secondary" style="font-size: 0.8rem; padding: 0.4rem 0.75rem;">
                                Full Catalog ↗
                            </a>
                            <a href="/api/catalog?run_id=${currentRunId}" target="_blank" class="btn btn-secondary" style="font-size: 0.8rem; padding: 0.4rem 0.75rem; opacity: 0.7;">
                                JSON
                            </a>
                        </div>
                    </div>`;
            }
            
            if (!result.canDrillFurther || result.nextDrillOptions.length === 0) {
                contentEl.innerHTML = catalogBanner + renderDetailView(currentState.rootType, result.items);
            } else {
                contentEl.innerHTML = catalogBanner + renderGroupView(currentState.rootType, result.nextDrillOptions, result.groupField);
            }
            
            panel.classList.remove('hidden');
        }
        
        function renderGroupView(rootType, options, groupField) {
            const fieldLabel = groupField.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
            return options.map(opt => `
                <div class="drill-group" onclick="drillIntoGroup('${rootType}', '${opt.field}', '${opt.value.replace(/'/g, "\\'")}')">
                    <div class="drill-group-header">
                        <span class="drill-group-label">${formatDrillValue(opt.value, opt.field)}</span>
                        <span class="drill-group-count">${opt.count} item${opt.count !== 1 ? 's' : ''}</span>
                    </div>
                    <div class="drill-group-hint">${opt.canDrillDeeper ? 'Click to drill deeper' : 'Click to view details'}</div>
                </div>
            `).join('');
        }
        
        function renderDetailView(rootType, items) {
            if (items.length === 0) {
                return '<div class="drill-no-data">No further details available.</div>';
            }
            
            const schema = DRILL_SCHEMA.entities[rootType];
            if (!schema) {
                return '<div class="drill-no-data">Unknown entity type.</div>';
            }
            
            detailPagination.items = items;
            detailPagination.rootType = rootType;
            detailPagination.itemIndex = 0;
            
            return renderSingleItemDetail(items[0], rootType, 0, items.length);
        }
        
        function getPlainEnglishReason(reasonCode, reasonDetail) {
            const domainMention = reasonDetail?.split(':').pop()?.trim() || '';
            
            if (reasonDetail) {
                const detail = reasonDetail.toLowerCase();
                
                if (detail.includes('corporate root domain') || detail.includes('root domain')) {
                    return {
                        summary: `Traffic to "${domainMention}" was detected, but this is a vendor's main website — not a specific application.`,
                        whyRejected: `We saw network activity to ${domainMention}, which is the vendor's public homepage or marketing site. This root domain isn't a specific application instance — it's like visiting "salesforce.com" instead of "yourcompany.salesforce.com". Only tenant-specific subdomains (where your organization actually uses the service) are tracked as assets.`,
                        action: 'No',
                        actionDetail: `This is normal. If your team uses this vendor, look for tenant-specific domains in your catalog (e.g., "yourcompany.${domainMention}" or "app.${domainMention}"). If those are missing but expected, check if the subdomain traffic is being captured correctly.`
                    };
                }
                
                if (detail.includes('infrastructure') || detail.includes('internal')) {
                    return {
                        summary: `This is internal infrastructure, not a business application.`,
                        whyRejected: `We detected this as an internal system (like a server, database, or network service) rather than a software application your team uses directly.`,
                        action: 'No',
                        actionDetail: `Infrastructure components are managed separately from business applications. This keeps your asset catalog focused on the software tools your teams actually use.`
                    };
                }
            }
            
            if (reasonCode === 'admission_failed' || reasonCode === 'no_admission_evidence') {
                return {
                    summary: `We couldn't confirm this is a real application your organization uses.`,
                    whyRejected: `We saw some activity for this item, but we couldn't find it in any of your official systems — not in your IT inventory (CMDB), login system (IdP), cloud accounts, or financial records. Without at least one of these confirmations, we can't be sure it's a real business tool.`,
                    action: 'Maybe',
                    actionDetail: `If you recognize this as a legitimate tool your team uses, you may want to add it to your CMDB or IdP so it gets tracked properly next time. If you don't recognize it, it might just be noise and safe to ignore.`
                };
            }
            
            if (reasonCode === 'duplicate_entity') {
                return {
                    summary: `This was combined with another item to avoid double-counting.`,
                    whyRejected: `We found this item appears to be the same as another asset already in the catalog (same domain, same vendor, or matching identifiers). Instead of showing it twice, we merged them together.`,
                    action: 'No',
                    actionDetail: `This is normal housekeeping. The asset still exists in your catalog — just not as a separate entry. Check the main Assets list to find the merged record.`
                };
            }
            
            if (reasonCode === 'insufficient_activity') {
                return {
                    summary: `No recent usage was detected for this item.`,
                    whyRejected: `We found records mentioning this item, but there's no evidence anyone has actually used it recently. Without activity, we can't confirm it's still relevant.`,
                    action: 'Maybe',
                    actionDetail: `If this is something your team still uses, the usage data might not be flowing correctly. Otherwise, this might be an old or unused tool.`
                };
            }
            
            if (reasonCode === 'test_environment') {
                return {
                    summary: `This appears to be a test or sandbox environment.`,
                    whyRejected: `We identified this as a non-production environment (like a staging server or developer sandbox). Test environments are excluded from the production asset catalog.`,
                    action: 'No',
                    actionDetail: `This is expected behavior. Test environments are tracked separately to keep your production catalog clean and accurate.`
                };
            }
            
            return {
                summary: `This item didn't meet the criteria for inclusion in your asset catalog.`,
                whyRejected: reasonDetail || `The system determined this item should not be included based on the available evidence. This could be due to insufficient data, duplicate detection, or exclusion rules.`,
                action: 'Unlikely',
                actionDetail: `Review the raw data below if you need more details about why this specific item was excluded.`
            };
        }
        
        function renderSingleItemDetail(item, rootType, index, total) {
            const schema = DRILL_SCHEMA.entities[rootType];
            const name = item.name || item.entity_name || item.finding_type || item.artifact_type || 'Item';
            const plane = item.plane || item.source_lens || item.source || null;
            const itemType = item.asset_type || item.artifact_type || item.finding_type || item.reason_code || null;
            
            const keyFactFields = ['vendor', 'product', 'domain', 'environment', 'triage_priority', 'reason', 'explanation'];
            const keyFacts = [];
            keyFactFields.forEach(field => {
                if (item[field] !== undefined && item[field] !== null && typeof item[field] !== 'object') {
                    let displayValue = item[field];
                    if (field === 'vendor' && (displayValue === 'unknown' || !displayValue) && item.vendor_hypothesis) {
                        const hyp = item.vendor_hypothesis;
                        const conf = Math.round((hyp.confidence || 0) * 100);
                        displayValue = `Likely ${hyp.value} (${conf}% confidence, based on ${hyp.basis})`;
                    }
                    keyFacts.push({ label: field.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()), value: displayValue });
                }
            });
            
            if ((!item.vendor || item.vendor === 'unknown') && item.vendor_hypothesis) {
                const hyp = item.vendor_hypothesis;
                const conf = Math.round((hyp.confidence || 0) * 100);
                const existingVendor = keyFacts.find(f => f.label === 'Vendor');
                if (!existingVendor) {
                    keyFacts.unshift({ 
                        label: 'Vendor', 
                        value: `Likely ${hyp.value} (${conf}% confidence, based on ${hyp.basis})` 
                    });
                }
            }
            
            let rejectionExplanation = null;
            if (rootType === 'rejections' && item.reason_code) {
                rejectionExplanation = getPlainEnglishReason(item.reason_code, item.reason_detail);
            }
            
            if (item.lens_status && typeof item.lens_status === 'object') {
                const lenses = Object.entries(item.lens_status).map(([k, v]) => `${k}: ${v}`).join(', ');
                keyFacts.push({ label: 'Lens Status', value: lenses });
            }
            
            if (item.identifiers && typeof item.identifiers === 'object' && Object.keys(item.identifiers).length > 0) {
                const ids = Object.entries(item.identifiers).map(([k, v]) => `${k}: ${safeStr(v, 50)}`).join(', ');
                keyFacts.push({ label: 'Identifiers', value: ids });
            }
            
            let html = `<div class="drill-detail" style="padding: 1.25rem;">`;
            
            html += `<div class="item-detail-header">
                <div>
                    <div class="item-detail-title">${safeStr(name, 100)}</div>
                    <div class="item-detail-meta">
                        ${plane ? `<span class="item-detail-tag">${safeStr(plane, 30)}</span>` : ''}
                        ${itemType ? `<span class="item-detail-tag">${safeStr(itemType, 30)}</span>` : ''}
                    </div>
                </div>
                ${total > 1 ? `<div style="color: var(--slate-500); font-size: 0.8rem;">Item ${index + 1} of ${total}</div>` : ''}
            </div>`;
            
            if (rejectionExplanation) {
                const actionColor = rejectionExplanation.action === 'No' ? 'var(--green-400)' : 
                                   rejectionExplanation.action === 'Maybe' ? 'var(--amber-400)' : 'var(--slate-400)';
                html += `
                <div style="background: var(--slate-800); border-radius: 8px; padding: 1rem; margin-bottom: 1rem; border-left: 3px solid var(--cyan-500);">
                    <div style="font-size: 1rem; font-weight: 600; color: white; margin-bottom: 0.75rem;">${rejectionExplanation.summary}</div>
                    
                    <div style="margin-bottom: 0.75rem;">
                        <div style="font-size: 0.7rem; text-transform: uppercase; color: var(--slate-500); margin-bottom: 0.25rem;">Why was this rejected?</div>
                        <div style="font-size: 0.85rem; color: var(--slate-300); line-height: 1.5;">${rejectionExplanation.whyRejected}</div>
                    </div>
                    
                    <div style="background: var(--gray-900); border-radius: 6px; padding: 0.75rem; display: flex; gap: 0.75rem; align-items: flex-start;">
                        <div style="background: ${actionColor}; color: var(--gray-900); font-weight: 700; font-size: 0.7rem; padding: 0.2rem 0.5rem; border-radius: 4px; flex-shrink: 0;">ACTION NEEDED: ${rejectionExplanation.action.toUpperCase()}</div>
                        <div style="font-size: 0.8rem; color: var(--slate-400); line-height: 1.4;">${rejectionExplanation.actionDetail}</div>
                    </div>
                </div>`;
            }
            
            if (keyFacts.length > 0) {
                html += `<div class="key-facts-grid">`;
                keyFacts.forEach(fact => {
                    const isFullWidth = ['explanation', 'why rejected'].includes(fact.label.toLowerCase());
                    const maxLen = isFullWidth ? 1000 : 200;
                    html += `<div class="key-fact" ${isFullWidth ? 'style="grid-column: 1 / -1;"' : ''}><div class="key-fact-label">${fact.label}</div><div class="key-fact-value">${safeStr(fact.value, maxLen)}</div></div>`;
                });
                html += `</div>`;
            }
            
            const arrayFields = ['transactions', 'records', 'data', 'evidence_summary', 'candidate_names', 'raw_data'];
            arrayFields.forEach(field => {
                const arr = item[field];
                if (Array.isArray(arr) && arr.length > 0) {
                    html += renderRecordsTable(field, arr);
                } else if (field === 'data' && typeof arr === 'object' && arr !== null && !Array.isArray(arr)) {
                    const dataArrays = Object.entries(arr).filter(([k, v]) => Array.isArray(v) && v.length > 0);
                    dataArrays.forEach(([key, value]) => {
                        html += renderRecordsTable(key, value);
                    });
                }
            });
            
            const rawJson = JSON.stringify(item, null, 2);
            const jsonId = `rawJson_${index}`;
            html += `<div class="raw-json-section">
                <div class="raw-json-toggle" onclick="toggleRawJson('${jsonId}')">
                    <span id="${jsonId}_icon">▶</span> Raw JSON (advanced)
                </div>
                <div class="raw-json-content" id="${jsonId}">
                    <pre class="raw-json-pre">${safeJsonPreview(item, 5000)}</pre>
                    <button class="copy-json-btn" onclick="copyToClipboard(\`${rawJson.replace(/`/g, '\\`').replace(/\\/g, '\\\\')}\`)">Copy JSON</button>
                </div>
            </div>`;
            
            if (total > 1) {
                html += `<div class="pagination-controls">
                    <span class="pagination-info">Viewing item ${index + 1} of ${total}</span>
                    <div class="pagination-btns">
                        <button class="pagination-btn" onclick="navigateDetailItem(${index - 1})" ${index === 0 ? 'disabled' : ''}>← Prev</button>
                        <button class="pagination-btn" onclick="navigateDetailItem(${index + 1})" ${index >= total - 1 ? 'disabled' : ''}>Next →</button>
                    </div>
                </div>`;
            }
            
            html += `</div>`;
            return html;
        }
        
        function renderRecordsTable(title, records) {
            if (!records || records.length === 0) return '';
            
            const pageSize = 25;
            const pageId = `records_${title.replace(/\s+/g, '_')}`;
            
            let columns = [];
            if (typeof records[0] === 'object' && records[0] !== null) {
                columns = Object.keys(records[0]).slice(0, 6);
            }
            
            let html = `<div class="records-section" id="${pageId}_section">
                <div class="records-section-title">${title.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())} (${records.length})</div>`;
            
            if (columns.length > 0) {
                html += `<table class="records-table"><thead><tr>`;
                columns.forEach(col => {
                    html += `<th>${col.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</th>`;
                });
                html += `</tr></thead><tbody>`;
                
                const displayRecords = records.slice(0, pageSize);
                displayRecords.forEach(rec => {
                    html += `<tr>`;
                    columns.forEach(col => {
                        let val = rec[col];
                        if (typeof val === 'object' && val !== null) {
                            val = JSON.stringify(val);
                        }
                        html += `<td>${safeStr(val, 80)}</td>`;
                    });
                    html += `</tr>`;
                });
                html += `</tbody></table>`;
                
                if (records.length > pageSize) {
                    html += `<div class="pagination-info" style="margin-top: 0.5rem;">Showing ${pageSize} of ${records.length} records</div>`;
                }
            } else {
                const displayItems = records.slice(0, pageSize);
                html += `<div style="font-size: 0.85rem; color: var(--slate-400);">${displayItems.map(r => safeStr(r, 100)).join(', ')}</div>`;
                if (records.length > pageSize) {
                    html += `<div class="pagination-info" style="margin-top: 0.5rem;">Showing ${pageSize} of ${records.length} items</div>`;
                }
            }
            
            html += `</div>`;
            return html;
        }
        
        function toggleRawJson(id) {
            const content = document.getElementById(id);
            const icon = document.getElementById(id + '_icon');
            if (content) {
                content.classList.toggle('open');
                if (icon) icon.textContent = content.classList.contains('open') ? '▼' : '▶';
            }
        }
        
        function navigateDetailItem(newIndex) {
            if (newIndex < 0 || newIndex >= detailPagination.items.length) return;
            detailPagination.itemIndex = newIndex;
            const contentEl = document.getElementById('drillContent');
            if (contentEl) {
                contentEl.innerHTML = renderSingleItemDetail(
                    detailPagination.items[newIndex], 
                    detailPagination.rootType, 
                    newIndex, 
                    detailPagination.items.length
                );
            }
        }
        
        function drillIntoGroup(rootType, field, value) {
            const currentState = drillStack.length > 0 ? drillStack[drillStack.length - 1] : { rootType, filters: {}, level: 0 };
            const newFilters = { ...currentState.filters, [field]: value };
            pushDrill({ rootType, filters: newFilters, level: currentState.level + 1 });
        }
        
        async function loadDrillData(type, runId) {
            const endpointMap = {
                observations: `/api/runs/${runId}/observations?limit=500`,
                validated: `/api/runs/${runId}/observations?limit=500`,
                ambiguous: `/api/runs/${runId}/ambiguous?limit=500`,
                rejections: `/api/runs/${runId}/rejections?limit=500`
            };
            
            const endpoint = endpointMap[type];
            if (!endpoint) return;
            
            try {
                const r = await fetch(endpoint);
                if (!r.ok) {
                    console.error(`Failed to load ${type} drill data`);
                    normalizedData[type] = [];
                    return;
                }
                const data = await r.json();
                const items = data.items || [];
                const { data: normalized, errors } = normalizeResponse(type, items);
                normalizedData[type] = normalized;
                if (errors.length > 0) console.warn(`${type} normalization errors:`, errors);
            } catch (e) {
                console.error(`Error loading ${type} drill data:`, e);
                normalizedData[type] = [];
            }
        }
        
        async function initiateDrill(type) {
            if (!currentRunId) return;
            
            if (['observations', 'validated', 'ambiguous', 'rejections'].includes(type)) {
                await loadDrillData(type, currentRunId);
            }
            
            if (['shadow', 'zombie'].includes(type) && normalizedData[type].length === 0) {
                try {
                    const dr = await fetch(`/api/runs/${currentRunId}/derived`);
                    if (dr.ok) {
                        const derived = await dr.json();
                        const items = type === 'shadow' ? (derived.shadow_assets || []) : (derived.zombie_assets || []);
                        const { data: normalized } = normalizeResponse(type, items);
                        normalizedData[type] = normalized;
                    }
                } catch (e) { console.error(`Error loading ${type} drill data:`, e); }
            }
            
            const sourceData = normalizedData[type] || [];
            if (sourceData.length === 0) {
                drillStack = [];
                const panel = document.getElementById('drillPanel');
                const titleEl = document.getElementById('drillPanelTitle');
                const contentEl = document.getElementById('drillContent');
                const schema = DRILL_SCHEMA.entities[type];
                titleEl.textContent = `Drill Down: ${schema?.displayName || type}`;
                document.getElementById('drillBreadcrumb').innerHTML = '';
                contentEl.innerHTML = '<div class="drill-no-data">No drill data captured for this run.</div>';
                panel.classList.remove('hidden');
                return;
            }
            
            drillStack = [];
            pushDrill({ rootType: type, filters: {}, level: 0 });
        }
        
        const STATUS_CONFIG = {
            'completed_with_results': { type: 'success', label: 'Completed', explanation: 'Pipeline completed successfully with assets discovered.' },
            'completed_no_assets': { type: 'warning', label: 'No Assets', explanation: 'Pipeline completed but no assets met admission criteria.' },
            'completed': { type: 'success', label: 'Completed', explanation: 'Pipeline completed successfully.' },
            'upstream_error': { type: 'error', label: 'Upstream Error', explanation: 'Failed to fetch data from Farm (server unreachable, non-JSON response, or HTTP error).' },
            'invalid_snapshot': { type: 'error', label: 'Invalid Snapshot', explanation: 'Snapshot failed validation (wrong schema version, missing planes, or invalid format).' },
            'invalid_input_contract': { type: 'error', label: 'Invalid Input', explanation: 'Snapshot does not conform to the expected input contract.' },
            'failed': { type: 'error', label: 'Failed', explanation: 'Pipeline execution failed unexpectedly.' },
            'running': { type: 'warning', label: 'Running', explanation: 'Pipeline is currently executing.' },
            'pending': { type: 'warning', label: 'Pending', explanation: 'Pipeline is queued for execution.' }
        };
        
        function showOutcome(status, message) {
            const panel = document.getElementById('outcomePanel');
            if (!panel) return;
            const config = STATUS_CONFIG[status] || { type: 'error', label: status, explanation: message };
            panel.className = `outcome-panel ${config.type}`;
            panel.innerHTML = `<span class="outcome-badge ${config.type}">${config.label}</span><span class="outcome-explanation">${message || config.explanation}</span>`;
            panel.classList.remove('hidden');
        }
        
        function hideOutcome() {
            const panel = document.getElementById('outcomePanel');
            if (panel) panel.classList.add('hidden');
        }

        async function checkHealth() {
            const dot = document.getElementById('healthDot');
            const text = document.getElementById('healthText');
            if (!dot || !text) return;
            try {
                const r = await fetch('/api/health'); const d = await r.json();
                dot.classList.remove('error');
                text.textContent = `v${d.version} - Healthy`;
            } catch { dot.classList.add('error'); text.textContent = 'Offline'; }
        }
        
        async function populateTenantsFromFarm() {
            // Always try to fetch - backend handles cache fallback
            const select = document.getElementById('tenantSelect');
            
            try {
                const tenantsRes = await fetch('/api/farm/tenants');
                let tenantsData;
                try {
                    tenantsData = await tenantsRes.json();
                } catch (parseErr) {
                    console.warn('Farm unavailable for tenant list');
                    return;
                }
                
                const errorStr = JSON.stringify(tenantsData).toUpperCase();
                const isFarmWaking = !tenantsRes.ok ||
                    tenantsData.ok === false || 
                    tenantsData.error === 'FARM_WAKING_OR_DOWN' ||
                    errorStr.includes('FARM_WAKING') ||
                    errorStr.includes('UNAVAILABLE');
                if (isFarmWaking && !tenantsData.tenants) {
                    console.warn('Farm unavailable');
                    return;
                }
                
                const tenants = tenantsData.tenants || [];
                
                // Clear dropdown and add placeholder
                select.innerHTML = '<option value="">Select a tenant...</option>';
                
                // Fetch all snapshots to find the latest one
                let latestTenant = null;
                try {
                    const snapshotsRes = await fetch('/api/farm/all-snapshots');
                    const rawData = await snapshotsRes.json();
                    // Backend returns a raw array when Farm is up,
                    // or { snapshots: [...], offline_mode: true } when cached/offline
                    const allSnapshots = Array.isArray(rawData) ? rawData : (rawData.snapshots || []);
                    if (allSnapshots.length > 0) {
                        // Find the most recent snapshot
                        allSnapshots.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
                        latestTenant = allSnapshots[0].tenant_id;
                    }
                } catch (e) {
                    console.warn('Could not fetch snapshot dates:', e);
                }
                
                // Add tenants to dropdown, marking the latest with ★
                tenants.forEach(t => {
                    const opt = document.createElement('option');
                    opt.value = t;
                    if (t === latestTenant) {
                        opt.textContent = `★ ${t} (Latest)`;
                    } else {
                        opt.textContent = t;
                    }
                    select.appendChild(opt);
                });
                
                // Auto-select the latest tenant
                if (latestTenant && tenants.includes(latestTenant)) {
                    select.value = latestTenant;
                    // Trigger change to load observation counts
                    await handleTenantChange();
                }
            } catch (e) {
                console.warn('Could not fetch Farm tenants:', e);
            }
        }
        
        async function handleTenantChange() {
            const tenantId = document.getElementById('tenantSelect').value;

            if (tenantId) {
                try {
                    const snapshotsRes = await fetch(`/api/farm/snapshots?tenant_id=${encodeURIComponent(tenantId)}`);
                    if (snapshotsRes.ok) {
                        const snapshotsData = await snapshotsRes.json();
                        if (snapshotsData.snapshots && snapshotsData.snapshots.length > 0) {
                            const latestSnapshot = snapshotsData.snapshots[0];
                            const snapshotRes = await fetch(`/api/farm/snapshot?tenant_id=${encodeURIComponent(tenantId)}&snapshot_id=${encodeURIComponent(latestSnapshot.snapshot_id)}`);
                            if (snapshotRes.ok) {
                                const snapshotData = await snapshotRes.json();
                                loadObservationPlaneCounts(snapshotData);
                                if (typeof updatePipelineStrip === 'function') updatePipelineStrip();
                                return;
                            }
                        }
                    }
                } catch (e) {
                    console.warn('Could not load snapshot for tenant:', e);
                }
            }
            loadObservationPlaneCounts(null);
            if (typeof updatePipelineStrip === 'function') updatePipelineStrip();
        }
        
        function updateTimingDisplay(runs) {
            const timingDisplay = document.getElementById('timingDisplay');
            const timingTotal = document.getElementById('timingTotal');
            if (runs && runs.length > 0) {
                const runWithTiming = runs.find(r => r.stage_timings && r.stage_timings.total);
                if (runWithTiming) {
                    timingDisplay.style.display = 'flex';
                    timingTotal.textContent = runWithTiming.stage_timings.total.toFixed(2);
                } else {
                    timingDisplay.style.display = 'none';
                }
            } else {
                timingDisplay.style.display = 'none';
            }
        }
        
        async function loadRuns(autoSelect = false) {
            const loading = document.getElementById('runsLoading'), list = document.getElementById('runsList');
            loading.classList.remove('hidden');
            try {
                const r = await fetch('/api/runs');
                if (!r.ok) {
                    const body = await r.text();
                    const err = new Error(`API ${r.status}: ${body.slice(0, 300)}`);
                    err.responseBody = body.slice(0, 500);
                    throw err;
                }
                let runs = await r.json();
                runs.sort((a, b) => new Date(b.started_at) - new Date(a.started_at));
                updateTimingDisplay(runs);
                if (runs.length === 0) { list.innerHTML = '<div class="empty-state">No runs yet. Fetch a snapshot to get started.</div>'; }
                else {
                    list.innerHTML = runs.map((run, idx) => {
                        const syncBadge = run.sync_status && run.sync_status !== 'not_applicable' 
                            ? `<span class="sync-status ${run.sync_status}" title="${run.sync_error || ''}">${run.sync_status === 'synced' ? 'SYNCED' : run.sync_status === 'failed' ? 'SYNC FAILED' : 'SYNCING'}</span>` 
                            : '';
                        const tenant = run.tenant_id || '-';
                        const latestTag = idx === 0 ? ' <span class="latest-run-badge">(Latest)</span>' : '';
                        const size = run.input_meta?.scale || '-';
                        const profile = run.input_meta?.enterprise_profile || '-';
                        const isCompleted = run.status.toLowerCase().includes('completed');
                        const catalogLink = isCompleted
                            ? `<a href="/api/catalog/view?run_id=${run.run_id}" target="_blank" class="catalog-link" onclick="event.stopPropagation();" title="View Asset Catalog">View Catalog ↗</a>`
                            : '';
                        const timingBadge = run.stage_timings && run.stage_timings.total
                            ? `<span class="run-timing" title="Pipeline execution time">${run.stage_timings.total.toFixed(1)}s</span>`
                            : '';
                        return `<div class="run-item ${run.run_id === currentRunId ? 'selected' : ''}" data-run-id="${run.run_id}">
                            <div class="run-info">
                                <span class="run-tenant">${tenant}${latestTag}</span>
                                <span class="run-status ${run.status}">${run.status.replace(/_/g, ' ')}</span>${syncBadge}${timingBadge}
                            </div>
                            <div class="run-meta">
                                <span class="run-size">${size}</span>
                                <span class="run-profile">${profile}</span>
                                ${catalogLink}
                            </div>
                        </div>`;
                    }).join('');
                    document.querySelectorAll('.run-item').forEach(item => item.addEventListener('click', () => selectRun(item.dataset.runId)));
                    
                    if (autoSelect && runs.length > 0 && !currentRunId) {
                        await selectRun(runs[0].run_id);
                    }
                }
            } catch (err) {
                console.error('Failed to load runs:', err);
                let detail = err.message || String(err);
                if (err.responseBody) detail += ' | ' + err.responseBody;
                list.innerHTML = `<div class="error-message">Failed to load runs: ${detail}</div>`;
            }
            finally {
                loading.classList.add('hidden');
                // Update runs count badge
                const badge = document.getElementById('runsCountBadge');
                if (badge) {
                    const count = document.querySelectorAll('#runsList .run-item').length;
                    badge.textContent = count;
                }
                if (typeof updatePipelineStrip === 'function') updatePipelineStrip();
            }
        }

        async function selectRun(runId) {
            currentRunId = runId;
            hideDrillPanel();
            document.querySelectorAll('.run-item').forEach(item => item.classList.toggle('selected', item.dataset.runId === runId));
            document.getElementById('resultsSection').classList.remove('hidden');
            await Promise.all([loadRunDetails(runId), loadAssets(runId), loadFindings(runId), loadArtifacts(runId)]);

            // Load handoff data for this run (merged from Handoff tab)
            const handoffSelect = document.getElementById('handoffRunSelect');
            if (handoffSelect) {
                if (!handoffSelect.querySelector(`option[value="${runId}"]`)) {
                    const opt = document.createElement('option');
                    opt.value = runId;
                    opt.textContent = runId;
                    handoffSelect.appendChild(opt);
                }
                handoffSelect.value = runId;
            }
            const statusFilter = document.getElementById('handoffStatusFilter')?.value || 'all';
            await loadHandoffCandidates(runId, statusFilter);
            document.getElementById('handoffSection')?.classList.remove('hidden');
            if (typeof updatePipelineStrip === 'function') updatePipelineStrip();
        }
        
        async function loadRunDetails(runId) {
            try {
                const r = await fetch(`/api/runs/${runId}`); const run = await r.json();
                document.getElementById('descRunId').textContent = run.run_id;
                document.getElementById('descTenant').textContent = run.tenant_id;
                document.getElementById('descStatus').textContent = run.status.replace(/_/g, ' ');
                document.getElementById('descCompleted').textContent = run.completed_at ? new Date(run.completed_at).toLocaleString() : '-';
                const obsIn = run.counts.observations_in || 0;
                const candidatesOut = run.counts.candidates_out || 0;
                const rejected = run.counts.rejected || 0;
                document.getElementById('statObservations').textContent = obsIn;
                document.getElementById('statValidated').textContent = candidatesOut;
                document.getElementById('statRejected').textContent = rejected;
                document.getElementById('statAssets').textContent = run.counts.assets_admitted;
            } catch (e) { console.error('Failed to load run details:', e); }
            
            try {
                const dr = await fetch(`/api/runs/${runId}/derived`);
                if (dr.ok) {
                    const derived = await dr.json();
                    const shadowCount = derived.shadow_count ?? 0;
                    const zombieCount = derived.zombie_count ?? 0;
                    document.getElementById('statShadow').textContent = shadowCount;
                    document.getElementById('statZombie').textContent = zombieCount;
                    
                    const shadowSublabel = document.getElementById('shadowAssetsSublabel');
                    if (shadowCount > 0) {
                        shadowSublabel.textContent = `${shadowCount} admitted`;
                    } else {
                        shadowSublabel.textContent = '';
                    }
                    
                    const zombieSublabel = document.getElementById('zombieAssetsSublabel');
                    if (zombieCount > 0) {
                        zombieSublabel.textContent = `${zombieCount} admitted`;
                    } else {
                        zombieSublabel.textContent = '';
                    }
                    
                    const { data: shadowNorm, errors: shadowErrs } = normalizeResponse('shadow', derived.shadow_assets || []);
                    normalizedData.shadow = shadowNorm;
                    if (shadowErrs.length > 0) console.warn('Shadow normalization errors:', shadowErrs);
                    
                    const { data: zombieNorm, errors: zombieErrs } = normalizeResponse('zombie', derived.zombie_assets || []);
                    normalizedData.zombie = zombieNorm;
                    if (zombieErrs.length > 0) console.warn('Zombie normalization errors:', zombieErrs);
                } else {
                    document.getElementById('statShadow').textContent = '-';
                    document.getElementById('statZombie').textContent = '-';
                    document.getElementById('shadowAssetsSublabel').textContent = '';
                    document.getElementById('zombieAssetsSublabel').textContent = '';
                    normalizedData.shadow = [];
                    normalizedData.zombie = [];
                }
            } catch (e) {
                console.error('Failed to load derived classifications:', e);
                document.getElementById('statShadow').textContent = '-';
                document.getElementById('statZombie').textContent = '-';
                document.getElementById('shadowAssetsSublabel').textContent = '';
                document.getElementById('zombieAssetsSublabel').textContent = '';
                normalizedData.shadow = [];
                normalizedData.zombie = [];
            }
        }
        
        async function loadAssets(runId) {
            try {
                const r = await fetch(`/api/catalog?run_id=${runId}`); catalogData = await r.json();
                const { data: normalized, errors } = normalizeResponse('assets', catalogData.assets || []);
                normalizedData.assets = normalized;
                if (errors.length > 0) console.warn('Asset normalization errors:', errors);
            } catch (e) { 
                console.error('Failed to load assets:', e);
                normalizedData.assets = [];
            }
        }
        
        async function loadFindings(runId) {
            const SECURITY_CATEGORIES = ['identity_access', 'shadow_it', 'data_integrity', 'security_risk'];
            const GOVERNANCE_CATEGORIES = ['visibility_gap', 'governance_hygiene', 'governance_finding'];
            
            try {
                const r = await fetch(`/api/findings?run_id=${runId}`); const data = await r.json();
                const allFindings = data.findings || [];
                
                const securityRisks = allFindings.filter(f => SECURITY_CATEGORIES.includes(f.category));
                const governanceHygiene = allFindings.filter(f => GOVERNANCE_CATEGORIES.includes(f.category));
                
                const { data: secNorm, errors: secErrs } = normalizeResponse('security_risks', securityRisks);
                normalizedData.security_risks = secNorm;
                if (secErrs.length > 0) console.warn('Security risks normalization errors:', secErrs);
                
                const { data: hygNorm, errors: hygErrs } = normalizeResponse('governance_hygiene', governanceHygiene);
                normalizedData.governance_hygiene = hygNorm;
                if (hygErrs.length > 0) console.warn('Governance hygiene normalization errors:', hygErrs);
                
                const p0Count = securityRisks.filter(f => f.triage_priority === 'p0').length;
                const p1Count = securityRisks.filter(f => f.triage_priority === 'p1').length;
                const p2Count = securityRisks.filter(f => f.triage_priority === 'p2' || !f.triage_priority).length;
                
                document.getElementById('statSecurityRisks').textContent = securityRisks.length;
                const breakdownEl = document.getElementById('riskBreakdown');
                const actionableCount = p0Count + p1Count;
                if (securityRisks.length > 0 && actionableCount > 0) {
                    breakdownEl.textContent = `${actionableCount} actionable`;
                } else {
                    breakdownEl.textContent = '';
                }
                
                const securityAssetIds = new Set(securityRisks.map(f => f.asset_id).filter(Boolean));
                const secAssetsEl = document.getElementById('securityAssetsCount');
                if (securityAssetIds.size > 0) {
                    secAssetsEl.textContent = `${securityAssetIds.size} admitted`;
                    secAssetsEl.dataset.assetIds = JSON.stringify([...securityAssetIds]);
                } else {
                    secAssetsEl.textContent = '';
                }
                
                document.getElementById('statGovernanceHygiene').textContent = governanceHygiene.length;
                
                const governanceAssetIds = new Set(governanceHygiene.map(f => f.asset_id).filter(Boolean));
                const govAssetsEl = document.getElementById('governanceAssetsCount');
                if (governanceAssetIds.size > 0) {
                    govAssetsEl.textContent = `${governanceAssetIds.size} admitted`;
                    govAssetsEl.dataset.assetIds = JSON.stringify([...governanceAssetIds]);
                } else {
                    govAssetsEl.textContent = '';
                }
            } catch (e) { 
                console.error('Failed to load findings:', e);
                normalizedData.security_risks = [];
                normalizedData.governance_hygiene = [];
                document.getElementById('statGovernanceHygiene').textContent = '-';
            }
        }
        
        async function loadArtifacts(runId) {
            // Load general artifacts (legacy endpoint)
            try {
                const r = await fetch(`/api/artifacts?run_id=${runId}`);
                if (r.ok) {
                    const data = await r.json();
                    const { data: normalized, errors } = normalizeResponse('artifacts', data.artifacts || []);
                    normalizedData.artifacts = normalized;
                    if (errors.length > 0) console.warn('Artifacts normalization errors:', errors);
                } else {
                    normalizedData.artifacts = [];
                }
            } catch (e) {
                console.error('Failed to load artifacts:', e);
                normalizedData.artifacts = [];
            }

            // Load Fabric Planes and Systems of Record
            try {
                const r = await fetch(`/api/runs/${runId}/artifacts`);
                if (r.ok) {
                    const data = await r.json();

                    // Fabric Planes
                    const fabricPlanes = data.fabric_planes || {};
                    const fabricCount = fabricPlanes.count || 0;
                    document.getElementById('statFabricPlanes').textContent = fabricCount;

                    const fabricBreakdown = document.getElementById('fabricPlaneBreakdown');
                    if (fabricCount > 0) {
                        const byType = fabricPlanes.by_plane_type || {};
                        const parts = [];
                        if ((byType.ipaas || []).length > 0) parts.push(`${byType.ipaas.length} iPaaS`);
                        if ((byType.api_gateway || []).length > 0) parts.push(`${byType.api_gateway.length} Gateway`);
                        if ((byType.event_bus || []).length > 0) parts.push(`${byType.event_bus.length} Event`);
                        if ((byType.warehouse || []).length > 0) parts.push(`${byType.warehouse.length} Warehouse`);
                        fabricBreakdown.textContent = parts.join(', ') || `${fabricPlanes.total_assets_with_fabric_tag || 0} assets`;
                    } else {
                        fabricBreakdown.textContent = '';
                    }

                    // Store fabric data for drill-down
                    normalizedData.fabric_planes = fabricPlanes.planes || [];

                    // Systems of Record
                    const sor = data.systems_of_record || {};
                    const sorCount = sor.count || 0;
                    document.getElementById('statSOR').textContent = sorCount;

                    const sorBreakdown = document.getElementById('sorBreakdown');
                    if (sorCount > 0) {
                        const highCount = sor.high_confidence_count || 0;
                        const medCount = sor.medium_confidence_count || 0;
                        const parts = [];
                        if (highCount > 0) parts.push(`${highCount} high`);
                        if (medCount > 0) parts.push(`${medCount} medium`);
                        sorBreakdown.textContent = parts.join(', ') || '';
                    } else {
                        sorBreakdown.textContent = '';
                    }

                    // Store SOR data for drill-down
                    normalizedData.sor = sor.assets || [];

                } else {
                    document.getElementById('statFabricPlanes').textContent = '-';
                    document.getElementById('fabricPlaneBreakdown').textContent = '';
                    document.getElementById('statSOR').textContent = '-';
                    document.getElementById('sorBreakdown').textContent = '';
                    normalizedData.fabric_planes = [];
                    normalizedData.sor = [];
                }
            } catch (e) {
                console.error('Failed to load fabric/SOR artifacts:', e);
                document.getElementById('statFabricPlanes').textContent = '-';
                document.getElementById('fabricPlaneBreakdown').textContent = '';
                document.getElementById('statSOR').textContent = '-';
                document.getElementById('sorBreakdown').textContent = '';
                normalizedData.fabric_planes = [];
                normalizedData.sor = [];
            }
        }
        
        document.getElementById('tenantSelect').addEventListener('change', handleTenantChange);
        
        document.getElementById('fetchFromFarm').addEventListener('click', async () => {
            const tenantId = document.getElementById('tenantSelect').value;
            
            hideOutcome();
            
            if (!tenantId) { 
                showToast('Please select a Tenant', 'error');
                return; 
            }
            
            const btn = document.getElementById('fetchFromFarm'); 
            btn.disabled = true; 
            btn.textContent = 'Running Discovery...';
            
            try {
                const snapshotsRes = await fetch(`/api/farm/snapshots?tenant_id=${encodeURIComponent(tenantId)}`);
                const snapshotsData = await snapshotsRes.json();
                
                if (!snapshotsData.snapshots || snapshotsData.snapshots.length === 0) {
                    showToast('No snapshots found for this tenant', 'error');
                    return;
                }
                
                const latestSnapshot = snapshotsData.snapshots[0];
                const snapshotId = latestSnapshot.snapshot_id || latestSnapshot.id;
                
                const r = await fetch('/api/runs/from-farm', { 
                    method: 'POST', 
                    headers: { 'Content-Type': 'application/json' }, 
                    body: JSON.stringify({ tenant_id: tenantId, snapshot_id: snapshotId }) 
                });
                
                const result = await r.json();
                
                if (!r.ok) {
                    const errorDetail = result.detail || 'Farm fetch failed';
                    if (errorDetail.includes('UPSTREAM_ERROR') || errorDetail.includes('FARM_')) {
                        showOutcome('upstream_error', errorDetail);
                    } else if (errorDetail.includes('INVALID_INPUT_CONTRACT') || errorDetail.includes('INVALID_SNAPSHOT')) {
                        showOutcome('invalid_snapshot', errorDetail);
                    } else {
                        showOutcome('failed', errorDetail);
                    }
                    return;
                }
                
                showOutcome(result.status, result.message);
                currentRunId = result.run_id;
                await loadRuns();
                await selectRun(result.run_id);
                const iframe = document.getElementById('topologyIframe');
                if (iframe) iframe.src = '/static/overview/index.html?v=' + Date.now();

                // Auto-trigger handoff to AAM after successful discovery
                if (result.status === 'completed' && typeof exportToAAM === 'function') {
                    console.log('[AOD] Discovery completed — auto-triggering handoff to AAM');
                    await exportToAAM();
                }
            } catch (e) {
                showOutcome('upstream_error', e.message);
            } finally {
                btn.disabled = false;
                btn.textContent = 'Run Discovery';
            }
        });
        
        setTimeout(() => {
            const goToFarmBtn = document.getElementById('goToFarmBtn');
            if (goToFarmBtn) {
                goToFarmBtn.addEventListener('click', async () => {
                    try {
                        const r = await fetch('/api/farm/url');
                        const data = await r.json();
                        if (data.farm_url) {
                            window.open(data.farm_url, 'aos_farm');
                        }
                    } catch (e) {
                        console.error('Failed to get Farm URL:', e);
                    }
                });
            }
        }, 0);
        
        
        document.querySelectorAll('.stat-card.clickable').forEach(card => {
            card.addEventListener('click', () => {
                const drillType = card.dataset.drillType;
                if (drillType && currentRunId) {
                    initiateDrill(drillType);
                }
            });
        });
        
        document.querySelectorAll('.stat-sublabel-link').forEach(sublabel => {
            sublabel.addEventListener('click', (e) => {
                e.stopPropagation();
                if (!currentRunId) return;
                
                const id = sublabel.id;
                if (id === 'shadowAssetsSublabel') {
                    initiateDrill('shadow');
                } else if (id === 'zombieAssetsSublabel') {
                    initiateDrill('zombie');
                } else if (id === 'securityAssetsCount') {
                    initiateDrill('security_risks');
                } else if (id === 'governanceAssetsCount') {
                    initiateDrill('governance_hygiene');
                }
            });
        });
        
        document.getElementById('drillBackBtn').addEventListener('click', () => {
            popDrill();
        });
        
        initMainTabs();
        initTriageTab();
        initTestTab();
        initHandoffTab();
        loadHandoffRuns();
        
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('from') === 'farm' || urlParams.get('source') === 'farm') {
            const consoleTab = document.querySelector('.header-nav-tab[data-tab="discovery"]');
            if (consoleTab) {
                document.querySelectorAll('.header-nav-tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.main-tab-content').forEach(c => c.classList.remove('active'));
                consoleTab.classList.add('active');
                document.getElementById('discoveryTabContent').classList.add('active');
            }
            window.history.replaceState({}, '', window.location.pathname);
        }
        
        checkHealth(); 
        loadRuns(true);
        
        (async function initConsoleTab() {
            loadObservationPlaneCounts(null);
            // Ensure farm status is checked before populating tenants
            await checkFarmStatus();
            await populateTenantsFromFarm();
        })().then(() => {
            // Build pipeline strip and wire interactive behaviors
            if (typeof initConsoleRedesign === 'function') initConsoleRedesign();
        });
        
        setInterval(checkHealth, 30000);
        
        if (typeof TourManager !== 'undefined') {
            TourManager.checkResume();
            const guidedTourBtn = document.getElementById('guidedTourBtn');
            if (guidedTourBtn) {
                guidedTourBtn.addEventListener('click', () => TourManager.start());
            }
        }
        
        const refreshBtn = document.getElementById('refreshBtn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', async () => {
                // Always refresh tenant/snapshot data (Overview tab)
                await populateTenantsFromFarm();
                await handleTenantChange();

                // Refresh whichever tab is currently active
                const activeTab = document.querySelector('.header-nav-tab.active');
                const activeTabId = activeTab ? activeTab.dataset.tab : null;

                // Always refresh both Console runs and Discovery iframe
                await loadRuns();
                const iframe = document.getElementById('topologyIframe');
                if (iframe) iframe.src = '/static/overview/index.html?v=' + Date.now();
                if (currentRunId) {
                    const sf = document.getElementById('handoffStatusFilter')?.value || 'all';
                    await loadHandoffCandidates(currentRunId, sf);
                }

                showToast('Data refreshed', 'success');
            });
        }
        
        const helpBtn = document.getElementById('helpBtn');
        const helpModal = document.getElementById('helpModal');
        const helpModalClose = document.getElementById('helpModalClose');
        if (helpBtn && helpModal) {
            helpBtn.addEventListener('click', () => helpModal.classList.add('active'));
        }
        if (helpModalClose && helpModal) {
            helpModalClose.addEventListener('click', () => helpModal.classList.remove('active'));
        }
        if (helpModal) {
            helpModal.addEventListener('click', (e) => {
                if (e.target.id === 'helpModal') helpModal.classList.remove('active');
            });
        }
        
        window.addEventListener('message', (event) => {
            if (event.data && event.data.action) {
                if (event.data.action === 'startGuidedTour') {
                    if (typeof TourManager !== 'undefined') {
                        TourManager.start();
                    }
                } else if (event.data.action === 'startSimulation') {
                    // Start simulation tour - opens Farm in new window
                    if (typeof TourManager !== 'undefined') {
                        TourManager.startSimulation();
                    }
                } else if (event.data.action === 'skipToSimulation') {
                    if (typeof TourManager !== 'undefined') {
                        TourManager.startSimulation();
                    }
                } else if (event.data.action === 'switchToConsole') {
                    document.querySelectorAll('.header-nav-tab').forEach(t => t.classList.remove('active'));
                    document.querySelectorAll('.main-tab-content').forEach(c => c.classList.remove('active'));
                    const consoleTab = document.querySelector('.header-nav-tab[data-tab="discovery"]');
                    if (consoleTab) consoleTab.classList.add('active');
                    document.getElementById('discoveryTabContent').classList.add('active');
                } else if (event.data.action === 'runDiscovery') {
                    // Programmatically trigger Run Discovery (same as clicking the button)
                    const btn = document.getElementById('fetchFromFarm');
                    if (btn) {
                        console.log('[AOD] postMessage: runDiscovery — clicking fetchFromFarm');
                        btn.click();
                    }
                } else if (event.data.action === 'triggerHandoff') {
                    // Programmatically trigger Export to AAM
                    if (typeof exportToAAM === 'function') {
                        console.log('[AOD] postMessage: triggerHandoff — calling exportToAAM()');
                        exportToAAM();
                    } else {
                        // Fallback: click the button
                        const btn = document.getElementById('exportToAAMBtn');
                        if (btn) btn.click();
                    }
                } else if (event.data.action === 'snapshotGenerated') {
                    // Farm generated a new snapshot — refresh tenants and auto-run discovery
                    console.log('[AOD] postMessage: snapshotGenerated — refreshing and running discovery');
                    (async () => {
                        await populateTenantsFromFarm();
                        // Select the tenant from the event if provided
                        if (event.data.tenant_id) {
                            const select = document.getElementById('tenantSelect');
                            if (select) {
                                select.value = event.data.tenant_id;
                                await handleTenantChange();
                            }
                        } else {
                            await handleTenantChange();
                        }
                        // Trigger discovery run (same as clicking "Run Discovery")
                        const btn = document.getElementById('fetchFromFarm');
                        if (btn) btn.click();
                    })();
                }
            }
        });
        
