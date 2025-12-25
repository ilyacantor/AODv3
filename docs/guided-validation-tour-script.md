# Simulation & Proof Tour Script

**Strategic Narrative: "Battle-Hardened" Discovery**

The story isn't "Look, our software works." The story is: *"Enterprise data is dirty. Most tools break. Watch us generate a mess (Farm) and then create order from chaos (AOD)."*

---

## Tour Overview

| System | Phases | Steps |
|--------|--------|-------|
| AOD | Entry, Discovery, Results, Risks, Triage, Catalog, Verify, Exit | Steps 1, 6-11, 13 |
| Farm | Chaos Generation, Handoff, Reconciliation | Steps 2-5, 12-13 |

**Total Experience**: 13 guided steps across both systems

---

## Phase 0: The Hook (AOD Entry)

| Step | Dialog Title | Dialog Text | Visual/Action |
|------|--------------|-------------|---------------|
| **1 of 13** | **The Visibility Gap** | Most enterprises don't know what they own. Between **Shadow IT** (risk) and **Zombie SaaS** (waste), millions are lost annually.<br><br>This tour doesn't just show you a static demo. We're going to generate a live, chaotic IT environment and watch AOD organize it in real-time. | Center Modal.<br>Button: **"Start Simulation"** |

---

## Phase 1: Creating the Chaos (Farm)

| Step | Dialog Title | Dialog Text | Visual/Action |
|------|--------------|-------------|---------------|
| **2 of 13** | **Simulating Reality** | Real data is messy. To prove AOD is battle-hardened, we use **The Farm** to generate complex, conflicted datasets—not "happy path" demo data.<br><br>Select **"Enterprise"** to simulate the scale where human management fails. | Highlight **Scale** dropdown. |
| **3 of 13** | **Stress Testing** | Clean data doesn't exist in the wild.<br><br>Select **"Messy"** or **"Adversarial."** We intentionally inject conflicting records, partial telemetry, and duplicates to force the system to resolve ambiguity—something simple asset managers can't handle. | Highlight **Realism** & **Data Preset**. |
| **4 of 13** | **Generate Ground Truth** | We are now creating thousands of raw signals—DNS logs, finance transactions, and SSO records.<br><br>Click **Generate** to create this "Ground Truth" snapshot. | Highlight **Generate Button**. |

---

## Phase 2: The Handoff (Farm → AOD)

| Step | Dialog Title | Dialog Text | Visual/Action |
|------|--------------|-------------|---------------|
| **5 of 13** | **The Raw Data** | The Farm has generated a complex estate with intentional anomalies.<br><br>Now, let's switch to **AOD** to ingest, normalize, and make sense of this chaos. | Highlight **"Continue to AOD"**. |

---

## Phase 3: The Engine (AOD Discovery)

| Step | Dialog Title | Dialog Text | Visual/Action |
|------|--------------|-------------|---------------|
| **6 of 13** | **Ingest & Resolve** | AOD is now processing raw observations. It doesn't just list rows; it **resolves identity**.<br><br>It is currently correlating disparate signals (e.g., a credit card charge vs. a login event) to determine what is a real asset and what is noise. | *Processing State Animation* |
| **7 of 13** | **The Discovery Dashboard** | Processing complete. AOD has distilled **{observations}** signals into **{assets}** trusted assets.<br><br>Notice the **Lifecycle Cards** below. This isn't just a count; it's a health check. We've isolated **{shadow} Shadow IT** (unmanaged apps) and **{zombie} Zombie Assets** (wasted spend) automatically. | Highlight the **Results/Lifecycle** row. |

---

## Phase 4: The Findings (Risks & Waste)

