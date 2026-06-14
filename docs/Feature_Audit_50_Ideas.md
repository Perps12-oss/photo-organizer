# Feature Audit — 50 Ideas

Structured reference for prioritizing Photo Organizer enhancements. Each item maps to current code, gaps, dependencies, and a suggested tier.

**Relationship to other docs:** This audit complements [Photo_Organizer_Pro_Development_Roadmap.md](Photo_Organizer_Pro_Development_Roadmap.md). The roadmap describes phased architecture (SQLite, scoring, comparison viewer). This document inventories **specific product ideas** from competitive research and aligns them with **what already exists** in the Enhanced app (`photo_organizer_enhanced.py` and related modules). Where they overlap (e.g. pHash, scoring), this audit marks current status; the roadmap still guides *how* to scale those features.

**AI policy (future work):**
- **Primary:** Local models (Ollama + vision LLMs such as LLaVA) for tagging, rotation, and search embeddings.
- **Optional:** Cloud APIs only when the user configures API keys in Settings (off by default).
- **Never:** Silent upload of library content to third-party services.

**Tier legend:**
- **T1** — Quick win; builds on existing modules, minimal new deps.
- **T2** — Core DAM capability; moderate scope, often needs indexing or new UI surfaces.
- **T3** — Heavy / AI / integration; new services, models, or external APIs.

---

## AI and Smart Organization

| # | Feature | Status | Existing code | Gaps | Deps | Tier |
|---|---------|--------|---------------|------|------|------|
| 1 | Local AI auto-tagging | Partial | `ai_local.py` Ollama scaffold, Settings toggle | `describe_image_local` not wired to gallery | Ollama, LLaVA | T3 |
| 2 | Face detection and recognition | Not started | `photo_organizer_pro.py` has stub `detect_faces` (unused in Enhanced) | No face index, no person grouping UI | OpenCV dlib / insightface / local model | T3 |
| 3 | Object and scene recognition | Not started | — | No object/scene labels in metadata DB | Local CLIP or cloud vision (opt-in) | T3 |
| 4 | AI-powered auto-rotation | Partial | EXIF orientation in `media_viewer.py` (`load_oriented_image`) | No ML-based rotation for images missing EXIF | Local orientation model | T3 |
| 5 | Sentiment analysis on images | Not started | — | No mood/emotion metadata | Vision + expression model | T3 |
| 6 | AI-based video summarization | Not started | Video extensions in scan list only | No keyframe/GIF extraction | ffmpeg, optional local VLM | T3 |
| 7 | AI document classification | Not started | `organizer_engine.py` sorts docs by layout | No NLP categorization (Finance/Medical/Legal) | Tesseract OCR + local LLM | T3 |
| 8 | Semantic search | Not started | Gallery text search is filename/tag substring (`media_gallery.py`) | No embedding index or natural-language query | Local embeddings (CLIP) or opt-in API | T3 |

---

## Advanced Duplicate Detection

| # | Feature | Status | Existing code | Gaps | Deps | Tier |
|---|---------|--------|---------------|------|------|------|
| 9 | Similar image detection (pHash) | Done | `duplicate_utils.cluster_phash`, `find_similar_paths`, Gallery **Find similar** | — | imagehash, Pillow | T1 |
| 10 | Similar video detection | Done | `video_dupes.py`, tolerance slider + checkbox in Duplicate Finder | pHash frame + duration clustering with persisted tolerance | ffmpeg, ffprobe, imagehash | T2 |
| 11 | Similar document detection (textual) | Partial | `duplicate_utils.document_text_fingerprint`, scan-phase clustering | PDF text needs pypdf; tolerance tuning | pypdf / pdfminer | T2 |
| 12 | Audio fingerprinting | Partial | `audio_fingerprint.py`, duration/size bucket; chromaprint if pyacoustid | Exact-match buckets only without chromaprint | pyacoustid optional | T2 |
| 13 | Preview and selective cleanup | Done | Duplicate groups UI, per-file delete, Smart Best scoring | — | — | — |
| 14 | Advanced filtering in duplicates | Done | `duplicate_utils.filter_duplicate_groups`, Min/Max KB in DuplicateView | — | — | T1 |

---

## Automation and File Management

