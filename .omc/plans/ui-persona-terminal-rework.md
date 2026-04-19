# UI Rework — Persona Terminal Shell + Component Refactor

**Status:** Draft · awaiting approval
**Owner:** @tan
**Created:** 2026-04-19
**Working dir:** `/home/tan/Documents/market_sentiment_analysis/ui/`
**Branch suggestion:** `ui/persona-terminal-rework`

---

## Requirements Summary

Rework the UI of the Next.js 14 dashboard at `ui/` from a scrappy-but-tokenized layout into a **Linear/Vercel-style enterprise quant terminal**. Scope is **shell + component refactor** — touch the chrome and visual primitives, do **not** touch data models, context providers, or the deck.gl choropleth map's rendering internals.

**Identity decisions (locked):**
| Element | Decision |
|---|---|
| Direction | Linear/Vercel dark dashboard (sidebar nav + Cards + ⌘K) |
| Product name | `Persona Terminal` *(provisional — isolated to 2 places, easy to rename)* |
| Body/UI font | Geist Sans via `next/font` (self-hosted) |
| Numeric/mono font | Geist Mono via `next/font` |
| Primary accent | Existing electric blue `#3b82f6` — no new brand color |
| Amber | Caveats only (existing rule preserved) |
| Theme | Dark only (no light mode) |

**Demo context:** Hook'em Hacks 2026 finance track, pivoted 2026-04-18. Work must be safely shippable at every phase boundary — each phase ends with a green `build` and a working dev server.

## Current-State Facts (verified via explore agent + direct read)

- Next.js 14.2.5, App Router, TypeScript strict mode, path alias `@/* → ./src/*`
- Tailwind 3.4.7 + `tailwindcss-animate` installed
- shadcn/ui already configured (`ui/components.json`); `src/components/ui/` contains `badge.tsx`, `switch.tsx`, `tabs.tsx`, `select.tsx`, `table.tsx`, `scroll-area.tsx`
- Radix primitives used: scroll-area, select, slot, switch, tabs
- Design-token system in `ui/src/app/globals.css:12-69` (surface, fg, accent, pipeline, political, sentiment palettes)
- Tailwind config extends those tokens (`ui/tailwind.config.ts:12-83`)
- Main layout at `ui/src/app/page.tsx:58-166` uses flex: header + (aside EventList | main Tabs | aside SidePanels)
- **Not yet installed:** `geist`, `lucide-react`, `sonner`
- **Not yet added via shadcn:** `card`, `separator`, `hover-card`, `tooltip`, `command`, `skeleton`, `button`

## Acceptance Criteria (testable)

### Shell

1. `ui/src/app/layout.tsx` imports `GeistSans` and `GeistMono` from the `geist` package and applies their `.variable` classes on `<html>`.
2. `ui/src/app/globals.css:66-68` prepends `var(--font-geist-sans)` and `var(--font-geist-mono)` to `--font-sans` / `--font-mono`. Fallback chain preserved.
3. `ui/src/app/page.tsx` top-level layout is `<Sidebar> | <MainColumn>` — the existing top `<header>` masthead is removed; `<TabsList>` is no longer in the main column (nav moves to the sidebar).
4. New file `ui/src/components/shell/Sidebar.tsx` exists, renders wordmark (`Persona Terminal` + inline SVG mark, no emoji), three nav items with Lucide icons (`Map`, `BarChart2`, `Zap` or equivalent) tied to `activeTab`, a `Separator`, the existing `<EventList />` under an "Events" micro-label inside a `ScrollArea`, and a footer row with `⌘K` hint + `v0.1`. Width: `w-60`.
5. New file `ui/src/components/shell/StatusBar.tsx` exists, renders a 28px bottom strip (`bg-surface-panel border-t border-border`) showing: persona count · ε (Deffuant) · current IC · `OK` status dot · `v0.1`. All numeric values use `font-mono`.
6. New file `ui/src/components/shell/CommandPalette.tsx` exists, uses shadcn `Command` inside a `Dialog`, opens on ⌘K / Ctrl-K via a global keyboard listener (with `preventDefault`), groups entries as `Events` (searchable by headline + ticker) and `Navigation` (Map / Ablations / Simulate). Enter on an event calls the event-context setter; Enter on nav switches `activeTab`.
7. The `EventBanner` component becomes a thin event-detail bar pinned above the main content area (no longer inside a global header). Ticker is larger/bolder (`text-base font-semibold`); headline on its own line; metadata on a third line using `·` dividers. Mono font on `−3.2` tone and timestamp. The tone badge gets a `HoverCard` showing the raw GDELT tone value + 1-sentence explanation.

