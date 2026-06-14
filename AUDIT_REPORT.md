# Photo Organizer — Comprehensive Audit Report

**Audit Date:** June 2025  
**Scope:** `Photo-Organizer/app/*.py` + `requirements.txt`  
**Files Audited:** 29 Python modules (~8,000+ lines)  
**Tools:** `py_compile`, AST analysis, manual code review, import mapping

---

## 1. Executive Summary

| Category | Severity | Count |
|----------|----------|-------|
| **Runtime Bugs / Syntax Errors** | High | 4 |
| **Dependency Errors** | Medium | 4 |
| **Performance Bottlenecks** | Medium | 6 |
| **Code Quality Issues** | Low | 10 |

**Overall Health:** The codebase is functional and well-structured in places, but has **two guaranteed runtime crashes**, **missing pip dependencies**, and **several O(n²) / disk-I/O bottlenecks** that will degrade performance on large photo libraries (10k+ files).

---

## 2. Syntax Errors & Runtime Bugs (CRITICAL)

### 2.1 `NameError` in `_on_more_autoselect` — `photo_organizer_enhanced.py` (~line 1762)
**Severity:** 🔴 **CRITICAL — Runtime Crash**

```python
def _on_more_autoselect(self, choice: str):
    self.more_select_var.set("More…")
    if choice == "Select all":
        self.smart_select("all")
    elif choice == "Clear all":
        self.smart_select("clear")

    for widget in self.gallery_frame.winfo_children():
        widget.destroy()
    self.gallery_grid = None
    self.gallery_empty = EmptyState(
        self.gallery_frame, icon=icon, title=title, subtitle=subtitle,
        action_text=action_text, action=action,   # ← UNDEFINED NAMES
    )
    self.gallery_empty.pack(expand=True, pady=80)
```

**Impact:** Opening the "More…" dropdown in the duplicate review gallery and selecting any option will crash with `NameError: name 'icon' is not defined`.

**Fix:** Remove the widget-destruction block or replace it with a proper `self._show_gallery_empty(...)` call with literal arguments.

---

### 2.2 Missing `_show_gallery_empty` method — `photo_organizer_enhanced.py` (~line 2427)
**Severity:** 🔴 **CRITICAL — Runtime Crash**

```python
self._show_gallery_empty(
    icon="✓",
    title="No duplicates found",
    subtitle=f"Scanned {total_count:,} files with no duplicate groups.",
)
```

**Impact:** When a scan completes with **zero duplicates**, the app crashes with `AttributeError: 'DuplicateView' object has no attribute '_show_gallery_empty'`.

**Fix:** Define the method (or inline the `EmptyState` creation):
```python
def _show_gallery_empty(self, icon="", title="", subtitle="", action_text=None, action=None):
    for widget in self.gallery_frame.winfo_children():
        widget.destroy()
    self.gallery_grid = None
    self.gallery_empty = EmptyState(
        self.gallery_frame, icon=icon, title=title, subtitle=subtitle,
        action_text=action_text, action=action,
    )
    self.gallery_empty.pack(expand=True, pady=80)
```

---

### 2.3 Settings save loses `video_duplicate_tolerance` and `recent_scan_folders` — `settings_view.py` (~line 478)
**Severity:** 🟡 **HIGH — Data Loss**

`_gather_app_settings()` rebuilds an `AppSettings()` object but **omits** two fields:

| Missing Field | Consequence |
|---------------|-------------|
| `video_duplicate_tolerance` | Resets to `3` every time user saves settings |
| `recent_scan_folders` | **Wipes the recent-scan history** on every save |

**Fix:** Add to `_gather_app_settings()`:
```python
video_duplicate_tolerance=self._app.video_duplicate_tolerance,
recent_scan_folders=self._app.recent_scan_folders,
```

Also add them to `reload()` so the UI reflects disk state.

---

### 2.4 Corrupted line endings in `video_dupes.py`
**Severity:** 🟡 **MEDIUM — Portability Risk**

The file contains `\r\r\n` (double carriage return) line endings, visible in every line. This can cause:
- Git diff noise
- Editor rendering issues on Linux/macOS
- Potential Python parser confusion on some platforms

**Fix:** Run `dos2unix` or re-save with LF (`\n`) endings.

---

## 3. Dependency Errors

### 3.1 Missing from `requirements.txt`

| Package | Used By | Graceful Fallback? |
|---------|---------|-------------------|
| `pytesseract` | `ocr_index.py` | ✅ Yes (HAS_PYTESSERACT flag) |
| `pypdf` (or `PyPDF2`) | `ocr_index.py` | ✅ Yes (HAS_PYPDF flag) |
| `pdfminer.six` | `ocr_index.py` | ✅ Yes (HAS_PDFMINER flag) |

