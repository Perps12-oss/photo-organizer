import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ImageDraw, ImageFont
import os
import sys
import hashlib
import threading
import datetime
import math
import time
import base64
import json
import tempfile
import webbrowser
import shutil
import logging
from collections import defaultdict

# --- DEPENDENCIES CHECK ---
try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False
    logging.warning("OpenCV not found. Quality scoring will be limited.")

try:
    import imagehash
    HAS_IMAGEHASH = True
except ImportError:
    HAS_IMAGEHASH = False
    logging.warning("imagehash not found. Similar image detection disabled.")

# --- CONFIGURATION ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

SUPPORTED_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.mov', '.mp4')

GLASS_COLORS = {
    'primary': '#00ffcc',      # Neon Cyan
    'secondary': '#00ccff',    # Blue
    'accent': '#ff00ff',        # Magenta
    'dark': '#1a1a2e',          # Deep Blue/Black
    'darker': '#0f0f1a',        # Almost Black
    'card_bg': '#16213e',       # Card Background
}

# --- UTILITIES (From Code A - Enhanced) ---
class PhotoUtils:
    @staticmethod
    def format_size(bytes_size):
        if bytes_size == 0: return "0 B"
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_size < 1024.0: return f"{bytes_size:.2f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.2f} PB"

    @staticmethod
    def get_file_hash(filepath):
        hasher = hashlib.md5()
        try:
            with open(filepath, 'rb') as f:
                while chunk := f.read(8192): hasher.update(chunk)
            return hasher.hexdigest()
        except: return None

    @staticmethod
    def calculate_phash(filepath):
        if not HAS_IMAGEHASH: return None
        try:
            return str(imagehash.average_hash(Image.open(filepath)))
        except: return None

    @staticmethod
    def calculate_score(filepath):
        """Unified scoring: higher = better quality."""
        score = 0.0
        try:
            if HAS_CV2:
                img = cv2.imread(filepath)
                if img is not None:
                    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                    # 1. Sharpness (Laplacian variance)
                    score += cv2.Laplacian(gray, cv2.CV_64F).var() * 0.4
                    # 2. Resolution
                    h, w = img.shape[:2]
                    score += ((w * h) / 1_000_000) * 0.2
            
            # 3. File Size
            mb = os.path.getsize(filepath) / (1024*1024)
            score += min(mb, 50) * 0.1
            
            # 4. Recency
            age = (time.time() - os.path.getmtime(filepath)) / 86400
            score += max(0, (365 - age) / 365) * 30
            
            # 5. Filename logic
            fname = os.path.basename(filepath).lower()
            if 'screenshot' in fname: score -= 20
            if any(k in fname for k in ['edit', 'final', 'best']): score += 15
            
        except Exception as e:
            logging.error(f"Score error: {e}")
        return round(score, 2)

    @staticmethod
    def get_score_color(score):
        if score > 70: return "#2ecc71" # Green
        if score > 40: return "#f1c40f" # Yellow
        return "#e74c3c" # Red

# --- UI COMPONENTS (From Code B - Pro Look) ---
class ModernSidebar(ctk.CTkFrame):
    def __init__(self, parent, command_callback):
        super().__init__(parent, width=220, corner_radius=0)
        self.command_callback = command_callback
        self.configure(fg_color=GLASS_COLORS['darker'])
        
        # Logo
        ctk.CTkLabel(self, text="📸", font=("Arial", 30)).pack(pady=(30, 5))
        ctk.CTkLabel(self, text="MANAGER PRO", font=("Arial", 14, "bold"), 
                     text_color=GLASS_COLORS['primary']).pack(pady=(0, 20))
        
        # Nav Buttons
        self.create_nav_button("🏠 Dashboard", "dashboard")
        self.create_nav_button("🖼️ 3D Gallery", "gallery")
        self.create_nav_button("🔍 Find Duplicates", "duplicates")
        self.create_nav_button("📁 Sort by Date", "sort")
        
        # Settings area
        self.create_nav_button("⚙️ Settings", "settings")

    def create_nav_button(self, text, cmd_name):
        btn = ctk.CTkButton(self, text=text, anchor="w", height=45,
                           fg_color="transparent", hover_color=GLASS_COLORS['dark'],
                           font=("Arial", 13), command=lambda: self.command_callback(cmd_name))
        btn.pack(fill="x", padx=15, pady=5)

# --- VIEWS ---

