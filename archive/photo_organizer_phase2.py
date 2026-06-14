import customtkinter as ctk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk, ImageDraw, ImageFont, ImageEnhance, ImageFilter
import os
import hashlib
import threading
import datetime
import logging
import shutil
import math
import time
from collections import defaultdict
import cv2
import numpy as np

# Try to import imagehash for advanced duplicate detection
try:
    import imagehash
    HAS_IMAGEHASH = True
except ImportError:
    HAS_IMAGEHASH = False
    logging.warning("imagehash not available. Install with: pip install imagehash")

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Theme System
class ThemeManager:
    def __init__(self):
        self.themes = {
            "Dark": {
                "name": "Dark",
                "bg_color": "#2b2b2b",
                "fg_color": "#3a3a3a", 
                "text_color": "#ffffff",
                "accent_color": "#3a7ebf",
                "success_color": "#198754",
                "warning_color": "#ffc107",
                "danger_color": "#dc3545",
                "border_color": "#555555",
                "hover_color": "#4a4a4a"
            },
            "Light": {
                "name": "Light",
                "bg_color": "#f0f0f0",
                "fg_color": "#ffffff",
                "text_color": "#000000",
                "accent_color": "#007bff",
                "success_color": "#28a745",
                "warning_color": "#ffc107", 
                "danger_color": "#dc3545",
                "border_color": "#cccccc",
                "hover_color": "#e0e0e0"
            },
            "Blue": {
                "name": "Blue",
                "bg_color": "#1e3a5f",
                "fg_color": "#2d4a6b",
                "text_color": "#ffffff",
                "accent_color": "#4a90e2",
                "success_color": "#2ecc71",
                "warning_color": "#f39c12",
                "danger_color": "#e74c3c",
                "border_color": "#4a6fa5",
                "hover_color": "#3d5a8b"
            },
            "Purple": {
                "name": "Purple",
                "bg_color": "#2d1b69",
                "fg_color": "#3e2a7a", 
                "text_color": "#ffffff",
                "accent_color": "#9b59b6",
                "success_color": "#2ecc71",
                "warning_color": "#f39c12",
                "danger_color": "#e74c3c",
                "border_color": "#5d4a8a",
                "hover_color": "#4e3d8c"
            },
            "Matrix": {
                "name": "Matrix",
                "bg_color": "#001100",
                "fg_color": "#002200",
                "text_color": "#00ff00",
                "accent_color": "#00cc00",
                "success_color": "#00ff00",
                "warning_color": "#ffff00",
                "danger_color": "#ff0000",
                "border_color": "#004400",
                "hover_color": "#003300"
            },
            "Sunset": {
                "name": "Sunset",
                "bg_color": "#1a0f0a",
                "fg_color": "#2d1b10",
                "text_color": "#ffcc99",
                "accent_color": "#ff6b35",
                "success_color": "#ff8c42",
                "warning_color": "#ffd93d",
                "danger_color": "#ff4757",
                "border_color": "#4d2c1a",
                "hover_color": "#3d2215"
            }
        }
        self.current_theme = "Dark"
        
    def get_theme(self, theme_name=None):
        if theme_name is None:
            theme_name = self.current_theme
        return self.themes.get(theme_name, self.themes["Dark"])
    
    def set_theme(self, theme_name):
        if theme_name in self.themes:
            self.current_theme = theme_name
            return True
        return False
    
    def get_theme_names(self):
        return list(self.themes.keys())
    
    def apply_theme(self, widget, theme_name=None):
        theme = self.get_theme(theme_name)
        
        # Apply theme colors to widget
        if hasattr(widget, 'configure'):
            try:
                widget.configure(
                    bg_color=theme["bg_color"],
                    fg_color=theme["fg_color"],
                    text_color=theme["text_color"]
                )
            except:
                pass
        
        return theme

# Global theme manager
theme_manager = ThemeManager()

# Image Adjustment System
class ImageAdjuster:
    def __init__(self):
        self.adjustments = {
            'brightness': 1.0,
            'contrast': 1.0,
            'saturation': 1.0,
            'sharpness': 1.0,
            'blur': 0.0
        }
    
    def apply_adjustments(self, image):
        """Apply all adjustments to an image."""
        if not isinstance(image, Image.Image):
            return image
            
        result = image.copy()
        
        # Brightness
        if self.adjustments['brightness'] != 1.0:
            enhancer = ImageEnhance.Brightness(result)
            result = enhancer.enhance(self.adjustments['brightness'])
        
        # Contrast
        if self.adjustments['contrast'] != 1.0:
            enhancer = ImageEnhance.Contrast(result)
            result = enhancer.enhance(self.adjustments['contrast'])
        
        # Saturation (Color)
        if self.adjustments['saturation'] != 1.0:
            enhancer = ImageEnhance.Color(result)
            result = enhancer.enhance(self.adjustments['saturation'])
        
        # Sharpness
        if self.adjustments['sharpness'] != 1.0:
            enhancer = ImageEnhance.Sharpness(result)
            result = enhancer.enhance(self.adjustments['sharpness'])
        
        # Blur
        if self.adjustments['blur'] > 0:
            blur_radius = self.adjustments['blur']
            result = result.filter(ImageFilter.GaussianBlur(blur_radius))
        
        return result
    
    def reset_all(self):
        """Reset all adjustments to defaults."""
        self.adjustments = {
            'brightness': 1.0,
            'contrast': 1.0,
            'saturation': 1.0,
            'sharpness': 1.0,
            'blur': 0.0
        }

