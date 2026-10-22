---
type: spec
status: not-measured
updated: 2026-10-23
---

# WP88 — Zoom, scrolling and full screen for the workbench's diagrams (C5)

Status: **Approved and in progress** (2026-10-23, owner: „zieh C9 und C5 vor") · Owner: Mischa Eismann · Author:
Claude. Backlog C5, the owner's wish of 2026-10-21: „zoom in/out … mit eigenen scrollbars pro kachel".

## 1 What is missing

Mermaid's SVG is scaled to the tile's width (`.mermaid-host svg { max-width: 100% }`), so a diagram of 30 tables
or 180 constructs shrinks until it is unreadable, and the tile never scrolls.

## 2 The rules (one component, `components/Mermaid.tsx`, every diagram of the workbench)

1. A toolbar per tile: **zoom out**, **zoom in** (factor 1.25), **fit** (the tile's width, the default),
   **1:1** (the SVG's natural width from its `viewBox`), **full screen**. Ctrl/⌘ + mouse wheel zooms too.
2. Zoomed, the SVG takes its width in pixels and the tile scrolls **in both directions**, its height capped
   (`70vh`), so the page around it stays usable.
3. Full screen: the tile covers the window (a dialog), with the same toolbar; Escape or the button closes it.
4. The zoom is remembered per tile (by its title) while the page is open; a reload starts at fit.

## 3 Acceptance (keyless)

`frontend/src/Mermaid.test.tsx` with Mermaid mocked: the toolbar exists; 1:1 sets the natural width, zoom in/out
scale it, fit returns to the tile's width; Ctrl + wheel zooms; full screen opens a dialog and Escape closes it;
a second mount of the same title starts at the remembered zoom.