| # | Feature | Status | Existing code | Gaps | Deps | Tier |
|---|---------|--------|---------------|------|------|------|
| 15 | Advanced rule-based file watcher | Partial | `inbox_watcher.py`, `organizer_engine.py` | No visual rule engine (Hazel-style); rules are layout/scope enums | — | T2 |
| 16 | Complete undo/redo system | Partial | `operation_journal.py`, Ctrl+Z/Ctrl+Y, quarantine delete undo | Redo for edge cases; trash in `%APPDATA%\PhotoOrganizer\quarantine` | — | T2 |
| 17 | File snapshot and rollback | Partial | `snapshots.py`, `create_folder_snapshot`, Settings restore UI | Full-folder wizard UI not added | — | T2 |
| 18 | Dynamic placeholders in auto-organize | Done | `organizer_engine.resolve_template`, template fields in File Organizer | `{artist}` needs audio metadata source | — | T1 |
| 19 | Profile-based organization | Not started | Single watcher config in `watcher_settings.json` | No named profiles (Work/Personal) | — | T2 |
| 20 | Batch processing with async operations | Partial | Parallel hashing, async organizer preview thread | Execute already threaded; very large previews may still lag | — | T1 |
| 21 | Intelligent file conflict resolution | Done | `ConflictPolicy` in `organizer_engine.py`, UI in SortView | Rename path in metadata_tools still suffix-only | — | T1 |

---

## Media Gallery and Viewing

| # | Feature | Status | Existing code | Gaps | Deps | Tier |
|---|---------|--------|---------------|------|------|------|
| 22 | Google Takeout support | Partial | `takeout_import.py`, album discovery/import, gallery buttons | Bulk album picker is name-based | Google Takeout format | T2 |
| 23 | GPS map view | Partial | `gps_utils.py`, Map view dialog, per-photo Map button | No embedded map canvas | OpenStreetMap browser | T2 |
| 24 | Dynamic sorting and filtering in gallery | Done | Tag, rating, search, sort in `media_gallery.py` | No date-range or file-size filters | — | T1 |
| 25 | Slideshow with Ken Burns effect | Not started | Lightbox navigation in `media_viewer.py` | No slideshow mode or pan/zoom animation | — | T2 |
| 26 | Side-by-side comparison | Partial | `SideBySideCompareDialog`, Gallery Compare button | Duplicate review compare unchanged | — | T1 |
| 27 | Advanced lightbox features | Partial | `LightboxViewer` in `media_viewer.py`, F fullscreen shortcut | No pinch-to-zoom, gesture UI, auto-hide chrome | — | T2 |
| 28 | Video playback in lightbox | Partial | `video_player.py`, OpenCV inline player in lightbox + embedded Play | Requires opencv-python; scrub/speed in lightbox | opencv-python | T2 |
| 29 | RAW and HEIC formats | Partial | `.heic` in extensions; Pillow load paths | No rawpy; HEIC may fail without pyheif | rawpy, pyheif | T2 |
| 30 | Extract video thumbnails | Done | `video_thumbs.py`, `list_gallery_media`, gallery grid + embedded/lightbox preview | Inline video playback still optional | ffmpeg | T1 |

---

## Metadata and Organization

| # | Feature | Status | Existing code | Gaps | Deps | Tier |
|---|---------|--------|---------------|------|------|------|
| 31 | Advanced EXIF metadata editing | Done | `metadata_tools.py` read/write; gallery panel; auto-save in `app_settings.py` | Batch edit limited to rename plan | piexif, Pillow | — |
| 32 | XMP sidecar support | Done | `metadata_tools.py` parse/merge; `SidecarMappingDialog`, `SidecarMergeDialog` | Write XMP sidecars optional future | — | — |
| 33 | Bulk metadata imputation | Done | `AutodetectWizardDialog` in `media_gallery.py`, `batch_autodetect_plan` | Rating imputation not in wizard | — | T1 |
| 34 | Smart playlists based on rules | Partial | `smart_playlists.py`, date_from/date_to fields, gallery date filter | Playlist UI for dates is manual entry | — | T2 |
| 35 | Embed AI tags into files | Not started | IPTC/EXIF write exists | Needs AI tag source first | Same as #1 | T3 |
| 36 | Custom metadata fields and templates | Not started | Fixed fields in `ImageMetadata` | No user-defined fields or templates | — | T2 |
| 37 | Export metadata as CSV/JSON | Done | `export_metadata_csv/json` in `metadata_tools.py`, gallery Export buttons | Export all-folder vs filtered only (filtered) | — | T1 |

