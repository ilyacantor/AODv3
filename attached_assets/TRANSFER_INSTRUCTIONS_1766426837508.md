# AutonomOS Landing Page - Transfer Instructions

Use these instructions to transfer the AutonomOS landing page to another Replit project.

## 1. Install Dependencies

Run the following command to install the necessary packages:

```bash
npm install framer-motion lucide-react clsx tailwind-merge @radix-ui/react-slot
```

(Note: `framer-motion` is used for animations, `lucide-react` for icons.)

## 2. Setup Tailwind CSS & Global Styles

Replace or update your `client/src/index.css` with the following content to include the custom color palette and theme variables.

**File:** `client/src/index.css`

```css
@import "tailwindcss";
@import "tw-animate-css";
@import "@xyflow/react/dist/style.css";

@custom-variant dark (&:is(.dark *));

@theme inline {
  --radius-sm: calc(var(--radius) - 4px);
  --radius-md: calc(var(--radius) - 2px);
  --radius-lg: var(--radius);
  --radius-xl: calc(var(--radius) + 4px);
  
  --color-background: hsl(var(--background));
  --color-foreground: hsl(var(--foreground));
  
  --color-card: hsl(var(--card));
  --color-card-foreground: hsl(var(--card-foreground));
  
  --color-popover: hsl(var(--popover));
  --color-popover-foreground: hsl(var(--popover-foreground));
  
  --color-primary: hsl(var(--primary));
  --color-primary-foreground: hsl(var(--primary-foreground));
  
  --color-secondary: hsl(var(--secondary));
  --color-secondary-foreground: hsl(var(--secondary-foreground));
  
  --color-muted: hsl(var(--muted));
  --color-muted-foreground: hsl(var(--muted-foreground));
  
  --color-accent: hsl(var(--accent));
  --color-accent-foreground: hsl(var(--accent-foreground));
  
  --color-destructive: hsl(var(--destructive));
  --color-destructive-foreground: hsl(var(--destructive-foreground));
  
  --color-border: hsl(var(--border));
  --color-input: hsl(var(--input));
  --color-ring: hsl(var(--ring));
  
  --font-sans: 'Quicksand', sans-serif;
  --font-display: 'Quicksand', sans-serif;
  
  --radius: 0.5rem;
}

:root {
  /* AutonomOS Palette - Dark Mode Default */
  --background: 222 47% 11%;   /* Slate 950 #0f172a */
  --foreground: 210 40% 98%;   /* Slate 50 */

  --card: 222 47% 11%;         /* Slate 900 base */
  --card-foreground: 210 40% 98%;

  --popover: 222 47% 11%;
  --popover-foreground: 210 40% 98%;

  /* Cyan-500 #0bcad9 */
  --primary: 184 90% 45%; 
  --primary-foreground: 222 47% 11%;

  /* Blue-500 #3b82f6 */
  --secondary: 217 91% 60%;
  --secondary-foreground: 210 40% 98%;

  /* Slate 800/60 */
  --muted: 215 28% 17%;
  --muted-foreground: 215 20% 65%; /* Slate 400 */

  /* Purple-500 #a855f7 */
  --accent: 271 91% 65%;
  --accent-foreground: 210 40% 98%;

  /* Red-500 #ef4444 */
  --destructive: 0 84% 60%;
  --destructive-foreground: 210 40% 98%;

  /* Slate 700 #334155 */
  --border: 215 25% 27%;
  --input: 215 25% 27%;
  
  /* Cyan-500/10 */
  --ring: 184 90% 45%;

  --radius: 0.5rem;
}

/* Dark mode overrides (same as root since default is dark) */
.dark {
  --background: 222 47% 11%;
  --foreground: 210 40% 98%;
  --card: 222 47% 11%;
  --card-foreground: 210 40% 98%;
  --popover: 222 47% 11%;
  --popover-foreground: 210 40% 98%;
  --primary: 184 90% 45%;
  --primary-foreground: 222 47% 11%;
  --secondary: 217 91% 60%;
  --secondary-foreground: 210 40% 98%;
  --muted: 215 28% 17%;
  --muted-foreground: 215 20% 65%;
  --accent: 271 91% 65%;
  --accent-foreground: 210 40% 98%;
  --destructive: 0 84% 60%;
  --destructive-foreground: 210 40% 98%;
  --border: 215 25% 27%;
  --input: 215 25% 27%;
  --ring: 184 90% 45%;
}

@layer base {
  * {
    @apply border-border;
  }
  body {
    @apply font-sans antialiased bg-background text-foreground;
  }
}

/* Utility classes for specific palette colors */
@layer utilities {
  .bg-cyan-brand { background-color: #0bcad9; }
  .text-cyan-brand { color: #0bcad9; }
  
  .bg-blue-brand { background-color: #3b82f6; }
  .text-blue-brand { color: #3b82f6; }
  
  .bg-purple-brand { background-color: #a855f7; }
  .text-purple-brand { color: #a855f7; }
  
  .bg-green-brand { background-color: #22c55e; }
  .text-green-brand { color: #22c55e; }

  /* Gradient Utilities */
  .bg-gradient-brand {
    background-image: linear-gradient(to right, #0bcad9, #2563eb);
  }
  
  .bg-glass {
    background-color: rgba(30, 41, 59, 0.6);
    backdrop-filter: blur(12px);
  }
}

/* Custom Scrollbar */
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background-color: rgba(148, 163, 184, 0.3);
  border-radius: 9999px;
}
::-webkit-scrollbar-thumb:hover {
  background-color: rgba(148, 163, 184, 0.5);
}
```