| Step | Dialog Title | Dialog Text | Visual/Action |
|------|--------------|-------------|---------------|
| **8 of 13** | **Risks & Waste** | Let's inspect the problems AOD found:<br><br>• **Shadow IT:** Apps running without IT's knowledge (Security Risk).<br>• **Zombies:** Paid licenses with zero usage (Financial Waste).<br><br>Click the **Shadow** card to drill down. | Highlight **Shadow** or **Zombie** card (whichever has data). |
| **8 of 13** (fallback) | **Risks & Waste** | This simulation produced a clean run with no Shadow IT detected. In real enterprise environments, Shadow assets are common.<br><br>Let's continue to the Triage console. | If shadow count = 0 |

---

## Phase 5: Taking Action (Triage)

| Step | Dialog Title | Dialog Text | Visual/Action |
|------|--------------|-------------|---------------|
| **9 of 13** | **The Decision Layer** | Discovery is useless without action.<br><br>The **Triage Console** prioritizes findings by urgency. You don't have to review 10,000 lines—just the Tier 1 issues that require human judgment.<br><br>You can acknowledge, reject, or flag assets right here. | Highlight the **Triage List** / Actions column. |

---

## Phase 6: The Bridge (Catalog)

| Step | Dialog Title | Dialog Text | Visual/Action |
|------|--------------|-------------|---------------|
| **10 of 13** | **The Trusted Catalog** | This is the "Golden Record."<br><br>While Triage handles the exceptions, the **Catalog** contains the fully verified estate.<br><br>This trusted list is what feeds the **Adaptive API Mesh (AAM)** to automate connections and the **Business Logic Layer (BLL)** to generate reports. | Navigate to **Catalog Tab**. Highlight the list. |
| **10 of 13** (fallback) | **The Trusted Catalog** | The Catalog is still being populated. In production, this becomes the "Golden Record" that feeds downstream systems. | If catalog empty |

---

## Phase 7: The Audit (Verification)

| Step | Dialog Title | Dialog Text | Visual/Action |
|------|--------------|-------------|---------------|
| **11 of 13** | **Trust, but Verify** | In a demo, you trust the vendor. In AutonomOS, we let you audit the math.<br><br>Let's go back to **The Farm** to compare AOD's findings against the Ground Truth we generated earlier. We measure our own Precision and Recall. | Button: **"Verify in Farm"** |

---

## Phase 8: Reconciliation (Farm)

| Step | Dialog Title | Dialog Text | Visual/Action |
|------|--------------|-------------|---------------|
| **12 of 13** | **The Scorecard** | This report compares what *actually* existed (Farm) vs. what AOD *found*.<br><br>If AOD missed a Shadow asset, it shows up here. This transparency ensures that when you deploy on real enterprise data, the results are defensible. | Highlight **Reconciliation Scorecard**. |
| **13 of 13** | **Tour Complete** | You've seen the cycle: **Generate Chaos → Discover Order → Audit Accuracy.**<br><br>You are now free to explore the Catalog, run new simulations, or drill into specific asset details. | Button: **"Finish & Explore"** |

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
| Phase 8 → AOD | `return_url` | `?guided=1&tour_phase=8` |

---

## UI Design

- **Style**: Glassmorphism with `backdrop-filter: blur(20px)`, `rgba(0,0,0,0.6)` background
- **Accent**: Cyan (`#00D9FF`) for highlights and pulsing indicator
- **Dialog**: Draggable header, step counter, progress bar
- **Navigation**: Back/Next buttons with conditional rendering based on phase
- **Branding**: "Simulation & Proof" (not "Guided Validation")

---

## Implementation Notes

1. **Terminology**: Replace "Validation" with "Simulation" or "Verification" throughout
2. **Fallback Logic**: Ensure "Guided Tour" preset in Farm defaults to a seed that guarantees at least 1 Shadow and 1 Zombie asset
3. **Visuals**: When discussing Shadows (Step 8), the UI should filter to show only those items
4. **Button Text**:
   - Entry: "Start Simulation"
   - Verify: "Verify in Farm"
   - Exit: "Finish & Explore"

---

## AOD Phase Order

```javascript
phaseOrder: [0, 3, 4, 5, 6, 7, 8]
```

With conditional intermediate phases:
- `3b`: The Discovery Dashboard (after run completes)
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
