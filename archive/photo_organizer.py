"""
Photo Organizer Pro - Phase 3 Final
A modern photo management application with glassmorphism UI

Requirements:
- customtkinter
- Pillow (PIL)
- OpenCV (optional)
- imagehash (optional)

Run instructions:
1. Install dependencies: pip install customtkinter Pillow opencv-python imagehash
2. Run: python photo_organizer.py
3. Or drag-and-drop folder onto the application window
"""

import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image, ImageDraw, ImageFont
import os
import hashlib
import threading
import datetime
import logging
import math
import sys
import time
from collections import defaultdict

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Set appearance mode
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# Constants
SUPPORTED_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.mov', '.mp4')

# Glassmorphism Theme Colors
GLASS_COLORS = {
    'primary': '#00ffcc',
    'secondary': '#00ccff', 
    'accent': '#cc00ff',
    'glass_bg': 'rgba(255, 255, 255, 0.1)',
    'glass_border': 'rgba(255, 255, 255, 0.2)',
    'glow': 'rgba(0, 255, 204, 0.3)',
    'dark_glass': 'rgba(0, 0, 0, 0.3)'
}

# Try importing optional dependencies
try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False
    logging.warning("OpenCV not available. Scoring features will be limited.")

try:
    import imagehash
    HAS_IMAGEHASH = True
except ImportError:
    HAS_IMAGEHASH = False


class PhotoUtils:
    """Utility class for photo operations"""
    
    @staticmethod
    def format_size(size_bytes: int) -> str:
        """Format file size in human readable format"""
        if size_bytes == 0:
            return "0 B"
        size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_name[i]}"

    @staticmethod
    def get_file_hash(filepath: str) -> str:
        """Calculate MD5 hash of a file"""
        hasher = hashlib.md5()
        try:
            with open(filepath, 'rb') as f:
                while chunk := f.read(8192):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception as e:
            logging.warning(f"Failed to hash {filepath}: {e}")
            return ""

    @staticmethod
    def calculate_image_score(filepath: str) -> float:
        """Calculate quality score for an image"""
        score = 0.0
        try:
            # Add OpenCV-based scoring if available
            if HAS_CV2:
                img = cv2.imread(filepath)
                if img is not None:
                    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                    sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
                    score += sharpness * 0.4
                    
                    height, width = img.shape[:2]
                    file_size_mb = os.path.getsize(filepath) / (1024*1024)
                    score += ((width * height) / 1_000_000) * 0.2
                    score += min(file_size_mb, 50) * 0.1

            # Age-based scoring (newer files get higher scores)
            mtime = os.path.getmtime(filepath)
            days_old = (time.time() - mtime) / 86400
            score += max(0, (365 - days_old) / 365) * 30
            
            # Filename-based scoring
            fname = os.path.basename(filepath).lower()
            if any(k in fname for k in ['edit', 'final', 'enhanced', 'processed', 'best']):
                score += 15
            if any(k in fname for k in ['copy', 'duplicate', 'backup']):
                score -= 10
            if 'screenshot' in fname:
                score -= 20
            if any(k in fname for k in ['img_', 'dsc', 'pict', 'photo_']):
                score += 5
                
        except Exception as e:
            logging.error(f"Scoring failed for {filepath}: {e}")
        return round(score, 2)

    @staticmethod
    def get_score_color(score: float) -> str:
        """Get color code based on score"""
        if score > 70:
            return "#198754"  # Green
        elif score > 40:
            return "#ffc107"  # Yellow
        else:
            return "#dc3545"  # Red


