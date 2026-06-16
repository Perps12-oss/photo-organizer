# Design System V1 — Living Plan

Track progress here as we implement and iterate. **Branch:** `ui/design-system-v1` · **Base:** `master` · **First commit:** `13132eb`

## How to use this doc

| Symbol | Meaning |
|--------|---------|
| `[x]` | Done (shipped on branch) |
| `[ ]` | Not started |
| `[~]` | Partial — core done, polish or sub-version remains |
| **Phase X.Y** | Sub-version / variation under phase X (add rows as needed) |

**Variations rule:** Any design tweak, optional enhancement, or scope change gets a **Phase X.Y** line under the parent phase — either under *In progress* (current phase) or *Planned* (future phases). Do not create orphan tasks outside a phase.

**Status key:** `done` · `partial` · `planned` · `deferred`

---

## Phase gate (required after every phase)

Do **not** mark a phase complete or push until all of the following pass:

1. **Syntax** — `python -m py_compile` on touched modules (from `app/`):
   ```powershell
   cd app
   python -m py_compile theme.py design_system.py assets.py ui_components.py photo_organizer_enhanced.py
   python -m py_compile views/*.py settings_view.py media_gallery.py media_viewer.py video_player.py
   ```
2. **Lint** — fix IDE/linter diagnostics on changed files (Cursor: no errors on edited paths).
3. **Run** — app must start without traceback:
   ```powershell
   cd app
   python -c "from photo_organizer_enhanced import PhotoOrganizerApp; r=PhotoOrganizerApp(); r.update_idletasks(); r.destroy(); print('OK')"
   ```
   Optional: manual click-through of the phase’s screens.
4. **Plan** — tick checkboxes in this doc; add **Phase X.Y** rows for any variations.
5. **Commit & push** — one commit per landed phase (or agreed sub-phase); push `ui/design-system-v1`:
   ```powershell
   git add <phase files only>
   git commit -m "..."
   git push
   ```

**Rule:** If syntax, lint, or startup fails — fix first, then commit. Never push a broken branch at a phase boundary.

---

## Overall progress

| Phase | Name | Status | Notes |
|-------|------|--------|-------|
| 0 | Branch & assets | **done** | Branch pushed; fonts + icons committed |
| 1 | Token layer | **done** | `theme.py` V1 tokens + `init_fonts()` |
| 2 | Component library | **partial** | Core widgets in `design_system.py`; `ViewPage` unused widely |
| 3 | Shell integration | **done** | `ModernSidebar`, `StatusBar`, shell wiring |
| 4 | Find Duplicates (reference) | **partial** | Pre + post-scan V1 cards; 4.4 tip bar open |
| 5 | Roll out other views | **partial** | ElevatedCard + DS controls on all main views; gallery side panel open |
| 6 | Cleanup & verification | **partial** | Toast V1; hex clean; formal QA checklist open |

---

## Design philosophy (fixed for V1)

- **Not:** glassmorphism, blur, transparency tricks, neon overlays
- **Yes:** elevation, surface hierarchy, clean geometry, strong typography, controlled accents
- **Reference:** PowerToys / Linear / modern Windows utilities — not Dribbble fantasy

---

## Phase 0 — Branch and assets

**Status:** done · **Branch:** `ui/design-system-v1`

- [x] Create branch from `master`
- [x] `assets/fonts/` — Inter Regular + Bold
- [x] `assets/icons/` — PNG set (home, search, image, folder, inbox, settings, check, …)
- [x] `scripts/generate_icons.py` — regenerate icons
- [x] `app/assets.py` — `load_icon()`, `register_fonts()`
- [x] Push branch to `origin`

### Variations (Phase 0.x)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| 0.1 | Add more icon sizes / names as views need them | planned | e.g. `x`, `chevron`, `info` |
| 0.2 | Ship Inter license file in `assets/fonts/` | planned | Compliance nicety |
| 0.3 | CI step: run `generate_icons.py` + fail if dirty | deferred | Only if icon churn becomes frequent |

---

## Phase 1 — Token layer (`app/theme.py`)

**Status:** done

- [x] V1 color stack (`WINDOW_BG`, `SURFACE_BG`, `INPUT_BG`, `BORDER`, accents, semantic colors)
- [x] Spacing tokens (`CARD_PADDING`, `SECTION_GAP`, `CONTROL_GAP`, `CONTENT_MARGIN`)
- [x] Shape tokens (`CARD_RADIUS`, `INPUT_RADIUS`, `BTN_RADIUS`, `SIDEBAR_WIDTH`)
- [x] Typography via `init_fonts()` — Inter with Segoe UI fallback
- [x] Legacy aliases (`APP_*`) for gradual migration
- [x] Dark-only V1 for now (Light/System deferred)

### Variations (Phase 1.x)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| 1.1 | Full light palette + appearance mode mapping | planned | Settings dropdown stays; map to real light tokens |
| 1.2 | Remove legacy `APP_*` aliases after full migration | planned | Grep-driven cleanup |
| 1.3 | Accent override refreshes live widgets (not just globals) | planned | Today: mutates `theme` module only |
| 1.4 | High-DPI font/icon scale tokens | planned | 125% / 150% Windows scaling pass |