**Recommendation:** Add them as optional extras:
```text
customtkinter>=5.0.0
Pillow>=9.0.0
opencv-python>=4.5.0
imagehash>=4.3.0
numpy>=1.20.0
pystray>=0.19.0
piexif>=1.1.3
xxhash>=3.0.0

# Optional (OCR / PDF indexing)
pytesseract>=0.3.10
pypdf>=3.0.0
pdfminer.six>=20221105
```

### 3.2 External dependency: `ffmpeg`/`ffprobe`

Video duplicate detection and thumbnails require `ffmpeg` on the system `PATH`. The code handles absence gracefully, but **users won't know why video features are disabled**. Consider adding a startup check with a one-time dialog pointing to the download URL.

---

## 4. Performance Bottlenecks

### 4.1 O(n²) pHash / video clustering — `duplicate_utils.py` & `video_dupes.py`
**Severity:** 🟡 **MEDIUM — Scales poorly**

```python
# duplicate_utils.py  ~line 54
for i in range(n):
    for j in range(i + 1, n):
        if hamming_distance(...) <= tolerance:
            union(i, j)
```

A duplicate group with **500 images** performs ~125k Hamming-distance comparisons. Each `hex_to_hash` allocates a new `ImageHash` object. For 1k+ groups this becomes the dominant scan phase.

**Fix:** Use BK-trees, VP-trees, or locality-sensitive hashing (LSH) for sub-linear neighbor search. Alternatively, pre-bucket by coarse hash prefix before full Hamming distance.

---

### 4.2 Repeated metadata disk reads — `media_gallery.py` `_sort_files` & `_render_gallery`
**Severity:** 🟡 **MEDIUM — Major I/O overhead**

```python
# _sort_files (~line 718)
def meta_for(path: str) -> ImageMetadata:
    return self._meta_cache.get(path) or read_metadata(path)  # ← disk read on cache miss

sorted(files, key=lambda p: meta_for(p).date_taken or datetime.datetime.min, reverse=True)
```

Sorting by date or rating reads **every file's EXIF** from disk. On a cold cache with 10k files, this is 10k disk reads. `_render_gallery` then calls `read_metadata` **again** for every thumbnail.

**Fix:** Warm the full cache once in `_scan_folder` (already partially done) and ensure `_sort_files` only hits the cache, never disk.

---

### 4.3 Main-thread image loading in duplicate review — `photo_organizer_enhanced.py` `create_image_card`
**Severity:** 🟡 **MEDIUM — UI Freeze**

```python
# ~line 2566
pil_img = Image.open(path)
pil_img.thumbnail(thumb_size, Image.Resampling.LANCZOS)
```

Called directly from `load_group()` on the **main UI thread**. Loading a 50MB RAW/HEIC on the main thread will freeze the UI for seconds.

**Fix:** Move thumbnail generation to a background thread (or `ThreadPoolExecutor`) and show a placeholder spinner until the image is ready.

---

### 4.4 Synchronous blocking in `_ensure_group_scores` — `photo_organizer_enhanced.py`
**Severity:** 🟡 **MEDIUM — UI Freeze**

```python
def _ensure_group_scores(self, paths: list[str]):
    with ThreadPoolExecutor(max_workers=SCORE_WORKERS) as pool:
        futures = {pool.submit(calculate_image_score, fp, True): fp for fp in missing}
        for fut in as_completed(futures):   # ← BLOCKS UI thread
            ...
```

The UI thread waits until **all** scores are computed before showing the group. For a group of 20 images, this is a noticeable lag.

**Fix:** Show the group immediately with placeholder scores, then update card UIs asynchronously as results arrive.

---

### 4.5 `cv2.imread` on main thread for scoring — `photo_organizer_enhanced.py` `calculate_image_score`
**Severity:** 🟡 **LOW — Micro-freezes**

`cv2.imread()` is a blocking I/O + decode operation. Called from the score worker threads it is fine, but if ever called from the main thread it will jank.

**Fix:** Ensure `calculate_image_score` is **only** ever called from worker threads. Add a docstring warning.

---

### 4.6 `organizer_engine.py` eagerly opens images for EXIF
**Severity:** 🟡 **LOW — Unnecessary I/O**

```python
def _exif_datetime(self, filepath: str) -> Optional[datetime.datetime]:
    if not HAS_PIL or os.path.splitext(filepath)[1].lower() not in IMAGE_EXT:
        return None
    try:
        with Image.open(filepath) as img:   # ← opens file even when date_source != EXIF
            ...
```

`get_file_date()` calls `_exif_datetime()` unconditionally when `HAS_PIL` is True, even if the user selected "File modified date" as the date source.