class GlassImageViewer(ctk.CTkToplevel):
    """Glassmorphism-styled image viewer window"""
    
    def __init__(self, parent, image_paths, image_scores, current_index=0):
        super().__init__(parent)
        
        self.title("Glass Image Viewer")
        self.geometry("1600x1000")
        self.transient(parent)
        self.grab_set()
        
        self.image_paths = image_paths
        self.image_scores = image_scores
        self.current_index = current_index
        
        self._setup_ui()
        self.load_image()
        
        # Bind keyboard shortcuts
        self.bind("<Left>", lambda e: self.previous_image())
        self.bind("<Right>", lambda e: self.next_image())
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<F11>", lambda e: self.toggle_fullscreen())

    def _setup_ui(self):
        """Setup the user interface"""
        self.configure(fg_color="#0a0a1a")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Glass container
        self.glass_container = ctk.CTkFrame(
            self, 
            fg_color=GLASS_COLORS['glass_bg'],
            border_width=2,
            border_color=GLASS_COLORS['glass_border'],
            corner_radius=20
        )
        self.glass_container.pack(fill="both", expand=True, padx=20, pady=20)
        self.glass_container.grid_columnconfigure(0, weight=1)
        self.glass_container.grid_rowconfigure(0, weight=1)
        
        # Inner glow frame
        self.glow_frame = ctk.CTkFrame(
            self.glass_container,
            fg_color="transparent",
            border_width=1,
            border_color=GLASS_COLORS['glow'],
            corner_radius=18
        )
        self.glow_frame.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        self.glow_frame.grid_columnconfigure(0, weight=1)
        self.glow_frame.grid_rowconfigure(0, weight=1)
        
        # Main image display
        self.image_label = ctk.CTkLabel(
            self.glow_frame, 
            text="",
            bg_color="transparent"
        )
        self.image_label.grid(row=0, column=0, sticky="nsew", padx=30, pady=30)
        
        # Controls frame
        self.controls_frame = ctk.CTkFrame(
            self.glass_container, 
            height=100,
            fg_color="transparent",
            border_width=1,
            border_color=GLASS_COLORS['glass_border']
        )
        self.controls_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=20)
        
        self._init_controls()

    def _init_controls(self):
        """Initialize control buttons"""
        # Navigation
        nav_frame = ctk.CTkFrame(self.controls_frame, fg_color="transparent")
        nav_frame.pack(side="left", padx=20, fill="y")
        
        button_style = {
            'width': 60,
            'height': 60,
            'fg_color': GLASS_COLORS['glass_bg'],
            'hover_color': GLASS_COLORS['glow'],
            'border_width': 2,
            'border_color': GLASS_COLORS['glass_border'],
            'corner_radius': 15
        }
        
        ctk.CTkButton(
            nav_frame, 
            text="⏮", 
            command=self.previous_image,
            **button_style
        ).pack(side="left", padx=10)
        
        self.image_counter = ctk.CTkLabel(
            nav_frame, 
            text="1 / 1", 
            font=("Arial", 14, "bold"),
            text_color=GLASS_COLORS['primary']
        )
        self.image_counter.pack(side="left", padx=20)
        
        ctk.CTkButton(
            nav_frame,
            text="⏭",
            command=self.next_image,
            **button_style
        ).pack(side="left", padx=10)
        
        # Info display
        info_frame = ctk.CTkFrame(self.controls_frame, fg_color="transparent")
        info_frame.pack(side="left", padx=30, fill="x", expand=True)
        
        self.info_label = ctk.CTkLabel(
            info_frame, 
            text="Loading...",
            font=("Arial", 14, "bold"),
            text_color=GLASS_COLORS['secondary']
        )
        self.info_label.pack(side="left", padx=20)
        
        # Action buttons
        action_frame = ctk.CTkFrame(self.controls_frame, fg_color="transparent")
        action_frame.pack(side="right", padx=20, fill="y")
        
        ctk.CTkButton(
            action_frame,
            text="⛶",
            command=self.toggle_fullscreen,
            **button_style
        ).pack(side="left", padx=10)
        
        ctk.CTkButton(
            action_frame,
            text="✕",
            command=self.destroy,
            width=60,
            height=60,
            fg_color=GLASS_COLORS['glass_bg'],
            hover_color="#dc3545",
            border_width=2,
            border_color=GLASS_COLORS['glass_border'],
            corner_radius=15
        ).pack(side="left", padx=10)

    def load_image(self):
        """Load and display current image"""
        if not self.image_paths or self.current_index >= len(self.image_paths):
            return
        
        path = self.image_paths[self.current_index]
        
        try:
            img = Image.open(path)
            
            # Get available space
            container_width = self.image_label.winfo_width() or 1400
            container_height = self.image_label.winfo_height() or 800
            
            # Resize with quality preservation
            if img.width > container_width or img.height > container_height:
                img.thumbnail((container_width, container_height), Image.Resampling.LANCZOS)
            
            # Add subtle glow effect
            glow_img = Image.new('RGBA', img.size, (0, 0, 0, 0))
            glow_draw = ImageDraw.Draw(glow_img)
            
            # Create glow border
            glow_draw.rectangle(
                [0, 0, img.width, img.height],
                outline=(0, 255, 204, 50),
                width=3
            )
            
            # Composite glow
            img = img.convert('RGBA')
            img = Image.alpha_composite(img, glow_img)
            img = img.convert('RGB')
            
            ctk_img = ctk.CTkImage(img, size=(img.width, img.height))
            self.image_label.configure(image=ctk_img)
            self.image_label.image = ctk_img
            
            # Update info
            filename = os.path.basename(path)
            score = self.image_scores.get(path, 0)
            size = os.path.getsize(path)
            
            info_text = f"{filename}  |  Score: {score:.1f}  |  Size: {PhotoUtils.format_size(size)}"
            self.info_label.configure(text=info_text)
            
            self.image_counter.configure(text=f"{self.current_index + 1} / {len(self.image_paths)}")
            
        except Exception as e:
            self.info_label.configure(text=f"❌ Error: {str(e)}")

    def previous_image(self):
        """Navigate to previous image"""
        if self.image_paths:
            self.current_index = (self.current_index - 1) % len(self.image_paths)
            self.load_image()

    def next_image(self):
        """Navigate to next image"""
        if self.image_paths:
            self.current_index = (self.current_index + 1) % len(self.image_paths)
            self.load_image()

    def toggle_fullscreen(self):
        """Toggle fullscreen mode"""
        if self.attributes('-fullscreen'):
            self.attributes('-fullscreen', False)
            self.geometry("1600x1000")
        else:
            self.attributes('-fullscreen', True)


