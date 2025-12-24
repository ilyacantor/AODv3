# Guided Validation Tour Script

Complete narrated walkthrough coordinating between AOD (discovery) and Farm (data generation/verification).

## Tour Overview

| System | Phases | Steps |
|--------|--------|-------|
| AOD | Entry, Discovery, Results, Triage, Catalog, Exit | 8 steps |
| Farm | Snapshot Generation, Snapshot Display, Verification | 11 steps |

**Total Experience**: 8 AOD steps + 11 Farm steps = 19 guided interactions

---

## Phase 0: Entry Framing (AOD)

| Step | Dialog Title | Dialog Text | Action |
|------|--------------|-------------|--------|
| 1 of 8 | Welcome to AOD | "AOD discovers what actually exists in an enterprise environment. This run shows how discovery is executed, inspected, and verified." | Entry point, Next button proceeds |

---

## Phase 1: Snapshot Generation (Farm - 5 steps)

| Step | Dialog Text | Action |
|------|-------------|--------|
| 1 of 5 | "Select a Scale. Medium = ~50 assets, Enterprise = 500+, Mega = 1500+.<br><br>Or accept defaults and press Generate." | Highlights Scale dropdown, waits for selection or Generate click |
| 2 of 5 | "Select an Enterprise profile. Modern SaaS = heavy cloud, Regulated Finance = legacy + compliance.<br><br>Or accept defaults and press Generate." | Highlights Enterprise dropdown |
| 3 of 5 | "Select a Realism level. Clean = no mess, Typical = some conflicts, Messy = chaos.<br><br>Or accept defaults and press Generate." | Highlights Realism dropdown |
| 4 of 5 | "Select a Data Preset. Clean = easy baseline, Enterprise Mess = realistic conflicts, Adversarial = absolute disaster.<br><br>Or accept defaults and press Generate." | Highlights Data Preset dropdown |
| 5 of 5 | "Press Generate Snapshot to create ground truth data." | Highlights Generate button, button says "Generate Snapshot" |
| (loading) | "Generating snapshot..." | Shows while generating |

---

## Phase 2: Snapshot Display (Farm - 2 steps)

| Step | Dialog Text | Action |
|------|-------------|--------|
| 1 of 2 | "Snapshot represents a synthetic and hyper-realistic enterprise IT environment. AOD processes in excess of 10,000 raw observations, resolves over 1,000 candidate assets, evaluates tens of thousands of evidence relationships, and produces a verified catalog of over 1,000 trusted assets." | Highlights and expands snapshot |
| 2 of 2 | "Now we go back to AOD to run discovery on this data.<br><br>[Continue to AOD →]" | Shows handoff link to AOD |
| (no return URL) | "Snapshot ready. Return to AOD to run discovery, then come back for reconciliation." | Button: "Done" |

---

## Phase 3: Discovery Run (AOD)

| Step | Dialog Title | Dialog Text | Action |
|------|--------------|-------------|--------|
| 2 of 8 | Run Discovery | "Welcome back to AOD. The tenant has been loaded. Press Fetch & Run Discovery and then review the results of the Run below." | Highlights Fetch & Run Discovery button, waits for click |
| (loading) | Running Discovery | "Discovery in process ..." | Shows while processing |
| 3 of 8 | Discovery Results | "Discovery complete! AOD ingested {observations} observations, validated {validated}, rejected {rejected}, and cataloged {assets}. In addition, AOD discovered {shadow} Shadow assets, and identified savings opportunities by discovering {zombie} zombie assets. Feel free to click through to the details." | Dynamic stats from completed run |

---

## Phase 4: Shadow Assets Inspection (AOD)

| Step | Dialog Title | Dialog Text | Action |
|------|--------------|-------------|--------|
| 4 of 8 | Inspect Shadow Assets | "Shadow assets are systems that exist in your environment but lack proper governance. Click on the Shadow card to see which assets need attention." | Highlights Shadow stat card, waits for click |
| 4 of 8 (fallback) | Shadow Assets | "No shadow assets were discovered in this run. This is a good sign - it means all discovered assets have proper governance. Let's continue to the next step." | If shadow count = 0 |

