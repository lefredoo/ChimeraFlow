# ChimeraFlow Design System (DESIGN.md)

> **UI/UX reference document for AI agents and developers.**
> All new screens and components must strictly adhere to these rules to maintain visual identity.

---

## 1. Philosophy and Visual Identity

**ChimeraFlow is [define your product positioning - e.g., "a modern, professional tool"].**
- **[Define visual style - e.g., Minimalist, Bold, Playful]**
- **Micro-interactions**: Interface must feel responsive. Clicks react visually and provide feedback.
- **Depth & Hierarchy**: Clear visual hierarchy using size, weight, and spacing.

---

## 2. Color Palette (CSS Variables)

The application **never** uses static Tailwind color classes (`bg-blue-500`, `text-gray-900`) for structural elements. Everything uses tokens in `global.css`.

### Foundations (Light/Dark Theme)
- `--bg`: Global background
- `--bg-elevated`: Cards and panels background
- `--bg-subtle`: Secondary background
- `--surface`: Interactive elements (inputs, controls)

### Brand Colors (Accents)
- `--primary`: Main action color, primary buttons, links
- `--secondary`: Secondary actions
- `--accent`: Highlights, special features
- `--success`: Success states, positive feedback
- `--warning`: Warning states
- `--error`: Error states, destructive actions
- `--text-primary`, `--text-secondary`, `--text-muted`: Text hierarchy

---

## 3. Typography

1. **[Primary Font]**: Main interface font for UI, paragraphs, and body text. (Maximum readability)
2. **[Display Font]** (`.font-display`): Heading font. Used for large titles (H1, H2) and hero sections.
3. **[Mono Font]** (`.font-mono`): Monospace font. Used for code, counters, statistics, and key numbers.

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