---

## Phase 2 — Component library (`app/design_system.py` + `app/ui_components.py`)

**Status:** partial

### Core layout

- [x] `PageHeader(title, subtitle)`
- [x] `ElevatedCard` (fake shadow + bordered surface)
- [~] `ViewPage` — implemented, **not adopted** across all views yet

### Controls

- [x] `PrimaryButton` / `SecondaryButton` / `GhostButton`
- [x] `DangerButton` variant
- [x] `LabeledEntry`
- [x] `StyledOptionMenu`
- [x] `StyledCheckBox`
- [x] `ModernSlider` (canvas track + glow thumb)
- [x] `SectionLabel` (numbered sections)

### Shell

- [x] `SidebarNavButton` — icon, accent strip, active tile
- [x] `ModernSidebar` — brand, 6 nav items, footer status
- [x] `StatusBar` — 28px, dot, version slot
- [x] `SettingsSection` → extends `ElevatedCard`

### Results / scan

- [x] `ResultsCard` — idle / success / error states
- [x] `ScanProgressCard` — integrated progress (replaces overlay)

### Variations (Phase 2.x)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| 2.1 | Adopt `ViewPage` wrapper on every main view | planned | Single content margin + header row |
| 2.2 | `FormRow` / `LabeledSliderRow` (label + slider + value) | planned | Reduce duplicate row layout code |
| 2.3 | `DangerButton` variant | done | Delete actions in duplicate view |
| 2.4 | Gradient primary button (Pillow PNG) | deferred | Spec optional; solid accent shipped |
| 2.5 | Lucide `check` PNG in `ResultsCard` (vs canvas draw) | done | 72px green badge |
| 2.6 | Toast styling aligned to V1 tokens | done | `CARD_RADIUS` + `PrimaryButton` action |

---

## Phase 3 — Shell integration (`app/photo_organizer_enhanced.py`)

**Status:** done

- [x] Root `fg_color` = `WINDOW_BG`
- [x] `ModernSidebar` replaces inline sidebar build
- [x] All 6 nav keys with icons
- [x] `set_sidebar_scanning()` wired from duplicate scan
- [x] `StatusBar` V1 styling
- [x] `init_fonts(self)` at startup
- [x] `AppStatusController` API unchanged

### Variations (Phase 3.x)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| 3.1 | Sidebar footer sync with `AppStatusController` message text | planned | Today: scanning boolean + short label |
| 3.2 | Status bar multi-zone (left / center / right job detail) | planned | Optional; single label today |
| 3.3 | Collapsible sidebar (icon-only mode) | deferred | Width jump; needs design pass |
| 3.4 | Uniform `CONTENT_MARGIN` via shared wrapper vs per-view padx | planned | Some views set margin locally |

---

## Phase 4 — Find Duplicates reference (`app/views/duplicate_view.py`)

**Status:** partial — **reference screen for the system**

### Target layout

```
┌ PageHeader ─────────────────────────────────────┐
├ Settings Card (left) │ Results Card (right)    │
│  1. Select Folder    │  Scan Results / Progress│
│  2. Scan Scope       │  Empty / Success / List │
│  3. Precision sliders│                         │
│  4. Advanced         │                         │
│  Start Scan          │                         │
└─────────────────────────────────────────────────┘
```

### Checklist

- [x] Pre-scan: 2-column grid (`ElevatedCard` + `ResultsCard`)
- [x] `ModernSlider` for image/video similarity
- [x] `StyledOptionMenu` / `StyledCheckBox` / `PrimaryButton`
- [x] `ScanProgressCard` in right column (not modal)
- [x] Remove `NeonScanHero`
- [x] `ResultsCard` for no-duplicates success state
- [x] Post-scan panel — summary, filters, list, gallery chrome on `ElevatedCard`
- [x] Success icon — Lucide `check` PNG at 72px
- [ ] Bottom tip bar / “Open Results Folder” row from mockups | planned → **4.4**

### Variations (Phase 4.x)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| 4.1 | Post-scan: restyle summary, filters, group list, gallery chrome with `ElevatedCard` | done | |
| 4.2 | Post-scan: action bar + recommendation panel token cleanup | done | Subset of 4.1 |
| 4.3 | Results success icon → Lucide `check` PNG at 72px | done | |
| 4.4 | Pre-scan footer: tip row + secondary actions (mockup) | planned | Optional UX parity |
| 4.5 | Scan stats row on results (Files / Time / Duplicates columns) | partial | Basic stats in `ResultsCard`; enrich layout |
| 4.6 | Animated success glow / sparkle | deferred | Spec skip for V1 |
| 4.7 | Recent folder chips → `GhostButton` style | done | |

---

## Phase 5 — Roll out to remaining views

**Status:** partial — token/header pass done; **full component migration incomplete**

