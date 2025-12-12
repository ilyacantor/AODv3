# AOD Discover v3 - KPI Dashboard Update

This package contains the updated frontend code for the AOD Discover v3 dashboard, focusing on a compact, dark-themed KPI display.

## Files to Update

### 1. `client/src/pages/dashboard.tsx`
Replace the entire file content with the following React component. This implements the new KPI layout, removing the navigation and header as requested.

```tsx
import React from "react";
import { 
  Activity, 
  CheckCircle2, 
  ShieldAlert,
  FileWarning,
  Search,
  Ban
} from "lucide-react";

// Mock Data
const LIFECYCLE_METRICS = [
  { 
    label: "DISCOVERED", 
    value: 283, 
    color: "text-cyan-400", 
    border: "border-cyan-500/50",
    bg: "bg-cyan-950/20",
    icon: Search,
    description: "Total assets ingested"
  },
  { 
    label: "PARKED (BLOCKING)", 
    value: 64, 
    color: "text-red-400", 
    border: "border-red-500/50", 
    bg: "bg-red-950/20",
    icon: Ban,
    description: "Requires HITL intervention"
  },
  { 
    label: "CATALOGED", 
    value: 219, 
    color: "text-emerald-400", 
    border: "border-emerald-500/50", 
    bg: "bg-emerald-950/20",
    icon: CheckCircle2,
    description: "Validated & active"
  },
];

const BLOCKING_ISSUES = [
  { label: "SOR CONFLICT", value: 25, color: "text-orange-400", border: "border-orange-500/30" },
  { label: "SCHEMA MISMATCH", value: 39, color: "text-orange-400", border: "border-orange-500/30" },
  { label: "ID COLLISION", value: 0, color: "text-slate-400", border: "border-slate-700/30" },
  { label: "MISSING ID", value: 0, color: "text-slate-400", border: "border-slate-700/30" },
];

const FINDINGS = [
  { label: "SHADOW IT", value: 18, color: "text-amber-400", sub: "across all states" },
  { label: "GOVERNANCE GAP", value: 165, color: "text-amber-400", sub: "165 findings" },
  { label: "DATA CONFLICTS", value: 227, color: "text-amber-400", sub: "227 findings" },
  { label: "OPS RISK", value: 127, color: "text-amber-400", sub: "127 findings" },
  { label: "LOW CONFIDENCE", value: 0, color: "text-slate-400", sub: "0 findings" },
];

export default function Dashboard() {
  return (
    <div className="min-h-screen bg-[#0a0c10] text-slate-200 font-sans selection:bg-cyan-900 selection:text-cyan-50 p-6 md:p-8 flex items-center justify-center">
      
      <div className="w-full max-w-[1600px] space-y-8">
          
          {/* KPI Section 1: Lifecycle (The Prominent Ones) */}
          <section className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-2">
                <Activity className="w-4 h-4" /> Asset Lifecycle
              </h2>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {LIFECYCLE_METRICS.map((metric) => (
                <div 
                  key={metric.label}
                  className={`
                    relative group overflow-hidden rounded-xl border bg-[#0d1117] p-5 transition-all duration-300 hover:translate-y-[-2px] hover:shadow-lg
                    ${metric.border}
                  `}
                >
                  <div className={`absolute top-0 left-0 w-1 h-full opacity-60 ${metric.color.replace('text-', 'bg-')}`}></div>
                  <div className={`absolute top-0 left-0 w-full h-[1px] opacity-20 bg-gradient-to-r from-transparent via-current to-transparent ${metric.color}`}></div>
                  
                  <div className="flex justify-between items-start mb-2">
                    <h3 className="text-xs font-bold text-slate-500 uppercase tracking-widest">{metric.label}</h3>
                    <metric.icon className={`w-5 h-5 opacity-50 ${metric.color}`} />
                  </div>
                  
                  <div className="flex items-baseline gap-2">
                    <span className={`text-4xl font-mono font-bold tracking-tighter ${metric.color} drop-shadow-[0_0_8px_rgba(0,0,0,0.5)]`}>
                      {metric.value}
                    </span>
                  </div>
                  
                  <p className="text-xs text-slate-500 mt-2 font-medium">{metric.description}</p>
                </div>
              ))}
            </div>
          </section>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* KPI Section 2: Blocking Issues */}
            <section className="space-y-4">
              <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-2">
                <ShieldAlert className="w-4 h-4" /> Blocking Issues (Parked)
              </h2>
              
              <div className="grid grid-cols-2 gap-3">
                {BLOCKING_ISSUES.map((issue) => (
                  <div 
                    key={issue.label}
                    className={`
                      relative rounded-lg border bg-[#0d1117] p-4 transition-colors hover:bg-slate-900
                      ${issue.border}
                    `}
                  >
                    <div className="flex flex-col h-full justify-between">
                      <h3 className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1">{issue.label}</h3>
                      <span className={`text-2xl font-mono font-bold ${issue.value > 0 ? issue.color : 'text-slate-600'}`}>
                        {issue.value}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </section>

            {/* KPI Section 3: Non-Blocking Findings */}
            <section className="space-y-4">
              <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-2">
                <FileWarning className="w-4 h-4" /> Non-Blocking (Findings)
              </h2>
              
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {FINDINGS.map((finding) => (
                  <div 
                    key={finding.label}
                    className={`
                      relative rounded-lg border border-slate-800 bg-[#0d1117] p-4 transition-all hover:border-slate-700
                    `}
                  >
                    {finding.value > 0 && (
                      <div className="absolute top-0 right-0 w-0 h-0 border-t-[8px] border-r-[8px] border-t-amber-500/50 border-r-transparent rounded-bl-sm"></div>
                    )}
                    <h3 className="text-[10px] font-bold text-slate-500 uppercase tracking-widest truncate mb-1" title={finding.label}>
                      {finding.label}
                    </h3>
                    <div className="mt-1">
                      <span className={`text-2xl font-mono font-bold block ${finding.value > 0 ? finding.color : 'text-slate-600'}`}>
                        {finding.value}
                      </span>
                      <span className="text-[10px] text-slate-600 block mt-1">{finding.sub}</span>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          </div>
      </div>
    </div>
  );
}
```

### 2. `client/src/index.css`
Ensure your Tailwind CSS config handles the custom dark mode tokens.

```css
@import "tailwindcss";
@plugin "tailwindcss-animate";
@custom-variant dark (&:is(.dark *));

@theme inline {
  --color-background: var(--background);
  --color-foreground: var(--foreground);
  --font-sans: "Inter", sans-serif;
  --font-mono: "JetBrains Mono", monospace;
  --radius-sm: calc(var(--radius) - 4px);
  --radius-md: calc(var(--radius) - 2px);
  --radius-lg: var(--radius);
}

:root {
  --background: hsl(0 0% 100%);
  --foreground: hsl(222.2 84% 4.9%);
  --radius: 0.5rem;
}

.dark {
  --background: hsl(222.2 84% 4.9%);
  --foreground: hsl(210 40% 98%);
}

@layer base {
  * {
    @apply border-[hsl(215_27.9%_16.9%)];
  }
  body {
    @apply bg-background text-foreground antialiased;
  }
}
```

### 3. `client/index.html`
Update the font imports to include `Inter` and `JetBrains Mono`.

```html
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@100..900&family=JetBrains+Mono:wght@100..800&display=swap" rel="stylesheet">
```

## Implementation Instructions

1.  **Dependencies**: Ensure `lucide-react`, `tailwindcss`, and `tailwindcss-animate` are installed.
2.  **Typography**: The design relies on `Inter` for UI text and `JetBrains Mono` for data values.
3.  **Theme**: The dashboard is designed for a dark theme (`bg-[#0a0c10]`). Ensure the parent container or `body` allows this background color to extend to the full viewport.
