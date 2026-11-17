---
type: spec
status: not-measured
updated: 2026-11-17
---

# WP143 — A diagram can be printed and saved: the tile's own picture, light, on one sheet (C49)

Status: **Approved and in progress** (2026-11-17, on the owner's go of that day: all open workbench-usability
candidates) · Owner: Mischa Eismann · Author: Claude. Candidate C49. Third of four packages.

## 1 What is missing

The Model perspective's diagram tiles (`components/Mermaid.tsx`, WP88) zoom, fit and go full screen. Printing
the page prints the whole perspective in the dark theme with the diagram cut at the tile's width; there is no
way to take the picture out of the workbench.

## 2 The rules

1. **Two tools on every non-empty tile: „print" and „save SVG".** Both draw the tile's own source again with
   Mermaid's light theme — the same diagram the tile shows: the whole model, or the subject area when one is
   chosen (WP88), or the input model. The dark picture on the screen is not touched.
2. **Print** puts that picture on a sheet of its own — the tile's title above it, the run below — hides
   everything else for the print (`@media print`), asks the browser to print (`window.print()`), and removes
   the sheet afterwards. Landscape is suggested (`@page`), the picture scaled to the sheet's width; a very
   wide model stays readable only on a larger sheet or as SVG. The PDF is the browser's print dialog's.
3. **Save SVG** hands the same light picture to the browser as a file named after the tile's title — it
   scales and prints without loss in any viewer.
4. **Their look follows WP141**: tools of a tile are toggles and navigation — the tile's existing small
   buttons; neither is a `primary`.

**Decided by the author on C49's open points:** the browser's print dialog is enough — no server-side
export, no new dependency; the sheet carries the title and the run id.

**Unchanged.** The picture on the screen, zoom, fit, full screen; the report's diagrams.

## 3 Not built

No paging of a wide model over several sheets (the browser prints one scaled picture). No PNG. No print of
the inventory or of the whole perspective. Nothing in the report or the CLI.

## 4 Acceptance (Vitest, committed red; Mermaid mocked as in WP88)

- **G1** a tile with a diagram offers „print" and „save SVG"; an empty tile offers neither.
- **G2** print: Mermaid is asked for the light theme; a sheet with the title, the run line and an SVG is in
  the document while printing; `window.print` is called once; after `afterprint` the sheet is gone; the
  tile's own SVG is the one it was.
- **G3** save: a file of type `image/svg+xml` named after the title (`output-model-….svg`), carrying the SVG
  with its namespace.
- **G4** the stylesheet hides everything but the sheet when printing.
- **G5** WP88's five cases unchanged and green.

## 5 Pre-registration

- **P1** G1–G4 red before, green after; G5; `tsc`, the build.
- **P2** in a real Chromium on the canned stub state: the two tools on the output tile; the saved file is a
  light SVG that parses; the print sheet rendered to PDF by the browser (headless `page.pdf` with the print
  media) is one landscape page with the title and the picture. Kept as files.
- **Not measured:** a printer; a model of chain size on one sheet.

## 6 Measured (2026-11-17)

- **P1 held.** Four Vitest cases red at `8149998`, green with the change; WP88's five unchanged and green.
  Vitest 59, `tsc`, the build. No Python file touched.
- **P2 done — and it found two defects the mocked tests could not.** In a real Chromium on the canned stub
  state:
  1. **The file as first written was no XML.** Mermaid returns HTML-serialised markup (a label's `<br>` is
     not closed); the browser's own XML parser refused the saved file. The picture now goes through the DOM
     and `XMLSerializer`. Guard G3b added — red against the first implementation, green now.
  2. **Labels were HTML inside `<foreignObject>`**, which a browser draws and most other SVG viewers do
     not; and the sheet's rule for its own line (`.print-sheet p`) restyled every label paragraph. The
     light picture is drawn with `htmlLabels: false` (mermaid 12.2.0, `config.type.d.ts`, root-level
     `htmlLabels`), and the rule is scoped to the sheet's own children. With text labels a construct's name
     was then broken mid-word on paper (`link_account_cus` / `tomer`): `flowchart.wrappingWidth` is set wide
     for the light picture.
  After that: both tools on the output and the input tile; the saved files parse as SVG (output model: 6
  nodes, 12 text labels, no `foreignObject`; input model, an `erDiagram`: 45 text labels), names whole;
  under print media only the sheet is visible; the browser's PDF of each sheet is one landscape page with
  the title, the picture and the run line (kept as `wp143-print-sheet*.pdf`); after `afterprint` the sheet
  is gone and the screen's picture is the one it was.
- **G3 adjusted with the change:** the serialiser writes an empty group as `<g/>`; the guard takes both.
- **Not measured.** A printer; a model of chain size on one sheet (the picture is scaled to the page, a wide
  model becomes small — the SVG is the way out); a browser other than Chromium.