| View | File | Status | Done | Remaining |
|------|------|--------|------|-----------|
| Home | `app/views/home_view.py` | partial | `PageHeader`, `ElevatedCard`, DS buttons | — |
| Settings | `app/settings_view.py` | partial | `PageHeader`, `ModernSlider`, styled menus/checkboxes | Minor raw controls if any remain |
| File Organizer | `app/views/sort_view.py` | partial | `PageHeader`, `ElevatedCard` paths/rules/preview/browser | Footer DS buttons optional |
| Inbox Watcher | `app/views/inbox_view.py` | partial | `PageHeader`, `ElevatedCard` columns, DS footer | Status card inner frame optional |
| Media Gallery | `app/media_gallery.py` | partial | `PageHeader`, toolbar/filters `ElevatedCard`, DS toolbar | Side panel + filter buttons depth |

### Per-view checklist (tick as completed)

**Home**

- [x] Phase 5 — baseline pass
- [ ] Phase 5.1 — align hero spacing to mockups if needed

**Settings**

- [x] Phase 5 — baseline pass
- [x] Phase 5.2 — replace remaining raw `CTkOptionMenu` / `CTkCheckBox` with styled variants

**Sort / Organizer**

- [x] Phase 5 — baseline pass
- [x] Phase 5.3 — elevate paths + rules + preview cards
- [x] Phase 5.4 — library browser panels → `ElevatedCard`

**Inbox**

- [x] Phase 5 — baseline pass
- [x] Phase 5.5 — elevate left/right columns; DS buttons in footer

**Media Gallery**

- [x] Phase 5 — baseline pass
- [~] Phase 5.6 — toolbar/header/filters pass; side panel + bulk UI remain

### Variations (Phase 5.x) — cross-cutting

| ID | Item | Status | Notes |
|----|------|--------|-------|
| 5.7 | Dialogs / lightbox / sidecar UI (`media_viewer.py`, dialogs) | planned | Token pass started on viewer |
| 5.8 | `photo_organizer_pro.py` / `hybrid.py` — out of scope unless requested | deferred | Enhanced app is canonical shell |
| 5.9 | Empty states → shared `EmptyState` or `ResultsCard` pattern | planned | Gallery + sort preview |

---

## Phase 6 — Cleanup and verification

**Status:** partial

- [x] Remove `NeonScanHero` and exports
- [~] Grep hardcoded hex — **clean on main views**; gallery/sidecar spots remain
- [~] Phase gate automation documented (see top of this doc)
- [ ] Manual smoke test — formal sign-off | **6.1**
- [ ] Remove dead neon constants from any remaining imports | **6.2**

### Phase gate log

| Phase | Syntax | Lint | App start | Committed | Pushed | Commit |
|-------|--------|------|-----------|-----------|--------|--------|
| 0–4 (+ partial 5–6) | pass | pass | pass | yes | yes | `13132eb` |
| Plan doc + gate workflow | pass | pass | pass | yes | yes | `60f374f` |
| 4.1–4.7 + 5.2–5.6 (partial) + 2.3/2.5/2.6 | pass | pass | pass | yes | yes | `7ca4656` |

### Smoke test checklist (Phase 6.1)

- [ ] Navigate all 6 views; sidebar active indicator correct
- [ ] Duplicate scan: pre-scan → progress card → results → post-scan groups
- [ ] Settings save / reset / open config folder
- [ ] Shortcuts Ctrl+1–5, Ctrl+,
- [ ] Inbox watcher start/stop UI
- [ ] Gallery browse + metadata (spot check)
- [ ] 125% / 150% display scaling (Windows)

### Variations (Phase 6.x)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| 6.2 | Delete unused neon token names if any linger | planned | |
| 6.3 | Lint rule or script: flag `#` colors outside `theme.py` / `design_system.py` | deferred | |
| 6.4 | Screenshot baseline / visual regression | deferred | Manual only for now |
| 6.5 | Merge `ui/design-system-v1` → `master` via PR | planned | After 6.1 sign-off |

---

## Constraints (unchanged)

- CustomTkinter: fake shadow frames + canvas — not GPU blur
- Icons: pre-rendered PNGs (no runtime SVG parser)
- Business logic, scan engine, i18n keys: **styling only** unless a variation explicitly says otherwise

---

## PR strategy

| PR | Phases | Status |
|----|--------|--------|
| PR 1 | 0–4 core + partial 5–6 | **shipped** (`13132eb`) |
| PR 2 | 4.1–4.3 post-scan + results polish | **shipped** |
| PR 3 | 5.3–5.6 remaining view depth | **partial** (5.6 side panel open) |
| PR 4 | 1.1 light mode + 6.1 QA sign-off | planned |

---

## Change log (plan doc)

| Date | Change |
|------|--------|
| 2026-06-14 | Initial living plan; marked work through `13132eb` as done/partial |
| 2026-06-14 | ULTRAWORK: Phase 4 post-scan, 5.2–5.6 partial, DangerButton, toast V1 |

---

## Adding a new variation

1. Pick the **parent phase** (0–6).
2. Add the next **Phase X.Y** row in that phase’s *Variations* table.
3. Set status: `planned` · `in progress` · `done` · `deferred`.
4. If it spans views, note affected files in *Notes*.
5. Tick the matching checkbox when shipped; link commit or PR in *Notes* if helpful.