### Components

8. Four side panels (`IncomePanel`, `PoliticalPanel`, `AgePanel`, `GeographyPanel`) each wrap in `<Card>` with `<CardHeader>` (title + info-icon → `HoverCard` explainer) and `<CardContent>` (existing bar rows unchanged).
9. Ablation view inside `TabsContent value="ablation"` (`ui/src/app/page.tsx:129-157`) has each `<section>` wrapped in a `<Card>` (`Primary Ablation Table`, `Pearson IC by Pipeline`, `Supplementary Sharpe`). The `AblationTable` column headers get `<Tooltip>` explainers for `IC`, `t-stat`, `Sharpe`. Numeric cells use `font-mono`.
10. All `"Loading …"` plain-text nodes are replaced with shadcn `<Skeleton>` elements of appropriate shape (verified by grep: `rg -i "loading" ui/src/ --type tsx` returns only comments and props).
11. `SimulateTab` / `SimulateForm` submission success and error paths fire `sonner` toasts via `toast.success(...)` / `toast.error(...)`. Inline error/status text is removed. A `<Toaster />` is mounted once in `ui/src/app/layout.tsx`.
12. `EventList` rows use a tokenized active state (`bg-surface-active`) and keyboard navigation (arrow up/down selects neighbor, `Enter` activates).
13. **Zero** occurrences of hardcoded Tailwind color classes in `.tsx` files under `ui/src/components/` — verified by `rg '\b(text|bg|border)-(red|green|blue|amber|yellow|indigo|purple|orange|rose)-[0-9]{3}\b' ui/src/components/` returning no matches. Each occurrence is replaced with the equivalent tokenized class (e.g. `text-green-400` → `text-sentiment-pos` or `text-accent-green`; the correct target is picked per usage — `sentiment-*` for sentiment direction, `accent-*` for UI accent).

### Non-functional

14. No behavior change: data loading, map rendering, simulation logic unchanged. `ui/src/context/`, `ui/src/lib/`, `ui/src/types/` **untouched**.
15. `ChoroplethMap.tsx` internals (deck.gl layer configs, color arrays, pitch, zoom, projection) **untouched** — only its container may change.
16. `cd ui && npm run lint` → passes.
17. `cd ui && npm run build` → 0 type errors, 0 new warnings.
18. Manual smoke test (dev server) passes the checklist in the *Verification* section below.

## Implementation Phases

Each phase ends with a runnable app and a commit. If time runs out, any completed phase is shippable.

### Phase 0 — Setup (≈15 min)

- `git checkout -b ui/persona-terminal-rework`
- From `ui/`, install runtime deps:
  - `npm install geist lucide-react sonner`
- Add shadcn primitives (from `ui/`):
  - `npx shadcn@latest add card separator hover-card tooltip command skeleton button`
  - (sonner is installed directly; `Toaster` is imported from `sonner`)
- Commit: `chore(ui): install shadcn primitives, geist, lucide-react, sonner`

### Phase 1 — Typography (≈30 min)

- Edit `ui/src/app/layout.tsx`:
  - `import { GeistSans } from 'geist/font/sans'` and `import { GeistMono } from 'geist/font/mono'`
  - Apply `${GeistSans.variable} ${GeistMono.variable}` to the `<html>` className
- Edit `ui/src/app/globals.css:65-68`:
  - `--font-sans: var(--font-geist-sans), ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;`
  - `--font-mono: var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;`
- Smoke: `npm run dev`, inspect element → verify Geist loaded, verify no regression
- Commit: `feat(ui): load Geist Sans + Geist Mono via next/font`

### Phase 2 — Shell (≈90 min)

**Create `ui/src/components/shell/Sidebar.tsx`:**

