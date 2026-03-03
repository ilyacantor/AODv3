/* ============================================================
   AOD Console — Pipeline strip + interactive behaviors
   Replaces the old 877-line overlay with native HTML layout.
   Exposes: initConsoleRedesign(), updatePipelineStrip(), updateObsBars()
   ============================================================ */

// ════════════════════════════════════════════════════════════
// 1. PIPELINE STRIP  (JS-built, injected after consoleGuide)
// ════════════════════════════════════════════════════════════
function initConsoleRedesign() {
  if (document.querySelector('.console-pipeline')) return;
  const tabContent = document.getElementById('discoveryTabContent');
  if (!tabContent) return;

  const steps = [
    { n: 1, label: 'Select Tenant' },
    { n: 2, label: 'Review Sources' },
    { n: 3, label: 'Run Discovery' },
    { n: 4, label: 'Review Results' },
    { n: 5, label: 'Handoff to AAM' },
  ];
  const strip = document.createElement('div');
  strip.className = 'console-pipeline';
  steps.forEach((st, i) => {
    strip.innerHTML +=
      `<div class="cp-step" data-step="${st.n}">` +
        `<span class="cp-num">${st.n}</span>${st.label}</div>` +
      (i < steps.length - 1 ? '<span class="cp-arrow">\u203A</span>' : '');
  });
  const guide = document.getElementById('consoleGuide');
  if (guide) guide.after(strip);
  else tabContent.prepend(strip);

  // Wire interactive behaviors now that DOM is ready
  _wireRunsCollapse();
  _wireCandidatesCollapse();
  _wireObsHandoffBtn();
  _wireChipDrills();

  updatePipelineStrip();
  updateObsBars();
}

// ════════════════════════════════════════════════════════════
// 2. REACTIVE PIPELINE STRIP
// ════════════════════════════════════════════════════════════
function updatePipelineStrip() {
  const strip = document.querySelector('.console-pipeline');
  if (!strip) return;
  const steps = strip.querySelectorAll('.cp-step');
  if (steps.length < 5) return;

  const tenantVal = document.getElementById('tenantSelect')?.value;
  const step1Done = !!tenantVal;

  const obsCounts = ['planeCountDiscovery','planeCountIdp','planeCountCmdb',
    'planeCountCloud','planeCountEndpoint','planeCountNetwork','planeCountFinance'];
  const step2Done = obsCounts.some(id => {
    const n = parseInt(document.getElementById(id)?.textContent);
    return !isNaN(n) && n > 0;
  });

  const resultsSection = document.getElementById('resultsSection');
  const step3Done = resultsSection && !resultsSection.classList.contains('hidden');

  const assetsCount = parseInt(document.getElementById('statAssets')?.textContent);
  const step4Done = step3Done && !isNaN(assetsCount) && assetsCount > 0;

  const handoffCount = parseInt(document.getElementById('handoffTotalCount')?.textContent);
  const step5Done = !isNaN(handoffCount) && handoffCount > 0;

  const states = [step1Done, step2Done, step3Done, step4Done, step5Done];
  let activeIdx = states.findIndex(s => !s);
  if (activeIdx === -1) activeIdx = 4;

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

  // Enable/disable Handoff button
  const handoffBtn = document.getElementById('obsHandoffBtn');
  if (handoffBtn) handoffBtn.disabled = !step5Done;
}

// ════════════════════════════════════════════════════════════
// 3. UPDATE OBS SOURCE BAR WIDTHS
// ════════════════════════════════════════════════════════════
const OBS_BAR_MAP = [
  { countId: 'planeCountDiscovery', barId: 'obsBarDiscovery', max: 500 },
  { countId: 'planeCountIdp',       barId: 'obsBarIdp',       max: 200 },
  { countId: 'planeCountCmdb',      barId: 'obsBarCmdb',      max: 200 },
  { countId: 'planeCountCloud',     barId: 'obsBarCloud',     max: 200 },
  { countId: 'planeCountEndpoint',  barId: 'obsBarEndpoint',  max: 500 },
  { countId: 'planeCountNetwork',   barId: 'obsBarNetwork',   max: 4000 },
  { countId: 'planeCountFinance',   barId: 'obsBarFinance',   max: 400 },
];

function updateObsBars() {
  OBS_BAR_MAP.forEach(({ countId, barId, max }) => {
    const countEl = document.getElementById(countId);
    const barEl = document.getElementById(barId);
    if (!countEl || !barEl) return;
    const n = parseInt(countEl.textContent.replace(/[^\d]/g, ''));
    barEl.style.width = (isNaN(n) || n <= 0)
      ? '0%'
      : Math.min(100, Math.round(n / max * 100)) + '%';
  });
}

// ════════════════════════════════════════════════════════════
// 4. INTERACTIVE BEHAVIORS
// ════════════════════════════════════════════════════════════

