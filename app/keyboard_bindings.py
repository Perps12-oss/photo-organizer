"""Keyboard shortcut overrides from app_settings.json."""

from __future__ import annotations



from app_settings import load_app_settings

from ui_components import (

    DUPLICATE_SHORTCUTS,

    GALLERY_SHORTCUTS,

    GLOBAL_SHORTCUTS,

    INBOX_SHORTCUTS,

    ORGANIZER_SHORTCUTS,

)



DEFAULT_BINDINGS: dict[str, str] = {

    # Global navigation

    "nav_home": "<Control-Key-1>",

    "nav_duplicates": "<Control-Key-2>",

    "nav_gallery": "<Control-Key-3>",

    "nav_organizer": "<Control-Key-4>",

    "nav_inbox": "<Control-Key-5>",

    "nav_settings": "<Control-comma>",

    "undo": "<Control-z>",

    "redo": "<Control-y>",

    "shortcuts_help": "<F1>",

    # Duplicate review

    "dup_group_prev": "<Up>",

    "dup_group_next": "<Down>",

    "dup_image_prev": "<Left>",

    "dup_image_next": "<Right>",

    "dup_toggle_mark": "<space>",

    "dup_smart_best": "<Return>",

    "dup_delete": "<Delete>",

    "dup_help": "<question>",

    "dup_home": "<Escape>",

    "dup_compare": "<Control-d>",

    # Media gallery

    "gal_prev": "<Left>",

    "gal_next": "<Right>",

    "gal_browse": "<Control-o>",

    "gal_save": "<Control-s>",

    "gal_lightbox": "<Key-f>",

    "gal_help": "<question>",

    "gal_rating_0": "<Key-0>",

    "gal_rating_1": "<Key-1>",

    "gal_rating_2": "<Key-2>",

    "gal_rating_3": "<Key-3>",

    "gal_rating_4": "<Key-4>",

    "gal_rating_5": "<Key-5>",

    # File organizer

    "org_preview": "<Control-p>",

    "org_start": "<Control-Return>",

    "org_help": "<question>",

    # Inbox watcher

    "inbox_toggle": "<Control-w>",

    "inbox_help": "<question>",

    # Lightbox / media viewer

    "viewer_close": "<Escape>",

    "viewer_prev": "<Left>",

    "viewer_next": "<Right>",

    "viewer_toggle_video": "<space>",

    "viewer_save": "<Control-s>",

    "viewer_rating_0": "<Key-0>",

    "viewer_rating_1": "<Key-1>",

    "viewer_rating_2": "<Key-2>",

    "viewer_rating_3": "<Key-3>",

    "viewer_rating_4": "<Key-4>",

    "viewer_rating_5": "<Key-5>",

}



ACTION_LABELS: dict[str, str] = {

    "nav_home": "Go to Home",

    "nav_duplicates": "Go to Find Duplicates",

    "nav_gallery": "Go to Media Gallery",

    "nav_organizer": "Go to File Organizer",

    "nav_inbox": "Go to Inbox Watcher",

    "nav_settings": "Go to Settings",

    "undo": "Undo last operation",

    "redo": "Redo last operation",

    "shortcuts_help": "Show keyboard shortcuts",

    "dup_group_prev": "Previous duplicate group",

    "dup_group_next": "Next duplicate group",

    "dup_image_prev": "Previous image in group",

    "dup_image_next": "Next image in group",

    "dup_toggle_mark": "Toggle mark for deletion",

    "dup_smart_best": "Smart Best selection",

    "dup_delete": "Delete marked files",

    "dup_help": "Duplicate shortcuts help",

    "dup_home": "Return to Home",

    "dup_compare": "Compare two selected files",

    "gal_prev": "Previous photo",

    "gal_next": "Next photo",

    "gal_browse": "Browse for folder",

    "gal_save": "Save metadata",

    "gal_lightbox": "Fullscreen lightbox",

    "gal_help": "Gallery shortcuts help",

    "gal_rating_0": "Clear star rating",

    "gal_rating_1": "Set 1-star rating",

    "gal_rating_2": "Set 2-star rating",

    "gal_rating_3": "Set 3-star rating",

    "gal_rating_4": "Set 4-star rating",

    "gal_rating_5": "Set 5-star rating",

    "org_preview": "Preview organization",

    "org_start": "Start organizing",

    "org_help": "Organizer shortcuts help",

    "inbox_toggle": "Start/stop watcher",

    "inbox_help": "Inbox shortcuts help",

    "viewer_close": "Close lightbox",

    "viewer_prev": "Previous image in lightbox",

    "viewer_next": "Next image in lightbox",

    "viewer_toggle_video": "Play/pause video in lightbox",

    "viewer_save": "Save metadata from lightbox",

    "viewer_rating_0": "Clear rating in lightbox",

    "viewer_rating_1": "Set 1-star in lightbox",

    "viewer_rating_2": "Set 2-star in lightbox",

    "viewer_rating_3": "Set 3-star in lightbox",

    "viewer_rating_4": "Set 4-star in lightbox",

    "viewer_rating_5": "Set 5-star in lightbox",

}





def binding_variants(seq: str) -> list[str]:

    """Return binding variants — only duplicate single-letter keys (z/Z)."""

    if not seq:

        return []

    if seq.startswith("<") and seq.endswith(">"):

        inner = seq[1:-1]

        if "-" in inner:

            prefix, key = inner.rsplit("-", 1)

            if len(key) == 1 and key.isalpha():

                upper = f"<{prefix}-{key.upper()}>"

                return list(dict.fromkeys([seq, upper]))

    return [seq]





def resolve_binding(action: str) -> str:

    overrides = load_app_settings().keyboard_shortcuts or {}

    return overrides.get(action) or DEFAULT_BINDINGS.get(action, "")





def shortcuts_reference_text() -> str:

    return (

        f"{GLOBAL_SHORTCUTS}\n\n"

        f"Duplicate review\n{DUPLICATE_SHORTCUTS}\n\n"

        f"Media Gallery\n{GALLERY_SHORTCUTS}\n\n"

        f"File Organizer\n{ORGANIZER_SHORTCUTS}\n\n"

        f"Inbox Watcher\n{INBOX_SHORTCUTS}"

    )