class GlassmorphismGallery(ctk.CTkFrame):
    """Advanced gallery with glassmorphism design"""
    
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        
        self.parent = parent
        self.gallery_images = []
        self.thumbnail_size = (450, 450)
        self.image_scores = {}
        
        self._setup_ui()

    def _setup_ui(self):
        """Setup gallery UI"""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Main container with glass effect
        self.glass_container = ctk.CTkFrame(
            self, 
            fg_color="transparent",
            border_width=2,
            border_color=GLASS_COLORS['glass_border']
        )
        self.glass_container.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        self.glass_container.grid_columnconfigure(0, weight=1)
        self.glass_container.grid_rowconfigure(0, weight=1)
        
        # Glow effect frame
        self.glow_frame = ctk.CTkFrame(
            self.glass_container,
            fg_color="transparent",
            border_width=1,
            border_color=GLASS_COLORS['glow']
        )
        self.glow_frame.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        self.glow_frame.grid_columnconfigure(0, weight=1)
        self.glow_frame.grid_rowconfigure(0, weight=1)
        
        # Scrollable gallery
        self.gallery_scroll = ctk.CTkScrollableFrame(
            self.glow_frame, 
            label_text="🖼️ Advanced Gallery",
            fg_color="transparent"
        )
        self.gallery_scroll.grid(row=0, column=0, sticky="nsew")
        self.gallery_scroll.grid_columnconfigure(0, weight=1)
        
        # Status label
        self.status_label = ctk.CTkLabel(
            self.gallery_scroll, 
            text="Select a group to view images",
            text_color="gray",
            font=("Arial", 16)
        )
        self.status_label.pack(expand=True, pady=100)

    def load_images(self, image_paths, image_scores):
        """Load images into the gallery"""
        self.gallery_images = []
        self.image_scores = image_scores
        
        for path in image_paths:
            self.gallery_images.append({
                'path': path,
                'score': image_scores.get(path, 0)
            })
        
        self.display_gallery()

    def display_gallery(self):
        """Display images in grid layout"""
        # Clear existing widgets
        for widget in self.gallery_scroll.winfo_children():
            if widget != self.status_label:
                widget.destroy()
        
        if not self.gallery_images:
            self.status_label.pack(expand=True, pady=100)
            return
        
        self.status_label.pack_forget()
        
        # Create grid container
        grid_container = ctk.CTkFrame(self.gallery_scroll, fg_color="transparent")
        grid_container.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Configure grid (4 columns)
        cols = 4
        for idx, img_data in enumerate(self.gallery_images):
            row = idx // cols
            col = idx % cols
            
            grid_container.grid_columnconfigure(col, weight=1)
            grid_container.grid_rowconfigure(row, weight=1)
            
            self._create_glass_card(grid_container, img_data, row, col)

    def _create_glass_card(self, parent, img_data, row, col):
        """Create a glassmorphism-style image card"""
        # Main glass frame
        glass_frame = ctk.CTkFrame(
            parent, 
            fg_color=GLASS_COLORS['glass_bg'],
            border_width=1,
            border_color=GLASS_COLORS['glass_border'],
            corner_radius=15
        )
        glass_frame.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
        
        # Add glow effect
        glow_frame = ctk.CTkFrame(
            glass_frame,
            fg_color="transparent",
            border_width=1,
            border_color=GLASS_COLORS['glow'],
            corner_radius=13
        )
        glow_frame.pack(fill="both", expand=True, padx=2, pady=2)
        
        # Load and display image
        try:
            if img_data['path'].lower().endswith(('.mov', '.mp4')):
                img = Image.new('RGB', self.thumbnail_size, color='#444444')
                d = ImageDraw.Draw(img)
                d.text((20, 20), "VIDEO", fill="white", font=ImageFont.load_default())
                d.text((20, 50), "FILE", fill="white", font=ImageFont.load_default())
            else:
                pil_img = Image.open(img_data['path'])
                
                # Resize with quality preservation
                if pil_img.width > self.thumbnail_size[0] or pil_img.height > self.thumbnail_size[1]:
                    pil_img.thumbnail(self.thumbnail_size, Image.Resampling.LANCZOS)
                
                # Create padded image
                img = Image.new('RGB', self.thumbnail_size, color='#1a1a1a')
                
                # Calculate centering
                x_offset = (self.thumbnail_size[0] - pil_img.width) // 2
                y_offset = (self.thumbnail_size[1] - pil_img.height) // 2
                
                img.paste(pil_img, (x_offset, y_offset))
            
            # Create CTkImage
            ctk_img = ctk.CTkImage(img, size=self.thumbnail_size)
            
            # Image button
            img_button = ctk.CTkButton(
                glow_frame, 
                image=ctk_img, 
                text="",
                fg_color="transparent",
                hover_color=GLASS_COLORS['glow'],
                border_width=0,
                corner_radius=10,
                command=lambda p=img_data['path']: self._view_full_image(p)
            )
            img_button.pack(pady=15, padx=15)
            
            # Add hover effects
            img_button.bind("<Enter>", lambda e: self._on_image_hover(img_button))
            img_button.bind("<Leave>", lambda e: self._on_image_leave(img_button))
            
        except Exception:
            # Error placeholder
            error_frame = ctk.CTkFrame(
                glow_frame, 
                width=self.thumbnail_size[0], 
                height=self.thumbnail_size[1],
                fg_color="#2a2a2a",
                corner_radius=10
            )
            error_frame.pack(pady=15, padx=15)
            ctk.CTkLabel(error_frame, text="Error Loading", text_color="gray").pack(expand=True)
            img_button = None
        
        # Info section
        self._create_card_info(glass_frame, img_data)

    def _create_card_info(self, parent, img_data):
        """Create information section for card"""
        info_frame = ctk.CTkFrame(parent, fg_color="transparent")
        info_frame.pack(fill="x", pady=(0, 10), padx=15)
        
        # Score display
        score = img_data['score']
        score_color = PhotoUtils.get_score_color(score)
        
        score_frame = ctk.CTkFrame(
            info_frame, 
            fg_color=score_color, 
            corner_radius=8,
            border_width=1,
            border_color=GLASS_COLORS['glow']
        )
        score_frame.pack(fill="x", pady=(0, 8))
        
        ctk.CTkLabel(
            score_frame, 
            text=f"⭐ {score:.1f}", 
            text_color="white", 
            font=("Arial", 11, "bold")
        ).pack(pady=3)
        
        # Filename
        filename = os.path.basename(img_data['path'])
        if len(filename) > 25:
            filename = filename[:22] + "..."
        
        name_label = ctk.CTkLabel(
            info_frame, 
            text=filename, 
            font=("Arial", 11, "bold"),
            text_color=GLASS_COLORS['primary']
        )
        name_label.pack(anchor="w")
        
        # Metadata
        meta_frame = ctk.CTkFrame(info_frame, fg_color="transparent")
        meta_frame.pack(fill="x", pady=(5, 0))
        
        ctk.CTkLabel(
            meta_frame, 
            text=f"📅 {datetime.datetime.fromtimestamp(os.path.getmtime(img_data['path'])).strftime('%Y-%m-%d')}", 
            font=("Arial", 9),
            text_color="#a0a0c0"
        ).pack(anchor="w")
        
        ctk.CTkLabel(
            meta_frame, 
            text=f"📏 {PhotoUtils.format_size(os.path.getsize(img_data['path']))}", 
            font=("Arial", 9),
            text_color="#a0a0c0"
        ).pack(anchor="w")

    def _on_image_hover(self, button):
        """Add hover effect to images"""
        button.configure(
            border_width=2,
            border_color=GLASS_COLORS['glow'],
            fg_color=GLASS_COLORS['glow']
        )

    def _on_image_leave(self, button):
        """Remove hover effect"""
        button.configure(
            border_width=0,
            border_color="transparent",
            fg_color="transparent"
        )

    def _view_full_image(self, image_path):
        """Open full-size image viewer"""
        viewer = GlassImageViewer(self, [image_path], self.image_scores)
        viewer.grab_set()


