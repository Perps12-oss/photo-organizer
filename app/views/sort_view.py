"""File organizer / sort view."""
import customtkinter as ctk
import os
import threading
from tkinter import filedialog, messagebox

from organizer_engine import (
    OrganizerEngine, OrganizerConfig,
    LayoutMode, DateSource, FileScope, NameMode, ConflictPolicy,
    MEDIA_LIBRARY_DIRS,
)
from operation_journal import OperationJournal
from inbox_watcher import load_settings
from app_settings import load_app_settings, save_app_settings
from media_viewer import load_oriented_image, pil_to_ctk_image
from design_system import PageHeader
from theme import APP_BORDER, APP_CARD, APP_TEXT, APP_TEXT_MUTED, CONTENT_MARGIN, FONT_MONO_SM, INPUT_BG, SECTION_GAP, SIDEBAR_TILE_ACTIVE, TEXT_SECONDARY
from ui_components import ORGANIZER_SHORTCUTS
from views.helpers import truncate_middle
from i18n import t

BROWSE_THUMB_SIZE = 80
BROWSE_THUMB_MAX = 24
BROWSE_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp", ".heic", ".heif"}

class SortView(ctk.CTkFrame):
    """File organizer — rules engine with preview, copy, and move."""

    def __init__(self, parent, on_open_gallery=None, shortcut_manager=None):
        super().__init__(parent, fg_color="transparent")
        self.on_open_gallery = on_open_gallery
        self._shortcut_manager = shortcut_manager

        self.source_dir = ctk.StringVar()
        self.dest_dir = ctk.StringVar(value=os.path.expanduser("~/Media_Library"))
        self.organize_var = ctk.StringVar(value="copy")
        self.layout_var = ctk.StringVar(value=LayoutMode.YEAR_MONTH.value)
        self.date_var = ctk.StringVar(value=DateSource.MODIFIED.value)
        self.scope_var = ctk.StringVar(value=FileScope.PHOTOS_VIDEOS.value)
        self.name_var = ctk.StringVar(value=NameMode.KEEP.value)

        self.engine = OrganizerEngine()
        self._plan = []
        self._running = False
        self.total_files = 0
        self._selected_browse_folder = ""
        self._browse_folder_buttons: dict[str, ctk.CTkButton] = {}
        self._browse_thumb_refs: list[ctk.CTkImage] = []
        self._browse_load_token = 0
        self._organizer_key_bindings: list = []

        settings = load_settings()
        if settings.library_root.strip():
            self.dest_dir.set(settings.library_root.strip())
        _app = load_app_settings()
        self.conflict_var = ctk.StringVar(value=_app.conflict_policy)
        self.folder_template_var = ctk.StringVar(value=_app.folder_template)
        self.filename_template_var = ctk.StringVar(value=_app.filename_template)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        PageHeader(self, t("organizer.title"), t("organizer.subtitle")).grid(
            row=0, column=0, sticky="ew", padx=CONTENT_MARGIN, pady=(CONTENT_MARGIN, SECTION_GAP),
        )

        paths_frame = ctk.CTkFrame(self, fg_color=APP_CARD, corner_radius=18, border_width=1, border_color=APP_BORDER)
        paths_frame.grid(row=1, column=0, padx=CONTENT_MARGIN, pady=8, sticky="ew")
        paths_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(paths_frame, text="Source folder", font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=0, column=0, padx=12, pady=(12, 4), sticky="w")
        src_row = ctk.CTkFrame(paths_frame, fg_color="transparent")
        src_row.grid(row=0, column=1, padx=12, pady=(12, 4), sticky="ew")
        src_row.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(src_row, textvariable=self.source_dir, placeholder_text="Folder to organize").grid(
            row=0, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkButton(src_row, text="Browse", width=90, command=self.browse_source).grid(row=0, column=1, padx=(0, 4))
        ctk.CTkButton(src_row, text="Gallery", width=80, command=self.open_source_in_gallery).grid(row=0, column=2)

        ctk.CTkLabel(paths_frame, text="Destination root", font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=1, column=0, padx=12, pady=(4, 12), sticky="w")
        dest_row = ctk.CTkFrame(paths_frame, fg_color="transparent")
        dest_row.grid(row=1, column=1, padx=12, pady=(4, 12), sticky="ew")
        dest_row.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(dest_row, textvariable=self.dest_dir, placeholder_text="Where organized files go").grid(
            row=0, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkButton(dest_row, text="Browse", width=90, command=self.browse_dest).grid(row=0, column=1, padx=(0, 4))
        ctk.CTkButton(dest_row, text="Gallery", width=80, command=self.open_dest_in_gallery).grid(row=0, column=2)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=2, column=0, padx=CONTENT_MARGIN, pady=8, sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=0)
        body.grid_rowconfigure(1, weight=1)

        rules_frame = ctk.CTkFrame(body, fg_color=APP_CARD, corner_radius=10, border_width=1, border_color=APP_BORDER)
        rules_frame.grid(row=0, column=0, padx=(0, 8), pady=(0, 8), sticky="nsew")
        ctk.CTkLabel(rules_frame, text="Rules", font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="w", padx=14, pady=(14, 10))

        self._add_option(rules_frame, "Folder layout", self.layout_var, [m.value for m in LayoutMode])
        self._add_option(rules_frame, "Date from", self.date_var, [d.value for d in DateSource])
        self._add_option(rules_frame, "Include files", self.scope_var, [s.value for s in FileScope])
        self._add_option(rules_frame, "Rename", self.name_var, [n.value for n in NameMode])

        action_row = ctk.CTkFrame(rules_frame, fg_color="transparent")
        action_row.pack(fill="x", padx=14, pady=(8, 6))
        ctk.CTkLabel(action_row, text="Action", width=100, anchor="w").pack(side="left")
        ctk.CTkRadioButton(action_row, text="Copy", variable=self.organize_var, value="copy").pack(side="left", padx=(0, 12))
        ctk.CTkRadioButton(action_row, text="Move", variable=self.organize_var, value="move").pack(side="left")

        ctk.CTkButton(
            rules_frame, text="Create media library folders", command=self.create_library_tree,
            fg_color="transparent", border_width=1, border_color=APP_BORDER, hover_color=SIDEBAR_TILE_ACTIVE,
        ).pack(fill="x", padx=14, pady=(4, 8))

        tpl_hint = ctk.CTkLabel(
            rules_frame,
            text="Placeholders: {date} {year} {month} {extension} {name} {stem} {event} {category}",
            font=ctk.CTkFont(size=10), text_color=APP_TEXT_MUTED, wraplength=360, justify="left",
        )
        tpl_hint.pack(fill="x", padx=14, pady=(0, 4))
        tpl_row1 = ctk.CTkFrame(rules_frame, fg_color="transparent")
        tpl_row1.pack(fill="x", padx=14, pady=2)
        ctk.CTkLabel(tpl_row1, text="Folder template", width=100, anchor="w").pack(side="left")
        ctk.CTkEntry(tpl_row1, textvariable=self.folder_template_var, placeholder_text="{year}/{month}").pack(
            side="left", fill="x", expand=True,
        )
        tpl_row2 = ctk.CTkFrame(rules_frame, fg_color="transparent")
        tpl_row2.pack(fill="x", padx=14, pady=2)
        ctk.CTkLabel(tpl_row2, text="File template", width=100, anchor="w").pack(side="left")
        ctk.CTkEntry(tpl_row2, textvariable=self.filename_template_var, placeholder_text="{date_compact}_{stem}").pack(
            side="left", fill="x", expand=True,
        )
        conflict_row = ctk.CTkFrame(rules_frame, fg_color="transparent")
        conflict_row.pack(fill="x", padx=14, pady=(4, 14))
        ctk.CTkLabel(conflict_row, text="If file exists", width=100, anchor="w").pack(side="left")
        ctk.CTkOptionMenu(
            conflict_row, variable=self.conflict_var,
            values=["rename", "skip", "overwrite"], width=160,
        ).pack(side="left")

        preview_frame = ctk.CTkFrame(body, fg_color=APP_CARD, corner_radius=10, border_width=1, border_color=APP_BORDER)
        preview_frame.grid(row=0, column=1, padx=(8, 0), sticky="nsew")
        preview_frame.grid_rowconfigure(1, weight=1)
        preview_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(preview_frame, text="Preview", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, padx=14, pady=(14, 8), sticky="w")
        self.preview_box = ctk.CTkTextbox(
            preview_frame, font=FONT_MONO_SM, fg_color=INPUT_BG, text_color=APP_TEXT_MUTED,
            wrap="word", activate_scrollbars=True,
        )
        self.preview_box.grid(row=1, column=0, padx=14, pady=(0, 14), sticky="nsew")
        self.preview_box.insert("1.0", "Select source and destination, then click Preview Organization.")
        self.preview_box.configure(state="disabled")

        browse_frame = ctk.CTkFrame(body, fg_color=APP_CARD, corner_radius=10, border_width=1, border_color=APP_BORDER)
        browse_frame.grid(row=1, column=0, columnspan=2, sticky="nsew")
        browse_frame.grid_columnconfigure(1, weight=1)
        browse_frame.grid_rowconfigure(1, weight=1)

        browse_header = ctk.CTkFrame(browse_frame, fg_color="transparent")
        browse_header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=14, pady=(12, 6))
        ctk.CTkLabel(browse_header, text="Library Browser", font=ctk.CTkFont(size=14, weight="bold")).pack(
            side="left")
        self.browse_root_label = ctk.CTkLabel(
            browse_header, text="", text_color=APP_TEXT_MUTED, font=ctk.CTkFont(size=11), anchor="e",
        )
        self.browse_root_label.pack(side="right", fill="x", expand=True, padx=(12, 0))

        folders_panel = ctk.CTkFrame(browse_frame, fg_color="INPUT_BG", corner_radius=8)
        folders_panel.grid(row=1, column=0, padx=(14, 6), pady=(0, 10), sticky="nsew")
        folders_panel.grid_rowconfigure(1, weight=1)
        folders_panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            folders_panel, text="Folders", font=ctk.CTkFont(size=12, weight="bold"),
            text_color=APP_TEXT_MUTED,
        ).grid(row=0, column=0, padx=10, pady=(10, 6), sticky="w")
        self.browse_folder_list = ctk.CTkScrollableFrame(
            folders_panel, fg_color="transparent", width=220, height=200,
        )
        self.browse_folder_list.grid(row=1, column=0, padx=6, pady=(0, 8), sticky="nsew")

        preview_panel = ctk.CTkFrame(browse_frame, fg_color="INPUT_BG", corner_radius=8)
        preview_panel.grid(row=1, column=1, padx=(6, 14), pady=(0, 10), sticky="nsew")
        preview_panel.grid_rowconfigure(1, weight=1)
        preview_panel.grid_columnconfigure(0, weight=1)

        preview_top = ctk.CTkFrame(preview_panel, fg_color="transparent")
        preview_top.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))
        self.browse_folder_label = ctk.CTkLabel(
            preview_top, text="Select a folder", font=ctk.CTkFont(size=12, weight="bold"), anchor="w",
        )
        self.browse_folder_label.pack(side="left", fill="x", expand=True)
        self.browse_count_label = ctk.CTkLabel(
            preview_top, text="", text_color=APP_TEXT_MUTED, font=ctk.CTkFont(size=11), anchor="e",
        )
        self.browse_count_label.pack(side="right")

        self.browse_thumb_grid = ctk.CTkScrollableFrame(preview_panel, fg_color="transparent", height=200)
        self.browse_thumb_grid.grid(row=1, column=0, padx=8, pady=(0, 8), sticky="nsew")

        browse_actions = ctk.CTkFrame(browse_frame, fg_color="transparent")
        browse_actions.grid(row=2, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 12))
        ctk.CTkButton(
            browse_actions, text="Open in Gallery", width=140, command=self._browse_open_gallery,
            fg_color="transparent", border_width=1, border_color=APP_BORDER, hover_color=SIDEBAR_TILE_ACTIVE,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            browse_actions, text="Organize from here", width=160, command=self._browse_organize_from_here,
            fg_color=APP_ACCENT, text_color="#0a0a12", hover_color=APP_ACCENT_HOVER,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            browse_actions, text="Set as destination", width=150, command=self._browse_set_destination,
            fg_color="transparent", border_width=1, border_color=APP_BORDER, hover_color=SIDEBAR_TILE_ACTIVE,
        ).pack(side="left")

        self.dest_dir.trace_add("write", self._on_dest_dir_changed)
        self.after_idle(self._refresh_folder_list)

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=3, column=0, padx=CONTENT_MARGIN, pady=(8, CONTENT_MARGIN), sticky="ew")
        footer.grid_columnconfigure(0, weight=1)

        prog = ctk.CTkFrame(footer, fg_color="transparent")
        prog.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.progress_label = ctk.CTkLabel(prog, text="Ready", text_color=APP_TEXT_MUTED)
        self.progress_label.pack(anchor="w")
        self.progress_bar = ctk.CTkProgressBar(prog)
        self.progress_bar.pack(fill="x", pady=(6, 0))
        self.progress_bar.set(0)

        btn_row = ctk.CTkFrame(footer, fg_color="transparent")
        btn_row.grid(row=1, column=0)
        ctk.CTkButton(btn_row, text="Preview Organization", width=180, height=40,
                      command=self.preview_organization).pack(side="left", padx=(0, 10))
        self.start_btn = ctk.CTkButton(
            btn_row, text="Start Organizing", width=180, height=40,
            fg_color="#198754", hover_color="#13653f", command=self.start_organization,
        )
        self.start_btn.pack(side="left")

    def _add_option(self, parent, label, variable, values):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=4)
        ctk.CTkLabel(row, text=label, width=100, anchor="w").pack(side="left")
        ctk.CTkOptionMenu(row, variable=variable, values=values, width=320).pack(side="left", fill="x", expand=True)

    def _current_config(self) -> OrganizerConfig:
        policy_map = {
            "rename": ConflictPolicy.RENAME,
            "skip": ConflictPolicy.SKIP,
            "overwrite": ConflictPolicy.OVERWRITE,
        }
        return OrganizerConfig(
            layout=self._enum_from_value(LayoutMode, self.layout_var.get()),
            date_source=self._enum_from_value(DateSource, self.date_var.get()),
            scope=self._enum_from_value(FileScope, self.scope_var.get()),
            name_mode=self._enum_from_value(NameMode, self.name_var.get()),
            conflict_policy=policy_map.get(self.conflict_var.get(), ConflictPolicy.RENAME),
            folder_template=self.folder_template_var.get().strip(),
            filename_template=self.filename_template_var.get().strip(),
        )

    def _persist_organizer_templates(self):
        app = load_app_settings()
        app.conflict_policy = self.conflict_var.get()
        app.folder_template = self.folder_template_var.get().strip()
        app.filename_template = self.filename_template_var.get().strip()
        save_app_settings(app)

    @staticmethod
    def _enum_from_value(enum_cls, value):
        for member in enum_cls:
            if member.value == value:
                return member
        return list(enum_cls)[0]

    def _validate_paths(self, create_dest=False) -> tuple[str, str] | None:
        source = self.source_dir.get().strip()
        dest = self.dest_dir.get().strip()
        if not source or not os.path.isdir(source):
            messagebox.showerror("Error", "Please select a valid source folder.")
            return None
        if not dest:
            messagebox.showerror("Error", "Please enter a destination path.")
            return None
        if not os.path.isdir(dest):
            if create_dest:
                try:
                    os.makedirs(dest, exist_ok=True)
                except OSError as e:
                    messagebox.showerror("Error", f"Could not create destination folder:\n{e}")
                    return None
            else:
                messagebox.showerror("Error", "Destination folder does not exist.\nUse Browse or Create media library folders.")
                return None
        return source, dest

    def browse_source(self):
        path = filedialog.askdirectory()
        if path:
            self.source_dir.set(path)

    def browse_dest(self):
        path = filedialog.askdirectory()
        if path:
            self.dest_dir.set(path)

    def open_source_in_gallery(self):
        folder = self.source_dir.get().strip()
        if self.on_open_gallery:
            self.on_open_gallery(folder)

    def open_dest_in_gallery(self):
        folder = self.dest_dir.get().strip()
        if self.on_open_gallery:
            self.on_open_gallery(folder)

    def on_view_shown(self):
        """Refresh library browser when File Organizer tab is opened."""
        self._refresh_folder_list()

    def rebind_shortcuts(self):
        self.bind_organizer_keys()

    def bind_organizer_keys(self):
        self.unbind_organizer_keys()
        root = self.winfo_toplevel()
        sm = self._shortcut_manager
        if sm:
            bindings = {
                "org_preview": (lambda e: self.preview_organization(), "<Control-p>"),
                "org_start": (lambda e: self.start_organization(), "<Control-Return>"),
                "org_help": (lambda e: self._show_organizer_shortcuts(), "<question>"),
            }
            for action, (handler, default) in bindings.items():
                sm.bind(root, action, default, handler)
            return
        keys = {
            "<Control-p>": lambda e: self.preview_organization(),
            "<Control-P>": lambda e: self.preview_organization(),
            "<Control-Return>": lambda e: self.start_organization(),
            "<question>": lambda e: self._show_organizer_shortcuts(),
        }
        for seq, handler in keys.items():
            root.bind(seq, handler, add="+")
            self._organizer_key_bindings.append((root, seq, handler))

    def unbind_organizer_keys(self):
        root = self.winfo_toplevel()
        sm = getattr(self, "_shortcut_manager", None)
        if not sm:
            app = self.winfo_toplevel()
            sm = getattr(app, "shortcut_manager", None)
        if sm:
            sm.unbind_actions(root, ["org_preview", "org_start", "org_help"])
        for root, seq, handler in self._organizer_key_bindings:
            try:
                root.unbind(seq, handler)
            except Exception:
                pass
        self._organizer_key_bindings.clear()

    def _show_organizer_shortcuts(self):
        from tkinter import messagebox
        app = self.winfo_toplevel()
        if hasattr(app, "_show_shortcuts_help"):
            app._show_shortcuts_help(ORGANIZER_SHORTCUTS, "File Organizer shortcuts")
        else:
            messagebox.showinfo("File Organizer shortcuts", ORGANIZER_SHORTCUTS)

    def _library_root(self) -> str:
        dest = self.dest_dir.get().strip()
        if dest and os.path.isdir(dest):
            return dest
        settings = load_settings()
        root = settings.library_root.strip()
        if root:
            return root
        return dest or os.path.expanduser("~/Media_Library")

    def _on_dest_dir_changed(self, *_args):
        self.after_idle(self._refresh_folder_list)

    def _iter_browse_folders(self, root: str):
        if not root:
            return
        yield ("Library root", root)
        listed: set[str] = set()
        for sub in MEDIA_LIBRARY_DIRS:
            path = os.path.join(root, *sub.replace("/", os.sep).split(os.sep))
            norm = os.path.normpath(path)
            listed.add(norm)
            yield (sub.replace("/", " / "), path)
        if not os.path.isdir(root):
            return
        standard_tops = {d.split("/")[0] for d in MEDIA_LIBRARY_DIRS}
        try:
            for name in sorted(os.listdir(root)):
                if name.startswith("."):
                    continue
                full = os.path.join(root, name)
                if not os.path.isdir(full):
                    continue
                norm = os.path.normpath(full)
                if name in standard_tops:
                    try:
                        for child in sorted(os.listdir(full)):
                            if child.startswith("."):
                                continue
                            child_path = os.path.join(full, child)
                            if os.path.isdir(child_path):
                                child_norm = os.path.normpath(child_path)
                                if child_norm not in listed:
                                    listed.add(child_norm)
                                    yield (f"{name} / {child}", child_path)
                    except OSError:
                        pass
                elif norm not in listed:
                    listed.add(norm)
                    yield (name, full)
        except OSError:
            pass

    def _refresh_folder_list(self):
        root = self._library_root()
        self.browse_root_label.configure(text=truncate_middle(root, 72))
        for widget in self.browse_folder_list.winfo_children():
            widget.destroy()
        self._browse_folder_buttons.clear()

        folders = list(self._iter_browse_folders(root))
        if not folders:
            EmptyState(
                self.browse_folder_list,
                icon="📁",
                title="No library root",
                subtitle="Set a destination root to browse folders.",
            ).pack(fill="x", padx=4, pady=12)
            self._selected_browse_folder = ""
            self._clear_browse_thumbnails(
                icon="📂", title="No folder selected",
                subtitle="Pick a folder from the list on the left.",
            )
            return

        keep_selection = self._selected_browse_folder
        if keep_selection not in {path for _, path in folders}:
            keep_selection = folders[0][1]

        for label, path in folders:
            exists = os.path.isdir(path)
            btn = ctk.CTkButton(
                self.browse_folder_list,
                text=label,
                anchor="w",
                height=30,
                fg_color="transparent",
                hover_color=SIDEBAR_TILE_ACTIVE,
                text_color=APP_TEXT if exists else APP_TEXT_MUTED,
                command=lambda p=path: self._select_browse_folder(p),
            )
            btn.pack(fill="x", padx=2, pady=2)
            self._browse_folder_buttons[path] = btn

        self._select_browse_folder(keep_selection)

    def _highlight_browse_folder(self, folder: str):
        for path, btn in self._browse_folder_buttons.items():
            if path == folder:
                btn.configure(fg_color=APP_ACCENT, text_color="#0a0a12", hover_color=APP_ACCENT_HOVER)
            else:
                btn.configure(fg_color="transparent", text_color=APP_TEXT, hover_color=SIDEBAR_TILE_ACTIVE)

    def _select_browse_folder(self, folder: str):
        self._selected_browse_folder = folder
        self._highlight_browse_folder(folder)
        label = os.path.basename(folder) or folder
        self.browse_folder_label.configure(text=truncate_middle(label, 48))
        if not os.path.isdir(folder):
            self._clear_browse_thumbnails(
                icon="📁", title="Folder not created yet",
                subtitle="Use Create media library folders to set up this path.",
            )
            self.browse_count_label.configure(text="")
            return
        self._clear_browse_thumbnails(
            icon="⏳", title="Loading previews…", subtitle="",
        )
        self.browse_count_label.configure(text="")
        self._browse_load_token += 1
        token = self._browse_load_token
        threading.Thread(target=self._load_browse_thumbnails, args=(folder, token), daemon=True).start()

    def _list_browse_files(self, folder: str) -> list[str]:
        files = []
        try:
            for name in sorted(os.listdir(folder)):
                full = os.path.join(folder, name)
                if os.path.isfile(full) and os.path.splitext(name)[1].lower() in SUPPORTED_EXTENSIONS:
                    files.append(full)
        except OSError:
            pass
        return files

    def _load_browse_thumbnails(self, folder: str, token: int):
        files = self._list_browse_files(folder)
        total = len(files)
        preview_files = files[:BROWSE_THUMB_MAX]
        thumbs: list[tuple[str, object | None]] = []
        for path in preview_files:
            thumb_image = None
            ext = os.path.splitext(path)[1].lower()
            if ext in BROWSE_IMAGE_EXT:
                try:
                    img = load_oriented_image(path)
                    img.thumbnail((BROWSE_THUMB_SIZE, BROWSE_THUMB_SIZE), Image.Resampling.LANCZOS)
                    thumb_image = pil_to_ctk_image(img)
                except Exception:
                    thumb_image = None
            thumbs.append((path, thumb_image))
        self.after(0, self._apply_browse_thumbnails, folder, token, total, thumbs)

    def _clear_browse_thumbnails(
        self, message: str = "", icon: str = "🖼️", title: str = "", subtitle: str = "",
    ):
        for widget in self.browse_thumb_grid.winfo_children():
            widget.destroy()
        self._browse_thumb_refs.clear()
        if title or message:
            display_title = title or message
            display_sub = subtitle if title else ""
            EmptyState(
                self.browse_thumb_grid, icon=icon, title=display_title,
                subtitle=display_sub,
            ).pack(expand=True, pady=24)

    def _apply_browse_thumbnails(
        self, folder: str, token: int, total: int, thumbs: list[tuple[str, object | None]],
    ):
        if token != self._browse_load_token or folder != self._selected_browse_folder:
            return
        self._clear_browse_thumbnails()
        if total == 0:
            self.browse_count_label.configure(text="No media files")
            EmptyState(
                self.browse_thumb_grid,
                icon="🖼️",
                title="No media here",
                subtitle="No supported photos or videos in this folder.",
            ).pack(expand=True, pady=24)
            return
        shown = len(thumbs)
        if total > shown:
            self.browse_count_label.configure(text=f"Showing {shown} of {total} files")
        else:
            self.browse_count_label.configure(text=f"{total} file{'s' if total != 1 else ''}")

        cols = max(1, (self.browse_thumb_grid.winfo_width() or 520) // (BROWSE_THUMB_SIZE + 12))
        row_frame = None
        col = 0
        for path, thumb_image in thumbs:
            if col == 0:
                row_frame = ctk.CTkFrame(self.browse_thumb_grid, fg_color="transparent")
                row_frame.pack(fill="x", pady=2)
            cell = ctk.CTkFrame(row_frame, fg_color="#1a1a28", corner_radius=6, width=BROWSE_THUMB_SIZE + 8,
                                height=BROWSE_THUMB_SIZE + 8)
            cell.pack(side="left", padx=4, pady=4)
            cell.pack_propagate(False)
            if thumb_image is not None:
                self._browse_thumb_refs.append(thumb_image)
                ctk.CTkLabel(cell, text="", image=thumb_image).pack(expand=True)
            else:
                ext = os.path.splitext(path)[1].upper().lstrip(".") or "FILE"
                ctk.CTkLabel(
                    cell, text=ext[:4], font=ctk.CTkFont(size=11, weight="bold"), text_color=APP_TEXT_MUTED,
                ).pack(expand=True)
            col += 1
            if col >= cols:
                col = 0

    def _browse_open_gallery(self):
        folder = self._selected_browse_folder.strip()
        if not folder:
            messagebox.showinfo("Library Browser", "Select a folder first.")
            return
        if self.on_open_gallery:
            self.on_open_gallery(folder)

    def _browse_organize_from_here(self):
        folder = self._selected_browse_folder.strip()
        if not folder:
            messagebox.showinfo("Library Browser", "Select a folder first.")
            return
        if not os.path.isdir(folder):
            messagebox.showinfo("Library Browser", "Selected folder does not exist yet.")
            return
        self.source_dir.set(folder)

    def _browse_set_destination(self):
        folder = self._selected_browse_folder.strip()
        if not folder:
            messagebox.showinfo("Library Browser", "Select a folder first.")
            return
        self.dest_dir.set(folder)

    def create_library_tree(self):
        paths = self._validate_paths(create_dest=True)
        if not paths:
            return
        _, dest = paths
        OrganizerEngine.ensure_media_library_tree(dest)
        self.layout_var.set(LayoutMode.MEDIA_LIBRARY.value)
        self._refresh_folder_list()
        messagebox.showinfo("Media Library", f"Created folder tree under:\n{dest}")

    def _set_preview_text(self, text: str):
        self.preview_box.configure(state="normal")
        self.preview_box.delete("1.0", "end")
        self.preview_box.insert("1.0", text)
        self.preview_box.configure(state="disabled")

    def preview_organization(self):
        paths = self._validate_paths(create_dest=True)
        if not paths:
            return
        self._persist_organizer_templates()
        source, dest = paths
        action = self.organize_var.get()
        self.engine.set_config(self._current_config())
        self._set_preview_text("Building preview…")
        threading.Thread(
            target=self._preview_worker,
            args=(source, dest, action),
            daemon=True,
        ).start()

    def _preview_worker(self, source: str, dest: str, action: str):
        plan = self.engine.build_plan(source, dest)
        self._plan = plan
        preview = self.engine.format_preview(plan, dest, action)
        self.after(0, lambda: self._set_preview_text(preview))

    def start_organization(self):
        if self._running:
            return
        paths = self._validate_paths(create_dest=True)
        if not paths:
            return
        self._persist_organizer_templates()
        source, dest = paths
        action = self.organize_var.get()
        self.engine.set_config(self._current_config())
        self._plan = self.engine.build_plan(source, dest)
        if not self._plan:
            messagebox.showinfo("Organize", "No matching files found in the source folder.")
            return
        layout_label = self.layout_var.get()
        if not messagebox.askyesno(
            "Confirm",
            f"{action.capitalize()} {len(self._plan)} file(s) from\n{source}\n\n"
            f"into {dest}\n\nLayout: {layout_label}",
        ):
            return
        self._running = True
        self.start_btn.configure(state="disabled")
        self.progress_bar.set(0)
        self.progress_label.configure(text="Starting…")
        threading.Thread(
            target=self._run_organization,
            args=(dest, action),
            daemon=True,
        ).start()

    def _run_organization(self, dest, action):
        app = self.winfo_toplevel()
        journal = getattr(app, "op_journal", OperationJournal.load())

        def on_item_done(item, act):
            journal.record(act, item.source, item.destination)

        done, errors = self.engine.execute(
            self._plan, action, dest_root=dest,
            on_progress=self._on_engine_progress,
            on_item_done=on_item_done,
        )
        self.after(0, self._organization_finished, done, errors)

    def _on_engine_progress(self, fraction, done, total):
        self.after(0, self.update_sort_progress, fraction, done, total)

    def update_sort_progress(self, progress, processed, total=None):
        self.progress_bar.set(progress)
        if total is not None:
            self.total_files = total
        self.progress_label.configure(text=f"Processed {processed} of {self.total_files} files")

    def _organization_finished(self, files_organized, errors):
        self._running = False
        self.start_btn.configure(state="normal")
        result_msg = f"Successfully organized {files_organized} file(s)."
        if errors:
            error_list = "\n".join(errors[:8])
            if len(errors) > 8:
                error_list += f"\n… and {len(errors) - 8} more"
            result_msg += f"\n\nErrors:\n{error_list}"
        messagebox.showinfo("Organization Complete", result_msg)
        self.progress_label.configure(text="Ready")
        self.progress_bar.set(0)
        self._plan = []