---

## Document Handling

| # | Feature | Status | Existing code | Gaps | Deps | Tier |
|---|---------|--------|---------------|------|------|------|
| 38 | Full-text search with OCR indexing | Partial | `ocr_index.py`, auto OCR on folder load toggle in Settings | Index build still manual trigger optional | Tesseract, pypdf/pdfminer | T2 |
| 39 | Convert to searchable PDF/A | Not started | — | No PDF/A pipeline | ocrmypdf | T3 |
| 40 | Document tagging and correspondence | Not started | Image tagging only | No document-specific metadata model | — | T2 |
| 41 | Email attachment sorting | Not started | — | No .eml/.msg parser in watcher | extract-msg, eml parser | T3 |
| 42 | Receive and sort scanned documents | Partial | Inbox watcher + OCR gap | Watcher moves files; no OCR/tag on arrival | Tesseract + watcher hook | T2 |

---

## User Experience and Personalization

| # | Feature | Status | Existing code | Gaps | Deps | Tier |
|---|---------|--------|---------------|------|------|------|
| 43 | Color palette extraction from image | Not started | Theme tokens in `theme.py` | No dynamic accent from photo | Pillow quantize / colorthief | T2 |
| 44 | Dynamic theme system with live preview | Partial | `APPEARANCE_MODES`, Settings theme picker, custom accent hex | No full theme editor | — | T1 |
| 45 | Interactive dashboard with statistics | Partial | Home view stats from `media_index` + watcher | No charts yet | matplotlib optional | T2 |
| 46 | Customizable keyboard shortcuts | Partial | `keyboard_bindings.py`, `keyboard_shortcuts` in settings JSON | No remapping UI | — | T2 |
| 47 | Multi-language support | Partial | `i18n/en.json`, `i18n.t()` stub | UI strings not extracted | gettext / JSON locales | T2 |

---

## Cloud and Integration

| # | Feature | Status | Existing code | Gaps | Deps | Tier |
|---|---------|--------|---------------|------|------|------|
| 48 | Cloud storage integration | Not started | `file_utils.py` skips cloud placeholders (Yandex.Disk) | No Drive/Dropbox/OneDrive mount or API | rclone / vendor SDKs | T3 |
| 49 | Plex/Jellyfin integration | Not started | — | No library push or server API | Jellyfin/Plex API | T3 |
| 50 | Import from Cloud/Apple Photos | Not started | Sidecar JSON merge | No Photos/Google API import | Google Photos API, Apple export | T3 |

---

## Summary by status

| Status | Count |
|--------|-------|
| Done | 12+ |
| Partial | 14+ |
| Not started | 24+ |

## T2.6 sprint completed

- **#16** Quarantine delete + **Ctrl+Z** undo / **Ctrl+Y** redo (`operation_journal.py`)
- **#17** Snapshots before delete + restore from **Settings → Safety & performance**
- **#28** Video playback in lightbox (Space play/pause, scrub, speed) via OpenCV
- **SQLite media index** (`media_index.py`) — gallery load uses index when enabled in Settings

## Suggested next tiers (when moving beyond foundation)

**T2 remaining (core DAM):**
- #11 similar document detection · #12 audio fingerprinting
- #22 Takeout album import · #26 gallery side-by-side comparison
- #16/#17 polish: redo edge cases, full-folder snapshot wizard

**T3 AI and integrations (local-first):**
- #1–8 AI organization stack (Ollama-first)
- #48–50 cloud and media server integrations

---

## Foundation completed (this phase)

- **Startup config validation:** `config_bootstrap.py` validates `app_settings.json` and `watcher_settings.json` before UI load; corrupt files backed up; `schema_version: 1` on save.
- **Settings UI:** "Open config folder" in Settings; startup dialog for warnings/errors.

*Last updated: aligns with Config Validation + Feature Audit Foundation implementation.*