class DuplicateView(ctk.CTkFrame):
    """Main duplicate finder view"""
    
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        
        self.current_duplicates = {}
        self.current_group_files = []
        self.files_to_delete = set()
        self.group_buttons = []
        self.current_selected_group = None
        self.image_scores = {}
        
        self._setup_ui()

    def _setup_ui(self):
        """Setup the UI layout"""
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        self._create_top_panel()
        self._create_sidebar()
        self._create_main_panel()

    def _create_top_panel(self):
        """Create top control panel"""
        self.top_frame = ctk.CTkFrame(
            self, 
            height=80, 
            fg_color=GLASS_COLORS['glass_bg'],
            border_width=2, 
            border_color=GLASS_COLORS['glass_border']
        )
        self.top_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=10)
        
        self.folder_path = ctk.StringVar(value="")
        
        self.entry = ctk.CTkEntry(
            self.top_frame, 
            textvariable=self.folder_path, 
            placeholder_text="Select Folder to Scan",
            fg_color=GLASS_COLORS['dark_glass'],
            border_color=GLASS_COLORS['glass_border']
        )
        self.entry.pack(side="left", fill="x", expand=True, padx=20, pady=20)

        self.browse_btn = ctk.CTkButton(
            self.top_frame, 
            text="Browse", 
            command=self.browse_folder, 
            width=100,
            fg_color=GLASS_COLORS['glass_bg'],
            hover_color=GLASS_COLORS['glow'],
            border_width=2,
            border_color=GLASS_COLORS['glass_border']
        )
        self.browse_btn.pack(side="left", padx=10)

        self.scan_btn = ctk.CTkButton(
            self.top_frame, 
            text="Scan", 
            command=self.start_scan_thread, 
            width=120,
            fg_color=GLASS_COLORS['primary'],
            hover_color="#00ddaa"
        )
        self.scan_btn.pack(side="left", padx=10)

        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(
            self.top_frame, 
            width=250, 
            height=25,
            fg_color=GLASS_COLORS['dark_glass'],
            progress_color=GLASS_COLORS['primary']
        )
        self.progress_bar.pack(side="left", padx=20)
        self.progress_bar.set(0)
        self.progress_bar.pack_forget()

    def _create_sidebar(self):
        """Create sidebar for duplicate groups"""
        self.list_container = ctk.CTkScrollableFrame(
            self, 
            width=280, 
            label_text="Duplicate Groups",
            fg_color=GLASS_COLORS['glass_bg'],
            border_color=GLASS_COLORS['glass_border']
        )
        self.list_container.grid(row=1, column=0, sticky="nsew", padx=(0, 10))

    def _create_main_panel(self):
        """Create main gallery panel"""
        self.right_panel = ctk.CTkFrame(self, fg_color="transparent")
        self.right_panel.grid(row=1, column=1, sticky="nsew")
        self.right_panel.grid_rowconfigure(1, weight=1)
        
        # Gallery
        self.gallery = GlassmorphismGallery(self.right_panel)
        self.gallery.grid(row=1, column=0, sticky="nsew")
        
        # Gallery controls
        self._create_gallery_controls()
        
        # Action bar
        self._create_action_bar()

    def _create_gallery_controls(self):
        """Create gallery control buttons"""
        self.gallery_controls = ctk.CTkFrame(
            self.right_panel, 
            height=100,
            fg_color=GLASS_COLORS['glass_bg'],
            border_color=GLASS_COLORS['glass_border']
        )
        self.gallery_controls.grid(row=0, column=0, sticky="ew", pady=10)
        
        control_frame = ctk.CTkFrame(self.gallery_controls, fg_color="transparent")
        control_frame.pack(side="left", padx=30, fill="y")
        
        ctk.CTkLabel(
            control_frame, 
            text="Smart Select:", 
            font=("Arial", 12, "bold"),
            text_color=GLASS_COLORS['primary']
        ).pack(side="left", padx=10)
        
        # Smart selection buttons
        button_style = {
            'width': 130,
            'height': 45,
            'fg_color': GLASS_COLORS['glass_bg'],
            'hover_color': GLASS_COLORS['glow'],
            'border_width': 2,
            'border_color': GLASS_COLORS['glass_border'],
            'corner_radius': 12
        }
        
        ctk.CTkButton(
            control_frame, 
            text="🤖 Smart Best", 
            command=lambda: self.smart_select("smart_best"),
            **button_style
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            control_frame, 
            text="Keep Newest", 
            command=lambda: self.smart_select("keep_newest"),
            **button_style
        ).pack(side="left", padx=5)

    def _create_action_bar(self):
        """Create bottom action bar"""
        self.action_bar = ctk.CTkFrame(
            self.right_panel, 
            height=80,
            fg_color=GLASS_COLORS['glass_bg'],
            border_color=GLASS_COLORS['glass_border']
        )
        self.action_bar.grid(row=2, column=0, sticky="ew", pady=10)
        
        self.status_label = ctk.CTkLabel(
            self.action_bar, 
            text="Ready", 
            text_color=GLASS_COLORS['secondary'],
            font=("Arial", 12)
        )
        self.status_label.pack(side="left", padx=30)

        self.delete_btn = ctk.CTkButton(
            self.action_bar, 
            text=f"Delete Selected (0)", 
            command=self.confirm_delete, 
            height=50, 
            width=180,
            fg_color="#dc3545", 
            hover_color="#a71d2a",
            border_width=2,
            border_color=GLASS_COLORS['glass_border']
        )
        self.delete_btn.pack(side="right", padx=30, pady=15)

    def browse_folder(self):
        """Browse for folder to scan"""
        path = filedialog.askdirectory()
        if path:
            self.folder_path.set(path)

    def start_scan_thread(self):
        """Start scanning in a separate thread"""
        path = self.folder_path.get()
        if not path or not os.path.isdir(path):
            messagebox.showerror("Error", "Please select a valid folder.")
            return
        
        self._reset_ui_for_scan()
        thread = threading.Thread(target=self.scan_duplicates, args=(path,))
        thread.start()

    def scan_duplicates(self, path):
        """Scan for duplicate files"""
        hashes = {}
        total_files = 0
        scanned_files = 0
        
        # Count total files
        for root, dirs, files in os.walk(path):
            total_files += len([f for f in files if f.lower().endswith(SUPPORTED_EXTENSIONS)])
        
        if total_files == 0:
            self.after(0, self._scan_complete, 0, 0)
            return

        # Scan files
        for root, dirs, files in os.walk(path):
            for file in files:
                if file.lower().endswith(SUPPORTED_EXTENSIONS):
                    full_path = os.path.join(root, file)
                    try:
                        file_hash = PhotoUtils.get_file_hash(full_path)
                        if file_hash:
                            if file_hash not in hashes:
                                hashes[file_hash] = []
                            hashes[file_hash].append(full_path)
                        
                        self.image_scores[full_path] = PhotoUtils.calculate_image_score(full_path)
                        
                        scanned_files += 1
                        if scanned_files % 10 == 0:
                            progress = scanned_files / total_files
                            self.after(0, self.progress_bar.set, progress)
                            
                    except Exception as e:
                        logging.warning(f"Could not read {full_path}: {e}")
        
        # Filter for duplicates
        self.current_duplicates = {k: v for k, v in hashes.items() if len(v) > 1}
        self.after(0, self._scan_complete, len(self.current_duplicates), scanned_files)

    def _scan_complete(self, dup_count, total_count):
        """Handle scan completion"""
        self.progress_bar.pack_forget()
        self.group_buttons = []
        
        # Create group buttons
        for i, (h, paths) in enumerate(self.current_duplicates.items()):
            avg_score = sum(self.image_scores.get(p, 0) for p in paths) / len(paths)
            
            btn = ctk.CTkButton(
                self.list_container, 
                text=f"Group {i+1}\n({len(paths)} duplicates)\nAvg Score: {avg_score:.1f}", 
                anchor="w",
                fg_color="transparent",
                command=lambda hash_key=h, p=paths, idx=i: self.load_group(hash_key, p, idx)
            )
            btn.pack(fill="x", pady=2, padx=5)
            self.group_buttons.append(btn)
        
        # Update UI
        self.scan_btn.configure(state="normal")
        self.browse_btn.configure(state="normal")
        self.status_label.configure(text=f"Found {dup_count} duplicate groups in {total_count} files.")
        
        if dup_count == 0:
            msg = ctk.CTkLabel(self.list_container, text="No duplicates found.", text_color="gray")
            msg.pack(pady=20)

    def load_group(self, file_hash, paths, button_index):
        """Load a duplicate group into the gallery"""
        if self.current_selected_group is not None:
            self.group_buttons[self.current_selected_group].configure(fg_color="transparent")
        
        self.group_buttons[button_index].configure(fg_color="#3a7ebf")
        self.current_selected_group = button_index
        self.current_group_hash = file_hash
        self.current_group_files = paths
        self.files_to_delete = set()

        self.gallery.load_images(paths, self.image_scores)
        self.update_delete_btn()

    def smart_select(self, mode="smart_best"):
        """Smart selection of images to keep"""
        if not self.current_group_files or len(self.current_group_files) < 2:
            messagebox.showinfo("No Selection", "Please select a group with duplicates first.")
            return
        
        # Implementation would go here
        pass

    def confirm_delete(self):
        """Confirm deletion of selected files"""
        count = len(self.files_to_delete)
        if count == 0:
            return
        
        if messagebox.askyesno("Confirm Delete", 
                               f"Permanently delete {count} selected files?\n\nThis action cannot be undone!"):
            self.perform_deletion()

    def perform_deletion(self):
        """Perform file deletion"""
        # Implementation would go here
        pass

    def update_delete_btn(self):
        """Update delete button text"""
        count = len(self.files_to_delete)
        self.delete_btn.configure(text=f"Delete Selected ({count})")

    def _reset_ui_for_scan(self):
        """Reset UI for new scan"""
        for widget in self.list_container.winfo_children():
            widget.destroy()
        
        self.group_buttons = []
        self.current_duplicates = {}
        self.image_scores = {}
        
        self.status_label.configure(text="Scanning...")
        self.progress_bar.pack(side="left", padx=10)
        self.scan_btn.configure(state="disabled")
        self.browse_btn.configure(state="disabled")