```tsx
// pseudocode outline — final code should use existing hooks/context
<aside className="w-60 flex-none border-r border-border bg-surface-panel flex flex-col">
  <div className="px-4 py-4 flex items-center gap-2">
    <DiamondMark className="size-4 text-accent-blue" /> {/* inline SVG */}
    <span className="text-sm font-semibold tracking-tight">Persona Terminal</span>
  </div>
  <Separator />
  <nav className="px-2 py-2 space-y-0.5">
    {items.map(item => (
      <button
        className={cn(
          "w-full flex items-center gap-2 px-2 py-1.5 rounded text-sm",
          active === item.id ? "bg-surface-active text-fg" : "text-fg-dim hover:bg-surface-hover"
        )}
        onClick={() => onSelect(item.id)}
      >
        <item.Icon className="size-4" />
        {item.label}
      </button>
    ))}
  </nav>
  <Separator />
  <div className="px-3 pt-3 pb-1 u-label">Events</div>
  <ScrollArea className="flex-1"><EventList /></ScrollArea>
  <Separator />
  <div className="px-3 py-2 flex items-center justify-between text-xs text-fg-faint">
    <span>⌘K</span>
    <span>v0.1</span>
  </div>
</aside>
```

**Create `ui/src/components/shell/StatusBar.tsx`:**

```tsx
<div className="flex-none h-7 border-t border-border bg-surface-panel
                flex items-center justify-between px-4 text-xs text-fg-dim">
  <div className="flex items-center gap-4">
    <span><span className="font-mono">{personaCount.toLocaleString()}</span> personas</span>
    <span>ε <span className="font-mono">{epsilon.toFixed(2)}</span></span>
    <span>IC <span className="font-mono">{ic.toFixed(3)}</span></span>
  </div>
  <div className="flex items-center gap-2">
    <span className="size-1.5 rounded-full bg-accent-green" aria-hidden />
    <span>OK</span>
    <span className="text-fg-faint">· v0.1</span>
  </div>
</div>
```

**Create `ui/src/components/shell/CommandPalette.tsx`:**

- Uses `<CommandDialog>` (shadcn pattern)
- Opens on ⌘K / Ctrl-K via `useEffect` attaching a `keydown` listener to `window`; guards with `e.preventDefault()`
- Groups:
  - `Navigation` — 3 items, sets `activeTab`
  - `Events` — map `events` from context, search by `headline_text` + `ticker`, Enter calls `setCurrentEvent`

**Edit `ui/src/app/page.tsx`:**

- Replace the root `<div className="flex flex-col h-screen">` with:
  ```
  <div className="flex h-screen bg-surface">
    <Sidebar activeTab={...} onSelect={...} />
    <div className="flex-1 flex flex-col min-w-0">
      <EventBanner />
      <Tabs value={activeTab}>
        {/* existing TabsContent blocks, no TabsList */}
      </Tabs>
      <StatusBar personaCount={...} epsilon={0.3} ic={...} />
    </div>
    <CommandPalette />
  </div>
  ```
- Remove the `<header>` masthead and the `<TabsList>` / `<aside w-64 EventList>` (EventList moves into Sidebar).
- Keep the right-side `<aside>` with side panels for now (refactored in Phase 4).
- Keep the map-tab `Dynamics` Switch — relocate it to the top-right of the Map `<TabsContent>` (inline with map header).

- Commit: `feat(ui): add sidebar shell, status bar, command palette`

### Phase 3 — EventBanner refresh (≈30 min)

- Edit `ui/src/components/EventBanner.tsx`:
  - Restructure to three vertical lines inside a horizontal wrapper:
    - Line 1: Ticker (large, bold, `text-base font-semibold`)
    - Line 2: Headline (`text-sm text-fg-muted leading-snug`)
    - Line 3: metadata `· ` separated — `source · mm-dd HH:MM TZ · ToneBadge (HoverCard: GDELT raw + explanation) · SENTINEL if set`
  - Numeric tone and timestamp wrapped in `<span className="font-mono">`
  - `HoverCard` wraps the tone `Badge`; content: *"GDELT tone = <raw float>. Calculated as positive words − negative words per 1000, scaled ±10."*
