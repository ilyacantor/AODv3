/* ============================================================
   AOD Console Redesign v3
   Called once from initConsoleTab() in app.js
   Exposes: initConsoleRedesign(), updatePipelineStrip()
   ============================================================ */

function initConsoleRedesign() {
  // ── Guard: don't double-init ──────────────────────────────
  if (document.querySelector('.console-pipeline')) return;
  const tabContent = document.getElementById('discoveryTabContent');
  if (!tabContent) return;

  // ════════════════════════════════════════════════════════════
  // 1. PIPELINE STRIP  (reactive — updated by updatePipelineStrip)
  // ════════════════════════════════════════════════════════════
  (function buildPipeline() {
    const steps = [
      { n: 1, label: 'Select Tenant',  done: false },
      { n: 2, label: 'Review Sources', done: false },
      { n: 3, label: 'Run Discovery',  done: false },
      { n: 4, label: 'Review Results', done: false },
      { n: 5, label: 'Handoff to AAM', done: false },
    ];
    const strip = document.createElement('div');
    strip.className = 'console-pipeline';
    steps.forEach((st, i) => {
      const cls  = st.done ? 'done' : st.active ? 'active' : '';
      const icon = st.done ? '\u2713' : st.n;
      strip.innerHTML += `<div class="cp-step ${cls}" data-step="${st.n}">
        <span class="cp-num">${icon}</span>${st.label}</div>` +
        (i < steps.length - 1 ? '<span class="cp-arrow">\u203A</span>' : '');
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
      { icon: '\uD83D\uDD0D', name: 'Discovery',  count: 0, max: 500,  color: '#4299e1' },
      { icon: '\uD83D\uDD10', name: 'IdP',        count: 0, max: 200,  color: '#9f7aea' },
      { icon: '\uD83D\uDCCB', name: 'CMDB',       count: 0, max: 200,  color: '#48bb78' },
      { icon: '\u2601\uFE0F', name: 'Cloud',      count: 0, max: 200,  color: '#ed8936' },
      { icon: '\uD83D\uDCBB', name: 'Endpoint',   count: 0, max: 500,  color: '#f6ad55' },
      { icon: '\uD83C\uDF10', name: 'Network',    count: 0, max: 4000, color: '#63b3ed' },
      { icon: '\uD83D\uDCB0', name: 'Finance',    count: 0, max: 400,  color: '#fc8181' },
    ];
    // Read live counts from original observation-plane-card elements
    const origGrid = document.getElementById('observationPlanesGrid');
    if (origGrid) {
      Array.from(origGrid.querySelectorAll('.observation-plane-card')).forEach((card, i) => {
        if (i >= sources.length) return;
        const numEl = card.querySelector('.plane-count, [class*="count"], strong, b');
        if (numEl) {
          const n = parseInt(numEl.textContent.replace(/[^\d]/g, ''));
          if (!isNaN(n)) sources[i].count = n;
        }
        if (!sources[i].count) {
          const m = card.textContent.match(/\b(\d{2,5})\b/);
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
        <span id="farmStatusBadgeNew" style="font-size:.65rem;color:#48bb78;">\u25CF Farm Online</span>
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
            <span class="obs-source-count">${count ? count.toLocaleString() : '\u2014'}</span>
          </div>`;
        }).join('')}
      </div>
      <div class="obs-action-row">
        <button class="btn btn-primary" id="obsRunBtn">\u26A1 Run Discovery</button>
        <button class="btn btn-outline-secondary" id="obsHandoffBtn" disabled>Handoff \u2192</button>
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
      origSelect.addEventListener('change', () => { clone.value = origSelect.value; });
      panel.querySelector('#obs-tenant-mount').appendChild(clone);
    }

    // Wire Run Discovery button
    panel.querySelector('#obsRunBtn').addEventListener('click', () => {
      document.getElementById('fetchFromFarm')?.click();
    });

    // Wire Handoff button — triggers export and scrolls to handoff section
    panel.querySelector('#obsHandoffBtn').addEventListener('click', () => {
      const hs = document.getElementById('handoffSection');
      if (hs) hs.scrollIntoView({ behavior: 'smooth' });
      // Trigger export if exportToAAM is available
      if (typeof exportToAAM === 'function') {
        exportToAAM();
      } else {
        document.getElementById('exportToAAMBtn')?.click();
      }
    });

    // MutationObserver: keep counts in sync when original grid updates
    if (origGrid) {
      const observer = new MutationObserver(() => {
        Array.from(origGrid.querySelectorAll('.observation-plane-card')).forEach((card, i) => {
          if (i >= sources.length) return;
          const numEl = card.querySelector('.plane-count, [class*="count"], strong, b');
          if (!numEl) return;
          const n = parseInt(numEl.textContent.replace(/[^\d]/g, ''));
          if (isNaN(n)) return;
          const row     = panel.querySelector(`[data-source-idx="${i}"]`);
          const countEl = row?.querySelector('.obs-source-count');
          const barEl   = row?.querySelector('.obs-source-bar');
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
        val: c.querySelector('.stat-value')?.textContent?.trim() || '\u2014',
        sub: c.querySelector('.stat-sublabel')?.textContent?.trim() || '',
      };
    });

    const runId    = document.getElementById('descRunId')?.textContent?.trim()    || '\u2014';
    const tenant   = document.getElementById('descTenant')?.textContent?.trim()   || '\u2014';
    const status   = document.getElementById('descStatus')?.textContent?.trim()   || '\u2014';
    const compEl   = document.querySelector('#runDescriptors .run-desc-item:last-child .run-desc-value');
    const completed = compEl?.textContent?.trim() || '\u2014';

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
              <div class="kv" style="color:${KPI_COLORS[lbl]}" id="rpKpi${lbl}">${cardMap[lbl]?.val||'\u2014'}</div>
              <div class="kl">${lbl}</div>
            </div>`).join('')}
          </div>
        </div>
        <div class="kpi-group">
          <div class="kpi-group-label">Classifications</div>
          <div class="kpi-row-inner">
            ${['Shadow','Zombie','Security Risks','Governance'].map(lbl => {
              const safeId = lbl.replace(/\s+/g,'');
              return `<div class="kpi-cell">
                <div class="kv" style="color:${KPI_COLORS[lbl]}" id="rpKpi${safeId}">${cardMap[lbl]?.val||'\u2014'}</div>
                <div class="kl">${lbl==='Security Risks'?'Sec. Risks':lbl}</div>
                ${cardMap[lbl]?.sub ? `<div class="ks">${cardMap[lbl].sub}</div>` : ''}
              </div>`;
            }).join('')}
          </div>
        </div>
      </div>
      <div class="results-go-btn-wrap">
        <button class="btn btn-outline-secondary" id="rpGoToFarmBtn">Go to Farm for Grading \u2192</button>
      </div>`;

    panel.querySelector('#rpGoToFarmBtn').addEventListener('click', () => {
      document.getElementById('goToFarmBtn')?.click();
    });

    // Keep Results panel in sync when the hidden summaryTab updates
    const summaryTab = document.getElementById('summaryTab');
    if (summaryTab) {
      const syncResults = () => {
        document.querySelectorAll('#summaryTab .stat-card').forEach(c => {
          const lbl = c.querySelector('.stat-label')?.textContent?.trim() || '';
          const val = c.querySelector('.stat-value')?.textContent?.trim() || '\u2014';
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
                || c.querySelector('.run-tenant')?.textContent?.trim() || '\u2014',
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
          <span class="runs-chevron" id="runsChevron">\u25BC</span>
          <span class="runs-row-title">Discovery Runs</span>
          <span class="runs-count-badge" id="runsCountBadge">${total}</span>
        </div>
        <div class="runs-row-right">
          <input class="runs-filter-input" id="runsFilterInput"
                 type="text" placeholder="Filter tenant\u2026" autocomplete="off"/>
          <button class="runs-clear-btn" id="runsClearBtn"
                  title="Clear all runs from view">\u2298 Clear All</button>
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
        `Remove all ${total} discovery runs from this view?\n` +
        `(Display only \u2014 stored data is not affected.)`
      )) return;
      const list = document.getElementById('runsItemsList');
      list.innerHTML = `<div class="runs-no-results"
        style="display:block;padding:.6rem 0;color:#4a5568;">
        All runs cleared. Refresh to restore.</div>`;
      document.getElementById('runsCountBadge').textContent = '0';
      document.getElementById('runsFilterInput').disabled = true;
    });

    // Click a run row -> proxy to original run-item click
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
    document.querySelector('.console-top-row')?.remove();
    document.querySelector('.flow-divider')?.remove();

    const topRow = document.createElement('div');
    topRow.className = 'console-top-row';
    topRow.appendChild(obsPanel);
    topRow.appendChild(resultsPanel);

    const pipeline = document.querySelector('.console-pipeline');
    pipeline.after(topRow);

    // Hide original sections that the redesign replaces
    // (keep them in DOM so existing JS still reads/writes their values)
    const sectionRow = tabContent.querySelector('.section-row');
    if (sectionRow) sectionRow.style.setProperty('display', 'none', 'important');
    const resultsSection = document.getElementById('resultsSection');
    if (resultsSection) resultsSection.style.setProperty('display', 'none', 'important');

    // Flow divider between top row and handoff
    const divider = document.createElement('div');
    divider.className = 'flow-divider';
    divider.textContent = '\u2193  ready for handoff to AAM';
    const hs = document.getElementById('handoffSection');
    topRow.after(divider);
    if (hs) divider.after(hs);
  })();

  // ════════════════════════════════════════════════════════════
  // 6. RESTRUCTURE HANDOFF SECTION
  // ════════════════════════════════════════════════════════════
  (function restructureHandoff() {
    const hs = document.getElementById('handoffSection');
    if (!hs) return;

    // Guard: already restructured
    if (document.getElementById('hs-meta-row')) {
      _applyHandoffStyles();
      return;
    }

    // Collect original child elements
    const statsGrid    = hs.querySelector('.stats-grid');
    const fpBreakdown  = document.getElementById('fabricPlanesBreakdown');
    const filterActive = document.getElementById('fabricFilterActive');
    const farmMeta     = hs.querySelector('.farm-metadata-section');
    const auditPanel   = document.getElementById('fabricAuditPanel');

    // Find the controls div (containing handoffStatusFilter)
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

    // Extract metadata sections
    const fpSection  = farmMeta?.children[0];
    const sorSection = farmMeta?.children[1];

    // Build #hs-meta-row
    const metaRow = document.createElement('div');
    metaRow.id = 'hs-meta-row';
    if (fpSection)  metaRow.appendChild(fpSection);
    if (sorSection) metaRow.appendChild(sorSection);

    // Build #chipDrillPanel
    const chipDrill = document.createElement('div');
    chipDrill.id    = 'chipDrillPanel';
    chipDrill.className = 'chip-drill-panel';

    // Build #hs-controls-row
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
    if (ctrlDiv) ctrlRow.appendChild(ctrlDiv);

    // Build #hs-cand-section (collapsible candidates)
    const candSection   = document.createElement('div');
    candSection.id      = 'hs-cand-section';
    const candToggle    = document.createElement('div');
    candToggle.id       = 'hs-cand-toggle';
    const candCount     = document.getElementById('handoffTotalCount')?.textContent?.trim() || '\u2014';
    candToggle.innerHTML = `
      <div style="display:flex;align-items:center;gap:.5rem;">
        <span style="font-size:.78rem;font-weight:700;color:#63b3ed;">Connection Candidates</span>
        <span id="hs-cand-count-badge"
              style="font-size:.65rem;color:#718096;">${candCount} candidates</span>
      </div>
      <span id="hs-cand-chevron">\u25BC</span>`;

    const candBody = document.createElement('div');
    candBody.id = 'hs-cand-body';
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

    // Reassemble #handoffSection
    const title = hs.querySelector(':scope > h2.section-title, :scope > .section-title');
    while (hs.lastChild) hs.removeChild(hs.lastChild);
    if (title)       hs.appendChild(title);
    if (statsGrid)   hs.appendChild(statsGrid);
    hs.appendChild(metaRow);
    hs.appendChild(chipDrill);
    hs.appendChild(ctrlRow);
    hs.appendChild(candSection);
    if (auditPanel)  hs.appendChild(auditPanel);

    _applyHandoffStyles();
    _wireChipDrills(chipDrill);
  })(); // end restructureHandoff

  // ════════════════════════════════════════════════════════════
  // HELPER: apply inline styles to all handoff elements
  // ════════════════════════════════════════════════════════════
  function _applyHandoffStyles() {
    const hs = document.getElementById('handoffSection');
    if (!hs) return;

    Object.assign(hs.style, {
      background: '#0f1923', border: '1px solid #1e2a3a',
      borderRadius: '10px', padding: '.85rem', marginTop: '.5rem',
    });

    // KPI bar
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

    // Meta row
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
      if (sd) Object.assign(sd.style, { fontSize: '.6rem', color: '#718096', minWidth: '52px' });
      if (sn) Object.assign(sn.style, { fontSize: '.7rem', color: '#e2e8f0', fontWeight: '600', flex: '1' });
      if (st) Object.assign(st.style, { fontSize: '.58rem', color: '#a0aec0' });
      if (cb) {
        const isHigh   = cb.classList.contains('high');
        const isMedium = cb.classList.contains('medium');
        Object.assign(cb.style, {
          fontSize: '.58rem', padding: '.06rem .28rem', borderRadius: '3px', fontWeight: '600',
          background: isHigh   ? 'rgba(252,129,74,.15)' :
                      isMedium ? 'rgba(236,201,75,.15)' : 'rgba(160,174,192,.1)',
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
      if (fa)  Object.assign(fa.style, { display: 'flex', alignItems: 'center', gap: '.4rem', fontSize: '.67rem', flexShrink: '0' });
      const sel = document.getElementById('handoffStatusFilter');
      if (sel) Object.assign(sel.style, { fontSize: '.68rem', padding: '.2rem .4rem' });
      const vBtn = document.getElementById('viewFabricAuditBtn');
      if (vBtn) Object.assign(vBtn.style, { fontSize: '.67rem', padding: '.22rem .55rem', whiteSpace: 'nowrap' });
      const eBtn = document.getElementById('exportToAAMBtn');
      if (eBtn) Object.assign(eBtn.style, { fontSize: '.67rem', padding: '.22rem .65rem', whiteSpace: 'nowrap' });
    }

    // Candidates container
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
                           style="cursor:pointer;color:#4a5568;font-size:.8rem;padding:.1rem .3rem;">\u2715</span>`;

    // Fabric plane chips
    document.querySelectorAll('.fabric-plane-chip').forEach(chip => {
      chip.style.cursor = 'pointer';
      chip.addEventListener('click', () => {
        const type   = chip.querySelector('.plane-type')?.textContent?.trim()   || '\u2014';
        const vendor = chip.querySelector('.plane-vendor')?.textContent?.trim() || '\u2014';
        const health = chip.querySelector('.health-badge')?.textContent?.trim() || '\u2014';
        const source = chip.querySelector('.source-badge')?.textContent?.trim() || '\u2014';
        showDrill(`
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.35rem;">
            <span style="font-size:.72rem;font-weight:700;color:#63b3ed;">\uD83D\uDCCB ${type} \u2014 ${vendor}</span>
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
        const domain     = chip.querySelector('.sor-domain')?.textContent?.trim()      || '\u2014';
        const name       = chip.querySelector('.sor-name')?.textContent?.trim()        || '\u2014';
        const type       = chip.querySelector('.sor-type')?.textContent?.trim()        || '\u2014';
        const confidence = chip.querySelector('.confidence-badge')?.textContent?.trim() || '\u2014';
        const source     = chip.querySelector('.source-badge')?.textContent?.trim()    || '\u2014';
        showDrill(`
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.35rem;">
            <span style="font-size:.72rem;font-weight:700;color:#9f7aea;">\uD83D\uDDC3 ${domain} \u2014 ${name}</span>
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

  // Initial pipeline state
  updatePipelineStrip();

} // end initConsoleRedesign


// ════════════════════════════════════════════════════════════
// REACTIVE PIPELINE STRIP
// Exposed on window — called from app.js hooks
// ════════════════════════════════════════════════════════════
function updatePipelineStrip() {
  const strip = document.querySelector('.console-pipeline');
  if (!strip) return;

  const steps = strip.querySelectorAll('.cp-step');
  if (steps.length < 5) return;

  // Step 1: Select Tenant — done when tenantSelect has a value
  const tenantVal = document.getElementById('tenantSelect')?.value;
  const step1Done = !!tenantVal;

  // Step 2: Review Sources — done when any observation count > 0
  const obsCounts = ['planeCountDiscovery','planeCountIdp','planeCountCmdb','planeCountCloud','planeCountEndpoint','planeCountNetwork','planeCountFinance'];
  const step2Done = obsCounts.some(id => {
    const el = document.getElementById(id);
    const n = parseInt(el?.textContent);
    return !isNaN(n) && n > 0;
  });

  // Step 3: Run Discovery — done when resultsSection is visible with data
  const resultsSection = document.getElementById('resultsSection');
  const step3Done = resultsSection && !resultsSection.classList.contains('hidden');

  // Step 4: Review Results — done when there are actual assets
  const assetsEl = document.getElementById('statAssets');
  const assetsCount = parseInt(assetsEl?.textContent);
  const step4Done = step3Done && !isNaN(assetsCount) && assetsCount > 0;

  // Step 5: Handoff to AAM — done when handoff section has candidates
  const handoffTotal = document.getElementById('handoffTotalCount');
  const handoffCount = parseInt(handoffTotal?.textContent);
  const step5Done = !isNaN(handoffCount) && handoffCount > 0;

  const states = [
    step1Done,
    step2Done,
    step3Done,
    step4Done,
    step5Done,
  ];

  // Find the first incomplete step — that's "active"
  let activeIdx = states.findIndex(s => !s);
  if (activeIdx === -1) activeIdx = 4; // all done

  steps.forEach((step, i) => {
    step.classList.remove('done', 'active');
    const numEl = step.querySelector('.cp-num');
    if (states[i]) {
      step.classList.add('done');
      if (numEl) numEl.textContent = '\u2713';
    } else if (i === activeIdx) {
      step.classList.add('active');
      if (numEl) numEl.textContent = i + 1;
    } else {
      if (numEl) numEl.textContent = i + 1;
    }
  });

  // Enable/disable Handoff button based on data availability
  const handoffBtn = document.getElementById('obsHandoffBtn');
  if (handoffBtn) {
    handoffBtn.disabled = !step5Done;
  }
}

// Make updatePipelineStrip available globally
window.updatePipelineStrip = updatePipelineStrip;