# Image Viewer with adjustments
class ImageViewer(ctk.CTkToplevel):
    def __init__(self, parent, image_paths, current_index=0):
        super().__init__(parent)
        
        self.parent = parent
        self.image_paths = image_paths
        self.current_index = current_index
        self.original_images = {}
        self.adjusted_images = {}
        self.is_fullscreen = False
        self.zoom_level = 1.0
        self.pan_x = 0
        self.pan_y = 0
        
        self.adjuster = ImageAdjuster()
        
        self.title("Image Viewer")
        self.geometry("1400x900")
        
        # Configure grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Create main container
        self.main_container = ctk.CTkFrame(self)
        self.main_container.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.main_container.grid_columnconfigure(0, weight=1)
        self.main_container.grid_rowconfigure(0, weight=1)
        
        # Create image display
        self.image_label = ctk.CTkLabel(self.main_container, text="", bg_color="black")
        self.image_label.grid(row=0, column=0, sticky="nsew")
        
        # Create controls frame
        self.create_controls()
        
        # Bind keyboard shortcuts
        self.bind("<Left>", lambda e: self.previous_image())
        self.bind("<Right>", lambda e: self.next_image())
        self.bind("<F11>", lambda e: self.toggle_fullscreen())
        self.bind("<Escape>", lambda e: self.exit_fullscreen())
        self.bind("<Control-o>", lambda e: self.reset_adjustments())
        self.bind("<Control-r>", lambda e: self.reset_zoom())
        
        # Load first image
        self.load_image()
    
    def create_controls(self):
        """Create the control panel with adjustments."""
        self.controls_frame = ctk.CTkFrame(self)
        self.controls_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        
        # Navigation controls
        nav_frame = ctk.CTkFrame(self.controls_frame)
        nav_frame.pack(side="left", padx=10, pady=10)
        
        ctk.CTkButton(nav_frame, text="⏮ Previous", 
                     command=self.previous_image, width=80).pack(side="left", padx=5)
        
        self.image_counter = ctk.CTkLabel(nav_frame, text="1 / 1", width=80)
        self.image_counter.pack(side="left", padx=5)
        
        ctk.CTkButton(nav_frame, text="Next ⏭", 
                     command=self.next_image, width=80).pack(side="left", padx=5)
        
        ctk.CTkButton(nav_frame, text="⛶ Fullscreen", 
                     command=self.toggle_fullscreen, width=80).pack(side="left", padx=10)
        
        # Adjustment controls
        adj_frame = ctk.CTkFrame(self.controls_frame)
        adj_frame.pack(side="left", padx=10, pady=10, fill="x", expand=True)
        
        # Brightness
        self.create_adjustment_control(adj_frame, "Brightness", 0.5, 2.0, 1.0, 
                                     lambda v: self.update_adjustment('brightness', v))
        
        # Contrast
        self.create_adjustment_control(adj_frame, "Contrast", 0.5, 2.0, 1.0, 
                                     lambda v: self.update_adjustment('contrast', v))
        
        # Saturation
        self.create_adjustment_control(adj_frame, "Saturation", 0.0, 2.0, 1.0, 
                                     lambda v: self.update_adjustment('saturation', v))
        
        # Sharpness
        self.create_adjustment_control(adj_frame, "Sharpness", 0.0, 2.0, 1.0, 
                                     lambda v: self.update_adjustment('sharpness', v))
        
        # Blur
        self.create_adjustment_control(adj_frame, "Blur", 0.0, 5.0, 0.0, 
                                     lambda v: self.update_adjustment('blur', v))
        
        # Action buttons
        action_frame = ctk.CTkFrame(self.controls_frame)
        action_frame.pack(side="right", padx=10, pady=10)
        
        ctk.CTkButton(action_frame, text="Reset All", 
                     command=self.reset_adjustments, width=80).pack(side="left", padx=5)
        
        ctk.CTkButton(action_frame, text="Reset Zoom", 
                     command=self.reset_zoom, width=80).pack(side="left", padx=5)
        
        ctk.CTkButton(action_frame, text="Close", 
                     command=self.destroy, width=80).pack(side="left", padx=5)
    
    def create_adjustment_control(self, parent, label, min_val, max_val, default, callback):
        """Create a slider control for image adjustments."""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(side="left", padx=10, fill="x", expand=True)
        
        ctk.CTkLabel(frame, text=label, width=80).pack(side="left", padx=5)
        
        slider = ctk.CTkSlider(frame, from_=min_val, to=max_val, 
                              number_of_steps=100, width=120)
        slider.set(default)
        slider.pack(side="left", padx=5, fill="x", expand=True)
        slider.bind("<B1-Motion>", lambda e: callback(slider.get()))
        slider.bind("<ButtonRelease-1>", lambda e: callback(slider.get()))
        
        value_label = ctk.CTkLabel(frame, text=f"{default:.2f}", width=50)
        value_label.pack(side="left", padx=5)
        
        # Store reference for updates
        slider.value_label = value_label
        slider.callback = callback
        
        return slider
    
    def load_image(self):
        """Load and display the current image."""
        if not self.image_paths:
            return
        
        path = self.image_paths[self.current_index]
        
        # Load original image if not cached
        if path not in self.original_images:
            try:
                self.original_images[path] = Image.open(path)
            except Exception as e:
                print(f"Error loading image {path}: {e}")
                return
        
        # Apply adjustments
        original = self.original_images[path]
        adjusted = self.adjuster.apply_adjustments(original)
        self.adjusted_images[path] = adjusted
        
        # Display image
        self.display_image(adjusted)
        
        # Update counter
        self.image_counter.configure(
            text=f"{self.current_index + 1} / {len(self.image_paths)}"
        )
    
    def display_image(self, image):
        """Display an image with zoom and pan."""
        # Calculate display size
        window_width = self.main_container.winfo_width()
        window_height = self.main_container.winfo_height()
        
        if window_width <= 0 or window_height <= 0:
            window_width = 1200
            window_height = 700
        
        # Apply zoom
        display_width = int(window_width * self.zoom_level)
        display_height = int(window_height * self.zoom_level)
        
        # Resize image
        img_copy = image.copy()
        img_copy.thumbnail((display_width, display_height), Image.Resampling.LANCZOS)
        
        # Convert to CTkImage
        ctk_image = ctk.CTkImage(img_copy, size=(img_copy.width, img_copy.height))
        
        # Update display
        self.image_label.configure(image=ctk_image)
        self.image_label.image = ctk_image  # Keep reference
    
    def next_image(self):
        """Go to next image."""
        if self.image_paths:
            self.current_index = (self.current_index + 1) % len(self.image_paths)
            self.load_image()
    
    def previous_image(self):
        """Go to previous image."""
        if self.image_paths:
            self.current_index = (self.current_index - 1) % len(self.image_paths)
            self.load_image()
    
    def update_adjustment(self, adjustment_type, value):
        """Update an image adjustment."""
        self.adjuster.adjustments[adjustment_type] = value
        
        # Update slider value label
        for widget in self.controls_frame.winfo_children():
            if isinstance(widget, ctk.CTkFrame):
                for slider in widget.winfo_children():
                    if hasattr(slider, 'value_label') and hasattr(slider, 'callback'):
                        if slider.callback.__name__ == f'<lambda>':
                            # Find the right slider by checking the callback
                            slider.value_label.configure(text=f"{value:.2f}")
        
        # Reload current image with new adjustments
        self.load_image()
    
    def reset_adjustments(self):
        """Reset all adjustments to defaults."""
        self.adjuster.reset_all()
        
        # Reset all sliders
        for widget in self.controls_frame.winfo_children():
            if isinstance(widget, ctk.CTkFrame):
                for slider in widget.winfo_children():
                    if hasattr(slider, 'set'):
                        slider.set(1.0 if slider.cget('from_') <= 1.0 <= slider.cget('to') else 0.0)
        
        self.load_image()
    
    def reset_zoom(self):
        """Reset zoom to 100%."""
        self.zoom_level = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.load_image()
    
    def toggle_fullscreen(self):
        """Toggle fullscreen mode."""
        if self.is_fullscreen:
            self.exit_fullscreen()
        else:
            self.enter_fullscreen()
    
    def enter_fullscreen(self):
        """Enter fullscreen mode."""
        self.is_fullscreen = True
        self.attributes('-fullscreen', True)
        self.controls_frame.pack_forget()
    
    def exit_fullscreen(self):
        """Exit fullscreen mode."""
        self.is_fullscreen = False
        self.attributes('-fullscreen', False)
        self.controls_frame.pack(side="bottom", fill="x", padx=10, pady=(0, 10))