- Commit: `refactor(ui): tighten EventBanner layout with HoverCard tone explainer`

### Phase 4 — Side panels → Cards (≈60 min)

- For each of `IncomePanel.tsx`, `PoliticalPanel.tsx`, `AgePanel.tsx`, `GeographyPanel.tsx` in `ui/src/components/SidePanels/`:
  - Wrap root return in:
    ```tsx
    <Card>
      <CardHeader className="py-2 px-3 flex-row items-center justify-between space-y-0">
        <CardTitle className="text-xs font-semibold text-fg-muted">{title}</CardTitle>
        <HoverCard>
          <HoverCardTrigger><Info className="size-3.5 text-fg-faint" /></HoverCardTrigger>
          <HoverCardContent className="text-xs">{explainer}</HoverCardContent>
        </HoverCard>
      </CardHeader>
      <CardContent className="py-2 px-3">{/* existing bar rows */}</CardContent>
    </Card>
    ```
  - Replace every hardcoded `text-green-400` / `text-red-400` inside with `text-sentiment-pos` / `text-sentiment-neg`.
- Edit `ui/src/app/page.tsx` right aside:
  - Change aside container to `space-y-2 p-2`.
  - Remove any manual borders between panels (Cards handle separation).
- Commit: `refactor(ui): wrap side panels in Card + HoverCard explainers`

### Phase 5 — Ablation → Cards + Tooltips (≈45 min)

- Edit `ui/src/app/page.tsx` `TabsContent value="ablation"` (lines ~129-157):
  - Wrap each existing `<section>` in `<Card>` with `<CardHeader>/<CardTitle>/<CardContent>`. Card titles:
    - "Primary Ablation Table — IC and Panel t-stat"
    - "Pearson IC by Pipeline"
    - "Supplementary Sharpe"
- Edit `ui/src/components/AblationTable.tsx`:
  - Column headers for `IC`, `t-stat`, `Sharpe` wrapped in `<Tooltip>` with 1-sentence metric definitions.
  - Add `font-mono` to numeric `<TableCell>`s.
- Edit `ui/src/components/AblationChart.tsx`:
  - Any text labels rendered inside the SVG that show IC values → `font-family: var(--font-mono)` (via className on the `<text>` or via `style`).
- Commit: `refactor(ui): ablation view uses Cards with metric tooltips`

### Phase 6 — Skeletons + Sonner (≈30 min)

- Grep `rg -n "Loading" ui/src/ --glob '*.tsx'` → every plain-text loading state replaced with a `<Skeleton>` of roughly the right shape.
  - The ablation loading fallback at `ui/src/app/page.tsx:151-153` becomes three stacked `<Skeleton className="h-32 w-full" />` inside a `space-y-3` wrapper.
- Edit `ui/src/app/layout.tsx`:
  - `import { Toaster } from 'sonner'`
  - Add `<Toaster position="top-right" theme="dark" />` inside the body next to `{children}`.
- Edit `ui/src/components/SimulateTab.tsx` and `ui/src/components/SimulateForm.tsx`:
  - On success: `toast.success(\`Simulated ${ticker} — ${n.toLocaleString()} personas reacted\`)`
  - On error: `toast.error(message)`
  - Remove any inline error string render paths; keep pending state (button disabled + `<Skeleton>` result preview).
- Commit: `refactor(ui): Skeleton loaders + Sonner toasts for simulate`

### Phase 7 — Token hygiene sweep (≈20 min)

- Run: `rg '\b(text|bg|border)-(red|green|blue|amber|yellow|indigo|purple|orange|rose)-[0-9]{3}\b' ui/src/components/`
- For each match, replace with the tokenized class:
  - Sentiment direction (score colors) → `*-sentiment-{pos,mid,neg}`
  - Party identity → `*-political-{d,r,i}`
  - Pipeline identity → `*-pipeline-{lm,finbert,zeroshot,persona,graph}`
  - General UI accent → `*-accent-{blue,green,red,amber}`
- Re-run the grep → must return zero matches.
- Commit: `chore(ui): sweep hardcoded Tailwind colors to design tokens`

