const TourManager = (function() {
    const STORAGE_KEY = 'aod_guided_tour';
    
    let aborted = false;
    let pendingTimeouts = [];
    
    const TOUR_PHASES = {
        0: { 
            title: "Welcome to AOD",
            content: "AOD discovers what actually exists in an enterprise environment. This run shows how discovery is executed, inspected, and verified.",
            step: 1
        },
        3: { 
            title: "Run Discovery",
            content: "Welcome back to AOD. The tenant has been loaded. Press Fetch & Run Discovery and then review the results of the Run below.",
            step: 2
        },
        '3b': { 
            title: "Discovery Results",
            content: "",
            step: 3
        },
        5: { 
            title: "Triage Findings",
            content: "Current configuration is three tiers - action recommended, needs judgment, and informational. The system is now configured as an information plane. It can also be configured as a control plane. Feel free to click on Actions to dispose of the issues.",
            step: 4
        },
        6: { 
            title: "Asset Catalog",
            content: "The penultimate product of the discovery effort is the Catalog which is then passed to the AOS Adaptive API Mesh to obtain and sustain connections autonomously.",
            step: 5
        },
        6.5: { 
            title: "Asset Catalog",
            content: "No assets found in the catalog for this run. This may indicate the run is still processing or no assets were discovered.",
            step: 5
        },
        7: { 
            title: "Verify Accuracy",
            content: "Now let's verify AOD's accuracy. Farm will compare AOD's classifications against the expected ground truth to measure precision and recall.",
            step: 6
        },
        8: { 
            title: "Tour Complete",
            content: "The guided validation is complete. You've seen how AOD discovers assets and how Farm verifies accuracy. You may now explore freely.",
            step: 7
        }
    };
    
    const TOTAL_STEPS = 7;
    
    function trackedTimeout(fn, delay) {
        const id = setTimeout(() => {
            pendingTimeouts = pendingTimeouts.filter(t => t !== id);
            if (!aborted) fn();
        }, delay);
        pendingTimeouts.push(id);
        return id;
    }
    
    function trackedDelay(delay) {
        return new Promise(resolve => {
            trackedTimeout(resolve, delay);
        });
    }
    
    function clearAllTimeouts() {
        pendingTimeouts.forEach(id => clearTimeout(id));
        pendingTimeouts = [];
    }
    
    function getState() {
        try {
            const stored = localStorage.getItem(STORAGE_KEY);
            if (stored) {
                return JSON.parse(stored);
            }
        } catch (e) {
            console.error('TourManager: Failed to read state', e);
        }
        return { active: false, phase: 0, runId: null };
    }
    
    function setState(state) {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
        } catch (e) {
            console.error('TourManager: Failed to save state', e);
        }
    }
    
    function clearState() {
        try {
            localStorage.removeItem(STORAGE_KEY);
        } catch (e) {
            console.error('TourManager: Failed to clear state', e);
        }
    }
    
    function removeOverlay() {
        const existingScrim = document.querySelector('.tour-scrim');
        const existingOverlay = document.querySelector('.tour-overlay');
        if (existingScrim) existingScrim.remove();
        if (existingOverlay) existingOverlay.remove();
        document.querySelectorAll('.tour-highlight').forEach(el => el.classList.remove('tour-highlight'));
    }
    
    function getStatCount(drillType) {
        const card = document.querySelector(`.stat-card[data-drill-type="${drillType}"]`);
        if (!card) return 0;
        const valueEl = card.querySelector('.stat-value');
        if (!valueEl) return 0;
        const val = parseInt(valueEl.textContent, 10);
        return isNaN(val) ? 0 : val;
    }
    
    function positionOverlayNearElement(overlay, element) {
        if (!element) return;
        
        element.scrollIntoView({ behavior: 'smooth', block: 'center' });
        
        const rect = element.getBoundingClientRect();
        const overlayHeight = 200;
        const viewportHeight = window.innerHeight;
        const viewportWidth = window.innerWidth;
        
        overlay.style.position = 'fixed';
        overlay.style.transform = 'none';
        
        const spaceBelow = viewportHeight - rect.bottom;
        const spaceAbove = rect.top;
        
        if (spaceBelow >= overlayHeight + 20) {
            overlay.style.top = (rect.bottom + 20) + 'px';
        } else if (spaceAbove >= overlayHeight + 20) {
            overlay.style.top = (rect.top - overlayHeight - 20) + 'px';
        } else {
            overlay.style.top = '50%';
            overlay.style.transform = 'translateY(-50%)';
        }
        
        const overlayWidth = 400;
        if (rect.left + overlayWidth / 2 < viewportWidth && rect.left > overlayWidth / 2) {
            overlay.style.left = Math.max(20, rect.left + rect.width / 2 - overlayWidth / 2) + 'px';
        } else if (rect.right > viewportWidth / 2) {
            overlay.style.right = '20px';
            overlay.style.left = 'auto';
        } else {
            overlay.style.left = '20px';
        }
    }
    
    function showOverlay(phaseKey, options = {}) {
        removeOverlay();
        
        const phaseConfig = TOUR_PHASES[phaseKey] || { title: 'Guided Validation', content: String(phaseKey), step: 1 };
        const title = options.title || phaseConfig.title;
        const content = options.content || phaseConfig.content;
        const currentStep = options.step || phaseConfig.step;
        const isLastStep = currentStep === TOTAL_STEPS;
        
        const scrim = document.createElement('div');
        scrim.className = 'tour-scrim';
        document.body.appendChild(scrim);
        
        const overlay = document.createElement('div');
        overlay.className = 'tour-overlay';
        overlay.id = 'tour-dialog';
        
        let highlightEl = null;
        if (options.highlightElement) {
            highlightEl = typeof options.highlightElement === 'string' 
                ? document.querySelector(options.highlightElement) 
                : options.highlightElement;
            if (highlightEl) {
                highlightEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        }
        
        if (options.position) {
            overlay.style.position = 'fixed';
            overlay.style.top = options.position.top || 'auto';
            overlay.style.left = options.position.left || 'auto';
            overlay.style.right = options.position.right || 'auto';
            overlay.style.bottom = options.position.bottom || 'auto';
            overlay.style.transform = options.position.transform || 'none';
        }
        
        overlay.innerHTML = `
            <div class="tour-overlay-header">
                <div class="tour-header-left">
                    <div class="tour-pulse-dot"></div>
                    <span class="tour-overlay-title">Guided Validation</span>
                </div>
                <button class="tour-close-btn" aria-label="Close tour">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M18 6L6 18M6 6l12 12"/>
                    </svg>
                </button>
            </div>
            <div class="tour-overlay-content">
                <div class="tour-step-counter">Step ${currentStep} of ${TOTAL_STEPS}</div>
                <h3 class="tour-content-title">${title}</h3>
                <div class="tour-content-body">
                    ${content.split('\n').map(line => `<p>${line}</p>`).join('')}
                </div>
            </div>
            <div class="tour-overlay-footer">
                <div class="tour-footer-left"></div>
                <div class="tour-footer-right">
                    ${currentStep > 1 && options.showBack !== false ? `
                        <button class="tour-btn-back" ${currentStep <= 1 ? 'disabled' : ''}>
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M15 18l-6-6 6-6"/>
                            </svg>
                            Back
                        </button>
                    ` : ''}
                    ${options.primaryButton !== false ? (isLastStep ? `
                        <button class="tour-btn-finish">${options.primaryButtonText || 'Finish'}</button>
                    ` : `
                        <button class="tour-btn-next">
                            ${options.primaryButtonText || 'Next'}
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M9 18l6-6-6-6"/>
                            </svg>
                        </button>
                    `) : ''}
                </div>
            </div>
            <div class="tour-progress-bar">
                <div class="tour-progress-fill" style="width: ${(currentStep / TOTAL_STEPS) * 100}%"></div>
            </div>
        `;
        
        document.body.appendChild(overlay);
        
        if (!options.position && highlightEl) {
            positionOverlayNearElement(overlay, highlightEl);
        }
        
        overlay.querySelector('.tour-close-btn').addEventListener('click', () => exit());
        
        const nextBtn = overlay.querySelector('.tour-btn-next');
        const finishBtn = overlay.querySelector('.tour-btn-finish');
        const backBtn = overlay.querySelector('.tour-btn-back');
        
        if (nextBtn) {
            nextBtn.addEventListener('click', () => {
                if (options.onContinue) {
                    options.onContinue();
                } else {
                    advance();
                }
            });
        }
        
        if (finishBtn) {
            finishBtn.addEventListener('click', () => {
                if (options.onContinue) {
                    options.onContinue();
                } else {
                    exit();
                }
            });
        }
        
        if (backBtn) {
            backBtn.addEventListener('click', () => {
                if (options.onBack) {
                    options.onBack();
                }
            });
        }
        
        makeDraggable(overlay);
        
        if (highlightEl) {
            highlightEl.classList.add('tour-highlight');
        }
    }
    
    function makeDraggable(element) {
        const header = element.querySelector('.tour-overlay-header');
        if (!header) return;
        
        let isDragging = false;
        let startX, startY, initialX, initialY;
        
        header.addEventListener('mousedown', (e) => {
            if (e.target.closest('button')) return;
            isDragging = true;
            startX = e.clientX;
            startY = e.clientY;
            const rect = element.getBoundingClientRect();
            initialX = rect.left;
            initialY = rect.top;
            element.style.transform = 'none';
            element.style.transition = 'none';
        });
        
        document.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            e.preventDefault();
            const dx = e.clientX - startX;
            const dy = e.clientY - startY;
            element.style.left = (initialX + dx) + 'px';
            element.style.top = (initialY + dy) + 'px';
        });
        
        document.addEventListener('mouseup', () => {
            isDragging = false;
            element.style.transition = '';
        });
    }
    
    function start() {
        aborted = false;
        clearAllTimeouts();
        const state = { active: true, phase: 0, runId: null };
        setState(state);
        executePhase(0);
    }
    
    function exit() {
        aborted = true;
        clearAllTimeouts();
        removeOverlay();
        clearState();
    }
    
    function advance() {
        if (aborted) return;
        
        const state = getState();
        if (!state.active) return;
        
        const phaseOrder = [0, 3, 5, 6, 7, 8];
        const currentIndex = phaseOrder.indexOf(state.phase);
        
        if (currentIndex === -1 || currentIndex >= phaseOrder.length - 1) {
            exit();
            return;
        }
        
        const nextPhase = phaseOrder[currentIndex + 1];
        state.phase = nextPhase;
        setState(state);
        executePhase(nextPhase);
    }
    
    function executePhase(phase) {
        if (aborted) return;
        
        const state = getState();
        
        switch (phase) {
            case 0:
                executePhase0();
                break;
            case 3:
                executePhase3();
                break;
            case 4:
                executePhase4();
                break;
            case 5:
                executePhase5();
                break;
            case 6:
                executePhase6();
                break;
            case 7:
                executePhase7();
                break;
            case 8:
                executePhase8();
                break;
            default:
                console.warn('TourManager: Unknown phase', phase);
        }
    }
    
    function executePhase0() {
        showOverlay(0, {
            primaryButtonText: 'Run Guided Validation',
            showBack: false,
            onContinue: () => {
                navigateToFarmWithGuided();
            }
        });
    }
    
    async function navigateToFarmWithGuided() {
        if (aborted) return;
        
        try {
            const r = await fetch('/api/farm/url');
            if (aborted) return;
            const data = await r.json();
            if (data.farm_url) {
                const returnUrl = encodeURIComponent(window.location.origin + '/?guided=1&phase=3');
                const separator = data.farm_url.includes('?') ? '&' : '?';
                const farmUrlWithGuided = `${data.farm_url}${separator}guided=1&tour_phase=1&return_url=${returnUrl}`;
                window.open(farmUrlWithGuided, 'aos_farm');
                
                const state = getState();
                state.phase = 3;
                setState(state);
                removeOverlay();
            }
        } catch (e) {
            console.error('TourManager: Failed to get Farm URL', e);
        }
    }
    
    async function executePhase3() {
        if (aborted) return;
        
        const consoleTab = document.querySelector('.header-nav-tab[data-tab="discovery"]');
        if (consoleTab) consoleTab.click();
        
        await trackedDelay(200);
        if (aborted) return;
        
        showOverlay(3, {
            highlightElement: '#fetchFromFarm',
            position: { top: '60%', left: '50%', transform: 'translateX(-50%)' },
            primaryButton: false,
            showBack: false
        });
        
        waitForUserRunAndContinue();
    }
    
    async function waitForUserRunAndContinue() {
        if (aborted) return;
        
        const fetchBtn = document.getElementById('fetchFromFarm');
        if (!fetchBtn) return;
        
        const clickHandler = async () => {
            fetchBtn.removeEventListener('click', clickHandler);
            removeOverlay();
            
            await trackedDelay(500);
            if (aborted) return;
            
            showProcessingDialog();
            
            const snapshotSelect = document.getElementById('snapshotSelect');
            await waitForRunCompletion(snapshotSelect ? snapshotSelect.value : null);
            
            if (aborted) return;
            
            const resultsSection = document.getElementById('resultsSection');
            if (resultsSection) {
                resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
            
            await trackedDelay(500);
            if (aborted) return;
            
            showPhase3bResultsDialog();
        };
        
        fetchBtn.addEventListener('click', clickHandler);
    }
    
    function showProcessingDialog() {
        removeOverlay();
        
        const scrim = document.createElement('div');
        scrim.className = 'tour-scrim';
        document.body.appendChild(scrim);
        
        const overlay = document.createElement('div');
        overlay.className = 'tour-overlay';
        overlay.id = 'tour-processing-overlay';
        overlay.style.position = 'fixed';
        overlay.style.bottom = '20px';
        overlay.style.left = '50%';
        overlay.style.top = 'auto';
        overlay.style.transform = 'translateX(-50%)';
        overlay.innerHTML = `
            <div class="tour-overlay-header">
                <div class="tour-header-left">
                    <div class="tour-pulse-dot"></div>
                    <span class="tour-overlay-title">Guided Validation</span>
                </div>
            </div>
            <div class="tour-overlay-content">
                <div class="tour-step-counter">Step 3 of ${TOTAL_STEPS}</div>
                <h3 class="tour-content-title">Running Discovery</h3>
                <div class="tour-content-body">
                    <p>Discovery in process ...</p>
                </div>
            </div>
            <div class="tour-progress-bar">
                <div class="tour-progress-fill" style="width: ${(3 / TOTAL_STEPS) * 100}%"></div>
            </div>
        `;
        document.body.appendChild(overlay);
        makeDraggable(overlay);
    }
    
    function showPhase3bResultsDialog() {
        if (aborted) return;
        
        const ingested = getStatCount('observations') || 0;
        const validated = getStatCount('validated') || 0;
        const rejected = getStatCount('rejected') || 0;
        const cataloged = getStatCount('assets') || 0;
        const shadow = getStatCount('shadow') || 0;
        const zombie = getStatCount('zombie') || 0;
        
        const message = `Discovery complete! AOD ingested ${ingested} observations, validated ${validated}, rejected ${rejected}, and cataloged ${cataloged}. In addition, AOD discovered ${shadow} Shadow assets, and identified savings opportunities by discovering ${zombie} zombie assets. Feel free to click through to the details.`;
        
        showOverlay('3b', {
            title: 'Discovery Results',
            content: message,
            step: 3,
            position: { bottom: '20px', left: '50%', transform: 'translateX(-50%)' },
            showBack: false
        });
    }
    
    async function waitForRunCompletion(snapshotId) {
        const maxAttempts = 120;
        const pollInterval = 300;
        
        for (let i = 0; i < maxAttempts; i++) {
            if (aborted) return;
            
            await trackedDelay(pollInterval);
            if (aborted) return;
            
            const totalAssetsEl = document.getElementById('totalAssets');
            if (totalAssetsEl) {
                const val = parseInt(totalAssetsEl.textContent, 10);
                if (!isNaN(val) && val > 0) {
                    return;
                }
            }
            
            const runsList = document.getElementById('runsList');
            if (runsList) {
                const runCards = runsList.querySelectorAll('.run-card');
                if (runCards.length > 0) {
                    const latestCard = runCards[0];
                    const statusBadge = latestCard.querySelector('.badge');
                    if (statusBadge && statusBadge.textContent.toLowerCase().includes('complete')) {
                        return;
                    }
                    if (snapshotId) {
                        const cardText = latestCard.textContent || '';
                        if (cardText.includes(snapshotId) && statusBadge) {
                            const status = statusBadge.textContent.toLowerCase();
                            if (status.includes('complete') || status.includes('success')) {
                                return;
                            }
                        }
                    }
                }
            }
            
            const resultSection = document.getElementById('resultsSection');
            if (resultSection && !resultSection.classList.contains('hidden')) {
                const statsLoaded = getStatCount('assets') > 0 || getStatCount('shadow') > 0 || getStatCount('zombie') > 0;
                if (statsLoaded) {
                    return;
                }
            }
        }
    }
    
    async function executePhase4() {
        if (aborted) return;
        advance();
    }
    
    async function executePhase5() {
        if (aborted) return;
        
        const triageTab = document.querySelector('.header-nav-tab[data-tab="triage"]');
        if (triageTab) triageTab.click();
        
        await trackedDelay(500);
        if (aborted) return;
        
        const triageSelect = document.getElementById('triageRunSelect');
        if (triageSelect && triageSelect.options.length > 1 && !triageSelect.value) {
            triageSelect.value = triageSelect.options[1].value;
            triageSelect.dispatchEvent(new Event('change'));
            await trackedDelay(500);
            if (aborted) return;
        }
        
        showOverlay(5, {
            highlightElement: '#triageSections',
            position: { top: '200px', left: '50%' }
        });
    }
    
    async function executePhase6() {
        if (aborted) return;
        
        const consoleTab = document.querySelector('.header-nav-tab[data-tab="discovery"]');
        if (consoleTab) consoleTab.click();
        
        await trackedDelay(300);
        if (aborted) return;
        
        const assetCount = getStatCount('assets');
        const catalogCard = document.querySelector('.stat-card[data-drill-type="assets"]');
        
        if (assetCount === 0) {
            showOverlay(6.5, {
                primaryButtonText: 'Continue',
                onContinue: () => {
                    if (aborted) return;
                    removeOverlay();
                    advance();
                }
            });
            return;
        }
        
        showOverlay(6, {
            highlightElement: catalogCard,
            onContinue: async () => {
                if (aborted) return;
                removeOverlay();
                if (catalogCard) {
                    catalogCard.click();
                    await trackedDelay(500);
                }
                if (aborted) return;
                advance();
            }
        });
    }
    
    async function executePhase7() {
        if (aborted) return;
        
        showOverlay(7, {
            primaryButtonText: 'Verify in Farm',
            onContinue: async () => {
                if (aborted) return;
                removeOverlay();
                await navigateToFarmForVerification();
            }
        });
    }
    
    async function navigateToFarmForVerification() {
        if (aborted) return;
        
        try {
            const r = await fetch('/api/farm/url');
            if (aborted) return;
            const data = await r.json();
            if (data.farm_url) {
                const returnUrl = encodeURIComponent(window.location.origin + '/?guided=1&phase=8');
                const separator = data.farm_url.includes('?') ? '&' : '?';
                const farmUrlWithGuided = `${data.farm_url}${separator}guided=1&tour_phase=7&return_url=${returnUrl}`;
                window.open(farmUrlWithGuided, 'aos_farm');
                
                const state = getState();
                state.phase = 8;
                setState(state);
            }
        } catch (e) {
            console.error('TourManager: Failed to get Farm URL for verification', e);
        }
    }
    
    function executePhase8() {
        if (aborted) return;
        
        showOverlay(8, {
            primaryButtonText: 'Finish',
            onContinue: () => {
                exit();
            }
        });
    }
    
    function checkResume() {
        const urlParams = new URLSearchParams(window.location.search);
        const guided = urlParams.get('guided');
        const phase = urlParams.get('phase');
        
        if (guided === '1' && phase) {
            const phaseNum = parseInt(phase, 10);
            if (!isNaN(phaseNum)) {
                aborted = false;
                clearAllTimeouts();
                const state = { active: true, phase: phaseNum, runId: null };
                setState(state);
                
                const newUrl = window.location.pathname;
                window.history.replaceState({}, '', newUrl);
                
                trackedTimeout(() => executePhase(phaseNum), 500);
                return;
            }
        }
        
        if (guided === '1') {
            const newUrl = window.location.pathname;
            window.history.replaceState({}, '', newUrl);
            
            const state = getState();
            if (state.active) {
                aborted = false;
                clearAllTimeouts();
                trackedTimeout(() => executePhase(state.phase), 500);
            }
        }
    }
    
    function isActive() {
        return getState().active;
    }
    
    return {
        start,
        exit,
        advance,
        checkResume,
        isActive,
        getState
    };
})();