class DashboardView(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        
        # Header
        header = ctk.CTkFrame(self, fg_color=GLASS_COLORS['dark'], corner_radius=15, height=150)
        header.pack(fill="x", padx=20, pady=20)
        header.pack_propagate(False)
        
        ctk.CTkLabel(header, text="Welcome to Photo Manager Pro", 
                    font=("Arial", 24, "bold"), text_color=GLASS_COLORS['primary']).pack(pady=40)
        
        # Stats Container
        stats_container = ctk.CTkFrame(self, fg_color="transparent")
        stats_container.pack(fill="x", padx=20)
        
        self.stat_photos = self.create_stat_card(stats_container, "📊", "Total Photos", "0")
        self.stat_size = self.create_stat_card(stats_container, "💾", "Storage Used", "0 MB")
        self.stat_dups = self.create_stat_card(stats_container, "👯", "Duplicates", "0")
        
        # Quick Actions
        actions = ctk.CTkFrame(self, fg_color=GLASS_COLORS['dark'], corner_radius=15)
        actions.pack(fill="x", padx=20, pady=20)
        ctk.CTkLabel(actions, text="Quick Actions", font=("Arial", 18, "bold")).pack(pady=20)
        
        btn_frame = ctk.CTkFrame(actions, fg_color="transparent")
        btn_frame.pack()
        
        ctk.CTkButton(btn_frame, text="🔍 Scan Folder", width=150, height=40, 
                     fg_color=GLASS_COLORS['primary'], hover_color="#00ddaa",
                     command=lambda: self.master.navigate_to("duplicates")).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="📁 Organize", width=150, height=40,
                     command=lambda: self.master.navigate_to("sort")).pack(side="left", padx=10)

    def create_stat_card(self, parent, icon, title, value):
        card = ctk.CTkFrame(parent, fg_color=GLASS_COLORS['card_bg'], corner_radius=10)
        card.pack(side="left", expand=True, fill="both", padx=5)
        
        ctk.CTkLabel(card, text=icon, font=("Arial", 20)).pack(pady=(15, 5))
        ctk.CTkLabel(card, text=title, text_color="gray").pack()
        lbl = ctk.CTkLabel(card, text=value, font=("Arial", 20, "bold"), text_color=GLASS_COLORS['secondary'])
        lbl.pack(pady=(5, 15))
        return lbl

    def update_stats(self, path):
        """Real stats calculation"""
        count = 0
        size = 0
        if path and os.path.isdir(path):
            for root, _, files in os.walk(path):
                for f in files:
                    if f.lower().endswith(SUPPORTED_EXTENSIONS):
                        count += 1
                        try: size += os.path.getsize(os.path.join(root, f))
                        except: pass
        
        self.stat_photos.configure(text=str(count))
        self.stat_size.configure(text=PhotoUtils.format_size(size))
        # Duplicate count is complex without full scan, leaving placeholder
        self.stat_dups.configure(text="Scan Required")

