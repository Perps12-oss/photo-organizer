# Photo Organizer — Remaining Work

Items not completed in the latest ultrawork session and why.

---

## T3 AI (#1–8, #35) — Blocked without full Ollama/vision stack

`ai_local.py` has Ollama scaffold only; `describe_image_local` returns `None`. Wiring gallery auto-tagging, semantic search, face/object detection, etc. requires:

- Local vision model (LLaVA or similar) integrated end-to-end
- Embedding index for semantic search (#8)
- AI tag source before embed-into-files (#35)

**Policy:** Local-first; no silent cloud upload. Document and implement when Ollama + model are validated on user hardware.

---

## T3 Integrations (#48–50)

Cloud storage (Drive/Dropbox/OneDrive), Plex/Jellyfin, and native Photos API import need external SDKs/API keys. `file_utils.py` already skips cloud placeholders gracefully.

---

## T2 deferred (moderate scope)

| # | Feature | Why deferred |
|---|---------|--------------|
| **2–3, 5–7** | Face/object/sentiment/doc AI | T3 model deps |
| **15** | Visual Hazel-style rule engine | Large UI; watcher enums exist |
| **16** | Full redo edge-case polish | Partial undo/redo works; needs targeted QA |
| **19** | Named organizer profiles | Needs profile storage + UI |
| **23** | Embedded map canvas | Map dialog + browser works |
| **25** | Ken Burns slideshow | Lightbox exists; animation scope |
| **27** | Pinch/gesture lightbox | Desktop Tk limits |
| **29** | RAW/HEIC via rawpy/pyheif | Optional deps + test matrix |
| **36** | Custom metadata fields | Schema design |
| **39–41** | PDF/A, doc tags, email sort | External pipelines |
| **42** | OCR on inbox arrival | Needs watcher hook + OCR perf |
| **43** | Charts (matplotlib) | Stats text dashboard done; charts optional |
| **46** | Full shortcut remapping UI | JSON + resolver stub done; no editor UI |

---

## Optional audit extras (not required)

- Merge `_scan_folder` metadata passes (`media_gallery.py`) — partial cache warm exists
- Further split `duplicate_view.py` — already extracted to `views/`

---

*See [PROGRESS.md](PROGRESS.md) for what was completed.*