// Discovery Runs collapse/expand
function _wireRunsCollapse() {
  const header = document.getElementById('runsRowHeader');
  const body = document.getElementById('runsBody');
  const chevron = document.getElementById('runsChevron');
  if (!header || !body) return;
  let open = true;
  header.addEventListener('click', () => {
    open = !open;
    body.classList.toggle('collapsed', !open);
    if (chevron) chevron.classList.toggle('collapsed', !open);
  });
}

// Connection Candidates collapse/expand
function _wireCandidatesCollapse() {
  const toggle = document.getElementById('hs-cand-toggle');
  const body = document.getElementById('hs-cand-body');
  const chevron = document.getElementById('hs-cand-chevron');
  if (!toggle || !body) return;
  let open = true;
  toggle.addEventListener('click', () => {
    open = !open;
    body.classList.toggle('collapsed', !open);
    if (chevron) chevron.style.transform = open ? '' : 'rotate(-90deg)';
  });
}

// Obs panel Handoff button
function _wireObsHandoffBtn() {
  const btn = document.getElementById('obsHandoffBtn');
  if (!btn) return;
  btn.addEventListener('click', () => {
    const hs = document.getElementById('handoffSection');
    if (hs) hs.scrollIntoView({ behavior: 'smooth' });
    if (typeof exportToAAM === 'function') {
      exportToAAM();
    } else {
      document.getElementById('exportToAAMBtn')?.click();
    }
  });
}

// Chip drill click handlers for fabric plane and SOR chips
function _wireChipDrills() {
  const drillPanel = document.getElementById('chipDrillPanel');
  if (!drillPanel) return;

  function showDrill(html) {
    drillPanel.innerHTML = html;
    drillPanel.style.display = 'block';
  }
  function drillRow(key, val) {
    return `<div style="display:flex;justify-content:space-between;padding:.16rem 0;border-bottom:1px solid #1e2a3a;">
      <span style="color:#718096;">${key}</span>
      <span style="color:#e2e8f0;font-weight:500;">${val}</span>
    </div>`;
  }
  const closeBtn = `<span onclick="document.getElementById('chipDrillPanel').style.display='none'"
    style="cursor:pointer;color:#4a5568;font-size:.8rem;padding:.1rem .3rem;">\u2715</span>`;

  // Use event delegation on handoffSection for dynamically rendered chips
  const hs = document.getElementById('handoffSection');
  if (!hs) return;

  hs.addEventListener('click', (e) => {
    const fpChip = e.target.closest('.fabric-plane-chip');
    if (fpChip) {
      const type   = fpChip.querySelector('.plane-type')?.textContent?.trim()   || '\u2014';
      const vendor = fpChip.querySelector('.plane-vendor')?.textContent?.trim() || '\u2014';
      const health = fpChip.querySelector('.health-badge')?.textContent?.trim() || '\u2014';
      const source = fpChip.querySelector('.source-badge')?.textContent?.trim() || '\u2014';
      showDrill(`
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.35rem;">
          <span style="font-size:.72rem;font-weight:700;color:#63b3ed;">\uD83D\uDCCB ${type} \u2014 ${vendor}</span>
          ${closeBtn}
        </div>
        ${drillRow('Type', type)}${drillRow('Vendor', vendor)}
        ${drillRow('Health', health)}${drillRow('Source', source)}`);
      hs.querySelectorAll('.fabric-plane-chip').forEach(c => c.style.borderColor = '#1e2a3a');
      fpChip.style.borderColor = '#4299e1';
      return;
    }

    const sorChip = e.target.closest('.sor-chip');
    if (sorChip) {
      const domain     = sorChip.querySelector('.sor-domain')?.textContent?.trim()      || '\u2014';
      const name       = sorChip.querySelector('.sor-name')?.textContent?.trim()        || '\u2014';
      const type       = sorChip.querySelector('.sor-type')?.textContent?.trim()        || '\u2014';
      const confidence = sorChip.querySelector('.confidence-badge')?.textContent?.trim() || '\u2014';
      const source     = sorChip.querySelector('.source-badge')?.textContent?.trim()    || '\u2014';
      showDrill(`
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.35rem;">
          <span style="font-size:.72rem;font-weight:700;color:#9f7aea;">\uD83D\uDDC3 ${domain} \u2014 ${name}</span>
          ${closeBtn}
        </div>
        ${drillRow('Domain', domain)}${drillRow('System', name)}
        ${drillRow('Type', type)}${drillRow('Confidence', confidence)}${drillRow('Source', source)}`);
      hs.querySelectorAll('.sor-chip').forEach(c => c.style.borderColor = '#1e2a3a');
      sorChip.style.borderColor = '#9f7aea';
    }
  });
}

// Expose globally
window.updatePipelineStrip = updatePipelineStrip;
window.updateObsBars = updateObsBars;
window.initConsoleRedesign = initConsoleRedesign;
