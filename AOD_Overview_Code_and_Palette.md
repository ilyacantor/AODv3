# AOD Overview - Code & Palette Reference

## Color Palette

### Core Colors (CSS Custom Properties)

| Role | HSL Variable | Hex | Usage |
|------|-------------|-----|-------|
| **Background** | `222 47% 11%` | `#0f172a` | Slate 950 - page background |
| **Foreground** | `210 40% 98%` | `#f8fafc` | Slate 50 - default text |
| **Primary** | `184 90% 45%` | `#0bcad9` | Cyan 500 - brand accent |
| **Secondary** | `217 91% 60%` | `#3b82f6` | Blue 500 - secondary actions |
| **Accent** | `271 91% 65%` | `#a855f7` | Purple 500 - highlights |
| **Destructive** | `0 84% 60%` | `#ef4444` | Red 500 - errors/danger |
| **Success** | -- | `#22c55e` | Green 500 - positive states |
| **Muted** | `215 28% 17%` | -- | Slate 800/60 - subdued backgrounds |
| **Muted Foreground** | `215 20% 65%` | -- | Slate 400 - secondary text |
| **Border** | `215 25% 27%` | `#334155` | Slate 700 - dividers |
| **Ring** | `184 90% 45%` | `#0bcad9` | Cyan 500/10 - focus rings |

### Brand Gradient

```css
.bg-gradient-brand {
  background-image: linear-gradient(to right, #0bcad9, #2563eb);
}
```

### Glass Effect

```css
.bg-glass {
  background-color: rgba(30, 41, 59, 0.6);
  backdrop-filter: blur(12px);
}
```

### Module Accent Colors (Platform Components Panel)

| Module | Border Color | Text Color |
|--------|-------------|------------|
| **AOD** (Discover) | `border-cyan-500` | `text-cyan-400` |
| **AAM** (API Mesh) | `border-orange-500` | `text-orange-400` |
| **DCL** (Data Layer) | `border-rose-500` | `text-rose-400` |
| **AOA** (Orchestration) | `border-green-500` | `text-green-400` |

### Glow Effects (Bullet Points)

```css
/* Cyan glow */
shadow-[0_0_8px_rgba(11,202,217,0.6)]

/* Green glow */
shadow-[0_0_8px_rgba(34,197,94,0.6)]
```

---

## Typography

- **Font Family**: Quicksand (Google Fonts)
- **Weights**: 300, 400, 500, 600, 700
- **Import**: `https://fonts.googleapis.com/css2?family=Quicksand:wght@300;400;500;600;700&display=swap`

```js
// tailwind.config.js
fontFamily: {
  sans: ['Quicksand', 'sans-serif'],
  display: ['Quicksand', 'sans-serif'],
}
```

---

## Scrollbar

```css
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

---

## Tech Stack

| Package | Version | Purpose |
|---------|---------|---------|
| `react` + `react-dom` | ^18.2.0 | UI framework |
| `framer-motion` | ^11.0.0 | Scroll animations |
| `lucide-react` | ^0.312.0 | Icons (Info, Search, Play) |
| `tailwindcss` | ^3.4.1 | Styling |
| `class-variance-authority` | ^0.7.0 | Button variants |
| `clsx` + `tailwind-merge` | ^2.1.0 / ^2.2.0 | Class composition |
| `@radix-ui/react-slot` | ^1.0.2 | Slot component for Button |
| `vite` | ^5.0.8 | Build tool |
| `typescript` | ^5.2.2 | Type checking |

---

## Project Structure

```
handoff/aos-overview-template/
├── index.html                # HTML entry point
├── package.json              # Dependencies
├── postcss.config.js         # PostCSS with Tailwind
├── tailwind.config.js        # Tailwind theme config
├── tsconfig.json             # TypeScript config
├── vite.config.ts            # Vite build config
└── src/
    ├── main.tsx              # React entry point
    ├── index.css             # Tailwind base + CSS variables + utilities
    ├── pages/
    │   └── Overview.tsx      # Main overview component (all sections)
    ├── components/
    │   └── ui/
    │       └── button.tsx    # Reusable Button with variants
    └── lib/
        └── utils.ts          # cn() class merge helper
