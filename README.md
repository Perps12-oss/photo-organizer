# Photo Organizer & Duplicate File Finder

A desktop app to find duplicate photos, score image quality, and organize files by date.

## Quick start

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the recommended app** (duplicate finder + sort by month)
   ```bash
   cd app
   python photo_organizer_enhanced.py
   ```
   Or double-click `Run Enhanced.bat` from this folder.

## Folder structure

```
Photo-Organizer/
├── app/                    # Active application scripts
│   ├── photo_organizer_enhanced.py   # Recommended: duplicates + quality + sort by month
│   ├── photo_organizer_hybrid.py     # Pro-style dashboard + enhanced duplicate logic
│   ├── photo_organizer_pro.py        # Full Pro UI (3D carousel, etc.)
│   └── organizer.py                  # Minimal: browse folder, count images
├── archive/                # Older development versions (reference only)
│   ├── photo_organizer22.py          # v1 base (no quality scoring)
│   ├── photo_organizer_phase2.py     # Phase 2 with themes/gallery
│   └── photo_organizer.py            # Phase 3 glassmorphism UI
├── docs/                   # Documentation
│   ├── Quick_Start_Today.md
│   ├── Phase_1_Implementation_Guide.md
│   ├── Phase_2_Implementation_Guide.md
│   ├── Photo_Organizer_Pro_Development_Roadmap.md
│   └── Competitive_Analysis_and_Unique_Features.md
├── requirements.txt
├── Run Enhanced.bat        # Run photo_organizer_enhanced.py
├── Run Hybrid.bat          # Run photo_organizer_hybrid.py
├── Run Pro.bat             # Run photo_organizer_pro.py
├── Run Simple.bat          # Run organizer.py
└── README.md
```

## Which app to use

| App | Use when |
|-----|----------|
| **photo_organizer_enhanced.py** | You want duplicate finding, quality scores, and sort-by-month in one place. |
| **photo_organizer_hybrid.py** | You want the Pro dashboard UI with working duplicate detection. |
| **photo_organizer_pro.py** | You want the full Pro UI (3D carousel, etc.). |
| **organizer.py** | You only need a simple folder browser and image count. |

Older versions in `archive/` are kept for reference but are no longer maintained.

## Requirements

- Python 3.8+
- customtkinter, Pillow, opencv-python, imagehash (see `requirements.txt`)

Optional: `opencv-python-headless` if standard OpenCV install fails.
