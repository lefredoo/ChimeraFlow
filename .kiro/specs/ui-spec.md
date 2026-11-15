# UI Specification

## Overview
Mobile-first dashboard with glassmorphism design

## Requirements

### R1: Dashboard Page
Components:
- Active rules list (name, status toggle)
- Recent correlations (last 10, real-time updates)
- Source health indicators (4 badges)
- Statistics panel (total correlations, rules, sources)

### R2: Rules Page
Features:
- Natural language input textarea
- JSON editor (Monaco or similar)
- Rules list table (id, trigger, status, actions)
- Predefined templates dropdown
- Create/Edit/Delete/Toggle actions

### R3: Correlation Cards
Display:
- Unified record data
- Per-source badges (color-coded)
- Provenance drawer (expandable)
- Timestamp and severity

### R4: Sources Page
Show for each source:
- Health status
- Last sync timestamp
- Record count
- Connection details (masked)

### R5: Settings Page
- Rate limit status
- LLM budget remaining
- Data refresh interval
- Language preference (FR/EN)

### R6: Accessibility
- WCAG AA contrast
- Keyboard navigation
- Focus indicators
- ARIA labels

### R7: Responsive
- Mobile: 360px min width
- Tablet: 768px
- Desktop: 1024px+

## Design System
- Glassmorphism panels
- Professional Blue palette
- IBM Plex fonts
- Smooth transitions

## Implementation (P3)