### Phase 8 — Verification + screenshot (≈20 min)

- Run lint/build/dev (see *Verification*).
- Take before/after screenshots for the PR description (Map tab, Ablation tab, ⌘K open).
- No commit needed if nothing changed.

## Verification Steps

Run in order. Each step must pass before the next.

1. **Clean install:** `cd ui && npm install` → no errors, no peer-dep warnings on the newly added packages.
2. **Lint:** `cd ui && npm run lint` → exits 0.
3. **Build:** `cd ui && npm run build` → exits 0, 0 type errors, no new warnings vs. baseline.
4. **Token sweep check:** `rg '\b(text|bg|border)-(red|green|blue|amber|yellow|indigo|purple|orange|rose)-[0-9]{3}\b' ui/src/components/` → **zero** matches.
5. **Non-goal check:** `git diff --stat main -- ui/src/context ui/src/lib ui/src/types` → **empty**.
6. **Map-untouched check:** `git diff --stat main -- ui/src/components/ChoroplethMap.tsx` → lines changed ≤ 5 (only container-shape tweaks, no layer/color/projection edits). If > 5, re-review.
7. **Dev smoke:** `cd ui && npm run dev`, hit `http://localhost:3000` and walk:
   - [ ] Geist Sans visible in headings; Geist Mono visible in `−3.2`, `0.142`, timestamps
   - [ ] Sidebar renders with wordmark, 3 nav items, Events list, ⌘K hint
   - [ ] Click each nav item — correct tab loads
   - [ ] Press ⌘K — Command palette opens
   - [ ] Type a ticker fragment → event appears → Enter selects → EventBanner updates
   - [ ] Type a nav name → Enter → tab switches
   - [ ] Status bar at bottom shows live persona count, ε, IC, OK dot
   - [ ] EventBanner: ticker bold on line 1, headline line 2, metadata line 3, tone HoverCard works on hover
   - [ ] Map tab: choropleth renders identically (visually unchanged); Dynamics switch still works
   - [ ] Side panels: all 4 in Cards, info icon shows HoverCard on hover
   - [ ] Ablation tab: 3 Cards, tooltips on column headers (`IC`, `t-stat`, `Sharpe`)
   - [ ] Simulate tab: submit → Sonner toast top-right
   - [ ] While ablation data loads first-time: Skeleton placeholders (not plain text)
8. **Keyboard nav:** in sidebar event list, arrow keys navigate; Enter selects.

## Risks & Mitigations

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| 1 | Geist font fails to load | Low | Medium | `next/font` self-hosts; CSS var fallback chain preserves system stack. Test prod build. |
| 2 | Choropleth map regresses | Low | **High** — it's the demo centerpiece | Do not touch `ChoroplethMap.tsx` internals. Verify item #6 under Verification after every phase. |
| 3 | ⌘K conflicts with browser shortcut | Low | Low | `e.preventDefault()` in global handler; accept browser ⌘F still works. |
| 4 | Shadcn install version conflicts | Low | Medium | `components.json` already exists, so `npx shadcn@latest add` will respect it. Review `package.json` diff before commit. |
| 5 | Token sweep hits `sentiment-mid` yellow → no exact token | Low | Low | Existing `--sentiment-mid` covers it; if a remaining hardcoded yellow doesn't map, flag in PR. |
| 6 | Sidebar breaks narrow viewport during demo | Medium | Low (demo on laptop) | Out of scope; if needed, add `@media (max-width: 900px)` collapse in a follow-up. |
| 7 | Time overrun | Medium | Medium | Phase 2 (shell) is the demo-safe checkpoint; phases 3-7 ship incrementally. Each phase has its own commit, so cut-line is any phase boundary. |
| 8 | "Persona Terminal" name rejected | Low | Low | Name lives in 2 places (`Sidebar.tsx` wordmark + `<title>` in `layout.tsx`). Rename is a 2-line diff. |
| 9 | Command palette `Dialog` captures focus badly | Low | Low | Follow shadcn's `CommandDialog` pattern verbatim; it handles focus trap correctly. |
| 10 | Sonner theme doesn't match dark palette | Low | Low | Pass `theme="dark"` and `className` override to match `--surface-panel`. |