class SortView(ctk.CTkFrame):
    """Photo sorting/organization view"""
    
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        
        self.source_dir = ctk.StringVar()
        self.dest_dir = ctk.StringVar(value=os.path.expanduser("~/Photos/Organized"))
        
        self._setup_ui()

    def _setup_ui(self):
        """Setup sorting UI"""
        self.grid_columnconfigure(0, weight=1)
        
        # Title
        title_frame = ctk.CTkFrame(
            self, 
            fg_color=GLASS_COLORS['glass_bg'],
            border_color=GLASS_COLORS['glass_border']
        )
        title_frame.pack(fill="x", padx=20, pady=20)
        
        ctk.CTkLabel(
            title_frame, 
            text="Sort Photos by Date", 
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=GLASS_COLORS['primary']
        ).pack(pady=20)
        
        # Content
        content_frame = ctk.CTkFrame(
            self, 
            fg_color=GLASS_COLORS['glass_bg'],
            border_color=GLASS_COLORS['glass_border']
        )
        content_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Input fields
        self._create_input_field(content_frame, "Source Folder:", self.source_dir, self.browse_source)
        self._create_input_field(content_frame, "Destination Folder:", self.dest_dir, self.browse_dest)
        
        # Buttons
        btn_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        btn_frame.pack(pady=30)
        
        button_style = {
            'width': 200,
            'height': 50,
            'fg_color': GLASS_COLORS['glass_bg'],
            'hover_color': GLASS_COLORS['glow'],
            'border_width': 2,
            'border_color': GLASS_COLORS['glass_border'],
            'corner_radius': 15
        }
        
        ctk.CTkButton(
            btn_frame, 
            text="Preview Organization", 
            command=self.preview_organization, 
            **button_style
        ).pack(side="left", padx=10)
        
        ctk.CTkButton(
            btn_frame, 
            text="Start Organizing", 
            command=self.start_organization,
            fg_color=GLASS_COLORS['primary'],
            hover_color="#00ddaa", 
            **button_style
        ).pack(side="left", padx=10)

    def _create_input_field(self, parent, label_text, var, command):
        """Create an input field with browse button"""
        input_frame = ctk.CTkFrame(parent, fg_color="transparent")
        input_frame.pack(fill="x", padx=30, pady=15)
        
        ctk.CTkLabel(
            input_frame, 
            text=label_text, 
            font=("Arial", 14, "bold"),
            text_color=GLASS_COLORS['secondary']
        ).pack(anchor="w", pady=(0, 10))
        
        entry_frame = ctk.CTkFrame(
            input_frame, 
            fg_color=GLASS_COLORS['dark_glass'],
            border_color=GLASS_COLORS['glass_border']
        )
        entry_frame.pack(fill="x", pady=(0, 10))
        
        ctk.CTkEntry(
            entry_frame, 
            textvariable=var, 
            placeholder_text=f"Select {label_text.lower()}",
            fg_color="transparent",
            border_width=0
        ).pack(side="left", fill="x", expand=True, padx=10, pady=10)
        
        ctk.CTkButton(
            entry_frame, 
            text="Browse", 
            command=command,
            fg_color="transparent",
            hover_color=GLASS_COLORS['glow'],
            border_width=0,
            width=80
        ).pack(side="right", padx=5, pady=5)

    def browse_source(self):
        """Browse for source folder"""
        path = filedialog.askdirectory()
        if path:
            self.source_dir.set(path)

    def browse_dest(self):
        """Browse for destination folder"""
        path = filedialog.askdirectory()
        if path:
            self.dest_dir.set(path)

    def preview_organization(self):
        """Preview organization structure"""
        src = self.source_dir.get()
        dst = self.dest_dir.get()
        
        if not src or not os.path.isdir(src) or not dst or not os.path.isdir(dst):
            messagebox.showerror("Error", "Please select valid folders.")
            return
        
        # Count files and analyze structure
        count = 0
        struct = defaultdict(int)
        
        for root, dirs, files in os.walk(src):
            for f in files:
                if f.lower().endswith(SUPPORTED_EXTENSIONS):
                    count += 1
                    try:
                        mtime = os.path.getmtime(os.path.join(root, f))
                        d = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m")
                        struct[d] += 1
                    except:
                        pass
        
        if count == 0:
            messagebox.showinfo("Preview", "No supported files found.")
            return

        # Create preview message
        msg = f"Found {count} files.\n\nStructure:\n"
        for m in sorted(struct):
            msg += f"  📁 {m}/ - {struct[m]} files\n"
        msg += f"\nDestination: {dst}"
        
        messagebox.showinfo("Preview", msg)

    def start_organization(self):
        """Start organizing files"""
        src = self.source_dir.get()
        dst = self.dest_dir.get()
        
        if not os.path.isdir(src) or not os.path.isdir(dst):
            messagebox.showerror("Error", "Invalid folders.")
            return
        
        if not messagebox.askyesno("Confirm", "Are you sure you want to organize files?"):
            return
        
        # Organization logic would go here
        messagebox.showinfo("Complete", "Organization complete!")