## 3. Utility Function

Ensure you have the `cn` utility for class merging.

**File:** `client/src/lib/utils.ts`

```typescript
import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```

## 4. Main Page Component

Create or update the file `client/src/pages/Overview.tsx`.

**File:** `client/src/pages/Overview.tsx`

```tsx
import React, { useRef } from "react";
import { motion } from "framer-motion";
import {
  Info,
  ArrowDown,
  Database,
  Network,
  Bot,
  ScanLine,
  Search,
  Play,
  AlertTriangle,
  Layers,
} from "lucide-react";
import { Button } from "@/components/ui/button";

export default function Overview() {
  const containerRef = useRef<HTMLDivElement>(null);

  return (
    <div
      ref={containerRef}
      className="min-h-screen bg-slate-950 text-slate-50 selection:bg-cyan-500/30 selection:text-cyan-50 overflow-x-hidden font-sans"
    >
      {/* --- SECTION 1: HERO (AutonomOS) --- */}
      <section className="relative z-10 w-full max-w-6xl mx-auto px-6 py-20 md:py-32 flex flex-col justify-center min-h-[80vh]">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          className="space-y-10"
        >
          {/* Main Headline & Description */}
          <div className="space-y-8 max-w-5xl">
            <h1 className="text-[30px] md:text-[40px] font-bold tracking-tight leading-[1.1] text-white">
              AutonomOS is an{" "}
              <span className="text-transparent bg-clip-text bg-gradient-brand">
                AI-native
              </span>
              , enterprise-grade platform that turns your scattered company data
              into action.
            </h1>

            <div className="space-y-6 max-w-3xl">
              <p className="text-xl md:text-2xl text-slate-400 leading-relaxed font-medium">
                <strong className="text-white">Our Core Tenet:</strong> We
                abstract complexity away. We'll get you context regardless of
                how disparate, numerous, and complex your data sources are.
              </p>
            </div>
          </div>
        </motion.div>

        {/* Scroll Indicator */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1.5, duration: 1 }}
          className="absolute bottom-10 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2 text-slate-500"
        >
          <span className="text-[10px] uppercase tracking-widest font-bold">
            Scroll to Explore
          </span>
          <ArrowDown className="w-4 h-4 animate-bounce text-cyan-500" />
        </motion.div>
      </section>

      {/* --- SECTION 2: AOD INTRODUCTION ("The Gateway") --- */}
      <section className="w-full max-w-5xl mx-auto px-6 py-24 md:py-32 border-t border-slate-800">
        <div className="flex flex-col gap-8 text-center md:text-left">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 text-xs font-bold tracking-widest uppercase w-fit mx-auto md:mx-0">
            <ScanLine className="w-3 h-3" />
            Foundation Layer
          </div>

          <h2 className="text-[30px] md:text-[40px] font-bold text-white leading-tight">
            AOD is the gateway to AutonomOS.
          </h2>

          <div className="mt-4">
            <div className="space-y-6 text-lg text-slate-400 leading-relaxed font-medium">
              <p>
                <strong className="text-white block mb-2 text-xl">
                  Before AI systems can integrate, automate, or act, they must
                  know what actually exists.
                </strong>
                AOD is responsible for discovering assets, resolving ambiguity
                across data sources, scoring evidence, and producing a trusted
                catalog.
              </p>
              <p>
                If discovery is wrong, everything downstream breaks. That is why
                AOD is measurable, explainable, and verifiable.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* --- SECTION 4: AOD REACTFLOW VISUAL --- */}
      <section className="relative w-full h-[85vh] border-y border-slate-800 bg-slate-950 flex flex-col md:flex-row overflow-hidden group">
        {/* Main Flow Area */}
        <div className="flex-1 relative h-full bg-slate-900/20">
          <iframe
            src="https://overview.autonomos.software/aod/embed"
            className="w-full h-full border-none opacity-80 group-hover:opacity-100 transition-opacity duration-500"
            title="AOD Graphical Overview"
            loading="lazy"
          />
        </div>

        {/* Fixed Side Panel */}
        <div className="w-full md:w-96 h-auto md:h-full bg-slate-900/80 backdrop-blur-xl border-t md:border-t-0 md:border-l border-slate-800 p-8 flex flex-col shrink-0 z-20 shadow-[-10px_0_30px_rgba(0,0,0,0.2)]">
          <div className="mb-8">
            <h2 className="text-xl font-bold text-white flex items-center gap-2 mb-2">
              <Search className="w-5 h-5 text-green-400" />
              What AOD Does
            </h2>
            <div className="h-0.5 w-16 bg-green-500 rounded-full" />
          </div>

          <div className="space-y-6 text-sm text-slate-400 leading-relaxed">
            <ul className="space-y-6">
              <li className="flex gap-3 items-start">
                <div className="mt-2 w-1.5 h-1.5 rounded-full bg-cyan-500 shadow-[0_0_8px_rgba(11,202,217,0.6)] shrink-0" />
                <span>
                  Ingests signals from identity, finance, cloud, endpoints, DNS,
                  and CMDBs
                </span>
              </li>
              <li className="flex gap-3 items-start">
                <div className="mt-2 w-1.5 h-1.5 rounded-full bg-cyan-500 shadow-[0_0_8px_rgba(11,202,217,0.6)] shrink-0" />
                <span>Correlates signals into assets</span>
              </li>
              <li className="flex gap-3 items-start">
                <div className="mt-2 w-1.5 h-1.5 rounded-full bg-cyan-500 shadow-[0_0_8px_rgba(11,202,217,0.6)] shrink-0" />
                <span>Scores evidence and resolves conflicts</span>
              </li>
              <li className="flex gap-3 items-start">
                <div className="mt-2 w-1.5 h-1.5 rounded-full bg-cyan-500 shadow-[0_0_8px_rgba(11,202,217,0.6)] shrink-0" />
                <span>
                  Classifies outcomes (clean, shadow, zombie, mismatched)
                </span>
              </li>
              <li className="flex gap-3 items-start">
                <div className="mt-2 w-1.5 h-1.5 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)] shrink-0" />
                <span className="font-bold text-white">
                  Produces a catalog used by the rest of AOS
                </span>
              </li>
            </ul>

            <div className="mt-8 p-4 bg-cyan-950/30 border border-cyan-900/50 rounded-lg text-cyan-200 text-s font-medium text-center">
              While discovery is its primary function, AOD also delivers
              immediate operational value by surfacing unmanaged systems,
              inactive assets, and data conflicts.
            </div>
          </div>
        </div>
      </section>

      {/* --- SECTION 5: WHY FARM EXISTS --- */}
      <section className="w-full max-w-3xl mx-auto px-6 py-24 md:py-32 text-center">
        <div className="mb-6 flex justify-center">
          <div className="p-4 bg-blue-900/20 rounded-full border border-blue-500/20">
            <Info className="w-8 h-8 text-blue-500" />
          </div>
        </div>

        <h2 className="text-3xl md:text-4xl font-bold text-white mb-6">
          Why You’ll See “Farm”
        </h2>

        <div className="space-y-6 text-lg text-slate-400">
          <p className="font-semibold text-white text-xl">
            Complex enterprise systems are easy to demo and hard to trust.
          </p>
          <p className="leading-relaxed">
            AOS Farm is a large-scale intelligent synthetic data generator that
            produces realistic enterprise environments—including intentionally{" "}
            <span className="text-orange-400">bad data</span>,{" "}
            <span className="text-red-400">conflicts</span>, and{" "}
            <span className="text-slate-300">unmanaged systems</span>.
            Reconciliation exists to prove accuracy, not to simulate it.
          </p>
        </div>
      </section>

      {/* --- SECTION 6: CALL TO ACTION --- */}
      <section className="w-full bg-gradient-brand py-20 px-6 relative overflow-hidden">
        <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20" />

        <div className="max-w-4xl mx-auto flex flex-col md:flex-row items-center justify-between gap-8 relative z-10">
          <div className="space-y-2 text-center md:text-left">
            <h2 className="text-3xl md:text-4xl font-bold text-white">
              Ready to see it in action?
            </h2>
            <p className="text-cyan-100 font-medium">
              Validate your environment or explore the platform.
            </p>
          </div>

          <div className="flex flex-col sm:flex-row gap-4 w-full md:w-auto">
            <Button
              size="lg"
              className="bg-white text-blue-600 hover:bg-slate-100 border-none font-bold text-base px-8 h-14 rounded-full shadow-lg hover:translate-y-[-2px] transition-transform"
            >
              <Play className="w-4 h-4 mr-2 fill-current" />
              Run Guided Validation
            </Button>

            <Button
              size="lg"
              variant="outline"
              className="bg-blue-600/50 border-white/30 text-white hover:bg-blue-600 hover:text-white hover:border-white font-medium text-base px-8 h-14 rounded-full backdrop-blur-sm"
            >
              <Search className="w-4 h-4 mr-2" />
              Explore Freely
            </Button>
          </div>
        </div>
      </section>

      {/* Footer minimal */}
      <footer className="w-full py-8 text-center text-xs text-slate-600 border-t border-slate-900 bg-slate-950">
        © 2025 AutonomOS. All rights reserved.
      </footer>
    </div>
  );
}
```

## 5. UI Components

If your new project uses Shadcn/UI, ensure you have the Button component installed:

```bash
npx shadcn-ui@latest add button
```

If not using Shadcn, you can replace `<Button>` with standard `<button>` elements styled with Tailwind classes like `px-4 py-2 bg-blue-500 text-white rounded`.
