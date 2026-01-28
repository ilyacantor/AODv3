# AOS Overview Template

A reusable React + Tailwind CSS overview/landing page template for AOS modules. Features the autonomOS dark slate design system with cyan/purple accents and smooth scroll animations.

## Quick Start

```bash
cd handoff/aos-overview-template
npm install
npm run dev      # Development server
npm run build    # Build for production
```

## Integration into an AOS Module

1. **Copy the `src/` folder** to your module's client directory
2. **Install dependencies** from `package.json`
3. **Configure Vite** to build to your static folder:
   ```ts
   build: {
     outDir: '../static/overview',
     emptyOutDir: true,
   },
   base: '/static/overview/',
   ```
4. **Embed via iframe** in your main template:
   ```html
   <iframe src="/static/overview/index.html" class="w-full h-full"></iframe>
   ```

## Architecture

```
src/
├── main.tsx              # React entry point
├── index.css             # Tailwind + CSS variables (autonomOS palette)
├── pages/
│   └── Overview.tsx      # Main overview component
├── components/
│   └── ui/
│       └── button.tsx    # Reusable button component
└── lib/
    └── utils.ts          # cn() helper for class merging
```

## Design System

### Color Palette (CSS Variables)
- **Background**: Slate 950 `#0f172a`
- **Primary**: Cyan 500 `#0bcad9` (brand accent)
- **Secondary**: Blue 500 `#3b82f6`
- **Accent**: Purple 500 `#a855f7`
- **Destructive**: Red 500 `#ef4444`
- **Success**: Green 500 `#22c55e`

### Typography
- Font: **Quicksand** (Google Fonts)
- Weights: 300, 400, 500, 600, 700

### Key Tailwind Classes
```css
.bg-gradient-brand     /* Cyan to Blue gradient */
.bg-glass              /* Frosted glass effect */
.text-cyan-brand       /* Brand cyan color */
```

## Section Structure

The Overview uses modular sections with consistent patterns:

```tsx
<section id="section-name" className="w-full max-w-6xl mx-auto px-6 py-24 border-t border-slate-800">
  <motion.div
    initial={{ opacity: 0, y: 20 }}
    whileInView={{ opacity: 1, y: 0 }}
    viewport={{ once: true }}
    transition={{ duration: 0.6 }}
  >
    {/* Section content */}
  </motion.div>
</section>
```

### Available Section Types

1. **Hero Section** - Full-width intro with gradient text
2. **Stats Grid** - 2x2 or 4-column metric cards
3. **Comparison Cards** - Side-by-side legacy vs new
4. **Iframe Embed + Sidebar** - Interactive demo with description
5. **Info Box** - Centered icon + explanation
6. **CTA Section** - Gradient background with action button

## Parent-Child Communication

The Overview listens for postMessage events:

```js
// Scroll to a section
window.postMessage({ action: 'scrollToSection', section: 'pipeline' }, '*');

// Trigger demo in embedded iframe
window.postMessage({ action: 'triggerPipelineDemo' }, '*');
```

## Customization Checklist

When adapting for a new AOS module:

1. [ ] Update section content in `Overview.tsx`
2. [ ] Replace iframe `src` URLs with your module's embeds
3. [ ] Update module name/branding
4. [ ] Adjust color accents if needed (CSS variables)
5. [ ] Add/remove sections as needed
6. [ ] Update `base` path in `vite.config.ts`

## Dependencies

| Package | Purpose |
|---------|---------|
| `react` + `react-dom` | UI framework |
| `framer-motion` | Scroll animations |
| `lucide-react` | Icons |
| `tailwindcss` | Styling |
| `class-variance-authority` | Button variants |
| `clsx` + `tailwind-merge` | Class composition |

## Build Output

Production build generates:
- `index.html` - Entry point
- `assets/index-*.js` - Bundled React app
- `assets/index-*.css` - Compiled styles

Serve from any static file server or embed in a larger application.