**Fix:** Only call `_exif_datetime()` when `self.config.date_source == DateSource.EXIF`.

---

## 5. Code Quality & Maintainability

### 5.1 Monolithic main file — `photo_organizer_enhanced.py` (~3,500 lines)
**Impact:** Violates Single Responsibility Principle. Navigation, duplicate scanning, inbox watching, file organizing, and gallery browsing are all in one file.

**Recommendation:** Split into:
- `views/home_view.py`
- `views/duplicate_view.py`
- `views/sort_view.py`
- `views/inbox_view.py`

---

### 5.2 Module-level logging configuration — `photo_organizer_enhanced.py` (~line 34)

```python
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
```

**Impact:** If another module calls `basicConfig()` first, this line is silently ignored. The app's log format becomes unpredictable.

**Fix:** Move to `if __name__ == "__main__":` block, or use a `dictConfig` in `config_bootstrap.py`.

---

### 5.3 Type annotation mismatch — `after()` IDs typed as `str`

`ui_components.py` (`ToastManager._dismiss_job`) and `idle_scan.py` (`IdleDuplicateScanner._poll_job`) declare `Optional[str]`. Tkinter `after()` returns an **int**.

**Fix:** Change to `Optional[int]` or `Optional[str]` with `# type: ignore` if using a wrapper.

---

### 5.4 Redundant logic in `theme.py` `is_dark_mode()`

```python
def is_dark_mode() -> bool:
    mode = ctk.get_appearance_mode()
    if mode == "Dark":
        return True
    if mode == "Light":
        return False
    try:
        return ctk.get_appearance_mode() == "Dark"  # ← same call, same condition
    except Exception:
        return True
```

**Fix:** Simplify to:
```python
def is_dark_mode() -> bool:
    try:
        return ctk.get_appearance_mode() == "Dark"
    except Exception:
        return True
```

---

### 5.5 Excessive vertical whitespace — `app_settings.py`

The file uses **double blank lines** between every statement (649 lines with ~200 blank lines). This hinders readability and is non-standard PEP 8.

**Fix:** Run `black` or `ruff format` on the file.

---

### 5.6 `video_dupes.py` line-ending format

As noted in §2.4, the file contains `\r\r\n` endings. This should be normalized to `\n`.

---

### 5.7 Bare `except Exception:` in thumbnail loading — `media_gallery.py` (~line 1011)

```python
try:
    ...
except Exception:
    ...
```

This suppresses real errors (e.g., corrupted image files) and makes debugging harder.

**Fix:** Use `except (OSError, ValueError) as exc:` and `logger.debug("Thumb failed: %s", exc)`.

---

### 5.8 Duplicate / inconsistent PIL imports — `photo_organizer_enhanced.py`

```python
from PIL import Image, ImageTk, ImageDraw, ImageFont  # module level
# ... later inside create_image_card:
from PIL import ImageDraw, ImageFont  # redundant local import
```

**Fix:** Remove the local import.

---

### 5.9 `format_size` imprecision — `photo_organizer_enhanced.py`

```python
def format_size(self, size_bytes):
    i = int(math.floor(math.log(size_bytes, 1024)))
```

`math.log(1024, 1024)` returns `1.0` exactly, but `math.log(1023, 1024)` returns `0.999...`. A 1023-byte file could be mis-bucketed.

**Fix:** Use a simple loop or `humanize` library:
```python
def format_size(size_bytes):
    if size_bytes == 0: return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(units)-1:
        size_bytes /= 1024
        i += 1
    return f"{size_bytes:.2f} {units[i]}"
```

---

### 5.10 Missing `__all__` or export discipline in modules

Most modules expose everything at top level. For example, `theme.py` exports 60+ constants. This makes it hard to know what is intended as public API vs. internal.

**Fix:** Add `__all__ = [...]` to `theme.py`, `ui_components.py`, and `app_settings.py`.

---

## 6. Quick-Wins Checklist (Priority Order)

1. **Fix `_on_more_autoselect` undefined variables** — prevents crash on dropdown use.
2. **Define `_show_gallery_empty` method** — prevents crash on zero-duplicate scans.
3. **Add `video_duplicate_tolerance` and `recent_scan_folders` to `_gather_app_settings`** — prevents data loss.
4. **Normalize `video_dupes.py` line endings** — prevents cross-platform issues.
5. **Update `requirements.txt`** — add `pytesseract`, `pypdf`, `pdfminer.six`.
6. **Move `logging.basicConfig`** to `__main__` block.
7. **Fix `after()` return type annotations** (`str` → `int`).
8. **Simplify `is_dark_mode()`** — remove redundant branch.
9. **Format `app_settings.py`** with `black` or `ruff`.
10. **Add `__all__` exports** to public modules.

---

*End of Audit Report*
