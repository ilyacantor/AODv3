/* ============================================================
   AOD Console Redesign v3
   Called once from initConsoleTab()
   ============================================================ */
function initConsoleRedesign() {
  // ── Guard: don't double-init ──────────────────────────────
  if (document.querySelector('.console-pipeline')) return;
  const tabContent = document.getElementById('discoveryTabContent');
  if (!tabContent) return;
  // ════════════════════════════════════════════════════════════
  // 1. PIPELINE STRIP
  // ════════════════════════════════════════════════════════════
  (function buildPipeline() {
    const steps = [
      { n: 1, label: 'Select Tenant',  done: true  },
      { n: 2, label: 'Review Sources', done: true  },
      { n: 3, label: 'Run Discovery',  active: true },
      { n: 4, label: 'Review Results', done: false },
      { n: 5, label: 'Handoff to AAM', done: false },
    ];
    const strip = document.createElement('div');
    strip.className = 'console-pipeline';
    steps.forEach((st, i) => {
      const cls  = st.done ? 'done' : st.active ? 'active' : '';
      const icon = st.done ? '✓' : st.n;
      strip.innerHTML += `<div class="cp-step ${cls}">
        <span class="cp-num">${icon}</span>${st.label}</div>` +
        (i < steps.length - 1 ? '<span class="cp-arrow">›</span>' : '');
    });
    const guide = document.getElementById('consoleGuide');
    if (guide) guide.after(strip);
    else tabContent.prepend(strip);
  })();
  // ════════════════════════════════════════════════════════════
  // 2. OBS PANEL  (left half of top row)
  // ════════════════════════════════════════════════════════════
  const obsPanel = (function buildObsPanel() {
    const sources = [
      { icon: '🔍', name: 'Discovery',  countId: null, max: 500,  color: '#4299e1' },
      { icon: '🔐', name: 'IdP',        countId: null, max: 200,  color: '#9f7aea' },
      { icon: '📋', name: 'CMDB',       countId: null, max: 200,  color: '#48bb78' },
      { icon: '☁️', name: 'Cloud',      countId: null, max: 200,  color: '#ed8936' },
      { icon: '💻', name: 'Endpoint',   countId: null, max: 500,  color: '#f6ad55' },
      { icon: '🌐', name: 'Network',    countId: null, max: 4000, color: '#63b3ed' },
      { icon: '💰', name: 'Finance',    countId: null, max: 400,  color: '#fc8181' },
    ];
    // Read live counts from original observation-plane-card elements
    const origGrid = document.getElementById('observationPlanesGrid');
    if (origGrid) {
      Array.from(origGrid.querySelectorAll('.observation-plane-card')).forEach((card, i) => {
        if (i >= sources.length) return;
        const numEl = card.querySelector('.plane-count, [class*="count"], strong, b');
        if (numEl) {
          const n = parseInt(numEl.textContent.replace(/[^\\d]/g, ''));
          if (!isNaN(n)) sources[i].count = n;
        }
        if (!sources[i].count) {
          // fallback: find first standalone number in card text
          const m = card.textContent.match(/\\b(\\d{2,5})\\b/);
          if (m) sources[i].count = parseInt(m[1]);
        }
      });
    }
    const panel = document.createElement('div');
    panel.className = 'obs-panel';
    panel.innerHTML = `
      <div class="obs-panel-header">
        <div class="obs-panel-title">
          <span class="obs-online-dot"></span>Observation Sources
        </div>
        <span id="farmStatusBadgeNew" style="font-size:.65rem;color:#48bb78;">● Farm Online</span>
      </div>
      <div class="obs-tenant-row">
        <span class="obs-tenant-label">Tenant:</span>
        <div id="obs-tenant-mount" style="flex:1;min-width:0;"></div>
      </div>
      <div class="obs-sources-list" id="obsSourcesList">
        ${sources.map((s, i) => {
          const count = s.count || 0;
          const pct   = Math.min(100, Math.round(count / s.max * 100));
          return `<div class="obs-source-row" data-source-idx="${i}">
            <span class="obs-source-icon">${s.icon}</span>
            <span class="obs-source-name">${s.name}</span>
            <div class="obs-source-bar-wrap">
              <div class="obs-source-bar" style="width:${pct}%;background:${s.color};"></div>
            </div>
            <span class="obs-source-count">${count ? count.toLocaleString() : '—'}</span>
          </div>`;
        }).join('')}
      </div>
      <div class="obs-action-row">
        <button class="btn btn-primary" id="obsRunBtn">⚡ Run Discovery</button>
        <button class="btn btn-outline-secondary" id="obsHandoffBtn">Handoff →</button>
      </div>`;
    // Clone tenant select into new mount
    const origSelect = document.getElementById('tenantSelect');
    if (origSelect) {
      const clone = origSelect.cloneNode(true);
      clone.id = 'tenantSelectNew';
      clone.style.cssText = 'width:100%;font-size:.72rem;';
      clone.addEventListener('change', e => {
        origSelect.value = e.target.value;
        origSelect.dispatchEvent(new Event('change', { bubbles: true }));
      });
      // Keep original select in sync when changed externally
      origSelect.addEventListener('change', () => { clone.value = origSelect.value; });
      panel.querySelector('#obs-tenant-mount').appendChild(clone);
    }
    // Wire buttons to existing DOM buttons
    panel.querySelector('#obsRunBtn').addEventListener('click', () => {
      document.getElementById('fetchFromFarm')?.click();
    });
    panel.querySelector('#obsHandoffBtn').addEventListener('click', () => {
      document.getElementById('handoffBtn')?.click();
      document.getElementById('handoffSection')?.scrollIntoView({ behavior: 'smooth' });
    });
    // MutationObserver: keep counts in sync when original grid updates
    if (origGrid) {
      const observer = new MutationObserver(() => {
        Array.from(origGrid.querySelectorAll('.observation-plane-card')).forEach((card, i) => {
          if (i >= sources.length) return;
          const numEl = card.querySelector('.plane-count, [class*="count"], strong, b');
          if (!numEl) return;
          const n = parseInt(numEl.textContent.replace(/[^\\d]/g, ''));
          if (isNaN(n)) return;
          const row       = panel.querySelector(`[data-source-idx="${i}"]`);
          const countEl   = row?.querySelector('.obs-source-count');
          const barEl     = row?.querySelector('.obs-source-bar');
          if (countEl) countEl.textContent = n.toLocaleString();
          if (barEl)   barEl.style.width   = Math.min(100, Math.round(n / sources[i].max * 100)) + '%';
        });
      });
      observer.observe(origGrid, { childList: true, subtree: true, characterData: true });
    }
    return panel;
  })();
  // ════════════════════════════════════════════════════════════
  // 3. RESULTS PANEL  (right half of top row)
  // ════════════════════════════════════════════════════════════
  const resultsPanel = (function buildResultsPanel() {
    // Read live values from existing summaryTab
    const cardMap = {};
    document.querySelectorAll('#summaryTab .stat-card').forEach(c => {
      const lbl = c.querySelector('.stat-label')?.textContent?.trim() || '';
      cardMap[lbl] = {
        val: c.querySelector('.stat-value')?.textContent?.trim() || '—',
        sub: c.querySelector('.stat-sublabel')?.textContent?.trim() || '',
      };
    });
    const runId    = document.getElementById('descRunId')?.textContent?.trim()    || '—';
    const tenant   = document.getElementById('descTenant')?.textContent?.trim()   || '—';
    const status   = document.getElementById('descStatus')?.textContent?.trim()   || '—';
    const compEl   = document.querySelector('#runDescriptors .run-desc-item:last-child .run-desc-value');
    const completed = compEl?.textContent?.trim() || '—';
    const KPI_COLORS = {
      Ingested: '#63b3ed', Validated: '#48bb78', Rejected: '#fc8181', Cataloged: '#9f7aea',
      Shadow: '#ecc94b', Zombie: '#f6ad55', 'Security Risks': '#fc8181', Governance: '#48bb78',
    };
    const panel = document.createElement('div');
    panel.className = 'results-panel';
    panel.id        = 'resultsPanelNew';
    panel.innerHTML = `
      <div class="results-panel-title">Results</div>
      <div class="run-meta-bar">
        <span><span class="rml">Run: </span><span class="rmv" id="rpRunId">${runId}</span></span>
        <span><span class="rml">Tenant: </span><span class="rmv" id="rpTenant">${tenant}</span></span>
        <span><span class="rml">Status: </span><span class="rmv" id="rpStatus" style="color:#48bb78;">${status}</span></span>
        <span><span class="rml">Completed: </span><span class="rmv" id="rpCompleted">${completed}</span></span>
      </div>
      <div class="kpi-two-col">
        <div class="kpi-group">
          <div class="kpi-group-label">Lifecycle</div>
          <div class="kpi-row-inner">
            ${['Ingested','Validated','Rejected','Cataloged'].map(lbl => `
            <div class="kpi-cell">
              <div class="kv" style="color:${KPI_COLORS[lbl]}" id="rpKpi${lbl}">${cardMap[lbl]?.val||'—'}</div>
              <div class="kl">${lbl}</div>
            </div>`).join('')}
          </div>
        </div>
        <div class="kpi-group">
          <div class="kpi-group-label">Classifications</div>
          <div class="kpi-row-inner">
            ${['Shadow','Zombie','Security Risks','Governance'].map(lbl => {
              const safeId = lbl.replace(/\\s+/g,'');
              return `<div class="kpi-cell">
                <div class="kv" style="color:${KPI_COLORS[lbl]}" id="rpKpi${safeId}">${cardMap[lbl]?.val||'—'}</div>
                <div class="kl">${lbl==='Security Risks'?'Sec. Risks':lbl}</div>
                ${cardMap[lbl]?.sub ? `<div class="ks">${cardMap[lbl].sub}</div>` : ''}
              </div>`;
            }).join('')}
          </div>
        </div>
      </div>
      <div class="results-go-btn-wrap">
        <button class="btn btn-outline-secondary" id="rpGoToFarmBtn">Go to Farm for Grading →</button>
      </div>`;
    panel.querySelector('#rpGoToFarmBtn').addEventListener('click', () => {
      document.getElementById('goToFarmBtn')?.click();
    });
    // Keep meta bar in sync when original summaryTab updates
    const summaryTab = document.getElementById('summaryTab');
    if (summaryTab) {
      const syncResults = () => {
        document.
// ── Keep Results panel in sync when the hidden summaryTab updates ──
    const summaryTab = document.getElementById('summaryTab');
    if (summaryTab) {
      const syncResults = () => {
        // Re-read all stat-card values from the hidden original
        document.querySelectorAll('#summaryTab .stat-card').forEach(c => {
          const lbl = c.querySelector('.stat-label')?.textContent?.trim() || '';
          const val = c.querySelector('.stat-value')?.textContent?.trim() || '—';
          const sub = c.querySelector('.stat-sublabel')?.textContent?.trim() || '';
          // Map label → new panel element ID
          const idMap = {
            'Ingested':       'rpKpiIngested',
            'Validated':      'rpKpiValidated',
            'Rejected':       'rpKpiRejected',
            'Cataloged':      'rpKpiCataloged',
            'Shadow':         'rpKpiShadow',
            'Zombie':         'rpKpiZombie',
            'Security Risks': 'rpKpiSecurityRisks',
            'Governance':     'rpKpiGovernance',
          };
          const targetId = idMap[lbl];
          if (targetId) {
            const el = document.getElementById(targetId);
            if (el) el.textContent = val;
          }
        });
        // Sync run meta bar
        const syncField = (srcId, destId) => {
          const src = document.getElementById(srcId);
          const dst = document.getElementById(destId);
          if (src && dst) dst.textContent = src.textContent.trim();
        };
        syncField('descRunId',  'rpRunId');
        syncField('descTenant', 'rpTenant');
        syncField('descStatus', 'rpStatus');
        const compSrc = document.querySelector('#runDescriptors .run-desc-item:last-child .run-desc-value');
        const compDst = document.getElementById('rpCompleted');
        if (compSrc && compDst) compDst.textContent = compSrc.textContent.trim();
      };
      // Observe the hidden summaryTab for any content changes
      new MutationObserver(syncResults)
        .observe(summaryTab, { childList: true, subtree: true, characterData: true });
    }
    return panel;
  })(); // end buildResultsPanel
  // ════════════════════════════════════════════════════════════
  // 4. DISCOVERY RUNS  (collapsible strip inside resultsPanel)
  // ════════════════════════════════════════════════════════════
  (function buildRunsPanel() {
    const runsList = document.getElementById('runsList');
    if (!runsList) return;
    const runs = Array.from(runsList.children).map(c => ({
      runId:    c.dataset.runId || '',
      tenant:   c.querySelector('.run-tenant')?.childNodes[0]?.textContent?.trim()
                || c.querySelector('.run-tenant')?.textContent?.trim() || '—',
      isLatest: !!c.querySelector('.latest-run-badge'),
      status:   c.querySelector('.run-status')?.textContent?.trim() || '',
      sync:     c.querySelector('.sync-status')?.textContent?.trim() || '',
      timing:   c.querySelector('.run-timing')?.textContent?.trim() || '',
      isActive: c.classList.contains('selected'),
    }));
    const total = runs.length;
    function dotColor(status) {
      if (status.includes('completed')) return '#48bb78';
      if (status.includes('fail'))      return '#fc8181';
      return '#ecc94b';
    }
    const panel = document.createElement('div');
    panel.id        = 'resultsRunsPanel';
    panel.className = 'runs-row';
    panel.innerHTML = `
      <div class="runs-row-header" id="runsRowHeader">
        <div class="runs-row-left">
          <span class="runs-chevron" id="runsChevron">▼</span>
          <span class="runs-row-title">Discovery Runs</span>
          <span class="runs-count-badge" id="runsCountBadge">${total}</span>
        </div>
        <div class="runs-row-right">
          <input class="runs-filter-input" id="runsFilterInput"
                 type="text" placeholder="Filter tenant…" autocomplete="off"/>
          <button class="runs-clear-btn" id="runsClearBtn"
                  title="Clear all runs from view">⊘ Clear All</button>
        </div>
      </div>
      <div class="runs-body" id="runsBody">
        <div class="runs-items-list" id="runsItemsList">
          ${runs.map(r => `
            <div class="runs-row-item${r.isActive ? ' active' : ''}"
                 data-run-id="${r.runId}"
                 data-tenant="${r.tenant.toLowerCase()}">
              <span class="ri-dot" style="background:${dotColor(r.status)}"></span>
              <span class="ri-tenant">${r.tenant}</span>
              ${r.isLatest ? '<span class="ri-latest">Latest</span>' : ''}
              <span class="ri-sync">${r.sync}</span>
              <span class="ri-timing">${r.timing}</span>
            </div>`).join('')}
        </div>
        <div class="runs-no-results" id="runsNoResults">No runs match filter</div>
      </div>`;
    resultsPanel.appendChild(panel);
    // Toggle open/close
    let runsOpen = true;
    document.getElementById('runsRowHeader').addEventListener('click', e => {
      if (e.target.closest('#runsFilterInput') || e.target.closest('#runsClearBtn')) return;
      runsOpen = !runsOpen;
      document.getElementById('runsBody').classList.toggle('collapsed', !runsOpen);
      document.getElementById('runsChevron').classList.toggle('collapsed', !runsOpen);
    });
    // Live filter
    document.getElementById('runsFilterInput').addEventListener('input', function () {
      const q = this.value.trim().toLowerCase();
      let visible = 0;
      document.querySelectorAll('#runsItemsList .runs-row-item').forEach(item => {
        const hide = q && !item.dataset.tenant.includes(q);
        item.classList.toggle('hidden-by-filter', hide);
        if (!hide) visible++;
      });
      document.getElementById('runsCountBadge').textContent = q ? `${visible}/${total}` : total;
      document.getElementById('runsNoResults').style.display =
        (visible === 0 && q) ? 'block' : 'none';
    });
    // Clear all
    document.getElementById('runsClearBtn').addEventListener('click', e => {
      e.stopPropagation();
      if (!confirm(
        `Remove all ${total} discovery runs from this view?\\n` +
        `(Display only — stored data is not affected.)`
      )) return;
      const list = document.getElementById('runsItemsList');
      list.innerHTML = `<div class="runs-no-results"
        style="display:block;padding:.6rem 0;color:#4a5568;">
        All runs cleared. Refresh to restore.</div>`;
      document.getElementById('runsCountBadge').textContent = '0';
      document.getElementById('runsFilterInput').disabled = true;
    });
    // Click a run row → proxy to original run-item click (triggers existing app logic)
    document.querySelectorAll('#runsItemsList .runs-row-item').forEach(item => {
      item.addEventListener('click', e => {
        if (e.target.closest('#runsFilterInput') || e.target.closest('#runsClearBtn')) return;
        const origItem = runsList.querySelector(`[data-run-id="${item.dataset.runId}"]`);
        if (origItem) origItem.click();
        document.querySelectorAll('#runsItemsList .runs-row-item')
          .forEach(it => it.classList.remove('active'));
        item.classList.add('active');
      });
    });
    // Keep active highlight in sync when app selects a different run externally
    new MutationObserver(() => {
      const selectedOrig = runsList.querySelector('.run-item.selected');
      const activeRunId  = selectedOrig?.dataset?.runId;
      document.querySelectorAll('#runsItemsList .runs-row-item').forEach(it => {
        it.classList.toggle('active', it.dataset.runId === activeRunId);
      });
    }).observe(runsList, { attributes: true, subtree: true, attributeFilter: ['class'] });
  })(); // end buildRunsPanel
  // ════════════════════════════════════════════════════════════
  // 5. ASSEMBLE TOP ROW  (Obs Sources | Results)
  // ════════════════════════════════════════════════════════════
  (function assembleTopRow() {
    // Remove any previous attempt
    document.querySelector('.console-top-row')?.remove();
    document.querySelector('.flow-divider')?.remove();
    const topRow = document.createElement('div');
    topRow.className = 'console-top-row';
    topRow.appendChild(obsPanel);
    topRow.appendChild(resultsPanel);
    // Insert after pipeline strip
    const pipeline = document.querySelector('.console-pipeline');
    pipeline.after(topRow);
    // Flow divider between top row and handoff
    const divider = document.createElement('div');
    divider.className = 'flow-divider';
    divider.textContent = '↓  ready for handoff to AAM';
    const hs = document.getElementById('handoffSection');
    topRow.after(divider);
    // Ensure handoff section follows the divider
    divider.after(hs);
  })();
  // ════════════════════════════════════════════════════════════
  // 6. RESTRUCTURE HANDOFF SECTION
  // ════════════════════════════════════════════════════════════
  (function restructureHandoff() {
    const hs = document.getElementById('handoffSection');
    if (!hs) return;
    // ── Guard: already restructured ──────────────────────────
    if (document.getElementById('hs-meta-row')) {
      _applyHandoffStyles();
      return;
    }
    // ── Collect original child elements ──────────────────────
    // Original order inside #handoffSection (from index.html):
    //   h2.section-title
    //   .stats-grid.stats-grid-4          ← KPI bar (102 / 4 / 6 / 91)
    //   #fabricPlanesBreakdown            ← iPaaS/API Gateway/Warehouse/Event Bus tabs
    //   #fabricFilterActive               ← "Showing: All | Clear Filter"
    //   div (no id) with select+buttons   ← status filter + Audit + Export
    //   .farm-metadata-section            ← Fabric Planes + SOR boxes
    //     └─ .section (Fabric Planes)
    //         └─ h3.section-title + #farmFabricPlanesContainer
    //     └─ .section (Systems of Record)
    //         └─ h3.section-title + #farmSORsContainer
    //   div (no id) with candidates       ← "Connection Candidates" header + #handoffCandidatesContainer + #handoffDrillPanel
    //   #fabricAuditPanel                 ← hidden audit trail
    const statsGrid    = hs.querySelector('.stats-grid');
    const fpBreakdown  = document.getElementById('fabricPlanesBreakdown');
    const filterActive = document.getElementById('fabricFilterActive');
    const farmMeta     = hs.querySelector('.farm-metadata-section');
    const auditPanel   = document.getElementById('fabricAuditPanel');
    // Find the controls div (the one containing the select)
    let ctrlDiv = null;
    Array.from(hs.children).forEach(c => {
      if (!ctrlDiv && c.querySelector && c.querySelector('#handoffStatusFilter')) {
        ctrlDiv = c;
      }
    });
    // Find the candidates wrapper (contains #handoffCandidatesContainer)
    let candWrapper = null;
    Array.from(hs.children).forEach(c => {
      if (!candWrapper && c.querySelector && c.querySelector('#handoffCandidatesContainer')) {
        candWrapper = c;
      }
    });
    // Extract the two metadata sections from farm-metadata-section
    const fpSection  = farmMeta?.children[0]; // Fabric Planes section
    const sorSection = farmMeta?.children[1]; // Systems of Record section
    // ── Build #hs-meta-row  (Fabric Planes | SORs side by side) ──
    const metaRow = document.createElement('div');
    metaRow.id = 'hs-meta-row';
    if (fpSection)  metaRow.appendChild(fpSection);
    if (sorSection) metaRow.appendChild(sorSection);
    // ── Build #chipDrillPanel (inline drill for chip clicks) ──
    const chipDrill = document.createElement('div');
    chipDrill.id    = 'chipDrillPanel';
    chipDrill.className = 'chip-drill-panel';
    // ── Build #hs-controls-row ──────────────────────────────
    const ctrlRow = document.createElement('div');
    ctrlRow.id = 'hs-controls-row';
    const sep = () => {
      const s = document.createElement('span');
      s.style.cssText = 'color:#2d3748;font-size:.9rem;flex-shrink:0;';
      s.textContent = '|';
      return s;
    };
    if (fpBreakdown)  ctrlRow.appendChild(fpBreakdown);
    ctrlRow.appendChild(sep());
    if (filterActive) ctrlRow.appendChild(filterActive);
    const pushSep = sep();
    pushSep.style.marginLeft = 'auto';
    ctrlRow.appendChild(pushSep);
    if (ctrlDiv)      ctrlRow.appendChild(ctrlDiv);
    // ── Build #hs-cand-section (collapsible candidates) ──────
    const candSection   = document.createElement('div');
    candSection.id      = 'hs-cand-section';
    const candToggle    = document.createElement('div');
    candToggle.id       = 'hs-cand-toggle';
    const candCount     = document.getElementById('handoffTotalCount')?.textContent?.trim() || '—';
    candToggle.innerHTML = `
      <div style="display:flex;align-items:center;gap:.5rem;">
        <span style="font-size:.78rem;font-weight:700;color:#63b3ed;">Connection Candidates</span>
        <span id="hs-cand-count-badge"
              style="font-size:.65rem;color:#718096;">${candCount} candidates</span>
      </div>
      <span id="hs-cand-chevron">▼</span>`;
    const candBody      = document.createElement('div');
    candBody.id         = 'hs-cand-body';
    // Move everything from candWrapper into candBody
    if (candWrapper) {
      while (candWrapper.firstChild) candBody.appendChild(candWrapper.firstChild);
    }
    candSection.appendChild(candToggle);
    candSection.appendChild(candBody);
    // Toggle logic
    let candOpen = true;
    candToggle.addEventListener('click', () => {
      candOpen = !candOpen;
      candBody.classList.toggle('collapsed', !candOpen);
      const chev = document.getElementById('hs-cand-chevron');
      if (chev) chev.style.transform = candOpen ? '' : 'rotate(-90deg)';
    });
    // ── Reassemble #handoffSection ────────────────────────────
    // Keep: h2.section-title, statsGrid, auditPanel (hidden)
    // Remove everything else and append in new order
    const title = hs.querySelector(':scope > h2.section-title, :scope > .section-title');
    // Clear hs of everything except title
    while (hs.lastChild) hs.removeChild(hs.lastChild);
    if (title)       hs.appendChild(title);
    if (statsGrid)   hs.appendChild(statsGrid);
    hs.appendChild(metaRow);
    hs.appendChild(chipDrill);
    hs.appendChild(ctrlRow);
    hs.appendChild(candSection);
    if (auditPanel)  hs.appendChild(auditPanel);
    // ── Apply all inline styles ───────────────────────────────
    _applyHandoffStyles();
    // ── Wire chip drills ──────────────────────────────────────
    _wireChipDrills(chipDrill);
  })(); // end restructureHandoff
  // ════════════════════════════════════════════════════════════
  // HELPER: apply inline styles to all handoff elements
  // (separated so it can be called if restructure already ran)
  // ════════════════════════════════════════════════════════════
  function _applyHandoffStyles() {
    const hs = document.getElementById('handoffSection');
    if (!hs) return;
    // Section container
    Object.assign(hs.style, {
      background: '#0f1923', border: '1px solid #1e2a3a',
      borderRadius: '10px', padding: '.85rem', marginTop: '.5rem',
    });
    // KPI bar (compact flex row)
    const statsGrid = hs.querySelector('.stats-grid');
    if (statsGrid) {
      Object.assign(statsGrid.style, {
        display: 'flex', gap: '.5rem', flexWrap: 'wrap', marginBottom: '.6rem',
      });
      statsGrid.querySelectorAll('.stat-card').forEach(card => {
        Object.assign(card.style, {
          background: '#131f2e', border: '1px solid #1e2a3a',
          borderRadius: '7px', padding: '.3rem .65rem',
          textAlign: 'center', minWidth: '70px', flex: '0 0 auto',
        });
        const val = card.querySelector('.stat-value');
        const lbl = card.querySelector('.stat-label');
        if (val) Object.assign(val.style, { fontSize: '1.1rem', fontWeight: '700', lineHeight: '1.2' });
        if (lbl) Object.assign(lbl.style, { fontSize: '.6rem', color: '#718096' });
      });
    }
    // Meta row boxes
    const metaRow = document.getElementById('hs-meta-row');
    if (metaRow) {
      Object.assign(metaRow.style, {
        display: 'grid', gridTemplateColumns: '1fr 1fr',
        gap: '.6rem', marginBottom: '.6rem', alignItems: 'stretch',
      });
      Array.from(metaRow.children).forEach(box => {
        Object.assign(box.style, {
          background: '#131f2e', border: '1px solid #1e2a3a',
          borderRadius: '7px', padding: '.5rem .6rem',
          marginBottom: '0', marginTop: '0',
          display: 'flex', flexDirection: 'column', alignSelf: 'stretch',
        });
        const h3 = box.querySelector('h3');
        if (h3) Object.assign(h3.style, {
          fontSize: '.68rem', fontWeight: '700', color: '#a0aec0',
          marginBottom: '.35rem', display: 'flex', alignItems: 'center', gap: '.4rem',
        });
        const dc = box.querySelector('.farm-data-container');
        if (dc) Object.assign(dc.style, {
          display: 'flex', flexDirection: 'column',
          gap: '.2rem', flex: '1', justifyContent: 'space-between',
        });
      });
    }
    // Fabric plane chips
    document.querySelectorAll('.fabric-plane-chip').forEach(chip => {
      Object.assign(chip.style, {
        display: 'flex', alignItems: 'center', gap: '.35rem',
        padding: '.22rem .45rem', borderRadius: '5px',
        background: '#0d1117', border: '1px solid #1e2a3a',
        cursor: 'pointer', flexWrap: 'nowrap', overflow: 'hidden',
      });
      const pt = chip.querySelector('.plane-type');
      const pv = chip.querySelector('.plane-vendor');
      const hb = chip.querySelector('.health-badge');
      const sb = chip.querySelector('.source-badge');
      if (pt) Object.assign(pt.style, { fontSize: '.6rem', color: '#718096', minWidth: '68px' });
      if (pv) Object.assign(pv.style, {
        fontSize: '.7rem', color: '#e2e8f0', fontWeight: '600', flex: '1',
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '90px',
      });
      if (hb) Object.assign(hb.style, {
        fontSize: '.58rem', padding: '.06rem .28rem', borderRadius: '3px',
        background: 'rgba(72,187,120,.15)', color: '#48bb78', fontWeight: '600',
      });
      if (sb) Object.assign(sb.style, {
        fontSize: '.58rem', padding: '.06rem .28rem', borderRadius: '3px',
        background: 'rgba(99,179,237,.1)', color: '#63b3ed', fontWeight: '600',
      });
    });
    // SOR chips
    document.querySelectorAll('.sor-chip').forEach(chip => {
      Object.assign(chip.style, {
        display: 'flex', alignItems: 'center', gap: '.35rem',
        padding: '.22rem .45rem', borderRadius: '5px',
        background: '#0d1117', border: '1px solid #1e2a3a',
        cursor: 'pointer', flexWrap: 'nowrap', overflow: 'hidden',
      });
      const sd = chip.querySelector('.sor-domain');
      const sn = chip.querySelector('.sor-name');
      const st = chip.querySelector('.sor-type');
      const cb = chip.querySelector('.confidence-badge');
      const srcb = chip.querySelector('.source-badge');
      if (sd)   Object.assign(sd.style,   { fontSize: '.6rem', color: '#718096', minWidth: '52px' });
      if (sn)   Object.assign(sn.style,   { fontSize: '.7rem', color: '#e2e8f0', fontWeight: '600', flex: '1' });
      if (st)   Object.assign(st.style,   { fontSize: '.58rem', color: '#a0aec0' });
      if (cb) {
        const isHigh   = cb.classList.contains('high');
        const isMedium = cb.classList.contains('medium');
        Object.assign(cb.style, {
          fontSize: '.58rem', padding: '.06rem .28rem', borderRadius: '3px', fontWeight: '600',
          background: isHigh   ? 'rgba(252,129,74,.15)'  :
                      isMedium ? 'rgba(236,201,75,.15)'  : 'rgba(160,174,192,.1)',
          color:      isHigh   ? '#fc814a' : isMedium ? '#ecc94b' : '#a0aec0',
        });
      }
      if (srcb) Object.assign(srcb.style, {
        fontSize: '.58rem', padding: '.06rem .28rem', borderRadius: '3px',
        background: 'rgba(99,179,237,.1)', color: '#63b3ed', fontWeight: '600',
      });
    });
    // Controls row
    const ctrlRow = document.getElementById('hs-controls-row');
    if (ctrlRow) {
      Object.assign(ctrlRow.style, {
        display: 'flex', flexWrap: 'wrap', alignItems: 'center',
        gap: '.45rem', marginBottom: '.6rem', padding: '.4rem .55rem',
        background: '#131f2e', border: '1px solid #1e2a3a', borderRadius: '7px',
      });
      const fpb = document.getElementById('fabricPlanesBreakdown');
      if (fpb) Object.assign(fpb.style, { display: 'flex', flexWrap: 'wrap', gap: '.28rem', flexShrink: '0' });
      const fa = document.getElementById('fabricFilterActive');
      if (fa)  Object.assign(fa.style,  { display: 'flex', alignItems: 'center', gap: '.4rem', fontSize: '.67rem', flexShrink: '0' });
      const sel = document.getElementById('handoffStatusFilter');
      if (sel) Object.assign(sel.style, { fontSize: '.68rem', padding: '.2rem .4rem' });
      const vBtn = document.getElementById('viewFabricAuditBtn');
      if (vBtn) Object.assign(vBtn.style, { fontSize: '.67rem', padding: '.22rem .55rem', whiteSpace: 'nowrap' });
      const eBtn = document.getElementById('exportToAAMBtn');
      if (eBtn) Object.assign(eBtn.style, { fontSize: '.67rem', padding: '.22rem .65rem', whiteSpace: 'nowrap' });
    }
    // Candidates container scroll
    const candContainer = document.getElementById('handoffCandidatesContainer');
    if (candContainer) {
      Object.assign(candContainer.style, {
        maxHeight: '460px', overflowY: 'auto',
        display: 'flex', flexDirection: 'column', gap: '.3rem', paddingRight: '.2rem',
      });
    }
    // Candidate cards
    document.querySelectorAll('.handoff-candidate-card').forEach(card => {
      Object.assign(card.style, {
        background: '#131f2e', border: '1px solid #1e2a3a',
        borderRadius: '7px', padding: '.45rem .6rem', cursor: 'pointer',
      });
    });
    // Candidate card sub-elements
    document.querySelectorAll('.handoff-card-header').forEach(h =>
      Object.assign(h.style, { display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '.4rem' }));
    document.querySelectorAll('.handoff-card-title').forEach(t =>
      Object.assign(t.style, { fontSize: '.76rem', fontWeight: '700', color: '#e2e8f0' }));
    document.querySelectorAll('.handoff-card-subtitle').forEach(s =>
      Object.assign(s.style, { fontSize: '.65rem', color: '#718096' }));
    document.querySelectorAll('.handoff-card-badges').forEach(b =>
      Object.assign(b.style, { display: 'flex', gap: '.25rem', flexWrap: 'wrap', flexShrink: '0' }));
    document.querySelectorAll('.handoff-card-body').forEach(body =>
      Object.assign(body.style, { marginTop: '.2rem', display: 'flex', flexWrap: 'wrap', gap: '.25rem', alignItems: 'center' }));
    document.querySelectorAll('.handoff-sor-tag').forEach(tag =>
      Object.assign(tag.style, {
        display: 'inline-flex', flexDirection: 'row', alignItems: 'center',
        gap: '.2rem', padding: '.06rem .3rem', borderRadius: '3px',
        background: '#0d1117', border: '1px solid #1e2a3a', whiteSpace: 'nowrap', maxWidth: '200px',
      }));
    document.querySelectorAll('.handoff-sor-label').forEach(l =>
      Object.assign(l.style, { fontSize: '.58rem', color: '#718096', display: 'inline' }));
    document.querySelectorAll('.handoff-sor-value').forEach(v =>
      Object.assign(v.style, { fontSize: '.62rem', color: '#a0aec0', fontWeight: '600', display: 'inline' }));
    document.querySelectorAll('.handoff-sor-confidence').forEach(c =>
      Object.assign(c.style, { fontSize: '.58rem', color: '#63b3ed', display: 'inline' }));
    document.querySelectorAll('.handoff-finding-list').forEach(fl =>
      Object.assign(fl.style, { display: 'inline-flex', flexWrap: 'wrap', gap: '.2rem', alignItems: 'center' }));
    document.querySelectorAll('.handoff-finding').forEach(f => {
      const isHigh = f.classList.contains('severity-high');
      const isMed  = f.classList.contains('severity-med');
      Object.assign(f.style, {
        fontSize: '.6rem', padding: '.05rem .3rem', borderRadius: '3px',
        fontWeight: '500', whiteSpace: 'nowrap',
        background: isHigh ? 'rgba(252,129,74,.12)' : isMed ? 'rgba(236,201,75,.1)' : 'rgba(160,174,192,.1)',
        color:      isHigh ? '#fc8181'               : isMed ? '#ecc94b'             : '#a0aec0',
      });
    });
    // Hide the original Discovery Runs standalone section
    const drTitle = Array.from(document.querySelectorAll('.section-title'))
      .find(el => el.textContent.trim() === 'Discovery Runs');
    const drSection = drTitle?.closest('.section') || drTitle?.parentElement;
    if (drSection && !drSection.id) {
      drSection.id = 'aod-runs-original';
      drSection.style.setProperty('display', 'none', 'important');
    }
  } // end _applyHandoffStyles
  // ════════════════════════════════════════════════════════════
  // HELPER: wire click-to-drill on fabric plane + SOR chips
  // ════════════════════════════════════════════════════════════
  function _wireChipDrills(drillPanel) {
    function showDrill(html) {
      drillPanel.innerHTML = html;
      drillPanel.style.display = 'block';
    }
    function drillRow(key, val) {
      return `<div style="display:flex;justify-content:space-between;
                          padding:.16rem 0;border-bottom:1px solid #1e2a3a;">
                <span style="color:#718096;">${key}</span>
                <span style="color:#e2e8f0;font-weight:500;">${val}</span>
              </div>`;
    }
    const closeBtn = `<span onclick="document.getElementById('chipDrillPanel').style.display='none'"
                           style="cursor:pointer;color:#4a5568;font-size:.8rem;padding:.1rem .3rem;">✕</span>`;
    // Fabric plane chips
    document.querySelectorAll('.fabric-plane-chip').forEach(chip => {
      chip.style.cursor = 'pointer';
      chip.addEventListener('click', () => {
        const type   = chip.querySelector('.plane-type')?.textContent?.trim()   || '—';
        const vendor = chip.querySelector('.plane-vendor')?.textContent?.trim() || '—';
        const health = chip.querySelector('.health-badge')?.textContent?.trim() || '—';
        const source = chip.querySelector('.source-badge')?.textContent?.trim() || '—';
        showDrill(`
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.35rem;">
            <span style="font-size:.72rem;font-weight:700;color:#63b3ed;">📋 ${type} — ${vendor}</span>
            ${closeBtn}
          </div>
          ${drillRow('Type',   type)}
          ${drillRow('Vendor', vendor)}
          ${drillRow('Health', health)}
          ${drillRow('Source', source)}`);
        document.querySelectorAll('.fabric-plane-chip')
          .forEach(c => { c.style.borderColor = '#1e2a3a'; });
        chip.style.borderColor = '#4299e1';
      });
    });
    // SOR chips
    document.querySelectorAll('.sor-chip').forEach(chip => {
      chip.style.cursor = 'pointer';
      chip.addEventListener('click', () => {
        const domain     = chip.querySelector('.sor-domain')?.textContent?.trim()      || '—';
        const name       = chip.querySelector('.sor-name')?.textContent?.trim()        || '—';
        const type       = chip.querySelector('.sor-type')?.textContent?.trim()        || '—';
        const confidence = chip.querySelector('.confidence-badge')?.textContent?.trim() || '—';
        const source     = chip.querySelector('.source-badge')?.textContent?.trim()    || '—';
        showDrill(`
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.35rem;">
            <span style="font-size:.72rem;font-weight:700;color:#9f7aea;">🗃 ${domain} — ${name}</span>
            ${closeBtn}
          </div>
          ${drillRow('Domain',     domain)}
          ${drillRow('System',     name)}
          ${drillRow('Type',       type)}
          ${drillRow('Confidence', confidence)}
          ${drillRow('Source',     source)}`);
        document.querySelectorAll('.sor-chip')
          .forEach(c => { c.style.borderColor = '#1e2a3a'; });
        chip.style.borderColor = '#9f7aea';
      });
    });
  } // end _wireChipDrills
} // end initConsoleRedesign




Integration checklist
templates/index.html — no changes needed. All IDs the script references (tenantSelect, fetchFromFarm, handoffBtn, farmStatusBadge, observationPlanesGrid, summaryTab, runDescriptors, handoffSection, fabricPlanesBreakdown, fabricFilterActive, farmFabricPlanesContainer, farmSORsContainer, handoffCandidatesContainer, handoffDrillPanel, fabricAuditPanel, runsList, consoleGuide, discoveryTabContent) must remain in the HTML exactly as they are — the script reads from them but leaves them hidden.
static/js/app.js — find your existing Console tab init (likely something like function initConsoleTab() or a tab-switch handler for #consoleTab) and add one line at the end of it:
jsinitConsoleRedesign();
Load order — initConsoleRedesign() must run after the page's own initConsoleTab() has already populated #runsList, #summaryTab, and #handoffSection with live data. If your app lazy-populates these on first tab click, calling it at the end of that same callback is correct. If it runs on DOMContentLoaded before data loads, wrap with a short setTimeout or fire it from your existing data-ready callback.


