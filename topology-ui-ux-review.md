# Topology Tab — UI/UX Review

## Overall Impression

The tab has a solid dark-mode foundation and good information density, but it reads as a developer-built internal tool circa 2018–2020. The main issues are inconsistent visual hierarchy, overloaded sidebar, weak affordance on interactive elements, and a graph canvas that doesn't feel polished or explorable.

---

## Navigation Bar

**Issues:**
- The active tab ("Topology") uses a rounded rectangle with a teal background — that's fine in concept, but the shape is quite heavy and boxy. It visually competes with the logo rather than feeling like a smooth tab system.
- "Drift & Health" wraps to two lines in the nav. That's a layout bug at this viewport width — it makes the nav bar height inconsistent and looks rushed.
- The "AAM" logo/wordmark separated by a plain vertical pipe `|` is minimal to the point of feeling like a placeholder rather than a brand element.
- No active indicator for the current page beyond the box (e.g., no underline, no subtle animation, no icon).

**Suggestions:**
- Use underline-style or bottom-border tab indicators — cleaner and more modern.
- Fix the "Drift & Health" wrapping, either by abbreviating, using an icon, or widening the nav.
- Give AAM a small logomark or icon to the left of the text.

---

## Left Sidebar

This is the most problematic area. It mixes **status info**, **action triggers**, **logging**, and **view controls** all in one scrollable column with very little visual separation.

**Issues:**
- **Section labels** (RUN, TOPOLOGY, ACTIONS, PIPELINE LOG, VIEW, LEGEND) are in all-caps with minimal spacing — they're not visually distinct enough from content. They feel like CSS `text-transform: uppercase` applied as an afterthought.
- **Mixed button styles in ACTIONS** — "Fetch AOD Data" has an orange border (hover state? active?), "Run Inference" and "Export to DCL" are plain dark rectangles, "101 pipes, 89 exported (173s)" is a full green button that looks like a status alert or notification, and "Dispatch Runner" is ghost-green with "View Dispatch" being a regular dark button. Five different button treatments in one section with no consistent hierarchy.
- **"101 pipes, 89 exported (173s)"** — this is a status result, not an action, but it's styled as a large green button. It's confusing. Should be a status badge or inline text, not a clickable-looking block.
- **"Stop All"** is not visible in the initial scroll position. Critical destructive actions should not be buried below the fold.
- **Pipeline Log** items are plain text with green checkmarks. They wrap awkwardly (e.g., "Export: 89 pipes to DCL (accepted)" wraps mid-sentence). The log ID `aam_run_b7765bd72f2f` is raw and unformatted — it looks like debug output, not a user-facing log.
- **VIEW section dropdowns** look identical to buttons — flat dark rectangles. There's no visual cue that they are `<select>` elements (no chevron/arrow, no border differentiation).
- **"Reset" button** in the VIEW section looks identical to the dropdown items above it. It should be visually distinct as an action.
- The **LEGEND** is at the very bottom, requiring scrolling to reach it. It's the reference key for the graph — it should be persistently visible, ideally floating over the canvas or docked at the bottom of it.

**Suggestions:**
- Introduce card-style grouping or clear divider lines between sections with more breathing room.
- Normalize button hierarchy: primary (filled), secondary (outlined), tertiary (ghost), status (badge/pill — non-clickable).
- Move the legend to an overlay or pinned position on the graph canvas itself.
- Add chevron icons to the dropdowns so they read as selects.
- Consider collapsing the Pipeline Log into an expandable accordion — it's verbose and pushes VIEW/LEGEND out of view.

---

## Graph / Canvas Area

**Issues:**
- **Node shapes** are inconsistent and the distinction is hard to internalize: diamonds (4 different colors), squares (gray, yellow, orange), circles. Combined with color, this is a lot of simultaneous encoding. The legend helps but requires scrolling down.
- **Node labels** are small and often get cropped ("Aws_Api_Gateway" is shown as "Aws_Api_Gateway. API Gateway" split oddly; "Eventbridge_Event Bus" similarly). The raw underscore naming (`Aws_Api_Gateway`) exposes internal system identifiers to the user.
- **Edge arrows** are very faint thin gray lines on a near-black background. They're barely visible and lack weight or hierarchy — all connections look equally important.
- **Gray "unresolved" nodes** (the plain gray squares) blend into the dark background. It's hard to distinguish them from each other or understand what they represent at a glance.
- **No zoom controls** visible on the canvas (no +/- buttons, no minimap, no zoom percentage). Discoverability of zoom/pan is zero — users who don't know to scroll or pinch will feel stuck.
- **No search or highlight** functionality apparent on the canvas. With 20+ nodes it's already hard to find specific ones; at larger scale this would be unusable.
- **Large empty black space** surrounds the graph, especially at the top-right. The canvas feels wasteful.
- The **status bar at the bottom** ("Pipeline complete (173s): 101 pipes inferred...") is a bright teal pill that appears detached from the sidebar context where the same info lives. It's redundant.

**Suggestions:**
- Add floating zoom controls (+/−, fit-to-screen button) in a corner of the canvas.
- Add a minimap or at minimum a node search/filter input.
- Improve edge visibility — consider thicker lines, directional animation (flow dots), or color-coded edge types.
- Clean up node labels: display friendly names, hide internal identifiers or show them only on hover.
- Add a hover tooltip on nodes showing key stats (type, pipe count, status) rather than embedding them in the node label.
- Add a subtle canvas background grid or very faint texture to break up the flat black.

---

## Interaction & Feedback

- **Clicking a node** presumably opens a "Node Details" panel but this panel doesn't appear to be visible — it's possibly hidden off-screen or empty. The discoverability of this interaction is low.
- **No loading states or skeleton screens** — when actions like "Fetch AOD Data" run, the feedback comes only through the Pipeline Log text, which requires the user to scroll down.
- **"Done (160575r) 1772113323s"** appears as raw text somewhere in the sidebar — this looks like unformatted internal debug/telemetry data that should never be user-facing.

---

## Summary of Priorities

| Priority | Issue |
|----------|-------|
| 🔴 High | Button style inconsistency in Actions — status vs. action elements mixed |
| 🔴 High | No zoom controls or discoverability affordances on the graph |
| 🔴 High | "Drift & Health" nav wrapping / broken layout |
| 🟠 Medium | Legend buried below fold — should be on/near the canvas |
| 🟠 Medium | View dropdowns indistinguishable from buttons |
| 🟠 Medium | Raw system identifiers (underscores, UUIDs) exposed in node labels and log |
| 🟡 Low | Canvas whitespace / empty area |
| 🟡 Low | Faint edge lines on graph |
| 🟡 Low | Pipeline Log verbosity pushing VIEW section out of view |
