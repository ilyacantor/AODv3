const TourManager = (function() {
    const STORAGE_KEY = 'aod_guided_tour';
    
    const TOUR_COPY = {
        0: "AOD discovers what actually exists in an enterprise environment.\nThis run shows how discovery is executed, inspected, and verified.",
        3: "AOD ingests signals, resolves entities, scores evidence, and classifies assets.\nEvery result is traceable to source data.",
        4: "Shadow assets are systems in active use without governance coverage.\nClassification is based on evidence patterns, not hardcoded rules.",
        5: "Triage simulates decisions AOD can support or automate.\nActions change asset state and downstream eligibility.",
        6: "The catalog is the trusted output of discovery.\nOnly cataloged assets are eligible for integration and automation.",
        8: "The guided run is complete.\nYou may now explore freely or restart the validation."
    };
    
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
    
    function showOverlay(copy, options = {}) {
        removeOverlay();
        
        const scrim = document.createElement('div');
        scrim.className = 'tour-scrim';
        document.body.appendChild(scrim);
        
        const overlay = document.createElement('div');
        overlay.className = 'tour-overlay';
        
        if (options.position) {
            overlay.style.position = 'fixed';
            overlay.style.top = options.position.top || 'auto';
            overlay.style.left = options.position.left || 'auto';
            overlay.style.right = options.position.right || 'auto';
            overlay.style.bottom = options.position.bottom || 'auto';
            overlay.style.transform = 'none';
        }
        
        const header = document.createElement('div');
        header.className = 'tour-overlay-header';
        
        const title = document.createElement('span');
        title.className = 'tour-overlay-title';
        title.textContent = 'Guided Validation';
        header.appendChild(title);
        
        const exitBtn = document.createElement('button');
        exitBtn.className = 'tour-exit-btn';
        exitBtn.textContent = 'Exit Tour';
        exitBtn.addEventListener('click', () => exit());
        header.appendChild(exitBtn);
        
        overlay.appendChild(header);
        
        const copyDiv = document.createElement('div');
        copyDiv.className = 'tour-overlay-copy';
        copyDiv.innerHTML = copy.split('\n').map(line => `<p>${line}</p>`).join('');
        overlay.appendChild(copyDiv);
        
        const buttonsDiv = document.createElement('div');
        buttonsDiv.className = 'tour-overlay-buttons';
        
        if (options.primaryButton !== false) {
            const continueBtn = document.createElement('button');
            continueBtn.className = 'tour-continue-btn';
            continueBtn.textContent = options.primaryButtonText || 'Continue';
            continueBtn.addEventListener('click', () => {
                if (options.onContinue) {
                    options.onContinue();
                } else {
                    advance();
                }
            });
            buttonsDiv.appendChild(continueBtn);
        }
        
        overlay.appendChild(buttonsDiv);
        document.body.appendChild(overlay);
        
        if (options.highlightElement) {
            const el = typeof options.highlightElement === 'string' 
                ? document.querySelector(options.highlightElement) 
                : options.highlightElement;
            if (el) el.classList.add('tour-highlight');
        }
    }
    
    function start() {
        const state = { active: true, phase: 0, runId: null };
        setState(state);
        executePhase(0);
    }
    
    function exit() {
        removeOverlay();
        clearState();
    }
    
    function advance() {
        const state = getState();
        if (!state.active) return;
        
        const phaseOrder = [0, 3, 4, 5, 6, 8];
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
            case 8:
                executePhase8();
                break;
            default:
                console.warn('TourManager: Unknown phase', phase);
        }
    }
    
    function executePhase0() {
        showOverlay(TOUR_COPY[0], {
            primaryButtonText: 'Run Guided Validation',
            onContinue: () => {
                removeOverlay();
                navigateToFarmWithGuided();
            }
        });
    }
    
    async function navigateToFarmWithGuided() {
        try {
            const r = await fetch('/api/farm/url');
            const data = await r.json();
            if (data.farm_url) {
                const separator = data.farm_url.includes('?') ? '&' : '?';
                const farmUrlWithGuided = `${data.farm_url}${separator}guided=1`;
                window.open(farmUrlWithGuided, 'aos_farm');
            }
        } catch (e) {
            console.error('TourManager: Failed to get Farm URL', e);
        }
    }
    
    async function executePhase3() {
        const consoleTab = document.querySelector('.header-nav-tab[data-tab="discovery"]');
        if (consoleTab) consoleTab.click();
        
        await new Promise(resolve => setTimeout(resolve, 200));
        
        showOverlay(TOUR_COPY[3], {
            highlightElement: '#lifecycleStats',
            position: { top: '200px', left: '50%', transform: 'translateX(-50%)' },
            onContinue: () => {
                autoStartRun();
            }
        });
    }
    
    async function autoStartRun() {
        const state = getState();
        removeOverlay();
        
        const tenantSelect = document.getElementById('tenantSelect');
        const snapshotSelect = document.getElementById('snapshotSelect');
        
        if (tenantSelect && tenantSelect.options.length > 1 && !tenantSelect.value) {
            tenantSelect.value = tenantSelect.options[1].value;
            tenantSelect.dispatchEvent(new Event('change'));
            await new Promise(resolve => setTimeout(resolve, 1000));
        }
        
        if (snapshotSelect && snapshotSelect.options.length > 1 && !snapshotSelect.value) {
            snapshotSelect.value = snapshotSelect.options[1].value;
            snapshotSelect.dispatchEvent(new Event('change'));
            await new Promise(resolve => setTimeout(resolve, 500));
        }
        
        const fetchBtn = document.getElementById('fetchFromFarm');
        if (fetchBtn && !fetchBtn.disabled) {
            fetchBtn.click();
            
            await waitForRunCompletion();
        }
        
        advance();
    }
    
    async function waitForRunCompletion() {
        for (let i = 0; i < 60; i++) {
            await new Promise(resolve => setTimeout(resolve, 1000));
            const resultSection = document.getElementById('resultsSection');
            if (resultSection && !resultSection.classList.contains('hidden')) {
                return;
            }
        }
    }
    
    async function executePhase4() {
        const consoleTab = document.querySelector('.header-nav-tab[data-tab="discovery"]');
        if (consoleTab) consoleTab.click();
        
        await new Promise(resolve => setTimeout(resolve, 300));
        
        const shadowCard = document.querySelector('.stat-card[data-drill-type="shadow"]');
        
        showOverlay(TOUR_COPY[4], {
            highlightElement: shadowCard,
            position: { top: '250px', right: '100px' },
            onContinue: async () => {
                removeOverlay();
                if (shadowCard) {
                    shadowCard.click();
                    await new Promise(resolve => setTimeout(resolve, 500));
                }
                advance();
            }
        });
    }
    
    async function executePhase5() {
        const triageTab = document.querySelector('.header-nav-tab[data-tab="triage"]');
        if (triageTab) triageTab.click();
        
        await new Promise(resolve => setTimeout(resolve, 500));
        
        const triageSelect = document.getElementById('triageRunSelect');
        if (triageSelect && triageSelect.options.length > 1 && !triageSelect.value) {
            triageSelect.value = triageSelect.options[1].value;
            triageSelect.dispatchEvent(new Event('change'));
            await new Promise(resolve => setTimeout(resolve, 500));
        }
        
        showOverlay(TOUR_COPY[5], {
            highlightElement: '#triageSections',
            position: { top: '200px', left: '50%' }
        });
    }
    
    async function executePhase6() {
        const consoleTab = document.querySelector('.header-nav-tab[data-tab="discovery"]');
        if (consoleTab) consoleTab.click();
        
        await new Promise(resolve => setTimeout(resolve, 300));
        
        const catalogCard = document.querySelector('.stat-card[data-drill-type="assets"]');
        
        showOverlay(TOUR_COPY[6], {
            highlightElement: catalogCard,
            position: { top: '250px', right: '100px' },
            onContinue: async () => {
                removeOverlay();
                if (catalogCard) {
                    catalogCard.click();
                    await new Promise(resolve => setTimeout(resolve, 500));
                }
                advance();
            }
        });
    }
    
    function executePhase8() {
        showOverlay(TOUR_COPY[8], {
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
                const state = { active: true, phase: phaseNum, runId: null };
                setState(state);
                
                const newUrl = window.location.pathname;
                window.history.replaceState({}, '', newUrl);
                
                setTimeout(() => executePhase(phaseNum), 500);
                return;
            }
        }
        
        if (guided === '1') {
            const newUrl = window.location.pathname;
            window.history.replaceState({}, '', newUrl);
            
            const state = getState();
            if (state.active) {
                setTimeout(() => executePhase(state.phase), 500);
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