## Non-Goals (explicit)

- No touching `ui/src/context/EventContext.tsx`
- No touching `ui/src/lib/data-loader.ts`
- No touching `ui/src/types/`
- No modifying deck.gl / maplibre color arrays, pitch, zoom, or projection inside `ChoroplethMap.tsx`
- No changes to `AblationChart.tsx` SVG plot logic (only font-family on text elements)
- No light mode / theme switcher
- No mobile-responsive layout
- No new animations beyond what shadcn components provide out of the box
- No new routes or pages
- No file renames or moves outside of new `ui/src/components/shell/` additions
- No changes to the Parquet/JSON data files or loading pipeline

## Out-of-Scope Follow-ups (noted, not done)

- Mobile responsive collapse (`<900px`)
- Keyboard shortcut hints overlay (`?` key)
- Light mode theme
- Per-event detail dialog / drawer
- `react-query`-style data-fetching refactor

## File Change Inventory

**New files (3):**
- `ui/src/components/shell/Sidebar.tsx`
- `ui/src/components/shell/StatusBar.tsx`
- `ui/src/components/shell/CommandPalette.tsx`

**New shadcn primitives (7):**
- `ui/src/components/ui/card.tsx`
- `ui/src/components/ui/separator.tsx`
- `ui/src/components/ui/hover-card.tsx`
- `ui/src/components/ui/tooltip.tsx`
- `ui/src/components/ui/command.tsx`
- `ui/src/components/ui/skeleton.tsx`
- `ui/src/components/ui/button.tsx`

**Edited files (≈10):**
- `ui/src/app/layout.tsx` (fonts + Toaster)
- `ui/src/app/globals.css` (font-var prepend)
- `ui/src/app/page.tsx` (shell swap)
- `ui/src/components/EventBanner.tsx` (layout refresh + HoverCard)
- `ui/src/components/EventList.tsx` (keyboard nav + tokenized active)
- `ui/src/components/AblationTable.tsx` (tooltip headers + mono cells)
- `ui/src/components/AblationChart.tsx` (mono font on text only)
- `ui/src/components/SimulateTab.tsx` (Sonner)
- `ui/src/components/SimulateForm.tsx` (Sonner)
- `ui/src/components/SidePanels/*.tsx` (Card wrap + token sweep)

**Unchanged (enforced):**
- `ui/src/context/**`
- `ui/src/lib/**`
- `ui/src/types/**`
- `ui/src/components/ChoroplethMap.tsx` (save for container className tweaks)
- `ui/src/components/BivariateLegend.tsx`, `PhaseIndicator.tsx` (unless they contain hardcoded colors caught by the sweep)

## Commit Plan

1. `chore(ui): install shadcn primitives, geist, lucide-react, sonner`
2. `feat(ui): load Geist Sans + Geist Mono via next/font`
3. `feat(ui): add sidebar shell, status bar, command palette`
4. `refactor(ui): tighten EventBanner with HoverCard tone explainer`
5. `refactor(ui): wrap side panels in Card + HoverCard`
6. `refactor(ui): ablation view uses Cards with metric tooltips`
7. `refactor(ui): Skeleton loaders + Sonner toasts for simulate`
8. `chore(ui): sweep hardcoded Tailwind colors to design tokens`

Each commit leaves the app runnable. Demo cut-line is any commit boundary.

## Open Questions for User

1. **Product name** — `Persona Terminal` is provisional. Alternatives if you want: `Sentiment Desk`, `Persona Lens`, `Market Persona`, or keep current `LLM Persona Sentiment Simulator`. Confirm or override before Phase 2.
keep current
2. **Sidebar mark icon** — I'll draw an inline 16px SVG (e.g. a diamond or stacked-square mark). If you have a preference (hexagon, abstract "P", etc.), say so.
no preference
3. **Nav order / labels** — default: `Sentiment Map` → `Ablations` → `Simulate`. Any reordering or renaming?
can ablation be name something better for easier understanding
4. **Status bar content** — default: personas · ε · IC · OK · v0.1. Add anything? (e.g. data-freshness timestamp, last-sim time.)
no
