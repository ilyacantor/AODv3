const TourManager = (function() {
    const STORAGE_KEY = 'aod_guided_tour';
    
    let aborted = false;
    let pendingTimeouts = [];
    
    const INTRO_STEPS = 3;
    
    const TOUR_PHASES = {
        'intro_1': {
            title: "The Execution Pipeline",
            content: "AutonomOS operates as a <strong>linear execution pipeline</strong>.\n\nThe architecture moves from <strong>Discovery (AOD)</strong> to <strong>Connection (AAM)</strong>, <strong>Unification (DCL)</strong>, and <strong>Action (Agents)</strong>.\n\nOperations begin with Discovery.",
            step: 1,
            location: 'overview'
        },
        'intro_2': {
            title: "Discovery Gateway",
            content: "AOD is the foundation. Before AI systems can integrate, automate, or act—they must know what actually exists.\n\nAOD discovers assets, resolves ambiguity, scores evidence, and produces a trusted catalog.",
            step: 2,
            location: 'overview'
        },
        'intro_3': {
            title: "Simulation & Proof",
            content: "This tour doesn't just show you a static demo. We're going to <strong>generate a live, chaotic IT environment</strong> and watch AOD organize it in real-time.\n\nReady to begin the simulation?",
            step: 3,
            location: 'overview'
        },
        0: { 
            title: "The Visibility Gap",
            content: "Most enterprises don't know what they own. Between <strong>Shadow IT</strong> (risk) and <strong>Zombie SaaS</strong> (waste), millions are lost annually.\n\nThis tour doesn't just show you a static demo. We're going to generate a live, chaotic IT environment and watch AOD organize it in real-time.",
            step: 4
        },
        3: { 
            title: "Ingest & Resolve",
            content: "The Farm has generated a chaotic dataset. Now let's watch AOD make sense of it.\n\nClick <strong>Fetch & Run Discovery</strong> to ingest the snapshot and start the discovery process.",
            step: 9
        },
        '3b': { 
            title: "The Discovery Dashboard",
            content: "",
            step: 10
        },
        4: { 
            title: "Risks & Waste",
            content: "Let's inspect the problems AOD found:\n\n• <strong>Shadow IT:</strong> Apps running without IT's knowledge (Security Risk).\n• <strong>Zombies:</strong> Paid licenses with zero usage (Financial Waste).\n\nClick the <strong>Shadow</strong> card to drill down.",
            step: 11
        },
        4.5: { 
            title: "Risks & Waste",
            content: "This simulation produced a clean run with no Shadow IT detected. In real enterprise environments, Shadow assets are common.\n\nLet's continue to the Triage console.",
            step: 11
        },
        5: { 
            title: "The Decision Layer",
            content: "Discovery is useless without action.\n\nThe <strong>Triage Console</strong> prioritizes findings by urgency. You don't have to review 10,000 lines—just the Tier 1 issues that require human judgment.\n\nYou can acknowledge, reject, or flag assets right here.",
            step: 12
        },
        6: { 
            title: "The Trusted Catalog",
            content: "This is the \"Golden Record.\"\n\nWhile Triage handles the exceptions, the <strong>Catalog</strong> contains the fully verified estate.\n\nThis trusted list feeds the <strong>AAM</strong> for connecting and maintaining healthy connections, and then to <strong>DCL</strong> for creating a unified data ontology.",
            step: 13
        },
        6.5: { 
            title: "The Trusted Catalog",
            content: "The Catalog is still being populated. In production, this becomes the \"Golden Record\" that feeds downstream systems.",
            step: 13
        },
        7: { 
            title: "Trust, but Verify",
            content: "In a demo, you trust the vendor. In AutonomOS, we let you audit the math.\n\nLet's go back to <strong>The Farm</strong> to compare AOD's findings against the Ground Truth we generated earlier—verifying AOD's ability to create a verified, accurate asset inventory.",
            step: 14
        },
        8: { 
            title: "Tour Complete",
            content: "You've seen the cycle: <strong>Generate Chaos → Discover Order → Audit Accuracy.</strong>\n\nYou are now free to explore the Catalog, run new simulations, or drill into specific asset details.",
            step: 16
        }
    };
    
    const TOTAL_STEPS = 16;
    
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
    
    function waitForElement(selector, timeout = 5000) {
        return new Promise((resolve) => {
            const el = document.querySelector(selector);
            if (el) {
                resolve(el);
                return;
            }
            
            const startTime = Date.now();
            const checkInterval = setInterval(() => {
                if (aborted) {
                    clearInterval(checkInterval);
                    resolve(null);
                    return;
                }
                
                const el = document.querySelector(selector);
                if (el) {
                    clearInterval(checkInterval);
                    resolve(el);
                    return;
                }
                
                if (Date.now() - startTime > timeout) {
                    clearInterval(checkInterval);
                    resolve(null);
                }
            }, 100);
        });
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
    
    async function showOverlay(phaseKey, options = {}) {
        removeOverlay();
        
        const phaseConfig = TOUR_PHASES[phaseKey] || { title: 'Simulation & Proof', content: String(phaseKey), step: 1 };
        const title = options.title || phaseConfig.title;
        const content = options.content || phaseConfig.content;
        const currentStep = Number(options.step || phaseConfig.step) || 1;
        const isLastStep = currentStep === TOTAL_STEPS;
        
        const scrim = document.createElement('div');
        scrim.className = 'tour-scrim';
        document.body.appendChild(scrim);
        
        const overlay = document.createElement('div');
        overlay.className = 'tour-overlay';
        overlay.id = 'tour-dialog';
        
        let highlightEl = null;
        if (options.highlightElement) {
            if (typeof options.highlightElement === 'string') {
                highlightEl = await waitForElement(options.highlightElement, 3000);
            } else {
                highlightEl = options.highlightElement;
            }
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
                    <span class="tour-overlay-title">Simulation & Proof</span>
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
                } else {
                    goBack();
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
            const computedWidth = rect.width;
            
            element.style.width = computedWidth + 'px';
            element.style.right = 'auto';
            element.style.bottom = 'auto';
            element.style.transform = 'none';
            element.style.transition = 'none';
            element.style.left = rect.left + 'px';
            element.style.top = rect.top + 'px';
            
            initialX = rect.left;
            initialY = rect.top;
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
        const state = { active: true, phase: 'intro_1', runId: null };
        setState(state);
        
        const overviewTab = document.querySelector('.header-nav-tab[data-tab="overview"]');
        if (overviewTab) overviewTab.click();
        
        setTimeout(() => executePhase('intro_1'), 300);
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
        
        const phaseOrder = ['intro_1', 'intro_2', 'intro_3', 0, 3, 4, 5, 6, 7, 8];
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
    
    function goBack() {
        if (aborted) return;
        
        const state = getState();
        if (!state.active) return;
        
        const phaseOrder = ['intro_1', 'intro_2', 'intro_3', 0, 3, 4, 5, 6, 7, 8];
        const currentIndex = phaseOrder.indexOf(state.phase);
        
        if (currentIndex <= 0) {
            return;
        }
        
        const prevPhase = phaseOrder[currentIndex - 1];
        state.phase = prevPhase;
        setState(state);
        executePhase(prevPhase);
    }
    
    function executePhase(phase) {
        if (aborted) return;
        
        const state = getState();
        
        switch (phase) {
            case 'intro_1':
                executeIntroPhase('intro_1');
                break;
            case 'intro_2':
                executeIntroPhase('intro_2');
                break;
            case 'intro_3':
                executeIntroPhase('intro_3');
                break;
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
    
    async function executeIntroPhase(phaseKey) {
        const phaseConfig = TOUR_PHASES[phaseKey];
        const isLastIntro = phaseKey === 'intro_3';
        
        await showOverlay(phaseKey, {
            showBack: phaseKey !== 'intro_1',
            primaryButtonText: isLastIntro ? 'Start Simulation' : 'Next',
            onContinue: () => {
                if (isLastIntro) {
                    navigateToFarmWithGuided();
                } else {
                    advance();
                }
            }
        });
    }
    
    async function executePhase0() {
        await showOverlay(0, {
            primaryButtonText: 'Start Simulation',
            showBack: true,
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
        
        await showOverlay(3, {
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
            
            // Capture existing run IDs BEFORE the new run starts
            let existingRunIds = new Set();
            try {
                const resp = await fetch('/api/runs');
                const runs = await resp.json();
                existingRunIds = new Set(runs.map(r => r.run_id));
            } catch (e) {
                console.error('TourManager: Failed to get existing runs', e);
            }
            
            await trackedDelay(500);
            if (aborted) return;
            
            showProcessingDialog();
            
            // Wait for a NEW run to appear and complete
            const newRunId = await waitForNewRunCompletion(existingRunIds);
            
            if (aborted) return;
            
            const resultsSection = document.getElementById('resultsSection');
            if (resultsSection) {
                resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
            
            await trackedDelay(500);
            if (aborted) return;
            
            await showPhase3bResultsDialog(newRunId);
        };
        
        fetchBtn.addEventListener('click', clickHandler);
    }
    
    async function waitForNewRunCompletion(existingRunIds) {
        const maxAttempts = 120;
        const pollInterval = 500;
        
        for (let i = 0; i < maxAttempts; i++) {
            if (aborted) return null;
            
            await trackedDelay(pollInterval);
            if (aborted) return null;
            
            try {
                const resp = await fetch('/api/runs');
                const runs = await resp.json();
                
                // Find a run that didn't exist before
                const newRun = runs.find(r => !existingRunIds.has(r.run_id));
                
                if (newRun) {
                    // Check if it's completed
                    if (newRun.status && newRun.status.toLowerCase().includes('completed')) {
                        return newRun.run_id;
                    }
                }
            } catch (e) {
                console.error('TourManager: Error polling for new run', e);
            }
        }
        
        return null;
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
                    <span class="tour-overlay-title">Simulation & Proof</span>
                </div>
            </div>
            <div class="tour-overlay-content">
                <div class="tour-step-counter">Step 6 of ${TOTAL_STEPS}</div>
                <h3 class="tour-content-title">Ingest & Resolve</h3>
                <div class="tour-content-body">
                    <p>AOD is processing raw observations. It doesn't just list rows; it <strong>resolves identity</strong>.</p>
                    <p>Correlating disparate signals to determine what is a real asset and what is noise...</p>
                </div>
            </div>
            <div class="tour-progress-bar">
                <div class="tour-progress-fill" style="width: ${(6 / TOTAL_STEPS) * 100}%"></div>
            </div>
        `;
        document.body.appendChild(overlay);
        makeDraggable(overlay);
    }
    
    async function showPhase3bResultsDialog(runId) {
        if (aborted) return;
        
        let ingested = 0, validated = 0, rejected = 0, cataloged = 0, shadow = 0, zombie = 0;
        
        // If no runId provided, fall back to DOM reading
        if (!runId) {
            ingested = getStatCount('observations') || 0;
            validated = getStatCount('validated') || 0;
            rejected = getStatCount('rejected') || 0;
            cataloged = getStatCount('assets') || 0;
            shadow = getStatCount('shadow') || 0;
            zombie = getStatCount('zombie') || 0;
        } else {
            try {
                const [runResp, derivedResp] = await Promise.all([
                    fetch(`/api/runs/${runId}`),
                    fetch(`/api/runs/${runId}/derived`)
                ]);
                if (aborted) return;
                
                const runData = await runResp.json();
                const derivedData = await derivedResp.json();
                
                if (runData && runData.counts) {
                    ingested = runData.counts.observations_in || 0;
                    validated = runData.counts.candidates_out || 0;
                    rejected = runData.counts.rejected || 0;
                    cataloged = runData.counts.assets_admitted || 0;
                }
                if (derivedData) {
                    shadow = derivedData.shadow_count || 0;
                    zombie = derivedData.zombie_count || 0;
                }
            } catch (e) {
                console.error('TourManager: Failed to fetch run stats from API', e);
                ingested = getStatCount('observations') || 0;
                validated = getStatCount('validated') || 0;
                rejected = getStatCount('rejected') || 0;
                cataloged = getStatCount('assets') || 0;
                shadow = getStatCount('shadow') || 0;
                zombie = getStatCount('zombie') || 0;
            }
        }
        
        const message = `Processing complete. AOD has distilled <strong>${ingested}</strong> signals into <strong>${cataloged}</strong> trusted assets.\n\nNotice the <strong>Lifecycle Cards</strong> below. This isn't just a count; it's a health check. We've isolated <strong>${shadow} Shadow IT</strong> (unmanaged apps) and <strong>${zombie} Zombie Assets</strong> (wasted spend) automatically.`;
        
        await showOverlay('3b', {
            title: 'The Discovery Dashboard',
            content: message,
            step: 7,
            position: { bottom: '20px', left: '50%', transform: 'translateX(-50%)' },
            showBack: false
        });
    }
    
    
    async function executePhase4() {
        if (aborted) return;
        
        const consoleTab = document.querySelector('.header-nav-tab[data-tab="discovery"]');
        if (consoleTab) consoleTab.click();
        
        await trackedDelay(300);
        if (aborted) return;
        
        const shadowCount = getStatCount('shadow');
        const shadowCard = document.querySelector('.stat-card[data-drill-type="shadow"]');
        
        if (shadowCount === 0) {
            await showOverlay(4.5, {
                highlightElement: shadowCard,
                primaryButtonText: 'Continue',
                onContinue: () => {
                    if (aborted) return;
                    removeOverlay();
                    advance();
                }
            });
            return;
        }
        
        await showOverlay(4, {
            highlightElement: shadowCard,
            onContinue: async () => {
                if (aborted) return;
                removeOverlay();
                if (shadowCard) {
                    shadowCard.click();
                    await trackedDelay(500);
                }
                if (aborted) return;
                advance();
            }
        });
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
        
        await showOverlay(5, {
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
            await showOverlay(6.5, {
                primaryButtonText: 'Continue',
                onContinue: () => {
                    if (aborted) return;
                    removeOverlay();
                    advance();
                }
            });
            return;
        }
        
        await showOverlay(6, {
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
        
        await showOverlay(7, {
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
    
    async function executePhase8() {
        if (aborted) return;
        
        await showOverlay(8, {
            primaryButtonText: 'Finish & Explore',
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