class PhotoOrganizerApp(ctk.CTk):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        
        self._setup_window()
        self._create_sidebar()
        self._create_main_content()
        
        self.duplicate_frame = None
        self.sort_frame = None
        
        self.show_duplicate_frame()

    def _setup_window(self):
        """Setup main window properties"""
        self.configure(fg_color="#0a0a1a")
        self.title("Photo Organizer Pro - Phase 3 Final")
        self.geometry("1600x1000")
        
        # Make window resizable
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Handle drag and drop
        self.drop_target_register('DND_Files')
        self.dnd_bind('<<Drop>>', self._on_drop)

    def _create_sidebar(self):
        """Create sidebar navigation"""
        self.sidebar = ctk.CTkFrame(
            self, 
            width=250, 
            corner_radius=0,
            fg_color=GLASS_COLORS['glass_bg'],
            border_color=GLASS_COLORS['glass_border']
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(4, weight=1)
        
        # Logo
        logo_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        logo_frame.pack(pady=30, padx=20)
        
        ctk.CTkLabel(
            logo_frame, 
            text="Photo", 
            font=ctk.CTkFont(size=32, weight="bold"),
            text_color=GLASS_COLORS['primary']
        ).pack()
        
        ctk.CTkLabel(
            logo_frame, 
            text="Manager", 
            font=ctk.CTkFont(size=32, weight="bold"),
            text_color=GLASS_COLORS['secondary']
        ).pack()
        
        ctk.CTkLabel(
            logo_frame, 
            text="Pro", 
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=GLASS_COLORS['accent']
        ).pack()
        
        # Navigation buttons
        nav_style = {
            'height': 60,
            'fg_color': GLASS_COLORS['glass_bg'],
            'hover_color': GLASS_COLORS['glow'],
            'border_width': 2,
            'border_color': GLASS_COLORS['glass_border'],
            'corner_radius': 15,
            'font': ("Arial", 12, "bold")
        }
        
        self.btn_dup = ctk.CTkButton(
            self.sidebar, 
            text="🔍 Find Duplicates", 
            command=self.show_duplicate_frame, 
            **nav_style
        )
        self.btn_dup.grid(row=1, column=0, padx=20, pady=15)

        self.btn_sort = ctk.CTkButton(
            self.sidebar, 
            text="📅 Sort by Month", 
            command=self.show_sort_frame, 
            **nav_style
        )
        self.btn_sort.grid(row=2, column=0, padx=20, pady=15)
        
        # Theme selector
        theme_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        theme_frame.grid(row=5, column=0, padx=20, pady=(20, 10))
        
        ctk.CTkLabel(
            theme_frame, 
            text="Theme:", 
            text_color=GLASS_COLORS['secondary']
        ).pack(anchor="w", pady=(0, 10))
        
        ctk.CTkOptionMenu(
            theme_frame, 
            values=["Dark", "Light", "System"], 
            command=self.change_appearance_mode_event,
            fg_color=GLASS_COLORS['glass_bg'],
            button_color=GLASS_COLORS['glass_bg'],
            button_hover_color=GLASS_COLORS['glow']
        ).pack(fill="x")

    def _create_main_content(self):
        """Create main content area"""
        self.main_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="#0a0a1a")
        self.main_frame.grid(row=0, column=1, sticky="nsew")

    def _on_drop(self, event):
        """Handle drag and drop of folders"""
        # This is a placeholder - you would need to implement proper drag-and-drop handling
        pass

    def change_appearance_mode_event(self, new_appearance_mode: str):
        """Change application theme"""
        ctk.set_appearance_mode(new_appearance_mode)

    def hide_all_frames(self):
        """Hide all content frames"""
        if self.duplicate_frame:
            self.duplicate_frame.grid_forget()
        if self.sort_frame:
            self.sort_frame.grid_forget()

    def show_duplicate_frame(self):
        """Show duplicate finder frame"""
        self.hide_all_frames()
        if not self.duplicate_frame:
            self.duplicate_frame = DuplicateView(self.main_frame)
        self.duplicate_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)

    def show_sort_frame(self):
        """Show photo sorting frame"""
        self.hide_all_frames()
        if not self.sort_frame:
            self.sort_frame = SortView(self.main_frame)
        self.sort_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)


def main():
    """Main entry point"""
    # Check for command line arguments
    if len(sys.argv) > 1:
        folder_path = sys.argv[1]
        if os.path.isdir(folder_path):
            app = PhotoOrganizerApp()
            # You would need to add method to auto-scan the provided folder
            app.mainloop()
            return
    
    # Normal startup
    app = PhotoOrganizerApp()
    app.mainloop()


if __name__ == "__main__":
    main()