---

## Phase 5: Triage Findings (AOD)

| Step | Dialog Title | Dialog Text | Action |
|------|--------------|-------------|--------|
| 5 of 8 | Triage Findings | "Current configuration creates a \"Triage queue\" for the user to review and dispose of issues categorized in tiers. This workflow is customizable and can be configured as a control pane rather than an informational pane.<br><br>Click through on any actions or item for details." | Navigates to Triage tab, highlights findings |

---

## Phase 6: Asset Catalog Review (AOD)

| Step | Dialog Title | Dialog Text | Action |
|------|--------------|-------------|--------|
| 6 of 8 | Asset Catalog | "The penultimate product of the discovery effort is the Catalog which is then passed to the AOS Adaptive API Mesh to obtain and sustain connections autonomously." | Highlights catalog section |
| 6 of 8 (fallback) | Asset Catalog | "No assets found in the catalog for this run. This may indicate the run is still processing or no assets were discovered." | If catalog empty |

---

## Phase 7: Verification (Farm - 4 steps)

| Step | Dialog Title | Dialog Text | Action |
|------|--------------|-------------|--------|
| 7 of 8 (AOD) | Verify Accuracy | "Now let's verify AOD's accuracy. Farm will compare AOD's classifications against the expected ground truth to measure precision and recall." | Shows handoff link to Farm |
| 1 of 4 | Verification | "Verification: comparing AOD's classifications against Farm's ground truth expectations." | Loads data |
| 2 of 4 | Reconciliation | "Click the highlighted reconciliation to view the scorecard comparing AOD's results to Farm's ground truth." | Highlights reconciliation item, waits for click |
| 2 of 4 (fallback) | No Reconciliation | "No reconciliations found yet. AOD must process the snapshot and send results back to Farm for reconciliation." | If no reconciliation exists |
| 3 of 4 | Mismatches | "Mismatches reveal where AOD and Farm disagree. Each mismatch shows reasoning for investigation." | After viewing scorecard |
| 4 of 4 | Complete | "Verification complete. Return to AOD to review the full discovery results.<br><br>[Return to AOD →]" | Shows return link to AOD |
| 4 of 4 (no return URL) | Complete | "Verification complete. Farm generates test data, AOD processes it, reconciliation grades results." | Button: "Finish Tour" |

---

## Phase 8: Tour Complete (AOD)

| Step | Dialog Title | Dialog Text | Action |
|------|--------------|-------------|--------|
| 8 of 8 | Tour Complete | "The guided validation is complete. You've seen how AOD discovers assets and how Farm verifies accuracy. You may now explore freely." | Finish button ends tour |

---

## URL Contract

### Farm Receives
```
?guided=1&tour_phase=X&return_url=<encoded_aod_url>
```

### Farm Sends Back
| Phase | Destination | Parameters |
|-------|-------------|------------|
| Phase 2 → AOD | `return_url` | `&snapshot_id=xxx` |
| Phase 7 → AOD | `return_url` | `?guided=1&tour_phase=8` |

---

## UI Design

- **Style**: Glassmorphism with `backdrop-filter: blur(20px)`, `rgba(0,0,0,0.6)` background
- **Accent**: Cyan (`#00D9FF`) for highlights and pulsing indicator
- **Dialog**: Draggable header, step counter, progress bar
- **Navigation**: Back/Next buttons with conditional rendering based on phase

---

## Phase Order (AOD)

```javascript
phaseOrder: [0, 3, 4, 5, 6, 7, 8]
```

With conditional intermediate phases:
- `3b`: Discovery Results (after run completes)
- `4.5`: No Shadow Assets (fallback)
- `6.5`: Empty Catalog (fallback)

---

## State Persistence

Tour state is persisted in `localStorage` under key `aod_guided_tour`:
```json
{
  "phase": 3,
  "runId": "run_abc123",
  "timestamp": 1735000000000
}
```