# Enhanced Gallery with customization options
class EnhancedGallery(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        
        self.parent = parent
        self.gallery_images = []
        self.current_group_files = []
        self.thumbnail_size = (400, 400)  # Larger thumbnails
        self.gallery_columns = 2  # Default 2 columns for larger view
        self.view_mode = "grid"  # grid or list
        self.sort_by = "name"  # name, date, size, score
        self.sort_reverse = False
        
        # Configure grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Create toolbar
        self.create_toolbar()
        
        # Create main gallery area
        self.create_gallery_area()
    
    def create_toolbar(self):
        """Create gallery toolbar with customization options."""
        self.toolbar = ctk.CTkFrame(self, height=60)
        self.toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        
        # View mode buttons
        view_frame = ctk.CTkFrame(self.toolbar, fg_color="transparent")
        view_frame.pack(side="left", padx=10)
        
        ctk.CTkLabel(view_frame, text="View:").pack(side="left", padx=5)
        
        self.btn_grid_view = ctk.CTkButton(view_frame, text="⊞ Grid", 
                                          command=lambda: self.set_view_mode("grid"),
                                          width=80, fg_color="#3a7ebf")
        self.btn_grid_view.pack(side="left", padx=2)
        
        self.btn_list_view = ctk.CTkButton(view_frame, text="☰ List", 
                                          command=lambda: self.set_view_mode("list"),
                                          width=80)
        self.btn_list_view.pack(side="left", padx=2)
        
        # Thumbnail size control
        size_frame = ctk.CTkFrame(self.toolbar, fg_color="transparent")
        size_frame.pack(side="left", padx=20)
        
        ctk.CTkLabel(size_frame, text="Thumbnail Size:").pack(side="left", padx=5)
        
        self.size_slider = ctk.CTkSlider(size_frame, from_=200, to=600, 
                                        number_of_steps=8, width=150)
        self.size_slider.set(400)
        self.size_slider.pack(side="left", padx=5)
        self.size_slider.bind("<ButtonRelease-1>", self.on_size_change)
        
        self.size_label = ctk.CTkLabel(size_frame, text="400px", width=50)
        self.size_label.pack(side="left", padx=5)
        
        # Columns control
        cols_frame = ctk.CTkFrame(self.toolbar, fg_color="transparent")
        cols_frame.pack(side="left", padx=20)
        
        ctk.CTkLabel(cols_frame, text="Columns:").pack(side="left", padx=5)
        
        self.cols_slider = ctk.CTkSlider(cols_frame, from_=1, to=5, 
                                        number_of_steps=4, width=100)
        self.cols_slider.set(2)
        self.cols_slider.pack(side="left", padx=5)
        self.cols_slider.bind("<ButtonRelease-1>", self.on_columns_change)
        
        self.cols_label = ctk.CTkLabel(cols_frame, text="2", width=30)
        self.cols_label.pack(side="left", padx=5)
        
        # Sort controls
        sort_frame = ctk.CTkFrame(self.toolbar, fg_color="transparent")
        sort_frame.pack(side="left", padx=20)
        
        ctk.CTkLabel(sort_frame, text="Sort by:").pack(side="left", padx=5)
        
        self.sort_var = ctk.StringVar(value="name")
        sort_options = ["name", "date", "size", "score"]
        self.sort_menu = ctk.CTkOptionMenu(sort_frame, values=sort_options,
                                          variable=self.sort_var,
                                          command=self.on_sort_change,
                                          width=100)
        self.sort_menu.pack(side="left", padx=5)
        
        self.btn_sort_reverse = ctk.CTkButton(sort_frame, text="↓", 
                                             command=self.toggle_sort_reverse,
                                             width=40)
        self.btn_sort_reverse.pack(side="left", padx=2)
        
        # Quick actions
        actions_frame = ctk.CTkFrame(self.toolbar, fg_color="transparent")
        actions_frame.pack(side="right", padx=10)
        
        ctk.CTkButton(actions_frame, text="Select All", 
                     command=self.select_all, width=80).pack(side="left", padx=2)
        
        ctk.CTkButton(actions_frame, text="Clear All", 
                     command=self.clear_all, width=80).pack(side="left", padx=2)
        
        ctk.CTkButton(actions_frame, text="View Selected", 
                     command=self.view_selected, width=100).pack(side="left", padx=2)
    
    def create_gallery_area(self):
        """Create the main gallery display area."""
        self.gallery_scroll = ctk.CTkScrollableFrame(self, label_text="Gallery")
        self.gallery_scroll.grid(row=1, column=0, sticky="nsew")
        self.gallery_scroll.grid_columnconfigure(0, weight=1)
    
    def set_view_mode(self, mode):
        """Switch between grid and list view."""
        self.view_mode = mode
        
        # Update button states
        if mode == "grid":
            self.btn_grid_view.configure(fg_color="#3a7ebf")
            self.btn_list_view.configure(fg_color="transparent")
        else:
            self.btn_grid_view.configure(fg_color="transparent")
            self.btn_list_view.configure(fg_color="#3a7ebf")
        
        self.refresh_gallery()
    
    def on_size_change(self, event):
        """Handle thumbnail size change."""
        size = int(self.size_slider.get())
        self.thumbnail_size = (size, size)
        self.size_label.configure(text=f"{size}px")
        self.refresh_gallery()
    
    def on_columns_change(self, event):
        """Handle columns change."""
        cols = int(self.cols_slider.get())
        self.gallery_columns = cols
        self.cols_label.configure(text=str(cols))
        self.refresh_gallery()
    
    def on_sort_change(self, new_sort):
        """Handle sort method change."""
        self.sort_by = new_sort
        self.refresh_gallery()
    
    def toggle_sort_reverse(self):
        """Toggle sort direction."""
        self.sort_reverse = not self.sort_reverse
        self.btn_sort_reverse.configure(text="↑" if self.sort_reverse else "↓")
        self.refresh_gallery()
    
    def load_group(self, image_paths, image_scores=None):
        """Load a group of images into the gallery."""
        self.current_group_files = image_paths
        self.image_scores = image_scores or {}
        self.refresh_gallery()
    
    def refresh_gallery(self):
        """Refresh the gallery display."""
        # Clear existing items
        for widget in self.gallery_scroll.winfo_children():
            widget.destroy()
        
        if not self.current_group_files:
            ctk.CTkLabel(self.gallery_scroll, 
                        text="No images to display", 
                        text_color="gray").pack(pady=50)
            return
        
        # Sort images
        sorted_images = self.sort_images(self.current_group_files)
        
        if self.view_mode == "grid":
            self.display_grid_view(sorted_images)
        else:
            self.display_list_view(sorted_images)
    
    def sort_images(self, image_paths):
        """Sort images based on current sort settings."""
        if self.sort_by == "name":
            return sorted(image_paths, reverse=self.sort_reverse)
        elif self.sort_by == "date":
            return sorted(image_paths, 
                         key=lambda p: os.path.getmtime(p), 
                         reverse=self.sort_reverse)
        elif self.sort_by == "size":
            return sorted(image_paths, 
                         key=lambda p: os.path.getsize(p), 
                         reverse=self.sort_reverse)
        elif self.sort_by == "score":
            return sorted(image_paths, 
                         key=lambda p: self.image_scores.get(p, 0), 
                         reverse=self.sort_reverse)
        return image_paths
    
    def display_grid_view(self, image_paths):
        """Display images in grid view."""
        # Create grid container
        grid_container = ctk.CTkFrame(self.gallery_scroll, fg_color="transparent")
        grid_container.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Configure grid columns
        for col in range(self.gallery_columns):
            grid_container.grid_columnconfigure(col, weight=1)
        
        # Add images to grid
        for idx, path in enumerate(image_paths):
            row = idx // self.gallery_columns
            col = idx % self.gallery_columns
            
            self.create_grid_item(grid_container, path, row, col)
    
    def display_list_view(self, image_paths):
        """Display images in list view."""
        list_container = ctk.CTkFrame(self.gallery_scroll, fg_color="transparent")
        list_container.pack(fill="both", expand=True, padx=10, pady=10)
        
        for path in image_paths:
            self.create_list_item(list_container, path)
    
    def create_grid_item(self, parent, path, row, col):
        """Create a grid item for an image."""
        # Get file info
        try:
            size = os.path.getsize(path)
            mtime = os.path.getmtime(path)
            date_str = datetime.datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')
            size_str = self.format_size(size)
            score = self.image_scores.get(path, 0)
        except:
            size_str = "Unknown"
            date_str = "Unknown"
            score = 0
        
        score_color = get_score_color(score)
        
        # Create frame
        frame = ctk.CTkFrame(parent, border_width=2, border_color="gray", 
                           corner_radius=10, fg_color="transparent")
        frame.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
        
        # Load and display image
        try:
            img = Image.open(path)
            img.thumbnail(self.thumbnail_size, Image.Resampling.LANCZOS)
            
            # Create padded image to maintain aspect ratio
            padded_img = Image.new('RGB', self.thumbnail_size, color='#2b2b2b')
            padded_img.paste(img, 
                           ((self.thumbnail_size[0] - img.width) // 2,
                            (self.thumbnail_size[1] - img.height) // 2))
            
            ctk_img = ctk.CTkImage(padded_img, size=self.thumbnail_size)
            
            img_button = ctk.CTkButton(frame, image=ctk_img, text="", 
                                     fg_color="transparent", hover_color="gray30",
                                     command=lambda p=path: self.view_single_image(p))
            img_button.pack(pady=10)
            
        except Exception as e:
            error_label = ctk.CTkLabel(frame, text="Error Loading\nImage", 
                                     width=self.thumbnail_size[0], 
                                     height=self.thumbnail_size[1],
                                     text_color="gray")
            error_label.pack(pady=10)
        
        # Info section
        info_frame = ctk.CTkFrame(frame, fg_color="transparent")
        info_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        # Score display
        score_frame = ctk.CTkFrame(info_frame, fg_color=score_color, corner_radius=5)
        score_frame.pack(fill="x", pady=(0, 5))
        ctk.CTkLabel(score_frame, text=f"⭐ {score:.1f}", 
                    text_color="white", font=("Arial", 10, "bold")).pack(pady=2)
        
        # Filename
        filename = os.path.basename(path)
        if len(filename) > 30:
            filename = filename[:27] + "..."
        ctk.CTkLabel(info_frame, text=filename, font=("Arial", 10, "bold")).pack(anchor="w")
        
        # Details
        ctk.CTkLabel(info_frame, text=f"📅 {date_str}", font=("Arial", 9)).pack(anchor="w")
        ctk.CTkLabel(info_frame, text=f"📏 {size_str}", font=("Arial", 9)).pack(anchor="w")
        
        # Checkbox for selection
        del_var = ctk.BooleanVar(value=False)
        chk = ctk.CTkCheckBox(frame, text="Mark for Deletion", variable=del_var, 
                            checkbox_width=18, checkbox_height=18,
                            fg_color="#dc3545", hover_color="#a71d2a")
        chk.pack(pady=5)
        
        # Store metadata
        frame.meta_data = {
            "path": path,
            "var": del_var,
            "score": score
        }
    
    def create_list_item(self, parent, path):
        """Create a list item for an image."""
        # Implementation for list view
        pass  # Similar to grid but horizontal layout
    
    def select_all(self):
        """Select all images."""
        for widget in self.gallery_scroll.winfo_children():
            if isinstance(widget, ctk.CTkFrame):
                for child in widget.winfo_children():
                    if hasattr(child, 'meta_data'):
                        child.meta_data['var'].set(True)
    
    def clear_all(self):
        """Clear all selections."""
        for widget in self.gallery_scroll.winfo_children():
            if isinstance(widget, ctk.CTkFrame):
                for child in widget.winfo_children():
                    if hasattr(child, 'meta_data'):
                        child.meta_data['var'].set(False)
    
    def view_selected(self):
        """View all selected images."""
        selected_paths = []
        for widget in self.gallery_scroll.winfo_children():
            if isinstance(widget, ctk.CTkFrame):
                for child in widget.winfo_children():
                    if hasattr(child, 'meta_data') and child.meta_data['var'].get():
                        selected_paths.append(child.meta_data['path'])
        
        if selected_paths:
            ImageViewer(self, selected_paths)
        else:
            messagebox.showinfo("View Selected", "No images selected.")
    
    def view_single_image(self, image_path):
        """View a single image."""
        ImageViewer(self, [image_path])
    
    def get_selected_for_deletion(self):
        """Get list of images marked for deletion."""
        selected = []
        for widget in self.gallery_scroll.winfo_children():
            if isinstance(widget, ctk.CTkFrame):
                for child in widget.winfo_children():
                    if hasattr(child, 'meta_data') and child.meta_data['var'].get():
                        selected.append(child.meta_data['path'])
        return selected
    
    def format_size(self, size_bytes):
        """Format file size for display."""
        if size_bytes == 0:
            return "0 B"
        size_name = ("B", "KB", "MB", "GB", "TB")
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_name[i]}"

# Main Application
class PhotoOrganizerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Photo Organizer Pro - Phase 2")
        self.geometry("1600x1000")

        # Grid layout
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar Navigation
        self.sidebar_frame = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(6, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="Photo\nManager\nPro", 
                                      font=ctk.CTkFont(size=24, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        # Navigation buttons
        self.sidebar_button_1 = ctk.CTkButton(self.sidebar_frame, text="Find Duplicates", 
                                             command=self.show_duplicate_frame, height=40)
        self.sidebar_button_1.grid(row=1, column=0, padx=20, pady=10)

        self.sidebar_button_2 = ctk.CTkButton(self.sidebar_frame, text="Sort by Month", 
                                             command=self.show_sort_frame, height=40)
        self.sidebar_button_2.grid(row=2, column=0, padx=20, pady=10)

        # Theme selector
        self.theme_label = ctk.CTkLabel(self.sidebar_frame, text="Theme:", anchor="w")
        self.theme_label.grid(row=3, column=0, padx=20, pady=(10, 0))
        
        self.theme_option = ctk.CTkOptionMenu(self.sidebar_frame, 
                                             values=theme_manager.get_theme_names(),
                                             command=self.change_theme,
                                             variable=ctk.StringVar(value="Dark"))
        self.theme_option.grid(row=4, column=0, padx=20, pady=(10, 20))

        # Appearance mode
        self.appearance_mode_label = ctk.CTkLabel(self.sidebar_frame, text="Appearance:", anchor="w")
        self.appearance_mode_label.grid(row=5, column=0, padx=20, pady=(10, 0))
        self.appearance_mode_optionemenu = ctk.CTkOptionMenu(self.sidebar_frame, 
                                                            values=["Dark", "Light", "System"],
                                                            command=self.change_appearance_mode_event)
        self.appearance_mode_optionemenu.grid(row=6, column=0, padx=20, pady=(10, 20))

        # Main Area
        self.main_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew")

        self.duplicate_frame = None
        self.sort_frame = None
        
        self.show_duplicate_frame()
    
    def change_theme(self, theme_name):
        """Change application theme."""
        theme_manager.set_theme(theme_name)
        theme = theme_manager.get_theme()
        
        # Apply theme to main window
        self.configure(fg_color=theme["bg_color"])
        
        # Apply theme to sidebar
        self.sidebar_frame.configure(fg_color=theme["fg_color"])
        
        # Apply theme to main frames
        self.main_frame.configure(fg_color=theme["bg_color"])
        
        # Update customtkinter theme
        ctk.set_appearance_mode("Dark" if "Dark" in theme_name or "Matrix" in theme_name else "Light")
    
    def change_appearance_mode_event(self, new_appearance_mode: str):
        ctk.set_appearance_mode(new_appearance_mode)

    def hide_all_frames(self):
        if self.duplicate_frame:
            self.duplicate_frame.grid_forget()
        if self.sort_frame:
            self.sort_frame.grid_forget()

    def show_duplicate_frame(self):
        self.hide_all_frames()
        if not self.duplicate_frame:
            self.duplicate_frame = DuplicateView(self.main_frame)
        self.duplicate_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

    def show_sort_frame(self):
        self.hide_all_frames()
        if not self.sort_frame:
            self.sort_frame = SortView(self.main_frame)
        self.sort_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)


class DuplicateView(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.grid_columnconfigure(0, weight=0)  # Sidebar list
        self.grid_columnconfigure(1, weight=1)  # Gallery
        self.grid_rowconfigure(1, weight=1)

        self.current_duplicates = {} 
        self.current_group_files = []
        self.files_to_delete = set()
        self.group_buttons = []
        self.current_selected_group = None
        self.image_scores = {}
        self.perceptual_hashes = {}

        # --- Top Controls ---
        self.top_frame = ctk.CTkFrame(self, height=60)
        self.top_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=10)
        
        self.folder_path = ctk.StringVar(value="")
        self.entry = ctk.CTkEntry(self.top_frame, textvariable=self.folder_path, 
                                placeholder_text="Select Folder to Scan")
        self.entry.pack(side="left", fill="x", expand=True, padx=10)
        
        self.browse_btn = ctk.CTkButton(self.top_frame, text="Browse", 
                                       command=self.browse_folder, width=80)
        self.browse_btn.pack(side="left", padx=10)

        self.scan_btn = ctk.CTkButton(self.top_frame, text="Scan", 
                                     command=self.start_scan_thread, width=100)
        self.scan_btn.pack(side="left", padx=10)

        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(self.top_frame, width=200, height=20)
        self.progress_bar.pack(side="left", padx=10)
        self.progress_bar.set(0)
        self.progress_bar.pack_forget()

        # --- Left Sidebar (List of Groups) ---
        self.list_container = ctk.CTkScrollableFrame(self, width=250, 
                                                    label_text="Duplicate Groups")
        self.list_container.grid(row=1, column=0, sticky="nsew", padx=(0, 10))

        # --- Right Gallery Area ---
        self.right_panel = ctk.CTkFrame(self, fg_color="transparent")
        self.right_panel.grid(row=1, column=1, sticky="nsew")
        self.right_panel.grid_rowconfigure(1, weight=1)

        # Create enhanced gallery
        self.gallery = EnhancedGallery(self.right_panel)
        self.gallery.grid(row=1, column=0, sticky="nsew")

        # Gallery Controls (Batch Selection)
        self.gallery_controls = ctk.CTkFrame(self.right_panel, height=50)
        self.gallery_controls.grid(row=0, column=0, sticky="ew")
        
        ctk.CTkLabel(self.gallery_controls, text="Auto-Select:").pack(side="left", padx=10)
        
        # Enhanced smart selection buttons
        self.btn_smart_best = ctk.CTkButton(self.gallery_controls, text="🤖 Smart Best", 
                                           command=lambda: self.smart_select("smart_best"),
                                           fg_color="#20c997", hover_color="#1aa179", width=120)
        self.btn_smart_best.pack(side="left", padx=5)
        
        self.btn_sel_newest = ctk.CTkButton(self.gallery_controls, text="Keep Newest", 
                                           command=lambda: self.smart_select("keep_newest"), 
                                           fg_color="#198754", hover_color="#13653f", width=120)
        self.btn_sel_newest.pack(side="left", padx=5)
        
        self.btn_sel_oldest = ctk.CTkButton(self.gallery_controls, text="Keep Oldest", 
                                           command=lambda: self.smart_select("keep_oldest"),
                                          fg_color="#198754", hover_color="#13653f", width=120)
        self.btn_sel_oldest.pack(side="left", padx=5)
        
        self.btn_sel_largest = ctk.CTkButton(self.gallery_controls, text="Keep Largest", 
                                            command=lambda: self.smart_select("keep_largest"),
                                            fg_color="#198754", hover_color="#13653f", width=120)
        self.btn_sel_largest.pack(side="left", padx=5)
        
        self.btn_sel_smallest = ctk.CTkButton(self.gallery_controls, text="Keep Smallest", 
                                             command=lambda: self.smart_select("keep_smallest"),
                                             fg_color="#198754", hover_color="#13653f", width=120)
        self.btn_sel_smallest.pack(side="left", padx=5)

        self.btn_sel_all = ctk.CTkButton(self.gallery_controls, text="Select All", 
                                        command=lambda: self.smart_select("all"), 
                                        fg_color="#6610f2", width=100)
        self.btn_sel_all.pack(side="left", padx=5)

        self.btn_clear = ctk.CTkButton(self.gallery_controls, text="Clear All", 
                                      command=lambda: self.smart_select("clear"), 
                                      fg_color="#6c757d", width=100)
        self.btn_clear.pack(side="left", padx=5)

        # Bottom Action Bar
        self.action_bar = ctk.CTkFrame(self.right_panel, height=60)
        self.action_bar.grid(row=2, column=0, sticky="ew", pady=10)
        
        self.status_label = ctk.CTkLabel(self.action_bar, text="Ready", text_color="gray")
        self.status_label.pack(side="left", padx=20)

        self.delete_btn = ctk.CTkButton(self.action_bar, text=f"Delete Selected (0)", 
                                       fg_color="#dc3545", hover_color="#a71d2a", 
                                       command=self.confirm_delete, height=40, width=150)
        self.delete_btn.pack(side="right", padx=20, pady=10)

    def browse_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.folder_path.set(path)

    def start_scan_thread(self):
        path = self.folder_path.get()
        if not path or not os.path.isdir(path):
            messagebox.showerror("Error", "Please select a valid folder.")
            return
        
        # Clear previous
        for widget in self.list_container.winfo_children():
            widget.destroy()
        self.group_buttons = []
        self.current_duplicates = {}
        self.image_scores = {}
        self.perceptual_hashes = {}
        
        self.status_label.configure(text="Scanning...")
        self.progress_bar.pack(side="left", padx=10)
        self.scan_btn.configure(state="disabled")
        self.browse_btn.configure(state="disabled")
        
        thread = threading.Thread(target=self.scan_duplicates, args=(path,))
        thread.start()

    def scan_duplicates(self, path):
        # ... (existing scan_duplicates code remains the same)
        # Just add the gallery loading at the end:
        self.current_duplicates = {k: v for k, v in hashes.items() if len(v) > 1}
        self.after(0, self.update_list_ui, len(self.current_duplicates), scanned_files)

    def load_group(self, file_hash, paths, button_index):
        # Reset previous button highlight
        if self.current_selected_group is not None:
            self.group_buttons[self.current_selected_group].configure(fg_color="transparent")
        
        # Highlight current button
        self.group_buttons[button_index].configure(fg_color="#3a7ebf")
        self.current_selected_group = button_index
        
        self.current_group_hash = file_hash
        self.current_group_files = paths
        self.files_to_delete = set()
        
        # Load into enhanced gallery
        self.gallery.load_group(paths, self.image_scores)
        
        # Update delete button
        self.update_delete_btn()
    
    def smart_select(self, mode):
        # Delegate to gallery's smart selection
        if mode == "all":
            self.gallery.select_all()
        elif mode == "clear":
            self.gallery.clear_all()
        elif mode == "smart_best":
            # Use gallery's selection system
            pass  # Implementation would integrate with gallery
        
        # Update delete count
        self.update_delete_btn()
    
    def confirm_delete(self):
        selected = self.gallery.get_selected_for_deletion()
        if not selected:
            messagebox.showinfo("Delete", "No images selected for deletion.")
            return
        
        if messagebox.askyesno("Confirm Delete", 
                               f"Permanently delete {len(selected)} selected files?\n\n"
                               f"This action cannot be undone!"):
            self.perform_deletion(selected)
    
    def perform_deletion(self, files_to_delete):
        # Implementation for deletion
        errors = []
        deleted = 0
        
        for path in files_to_delete:
            try:
                os.remove(path)
                deleted += 1
            except Exception as e:
                errors.append(f"{os.path.basename(path)}: {str(e)}")
        
        messagebox.showinfo("Deletion Complete", 
                           f"Successfully deleted {deleted} files.\n\n"
                           f"Errors: {len(errors)}")
        
        # Refresh gallery
        self.current_group_files = [f for f in self.current_group_files 
                                   if f not in files_to_delete]
        self.gallery.load_group(self.current_group_files, self.image_scores)

    def update_delete_btn(self):
        selected = self.gallery.get_selected_for_deletion()
        count = len(selected)
        self.delete_btn.configure(text=f"Delete Selected ({count})")

# SortView remains similar to original
class SortView(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        # ... (implementation remains the same)

# Main execution
if __name__ == "__main__":
    app = PhotoOrganizerApp()
    app.mainloop()
