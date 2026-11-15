# ChimeraFlow Design System (DESIGN.md)

> **UI/UX reference document for AI agents and developers.**
> All new screens and components must strictly adhere to these rules to maintain visual identity.

---

## 1. Philosophy and Visual Identity

**ChimeraFlow is a modern business intelligence tool that brings order to chaos.**

Built for the reality of small businesses: where Excel spreadsheets, Access databases, and WhatsApp groups contain critical business data that needs to work together.

- **Glassmorphism**: Translucent panels with backdrop blur create depth and modernity
- **Professional but approachable**: Not enterprise-stiff, not startup-playful — practical and trustworthy
- **Micro-interactions**: Interface must feel responsive. Clicks react visually and provide feedback
- **Depth & Hierarchy**: Clear visual hierarchy using size, weight, and spacing
- **Data-centric**: Information is the hero, UI supports without overwhelming

---

## 2. Color Palette (CSS Variables)

**Professional Blue** — Trustworthy, clean, business-focused.

The application must not use static Tailwind color classes (`bg-blue-500`, `text-gray-900`) for structural elements. Everything uses tokens in `frontend/app/globals.css` (plain CSS: Tailwind v4 is not wired yet).

### Foundations (Light/Dark Theme)
- `--bg`: Global background
  - Light: `#f8f9fa` (cool white)
  - Dark: `#0f1419` (deep navy)
- `--bg-elevated`: Cards and panels background (with glassmorphism)
  - Light: `rgba(255, 255, 255, 0.7)` + `backdrop-blur(12px)`
  - Dark: `rgba(17, 24, 39, 0.7)` + `backdrop-blur(12px)`
- `--bg-subtle`: Secondary background
  - Light: `#e9ecef`
  - Dark: `#1a202c`
- `--surface`: Interactive elements (inputs, controls)
  - Light: `#ffffff`
  - Dark: `#2d3748`

### Brand Colors (Professional Blue)
- `--primary`: `#2563eb` (blue-600) — Main action color, primary buttons, links
- `--primary-hover`: `#1d4ed8` (blue-700)
- `--secondary`: `#64748b` (slate-500) — Secondary actions
- `--accent`: `#0ea5e9` (sky-500) — Highlights, correlations
- `--success`: `#10b981` (emerald-500) — Success states, healthy sources
- `--warning`: `#f59e0b` (amber-500) — Warning states, low stock
- `--error`: `#ef4444` (red-500) — Error states, failed connections
- `--info`: `#3b82f6` (blue-500) — Informational messages

### Text Hierarchy
- `--text-primary`: `#111827` (light) / `#f9fafb` (dark)
- `--text-secondary`: `#6b7280` (light) / `#9ca3af` (dark)
- `--text-muted`: `#6b7280` (light) / `#9ca3af` (dark) — raised from `#9ca3af` / `#6b7280` to reach 4.5:1 for text

### Text-safe status colors
`--success`, `--error` and `--primary` fail 4.5:1 as text on the light background. For text use
`--success-text` (`#047857` light / `#34d399` dark), `--error-text` (`#b91c1c` / `#f87171`) and
`--primary-text` (`#1d4ed8` / `#93c5fd`).

### Glassmorphism Effects
```css
.glass-panel {
  background: var(--bg-elevated);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.18);
  box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.07);
}
```

---

## 3. Typography

**Classic Professional** — IBM Plex family for technical credibility and excellent readability.

1. **IBM Plex Sans** (`.font-sans`): Main interface font for UI, paragraphs, and body text. Clean, professional, highly readable.
2. **IBM Plex Serif** (`.font-display`): Heading font. Used for large titles (H1, H2) and important callouts. Adds authority and distinction.
3. **IBM Plex Mono** (`.font-mono`): Monospace font. Used for JSON rules, data values, counters, statistics, and technical content.

### Import (in global.css or layout)
```css
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Serif:wght@400;600;700&display=swap');
```

### CSS Variables
```css
:root {
  --font-sans: 'IBM Plex Sans', system-ui, sans-serif;
  --font-display: 'IBM Plex Serif', Georgia, serif;
  --font-mono: 'IBM Plex Mono', 'Courier New', monospace;
}
```

### Type Scale
- `text-xs`: 12px
- `text-sm`: 14px
- `text-base`: 16px
- `text-lg`: 18px
- `text-xl`: 20px
- `text-2xl`: 24px
- `text-3xl`: 30px
- `text-4xl`: 36px

---

## 4. Components and Utility Classes

### Layouts
- **Standard layout components to be defined based on project needs**

### Effects and CSS Utilities
- `.card`: Standard card styling with border and shadow
- `.hover-lift`: Standard hover effect (translateY(-2px) + increased shadow). Use on all cards and buttons.
- `.active-press`: Click effect (scale(0.98)). Integrated into buttons by default.
- `.focus-ring`: Accessible focus indicator

---

## 5. Tactile and Haptic Experience

Buttons and main actions must simulate "touch":
1. **Visual**: All buttons use `active:scale-[0.98]` (managed via `.active-press` or CSS) to press down on click.
2. **Physical**: On mobile web (and native apps), use haptic feedback for important interactions.

---

## 6. Animations

To avoid static interfaces:
- **Reveal on scroll**: On public pages, animate element entry
- **Hover states**: All interactive elements should have smooth hover transitions
- **Loading states**: Clear loading indicators for async operations

---

## 7. Spacing System

Use Tailwind's spacing scale consistently:
- `0.5` (2px): Tight spacing
- `1` (4px): Very small gaps
- `2` (8px): Small spacing
- `4` (16px): Base spacing
- `6` (24px): Medium spacing
- `8` (32px): Large spacing
- `12` (48px): Extra large spacing

---

## 8. Responsive Design

- **Mobile-first**: Design for mobile, enhance for desktop
- **Breakpoints**:
  - `sm`: 640px
  - `md`: 768px
  - `lg`: 1024px
  - `xl`: 1280px
  - `2xl`: 1536px

---

## 9. Implementation Checklist (AI Agent)

- [ ] Used `var(--text-secondary)` instead of `text-gray-500`?
- [ ] Button uses proper variant (integrating effects)?
- [ ] Removed all inline `style={{}}` in favor of design system?
- [ ] Tested component renders well in Light Mode AND Dark Mode?
- [ ] Page is responsive (Mobile-first)?
- [ ] All interactive elements have hover states?
- [ ] Focus states are visible for keyboard navigation?
- [ ] Color contrast meets accessibility standards (4.5:1 for text)?

---

## 10. Do's and Don'ts

### Do ✅
- Use design tokens (CSS variables) for colors
- Use semantic HTML elements
- Maintain consistent spacing
- Test in both light and dark modes
- Provide loading and error states
- Use appropriate component variants

### Don't ❌
- Hardcode colors or sizes
- Use `style={{}}` instead of classes
- Create one-off components without checking if one exists
- Ignore accessibility (contrast, focus, keyboard)
- Mix different styling approaches
- Use `!important` to override styles (fix the root cause instead)

---

_This design system ensures consistency across ChimeraFlow. Update this document as design decisions evolve._