```

---

## Build Configuration

### vite.config.ts

```ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    outDir: '../static/overview',
    emptyOutDir: true,
  },
  base: '/static/overview/',
})
```

### tsconfig.json

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src"]
}
```

### postcss.config.js

```js
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
```

---

## CSS Variables (index.css)

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
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
  --radius: 0.5rem;
}

@layer utilities {
  .bg-cyan-brand { background-color: #0bcad9; }
  .text-cyan-brand { color: #0bcad9; }
  .bg-blue-brand { background-color: #3b82f6; }
  .text-blue-brand { color: #3b82f6; }
  .bg-purple-brand { background-color: #a855f7; }
  .text-purple-brand { color: #a855f7; }
  .bg-green-brand { background-color: #22c55e; }
  .text-green-brand { color: #22c55e; }

  .bg-gradient-brand {
    background-image: linear-gradient(to right, #0bcad9, #2563eb);
  }
  .bg-glass {
    background-color: rgba(30, 41, 59, 0.6);
    backdrop-filter: blur(12px);
  }
}
```

---

## Tailwind Theme (tailwind.config.js)

```js
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Quicksand', 'sans-serif'],
        display: ['Quicksand', 'sans-serif'],
      },
      colors: {
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))',
        },
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
    },
  },
  plugins: [],
}
```

---

## Component Code

### main.tsx

```tsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import Overview from './pages/Overview'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <Overview />
  </React.StrictMode>,
)
```

### lib/utils.ts

```ts
import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```

### components/ui/button.tsx

```tsx
import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary/90",
        destructive:
          "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        outline:
          "border border-input bg-background hover:bg-accent hover:text-accent-foreground",
        secondary:
          "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-9 rounded-md px-3",
        lg: "h-11 rounded-md px-8",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button, buttonVariants }
```

### pages/Overview.tsx

```tsx
import { useRef, useEffect } from "react";
import { motion } from "framer-motion";
import {
  Info,
  Search,
  Play,
} from "lucide-react";
import { Button } from "@/components/ui/button";

export default function Overview() {
  const containerRef = useRef<HTMLDivElement>(null);
  
  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      if (event.data?.action === 'scrollToSection') {
        const section = event.data.section;
        
        const sectionIds: Record<string, string> = {
          'market': 'section-market',
          'legacy': 'section-legacy',
          'paradigm': 'section-paradigm',
          'introducing': 'section-introducing',
          'pipeline': 'section-pipeline',
          'gateway': 'section-gateway',
          'aod-details': 'section-aod-details',
          'farm-info': 'section-farm-info',
          'cta': 'section-cta'
        };
        
        const targetId = sectionIds[section];
        if (targetId) {
          const element = document.getElementById(targetId);
          if (element) {
            element.scrollIntoView({ behavior: 'smooth', block: 'start' });
          }
        } else if (section === 'hero') {
          window.scrollTo({ top: 0, behavior: 'smooth' });
        }
      } else if (event.data?.action === 'triggerPipelineDemo') {
        const pipelineIframe = document.querySelector('iframe[title="autonomOS Pipeline Overview"]') as HTMLIFrameElement;
        if (pipelineIframe && pipelineIframe.contentWindow) {
          pipelineIframe.contentWindow.postMessage({ action: 'runDemo' }, '*');
        }
      }
    };
    
    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, []);

  return (
    <div
      ref={containerRef}
      className="min-h-screen bg-slate-950 text-slate-50 selection:bg-cyan-500/30 selection:text-cyan-50 overflow-x-hidden font-sans"
    >
      {/* --- SECTION 1: THE MARKET IS BROKEN --- */}
      <section id="section-market" className="w-full max-w-6xl mx-auto px-6 py-24 md:py-32 border-t border-slate-800">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
        >
          <h2 className="text-3xl md:text-4xl font-bold text-white mb-12">
            Enterprise IT Is Structurally Broken
          </h2>

          <div className="grid md:grid-cols-2 gap-12">
            {/* Left: The Enterprise Crisis */}
            <div className="space-y-6">
              <h3 className="text-2xl font-bold text-cyan-400">The Enterprise Crisis</h3>
              <p className="text-lg text-slate-400 leading-relaxed">
                Organizations are drowning in disconnected systems and unmanaged digital sprawl.
                Despite massive technology investment, enterprises remain{" "}
                <strong className="text-white">data-rich but action-poor</strong>.
              </p>
              <p className="text-lg text-slate-400 leading-relaxed">
                This isn't a tooling problem.{" "}
                <strong className="text-white">It's an operating failure.</strong>
              </p>
              <p className="text-lg text-slate-400 leading-relaxed">
                The result is a widening Insight-to-Action Gap that paralyzes decision-making, slows execution, and increases risk.
              </p>
            </div>

            {/* Right: Stats Grid */}
            <div className="grid grid-cols-2 gap-6">
              <div className="p-6 bg-slate-900/50 rounded-xl border border-slate-800">
                <div className="text-4xl font-bold text-transparent bg-clip-text bg-gradient-brand mb-2">1,000+</div>
                <div className="text-white font-semibold mb-1">Apps Per Enterprise</div>
                <div className="text-sm text-slate-500">Average for large organizations</div>
              </div>
              <div className="p-6 bg-slate-900/50 rounded-xl border border-slate-800">
                <div className="text-4xl font-bold text-transparent bg-clip-text bg-gradient-brand mb-2">80%</div>
                <div className="text-white font-semibold mb-1">Budget on Maintenance</div>
                <div className="text-sm text-slate-500">Not innovation</div>
              </div>
              <div className="p-6 bg-slate-900/50 rounded-xl border border-slate-800">
                <div className="text-4xl font-bold text-transparent bg-clip-text bg-gradient-brand mb-2">$2.6T</div>
                <div className="text-white font-semibold mb-1">Annual Legacy Spend</div>
                <div className="text-sm text-slate-500">Just keeping systems running</div>
              </div>
              <div className="p-6 bg-slate-900/50 rounded-xl border border-slate-800">
                <div className="text-4xl font-bold text-transparent bg-clip-text bg-gradient-brand mb-2">60%+</div>
                <div className="text-white font-semibold mb-1">Shadow Apps</div>
                <div className="text-sm text-slate-500">Will grow exponentially with agentic sprawl</div>
              </div>
            </div>
          </div>
        </motion.div>
      </section>

      {/* --- SECTION 1.5: LEGACY STACK EMBED --- */}
      <section id="section-legacy" className="w-full border-t border-slate-800">
        <div className="flex flex-col md:flex-row min-h-[70vh]">
          <div className="flex-1 bg-slate-900/30">
            <iframe
              src="https://overview.autonomos.software/legacy/embed"
              className="w-full h-full min-h-[50vh] md:min-h-[70vh] border-none"
              title="Legacy Stack Visualization"
              loading="lazy"
            />
          </div>
          
          <div className="w-full md:w-80 lg:w-96 bg-slate-900/50 border-l border-slate-800 p-8 flex flex-col justify-center">
            <motion.div
              initial={{ opacity: 0, x: 20 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6 }}
              className="space-y-6"
            >
              <h2 className="text-2xl md:text-3xl font-bold text-white leading-tight">
                Inside the Broken Legacy Stack
              </h2>
              <p className="text-base text-slate-400 leading-relaxed">
                Over decades, enterprises accumulated SaaS, on-prem systems, spreadsheets, bots, and human glue.
              </p>
              <p className="text-base text-slate-400 leading-relaxed">
                Each layer solved a local problem — none solved the system.
              </p>
            </motion.div>
          </div>
        </div>
      </section>

      {/* --- SECTION 2: PARADIGM SHIFT --- */}
      <section id="section-paradigm" className="w-full max-w-6xl mx-auto px-6 py-24 md:py-32 border-t border-slate-800">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="space-y-12"
        >
          <h2 className="text-2xl md:text-3xl font-bold text-white leading-tight">
            This Unsustainable Paradigm is Leading to the Fundamental Market Shift:{" "}
            <span className="text-transparent bg-clip-text bg-gradient-brand">From Software to Intelligence</span>
          </h2>

          <div className="grid md:grid-cols-2 gap-6">
            {/* Legacy Model */}
            <div className="p-6 bg-slate-900/50 rounded-xl border-l-4 border-slate-600">
              <h3 className="text-xl font-bold text-slate-400 mb-4">The Legacy Model: Software Navigation (Obsolete)</h3>
              <ul className="space-y-3 text-slate-400">
                <li className="flex gap-3 items-start">
                  <span className="mt-2 w-1.5 h-1.5 rounded-full bg-slate-500 shrink-0" />
                  <span>Users must navigate rigid, disconnected applications (ERP, CRM, etc.).</span>
                </li>
                <li className="flex gap-3 items-start">
                  <span className="mt-2 w-1.5 h-1.5 rounded-full bg-slate-500 shrink-0" />
                  <span>Operations require manual orchestration and specialized technical expertise.</span>
                </li>
                <li className="flex gap-3 items-start">
                  <span className="mt-2 w-1.5 h-1.5 rounded-full bg-slate-500 shrink-0" />
                  <span>Siloed systems create complexity and limit operational visibility.</span>
                </li>
                <li className="flex gap-3 items-start">
                  <span className="mt-2 w-1.5 h-1.5 rounded-full bg-slate-500 shrink-0" />
                  <span>Value is trapped within the applications.</span>
                </li>
              </ul>
            </div>

            {/* New Reality */}
            <div className="p-6 bg-slate-900/50 rounded-xl border-l-4 border-orange-500">
              <h3 className="text-xl font-bold text-orange-400 mb-4">The New Reality: Autonomous Orchestration (Emerging)</h3>
              <ul className="space-y-3 text-slate-300">
                <li className="flex gap-3 items-start">
                  <span className="mt-2 w-1.5 h-1.5 rounded-full bg-orange-500 shrink-0" />
                  <span>Users engage directly with data through natural language (Intent-driven).</span>
                </li>
                <li className="flex gap-3 items-start">
                  <span className="mt-2 w-1.5 h-1.5 rounded-full bg-orange-500 shrink-0" />
                  <span>Operations are managed autonomously by multi-agent AI systems.</span>
                </li>
                <li className="flex gap-3 items-start">
                  <span className="mt-2 w-1.5 h-1.5 rounded-full bg-orange-500 shrink-0" />
                  <span>A unified interface abstracts away underlying technical complexity.</span>
                </li>
                <li className="flex gap-3 items-start">
                  <span className="mt-2 w-1.5 h-1.5 rounded-full bg-orange-500 shrink-0" />
                  <span>The stack is commoditized; value shifts to the intelligence layer.</span>
                </li>
              </ul>
            </div>
          </div>

          <p className="text-xl md:text-2xl text-slate-300 text-center font-medium leading-relaxed max-w-4xl mx-auto">
            The Intelligence Shift Is Inevitable. Enterprise systems were never designed for it.{" "}
            <strong className="text-white">A new operating system is required.</strong>
          </p>
        </motion.div>
      </section>

      {/* --- SECTION 3: INTRODUCING AUTONOMOS --- */}
      <section id="section-introducing" className="w-full max-w-6xl mx-auto px-6 py-24 md:py-32 border-t border-slate-800 min-h-[500px] md:min-h-[550px] flex items-center">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="space-y-8 text-center w-full"
        >
          <h2 className="text-3xl md:text-4xl font-bold tracking-tight leading-[1.1] text-white">
            autonomOS:{" "}
            <span className="text-transparent bg-clip-text bg-gradient-brand">
              The Operating System
            </span>
            {" "}for the Intelligent Enterprise
          </h2>

          <p className="text-xl md:text-2xl text-slate-400 leading-relaxed font-medium max-w-4xl mx-auto">
            Leading the paradigm shift from rigid legacy software to unified, natural language engagement with enterprise data.
          </p>
        </motion.div>
      </section>

      {/* --- SECTION 4: PIPELINE WITH PLATFORM COMPONENTS --- */}
      <section id="section-pipeline" className="relative w-full h-[85vh] border-y border-slate-800 bg-slate-950 flex flex-col md:flex-row overflow-hidden group">
        {/* Main Flow Area */}
        <div className="flex-1 relative h-full bg-slate-900/20">
          <iframe
            src="https://overview.autonomos.software/embed"
            className="w-full h-full border-none opacity-80 group-hover:opacity-100 transition-opacity duration-500"
            title="autonomOS Pipeline Overview"
            loading="lazy"
          />
        </div>

        {/* Fixed Side Panel - Platform Components */}
        <div className="w-full md:w-[420px] h-auto md:h-full bg-slate-900/80 backdrop-blur-xl border-t md:border-t-0 md:border-l border-slate-800 p-6 flex flex-col shrink-0 z-20 shadow-[-10px_0_30px_rgba(0,0,0,0.2)] overflow-y-auto">
          <div className="mb-6">
            <h2 className="text-lg font-bold text-white mb-1">
              autonom<span className="text-transparent bg-clip-text bg-gradient-brand">OS</span> Platform (AOS) Components
            </h2>
            <div className="h-0.5 w-16 bg-gradient-brand rounded-full" />
          </div>

          <div className="space-y-3 text-sm">
            {/* AOD */}
            <div className="p-4 bg-slate-800/50 rounded-lg border-l-2 border-cyan-500">
              <div className="flex items-start gap-3">
                <Search className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
                <div>
                  <h3 className="font-bold text-cyan-400 mb-1">Discover (AOD) <span className="text-cyan-300 font-normal">— this demo</span></h3>
                  <p className="text-slate-400 text-xs leading-relaxed">
                    Builds a centralized, continuously updated source-of-truth catalog for all digital assets. Automatically deduplicates entries, infers ownership, and enriches asset profiles with comprehensive infrastructure and network metadata.
                  </p>
                </div>
              </div>
            </div>

            {/* AAM */}
            <div className="p-4 bg-slate-800/50 rounded-lg border-l-2 border-orange-500">
              <div className="flex items-start gap-3">
                <div className="w-4 h-4 text-orange-400 shrink-0 mt-0.5 flex items-center justify-center">
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
                    <path d="M12 2L2 7l10 5 10-5-10-5z" /><path d="M2 17l10 5 10-5" /><path d="M2 12l10 5 10-5" />
                  </svg>
                </div>
                <div>
                  <h3 className="font-bold text-orange-400 mb-1">Adaptive API Mesh (AAM)</h3>
                  <p className="text-slate-400 text-xs leading-relaxed">
                    Self-healing integration layer that monitors API health, detects schema changes, and autonomously adapts.
                  </p>
                </div>
              </div>
            </div>

            {/* DCL */}
            <div className="p-4 bg-slate-800/50 rounded-lg border-l-2 border-rose-500">
              <div className="flex items-start gap-3">
                <div className="w-4 h-4 text-rose-400 shrink-0 mt-0.5 flex items-center justify-center">
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
                    <circle cx="12" cy="12" r="10" /><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20" /><path d="M2 12h20" />
                  </svg>
                </div>
                <div>
                  <h3 className="font-bold text-rose-400 mb-1">Data Connectivity Layer (DCL)</h3>
                  <p className="text-slate-400 text-xs leading-relaxed">
                    Unified enterprise ontology mapping disparate sources into a coherent knowledge graph for intelligent decision-making.
                  </p>
                </div>
              </div>
            </div>

            {/* AOA */}
            <div className="p-4 bg-slate-800/50 rounded-lg border-l-2 border-green-500">
              <div className="flex items-start gap-3">
                <div className="w-4 h-4 text-green-400 shrink-0 mt-0.5 flex items-center justify-center">
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
                    <path d="M12 3v18" /><path d="M5.636 5.636l12.728 12.728" /><path d="M18.364 5.636L5.636 18.364" /><circle cx="12" cy="12" r="3" />
                  </svg>
                </div>
                <div>
                  <h3 className="font-bold text-green-400 mb-1">Agentic Orchestration Architecture (AOA)</h3>
                  <p className="text-slate-400 text-xs leading-relaxed">
                    Governance engine managing agent proliferation at scale with audit trails, HITL mechanisms, and observability.
                  </p>
                </div>
              </div>
            </div>
          </div>

          <div className="mt-6 pt-4 border-t border-slate-700">
            <p className="text-base text-white font-semibold leading-relaxed">
              autonomOS makes broken enterprise IT usable — without replacing it.
            </p>
          </div>
        </div>
      </section>

      {/* --- SECTION 5: AOD INTRODUCTION ("The Gateway") --- */}
      <section id="section-gateway" className="w-full max-w-5xl mx-auto px-6 py-24 md:py-32 border-t border-slate-800 min-h-[500px] md:min-h-[550px] flex items-center">
        <div className="flex flex-col gap-8 text-center md:text-left w-full">
          <h2 className="text-[30px] md:text-[40px] font-bold text-white leading-tight">
            AOD is the gateway to autonom<span className="text-cyan-400">OS</span>.
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
            </div>
          </div>
        </div>
      </section>

      {/* --- SECTION 6: AOD REACTFLOW VISUAL (What AOD Does) --- */}
      <section id="section-aod-details" className="relative w-full h-[85vh] border-y border-slate-800 bg-slate-950 flex flex-col md:flex-row overflow-hidden group">
        <div className="flex-1 relative h-full bg-slate-900/20">
          <iframe
            src="https://overview.autonomos.software/aod/embed"
            className="w-full h-full border-none opacity-80 group-hover:opacity-100 transition-opacity duration-500"
            title="AOD Graphical Overview"
            loading="lazy"
          />
        </div>

        <div className="w-full md:w-96 h-auto md:h-full bg-slate-900/80 backdrop-blur-xl border-t md:border-t-0 md:border-l border-slate-800 p-8 flex flex-col shrink-0 z-20 shadow-[-10px_0_30px_rgba(0,0,0,0.2)] overflow-y-auto">
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
                  Classifies outcomes (Security Risks, Governance Gaps, Shadow Assets, Zombie Assets)
                </span>
              </li>
              <li className="flex gap-3 items-start">
                <div className="mt-2 w-1.5 h-1.5 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)] shrink-0" />
                <span className="font-bold text-white">
                  Produces a catalog used by the rest of AOS
                </span>
              </li>
            </ul>

            <div className="mt-8 p-4 bg-cyan-950/30 border border-cyan-900/50 rounded-lg text-cyan-200 text-sm font-medium text-center">
              While discovery is its primary function, AOD also delivers
              immediate operational value by surfacing security risks,
              unmanaged systems, costly inactive assets, and governance issues.
            </div>
          </div>
        </div>
      </section>

      {/* --- SECTION 7: WHY FARM EXISTS --- */}
      <section id="section-farm-info" className="w-full max-w-3xl mx-auto px-6 py-24 md:py-32 text-center">
        <div className="mb-6 flex justify-center">
          <div className="p-4 bg-blue-900/20 rounded-full border border-blue-500/20">
            <Info className="w-8 h-8 text-blue-500" />
          </div>
        </div>

        <h2 className="text-3xl md:text-4xl font-bold text-white mb-6">
          Why You'll See "Farm"
        </h2>

        <div className="space-y-6 text-lg text-slate-400">
          <p className="font-semibold text-white text-xl">
            Complex enterprise systems are easy to demo and hard to trust.
          </p>
          <p className="leading-relaxed">
            AOS Farm is our stress-test engine. It validates the platform against a theoretical space of ~300,000 state combinations by generating realistic enterprise chaos:
          </p>
          <div className="space-y-4 text-left max-w-xl mx-auto">
            <div className="flex gap-3 items-start">
              <div className="mt-2 w-1.5 h-1.5 rounded-full bg-cyan-500 shadow-[0_0_8px_rgba(11,202,217,0.6)] shrink-0" />
              <span><strong className="text-white">17,000 Asset Permutations:</strong> From standard servers to "zombie" instances.</span>
            </div>
            <div className="flex gap-3 items-start">
              <div className="mt-2 w-1.5 h-1.5 rounded-full bg-cyan-500 shadow-[0_0_8px_rgba(11,202,217,0.6)] shrink-0" />
              <span><strong className="text-white">37 Edge Case Categories:</strong> Specifically targeting governance forks and data quality failures.</span>
            </div>
            <div className="flex gap-3 items-start">
              <div className="mt-2 w-1.5 h-1.5 rounded-full bg-cyan-500 shadow-[0_0_8px_rgba(11,202,217,0.6)] shrink-0" />
              <span><strong className="text-white">800,000 Rule Evaluations:</strong> Proving stability at scale.</span>
            </div>
          </div>
        </div>
      </section>

      {/* --- SECTION 8: CALL TO ACTION --- */}
      <section id="section-cta" className="w-full bg-gradient-brand py-20 px-6 relative overflow-hidden">
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

          <div className="flex flex-col sm:flex-row gap-4 w-full md:w-auto flex-wrap justify-center md:justify-end">
            <Button
              size="lg"
              className="bg-white text-blue-600 hover:bg-slate-100 border-none font-bold text-base px-8 h-14 rounded-full shadow-lg hover:translate-y-[-2px] transition-transform"
              onClick={() => {
                if (window.parent && window.parent !== window) {
                  window.parent.postMessage({ action: "startSimulation" }, "*");
                }
              }}
            >
              <Play className="w-4 h-4 mr-2 fill-current" />
              Run Simulation
            </Button>

            <Button
              size="lg"
              variant="outline"
              className="bg-blue-600/50 border-white/30 text-white hover:bg-blue-600 hover:text-white hover:border-white font-medium text-base px-8 h-14 rounded-full backdrop-blur-sm"
              onClick={() => {
                if (window.parent && window.parent !== window) {
                  window.parent.postMessage({ action: "switchToConsole" }, "*");
                }
              }}
            >
              <Search className="w-4 h-4 mr-2" />
              Explore Freely
            </Button>
          </div>
        </div>
      </section>

      {/* Footer minimal */}
      <footer className="w-full py-8 text-center text-xs text-slate-600 border-t border-slate-900 bg-slate-950">
        © 2025 autonom<span className="text-cyan-400">OS</span>. All rights reserved.
      </footer>
    </div>
  );
}
```

---

## Section Map

| # | Section ID | Title | Layout |
|---|-----------|-------|--------|
| 1 | `section-market` | Enterprise IT Is Structurally Broken | 2-col: text + stats grid |
| 1.5 | `section-legacy` | Inside the Broken Legacy Stack | iframe + sidebar |
| 2 | `section-paradigm` | From Software to Intelligence | 2-col comparison cards |
| 3 | `section-introducing` | autonomOS: The Operating System | Centered hero text |
| 4 | `section-pipeline` | AOS Platform Components | iframe + component panel |
| 5 | `section-gateway` | AOD is the gateway to autonomOS | Left-aligned statement |
| 6 | `section-aod-details` | What AOD Does | iframe + bullet sidebar |
| 7 | `section-farm-info` | Why You'll See "Farm" | Centered info box |
| 8 | `section-cta` | Ready to see it in action? | Gradient CTA with buttons |

## External Embeds

| URL | Section | Purpose |
|-----|---------|---------|
| `https://overview.autonomos.software/legacy/embed` | Legacy Stack | Interactive legacy stack visualization |
| `https://overview.autonomos.software/embed` | Pipeline | autonomOS pipeline flow diagram |
| `https://overview.autonomos.software/aod/embed` | AOD Details | AOD-specific flow visualization |

## Parent-Child postMessage API

### Inbound (parent to Overview iframe)

```js
{ action: 'scrollToSection', section: 'pipeline' }
{ action: 'triggerPipelineDemo' }
```

### Outbound (Overview iframe to parent)

```js
{ action: 'startSimulation' }
{ action: 'switchToConsole' }
```

## Animation Pattern

All sections use the same framer-motion reveal:

```tsx
<motion.div
  initial={{ opacity: 0, y: 20 }}
  whileInView={{ opacity: 1, y: 0 }}
  viewport={{ once: true }}
  transition={{ duration: 0.6 }}
>
```

Sidebar variants use `x: 20` instead of `y: 20` for horizontal slide-in.