class Gallery3DView(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.photos = []
        
        # Header
        top = ctk.CTkFrame(self, fg_color=GLASS_COLORS['dark'], corner_radius=15)
        top.pack(fill="x", padx=20, pady=20)
        
        ctk.CTkButton(top, text="📁 Load Folder", command=self.load_folder, 
                     fg_color=GLASS_COLORS['secondary']).pack(side="right", padx=20, pady=15)
        self.folder_lbl = ctk.CTkLabel(top, text="No folder loaded")
        self.folder_lbl.pack(side="right", padx=20)
        
        # Canvas Preview
        self.canvas = ctk.Canvas(self, bg=GLASS_COLORS['darker'], highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=20, pady=20)
        self.canvas.bind("<Configure>", lambda e: self.draw_preview())
        
        # Controls
        ctrl = ctk.CTkFrame(self, fg_color="transparent")
        ctrl.pack(fill="x", padx=20, pady=20)
        ctk.CTkButton(ctrl, text="🚀 Launch 3D Viewer", command=self.launch_3d,
                     fg_color=GLASS_COLORS['primary'], hover_color="#00ddaa").pack()

    def load_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.photos = [os.path.join(path, f) for f in os.listdir(path) 
                          if f.lower().endswith(SUPPORTED_EXTENSIONS)]
            self.folder_lbl.configure(text=f"Loaded {len(self.photos)} photos from {os.path.basename(path)}")
            self.draw_preview()

    def draw_preview(self):
        self.canvas.delete("all")
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        cx, cy = w//2, h//2
        
        # Draw simple 3D representation
        self.canvas.create_oval(cx-100, cy-100, cx+100, cy+100, outline=GLASS_COLORS['primary'], width=2)
        self.canvas.create_text(cx, cy, text="3D CAROUSEL", fill="white", font=("Arial", 14, "bold"))
        
        for i in range(min(len(self.photos), 8)):
            angle = (i / 8) * 6.28
            x = cx + int(80 * math.cos(angle))
            y = cy + int(80 * math.sin(angle))
            self.canvas.create_rectangle(x-20, y-20, x+20, y+20, fill=GLASS_COLORS['secondary'], outline="white")

    def launch_3d(self):
        if not self.photos: return messagebox.showwarning("Warning", "Load photos first")
        
        html = self.generate_html()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(html)
            webbrowser.open(f'file://{f.name}')

    def generate_html(self):
        photos_data = []
        for i, p in enumerate(self.photos[:10]): # Limit to 10 for performance
            try:
                with open(p, 'rb') as f: 
                    b64 = base64.b64encode(f.read()).decode('utf-8')
                    photos_data.append(f'data:image/jpeg;base64,{b64}')
            except: pass
            
        # Embed data in HTML template
        return f"""
        <!DOCTYPE html><html><head><style>
            body {{ background: #0f0f1a; display: flex; justify-content: center; align-items: center; height: 100vh; overflow: hidden; }}
            .carousel {{ width: 300px; height: 400px; position: absolute; transform-style: preserve-3d; animation: rot 20s infinite linear; }}
            @keyframes rot {{ from {{ transform: rotateY(0deg); }} to {{ transform: rotateY(360deg); }} }}
            .item {{ position: absolute; width: 300px; height: 400px; background-size: cover; border: 2px solid #00ffcc; box-shadow: 0 0 20px #00ffcc; }}
        </style></head><body>
        <div class="carousel">
            {"".join([f'<div class="item" style="transform: rotateY({i * (360/len(photos_data))}deg) translateZ(400px); background-image: url(\'{d}\');"></div>' for i, d in enumerate(photos_data)])}
        </div></body></html>
        """

class DuplicateView(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.current_duplicates = {}
        self.image_scores = {}
        self.files_to_delete = set()
        
        # Top Bar
        top = ctk.CTkFrame(self, fg_color=GLASS_COLORS['dark'], corner_radius=10)
        top.pack(fill="x", padx=20, pady=20)
        
        self.path_var = ctk.StringVar()
        ctk.CTkEntry(top, textvariable=self.path_var, placeholder_text="Select Folder or Drag & Drop").pack(side="left", fill="x", expand=True, padx=10)
        ctk.CTkButton(top, text="Browse", command=self.browse, width=80).pack(side="left", padx=5)
        self.scan_btn = ctk.CTkButton(top, text="Scan", command=self.start_scan, fg_color=GLASS_COLORS['primary'], width=80)
        self.scan_btn.pack(side="left", padx=5)
        
        self.progress = ctk.CTkProgressBar(top, width=150)
        self.progress.pack(side="left", padx=10)
        self.progress.set(0)

        # Main Content
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Left: List
        self.list_frame = ctk.CTkScrollableFrame(container, width=200, label_text="Groups")
        self.list_frame.pack(side="left", fill="y", padx=(0, 10))
        
        # Right: Gallery
        self.gallery_frame = ctk.CTkFrame(container, fg_color="transparent")
        self.gallery_frame.pack(side="right", fill="both", expand=True)
        self.gallery_msg = ctk.CTkLabel(self.gallery_frame, text="Scan to find duplicates", text_color="gray")
        self.gallery_msg.pack(expand=True)
        
        # Controls (Bottom)
        self.controls = ctk.CTkFrame(self, fg_color="transparent")
        self.controls.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkButton(self.controls, text="Keep Smart Best", command=lambda: self.select_smart("smart"), fg_color="#2ecc71").pack(side="left", padx=5)
        ctk.CTkButton(self.controls, text="Keep Newest", command=lambda: self.select_smart("newest")).pack(side="left", padx=5)
        ctk.CTkButton(self.controls, text="Keep Oldest", command=lambda: self.select_smart("oldest")).pack(side="left", padx=5)
        
        self.del_btn = ctk.CTkButton(self.controls, text="Delete Selected", fg_color="#e74c3c", state="disabled", command=self.confirm_del)
        self.del_btn.pack(side="right", padx=5)

    def browse(self):
        p = filedialog.askdirectory()
        if p: self.path_var.set(p)

    def set_path_scan(self, path):
        """For drag and drop startup"""
        self.path_var.set(path)
        self.start_scan()

    def start_scan(self):
        path = self.path_var.get()
        if not path: return
        
        # Clear UI
        for w in self.list_frame.winfo_children(): w.destroy()
        self.current_duplicates = {}
        self.gallery_msg.configure(text="Scanning...")
        
        # Thread Scan
        t = threading.Thread(target=self._scan_thread, args=(path,))
        t.start()

    def _scan_thread(self, path):
        hashes = {}
        phashes = {}
        files = []
        
        # Collect files
        for root, _, f in os.walk(path):
            for file in f:
                if file.lower().endswith(SUPPORTED_EXTENSIONS):
                    fp = os.path.join(root, file)
                    files.append(fp)
        
        total = len(files)
        for i, fp in enumerate(files):
            # Update Progress
            if i % 10 == 0: self.after(0, self.progress.set, i/total)
            
            # Hash
            md5 = PhotoUtils.get_file_hash(fp)
            if md5: 
                if md5 not in hashes: hashes[md5] = []
                hashes[md5].append(fp)
            
            ph = PhotoUtils.calculate_phash(fp)
            if ph:
                if ph not in phashes: phashes[ph] = []
                phashes[ph].append(fp)
                
            self.image_scores[fp] = PhotoUtils.calculate_score(fp)

        self.progress.set(1)
        # Filter duplicates
        dups = {k:v for k,v in hashes.items() if len(v) > 1}
        if HAS_IMAGEHASH:
            for k,v in phashes.items():
                if len(v) > 1: dups[f"sim_{k}"] = v
                
        self.current_duplicates = dups
        self.after(0, self._finish_scan)

    def _finish_scan(self):
        self.gallery_msg.pack_forget()
        for idx, (h, paths) in enumerate(self.current_duplicates.items()):
            btn = ctk.CTkButton(self.list_frame, text=f"Group {idx+1} ({len(paths)})", 
                               command=lambda p=paths, i=idx: self.load_group(p, i))
            btn.pack(fill="x", pady=2, padx=5)

    def load_group(self, paths, idx):
        self.files_to_delete = set()
        # Clear gallery
        for w in self.gallery_frame.winfo_children(): w.destroy()
        
        # Grid
        grid = ctk.CTkFrame(self.gallery_frame, fg_color="transparent")
        grid.pack(fill="both", expand=True)
        
        cols = min(3, len(paths))
        for i, p in enumerate(paths):
            row, col = i // cols, i % cols
            self._create_card(grid, p, row, col)
            
        self.del_btn.configure(state="normal")

    def _create_card(self, parent, path, r, c):
        f = ctk.CTkFrame(parent, fg_color=GLASS_COLORS['dark'], corner_radius=10, border_width=2)
        f.grid(row=r, column=c, padx=10, pady=10, sticky="nsew")
        
        # Score
        s = self.image_scores.get(path, 0)
        c_color = PhotoUtils.get_score_color(s)
        
        # Image
        try:
            img = Image.open(path)
            img.thumbnail((200, 200), Image.Resampling.LANCZOS)
            ctk_img = ctk.CTkImage(img, size=(200, 200))
            lbl = ctk.CTkLabel(f, image=ctk_img, text="")
            lbl.image = ctk_img
            lbl.pack(pady=10)
        except:
            ctk.CTkLabel(f, text="Error", text_color="red").pack(pady=10)
            
        # Info
        name = os.path.basename(path)
        if len(name) > 20: name = name[:20]+"..."
        ctk.CTkLabel(f, text=name).pack()
        ctk.CTkLabel(f, text=f"Score: {s}", text_color=c_color, font=("Arial", 12, "bold")).pack()
        
        # Selection Logic
        var = ctk.BooleanVar(value=False)
        chk = ctk.CTkCheckBox(f, text="Delete", variable=var, fg_color="#e74c3c",
                             command=lambda p=path, v=var: self._toggle_del(p, v))
        chk.pack(pady=10)
        
        f.path = path
        f.var = var
        f.frame_ref = f

    def _toggle_del(self, path, var):
        if var.get():
            self.files_to_delete.add(path)
            # Find widget to highlight
            for w in self.gallery_frame.winfo_children():
                if hasattr(w, 'path') and w.path == path:
                    w.configure(border_color="#e74c3c")
        else:
            self.files_to_delete.discard(path)
            for w in self.gallery_frame.winfo_children():
                if hasattr(w, 'path') and w.path == path:
                    w.configure(border_color="transparent")

    def select_smart(self, mode):
        widgets = [w for w in self.gallery_frame.winfo_children() if hasattr(w, 'path')]
        if not widgets: return
        
        keep_path = None
        if mode == "smart":
            keep_path = max(widgets, key=lambda w: self.image_scores[w.path]).path
        elif mode == "newest":
            keep_path = max(widgets, key=lambda w: os.path.getmtime(w.path)).path
        elif mode == "oldest":
            keep_path = min(widgets, key=lambda w: os.path.getmtime(w.path)).path
            
        for w in widgets:
            w.var.set(w.path != keep_path)
            self._toggle_del(w.path, w.var)

    def confirm_del(self):
        if not self.files_to_delete: return
        if messagebox.askyesno("Confirm", f"Delete {len(self.files_to_delete)} files?"):
            for p in list(self.files_to_delete):
                try: os.remove(p)
                except: pass
            messagebox.showinfo("Done", "Files deleted.")
            # Reload current view or list
            for w in self.gallery_frame.winfo_children(): w.destroy()

class SortView(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        
        top = ctk.CTkFrame(self, fg_color=GLASS_COLORS['dark'], corner_radius=10)
        top.pack(fill="x", padx=20, pady=20)
        
        self.src = ctk.StringVar()
        self.dst = ctk.StringVar(value=os.path.expanduser("~/Photos/Organized"))
        
        ctk.CTkButton(top, text="📂 Source", command=lambda: self.src.set(filedialog.askdirectory())).pack(side="left", padx=10)
        ctk.CTkLabel(top, textvariable=self.src).pack(side="left", padx=10)
        
        ctk.CTkButton(top, text="📂 Dest", command=lambda: self.dst.set(filedialog.askdirectory())).pack(side="left", padx=10)
        ctk.CTkLabel(top, textvariable=self.dst).pack(side="left", padx=10)
        
        ctk.CTkButton(top, text="Start Sorting", fg_color=GLASS_COLORS['secondary'], command=self.start_sort).pack(side="right", padx=20)

    def start_sort(self):
        src, dst = self.src.get(), self.dst.get()
        if not src or not dst: return
        if not messagebox.askyesno("Confirm", "Move files to organized folders?"): return
        
        def worker():
            count = 0
            for root, _, files in os.walk(src):
                for f in files:
                    if f.lower().endswith(SUPPORTED_EXTENSIONS):
                        p = os.path.join(root, f)
                        try:
                            mtime = os.path.getmtime(p)
                            folder = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m")
                            target = os.path.join(dst, folder)
                            os.makedirs(target, exist_ok=True)
                            shutil.move(p, os.path.join(target, f))
                            count += 1
                        except: pass
            messagebox.showinfo("Done", f"Moved {count} files.")
        
        threading.Thread(target=worker).start()

class SettingsView(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        ctk.CTkLabel(self, text="Settings", font=("Arial", 24)).pack(pady=20)
        ctk.CTkLabel(self, text="Application Theme: Dark Blue (Pro)").pack()
        ctk.CTkLabel(self, text="Version: Hybrid Ultimate 1.0").pack()

# --- MAIN APP ---
class PhotoOrganizerHybrid(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Photo Organizer Ultimate")
        self.geometry("1400x900")
        
        # Grid Layout
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Sidebar
        self.sidebar = ModernSidebar(self, self.navigate_to)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        # Content Area
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)
        
        # Initialize Views
        self.views = {
            'dashboard': DashboardView(self.content),
            'gallery': Gallery3DView(self.content),
            'duplicates': DuplicateView(self.content),
            'sort': SortView(self.content),
            'settings': SettingsView(self.content)
        }
        
        # Start
        self.navigate_to('dashboard')
        
        # Check for drag-drop args after UI loads
        self.after(100, self.handle_startup_args)

    def navigate_to(self, view_name):
        for v in self.views.values(): v.grid_forget()
        self.views[view_name].grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

    def handle_startup_args(self):
        if len(sys.argv) > 1:
            path = sys.argv[1].strip('"').strip("'")
            if os.path.exists(path):
                if os.path.isdir(path):
                    self.navigate_to('dashboard')
                    self.views['dashboard'].update_stats(path)
                    # Auto-scan
                    self.navigate_to('duplicates')
                    self.views['duplicates'].set_path_scan(path)
                else:
                    # If file, take its folder
                    folder = os.path.dirname(path)
                    self.navigate_to('duplicates')
                    self.views['duplicates'].set_path_scan(folder)

if __name__ == "__main__":
    app = PhotoOrganizerHybrid()
    app.mainloop()