import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import os
import hashlib
import threading
import datetime
import logging
import shutil
import math
from collections import defaultdict

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Set appearance mode and default color theme
ctk.set_appearance_mode("Dark")  # Default to dark for better photo viewing
ctk.set_default_color_theme("blue")

SUPPORTED_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.mov', '.mp4')

class PhotoOrganizerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Photo Organizer & Smart Duplicate Cleaner")
        self.geometry("1400x900")  # Increased window size

        # Grid layout (2 columns)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar Navigation
        self.sidebar_frame = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(4, weight=1) 

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="Photo\nManager", font=ctk.CTkFont(size=24, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        self.sidebar_button_1 = ctk.CTkButton(self.sidebar_frame, text="Find Duplicates", command=self.show_duplicate_frame, height=40)
        self.sidebar_button_1.grid(row=1, column=0, padx=20, pady=10)

        self.sidebar_button_2 = ctk.CTkButton(self.sidebar_frame, text="Sort by Month", command=self.show_sort_frame, height=40)
        self.sidebar_button_2.grid(row=2, column=0, padx=20, pady=10)

        self.appearance_mode_label = ctk.CTkLabel(self.sidebar_frame, text="Theme:", anchor="w")
        self.appearance_mode_label.grid(row=5, column=0, padx=20, pady=(10, 0))
        self.appearance_mode_optionemenu = ctk.CTkOptionMenu(self.sidebar_frame, values=["Dark", "Light", "System"],
                                                                       command=self.change_appearance_mode_event)
        self.appearance_mode_optionemenu.grid(row=6, column=0, padx=20, pady=(10, 20))

        # Main Area Frames
        self.main_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew")

        self.duplicate_frame = None
        self.sort_frame = None
        
        self.show_duplicate_frame()

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
        self.current_group_files = []  # List of files currently displayed
        self.files_to_delete = set()
        self.group_buttons = []  # Store references to group buttons
        self.current_selected_group = None

        # --- Top Controls ---
        self.top_frame = ctk.CTkFrame(self, height=60)
        self.top_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=10)
        
        self.folder_path = ctk.StringVar(value="")
        self.entry = ctk.CTkEntry(self.top_frame, textvariable=self.folder_path, placeholder_text="Select Folder to Scan")
        self.entry.pack(side="left", fill="x", expand=True, padx=10)
        
        self.browse_btn = ctk.CTkButton(self.top_frame, text="Browse", command=self.browse_folder, width=80)
        self.browse_btn.pack(side="left", padx=10)

        self.scan_btn = ctk.CTkButton(self.top_frame, text="Scan", command=self.start_scan_thread, width=100)
        self.scan_btn.pack(side="left", padx=10)

        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(self.top_frame, width=200, height=20)
        self.progress_bar.pack(side="left", padx=10)
        self.progress_bar.set(0)
        self.progress_bar.pack_forget()  # Hide initially

        # --- Left Sidebar (List of Groups) ---
        self.list_container = ctk.CTkScrollableFrame(self, width=250, label_text="Duplicate Groups")
        self.list_container.grid(row=1, column=0, sticky="nsew", padx=(0, 10))

        # --- Right Gallery Area ---
        self.right_panel = ctk.CTkFrame(self, fg_color="transparent")
        self.right_panel.grid(row=1, column=1, sticky="nsew")
        self.right_panel.grid_rowconfigure(1, weight=1)

        # Gallery Controls (Batch Selection)
        self.gallery_controls = ctk.CTkFrame(self.right_panel, height=50)
        self.gallery_controls.grid(row=0, column=0, sticky="ew")
        
        ctk.CTkLabel(self.gallery_controls, text="Auto-Select:").pack(side="left", padx=10)
        
        self.btn_sel_old = ctk.CTkButton(self.gallery_controls, text="Keep Newest", command=lambda: self.smart_select("keep_newest"), 
                                         fg_color="#198754", hover_color="#13653f", width=120)
        self.btn_sel_old.pack(side="left", padx=5)
        
        self.btn_sel_new = ctk.CTkButton(self.gallery_controls, text="Keep Oldest", command=lambda: self.smart_select("keep_oldest"),
                                        fg_color="#198754", hover_color="#13653f", width=120)
        self.btn_sel_new.pack(side="left", padx=5)
        
        self.btn_sel_large = ctk.CTkButton(self.gallery_controls, text="Keep Largest", command=lambda: self.smart_select("keep_largest"),
                                          fg_color="#198754", hover_color="#13653f", width=120)
        self.btn_sel_large.pack(side="left", padx=5)
        
        self.btn_sel_small = ctk.CTkButton(self.gallery_controls, text="Keep Smallest", command=lambda: self.smart_select("keep_smallest"),
                                          fg_color="#198754", hover_color="#13653f", width=120)
        self.btn_sel_small.pack(side="left", padx=5)

        self.btn_sel_all = ctk.CTkButton(self.gallery_controls, text="Select All", command=lambda: self.smart_select("all"), 
                                         fg_color="#6610f2", width=100)
        self.btn_sel_all.pack(side="left", padx=5)

        self.btn_clear = ctk.CTkButton(self.gallery_controls, text="Clear All", command=lambda: self.smart_select("clear"), 
                                       fg_color="#6c757d", width=100)
        self.btn_clear.pack(side="left", padx=5)

        # The Gallery Grid
        self.gallery_frame = ctk.CTkScrollableFrame(self.right_panel, label_text="Select images to DELETE")
        self.gallery_frame.grid(row=1, column=0, sticky="nsew")
        self.gallery_frame.grid_columnconfigure(0, weight=1)

        # Bottom Action Bar
        self.action_bar = ctk.CTkFrame(self.right_panel, height=60)
        self.action_bar.grid(row=2, column=0, sticky="ew", pady=10)
        
        self.status_label = ctk.CTkLabel(self.action_bar, text="Ready", text_color="gray")
        self.status_label.pack(side="left", padx=20)

        self.delete_btn = ctk.CTkButton(self.action_bar, text=f"Delete Selected (0)", fg_color="#dc3545", 
                                        hover_color="#a71d2a", command=self.confirm_delete, height=40, width=150)
        self.delete_btn.pack(side="right", padx=20, pady=10)
        
        # Initialize gallery message
        self.gallery_message = ctk.CTkLabel(self.gallery_frame, text="Select a duplicate group from the left panel", 
                                            text_color="gray", font=("Arial", 16))
        self.gallery_message.pack(expand=True, pady=100)

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
        
        # Clear gallery
        for widget in self.gallery_frame.winfo_children():
            widget.destroy()
        self.gallery_message = ctk.CTkLabel(self.gallery_frame, text="Scanning for duplicates...", 
                                            text_color="gray", font=("Arial", 16))
        self.gallery_message.pack(expand=True, pady=100)
        
        self.status_label.configure(text="Scanning...")
        self.progress_bar.pack(side="left", padx=10)
        self.scan_btn.configure(state="disabled")
        self.browse_btn.configure(state="disabled")
        
        thread = threading.Thread(target=self.scan_duplicates, args=(path,))
        thread.start()

    def scan_duplicates(self, path):
        hashes = {}
        total_files = 0
        scanned_files = 0
        
        # First count total files for progress
        for root, dirs, files in os.walk(path):
            total_files += len([f for f in files if f.lower().endswith(SUPPORTED_EXTENSIONS)])
        
        for root, dirs, files in os.walk(path):
            for file in files:
                if file.lower().endswith(SUPPORTED_EXTENSIONS):
                    full_path = os.path.join(root, file)
                    try:
                        file_hash = self.get_file_hash(full_path)
                        if file_hash not in hashes:
                            hashes[file_hash] = []
                        hashes[file_hash].append(full_path)
                        scanned_files += 1
                        
                        # Update progress
                        if scanned_files % 10 == 0:  # Update every 10 files to reduce UI updates
                            progress = scanned_files / total_files
                            self.after(0, self.update_progress, progress)
                            
                    except Exception as e:
                        logging.warning(f"Could not read {full_path}: {e}")
        
        self.current_duplicates = {k: v for k, v in hashes.items() if len(v) > 1}
        self.after(0, self.update_list_ui, len(self.current_duplicates), scanned_files)

    def get_file_hash(self, filepath):
        hasher = hashlib.md5()
        with open(filepath, 'rb') as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()

    def update_progress(self, progress):
        self.progress_bar.set(progress)

    def update_list_ui(self, dup_count, total_count):
        # Hide progress bar
        self.progress_bar.pack_forget()
        
        # Clear existing buttons
        self.group_buttons = []
        
        # Create buttons for groups
        for i, (h, paths) in enumerate(self.current_duplicates.items()):
            btn = ctk.CTkButton(
                self.list_container, 
                text=f"Group {i+1}\n({len(paths)} duplicates)", 
                anchor="w",
                fg_color="transparent",
                command=lambda hash_key=h, p=paths, idx=i: self.load_group(hash_key, p, idx)
            )
            btn.pack(fill="x", pady=2, padx=5)
            self.group_buttons.append(btn)
        
        self.scan_btn.configure(state="normal")
        self.browse_btn.configure(state="normal")
        self.status_label.configure(text=f"Found {dup_count} duplicate groups in {total_count} files.")
        
        if dup_count == 0:
            msg = ctk.CTkLabel(self.list_container, text="No duplicates found.", text_color="gray")
            msg.pack(pady=20)

    def load_group(self, file_hash, paths, button_index):
        # Reset previous button highlight
        if self.current_selected_group is not None:
            self.group_buttons[self.current_selected_group].configure(fg_color="transparent")
        
        # Highlight current button
        self.group_buttons[button_index].configure(fg_color="#3a7ebf")
        self.current_selected_group = button_index
        
        self.current_group_hash = file_hash
        self.current_group_files = paths
        self.files_to_delete = set()  # Reset selection for new group

        # Clear gallery
        for widget in self.gallery_frame.winfo_children():
            widget.destroy()
        
        # Create grid layout for images
        self.gallery_frame.grid_columnconfigure(0, weight=1)
        
        # Create a frame for the grid
        grid_frame = ctk.CTkFrame(self.gallery_frame, fg_color="transparent")
        grid_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Calculate grid dimensions
        num_images = len(paths)
        cols = min(3, num_images)  # Max 3 columns for better visibility
        rows = math.ceil(num_images / cols)
        
        for idx, path in enumerate(paths):
            row = idx // cols
            col = idx % cols
            
            # Configure grid weights
            grid_frame.grid_columnconfigure(col, weight=1)
            grid_frame.grid_rowconfigure(row, weight=1)
            
            self.create_image_card(grid_frame, path, row, col)

        self.update_delete_btn()

    def create_image_card(self, parent, path, row, col):
        frame = ctk.CTkFrame(parent, border_width=2, border_color="gray", corner_radius=10)
        frame.grid(row=row, column=col, padx=15, pady=15, sticky="nsew")
        
        # Get File Stats
        try:
            size = os.path.getsize(path)
            mtime = os.path.getmtime(path)
            date_str = datetime.datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')
            size_str = self.format_size(size)
        except:
            date_str = "Unknown"
            size_str = "Unknown"
            size = 0
            mtime = 0

        # Image Thumbnail
        try:
            thumb_size = (380, 380)  # Increased size for better viewing
            if path.lower().endswith(('.mov', '.mp4')):
                img = Image.new('RGB', thumb_size, color='#444444')
                # Add text for video
                from PIL import ImageDraw, ImageFont
                d = ImageDraw.Draw(img)
                d.text((10,10), "VIDEO FILE", fill="white")
            else:
                pil_img = Image.open(path)
                pil_img.thumbnail(thumb_size, Image.Resampling.LANCZOS)
                # Add padding to maintain aspect ratio
                img = Image.new('RGB', thumb_size, color='#2b2b2b')
                img.paste(pil_img, 
                         ((thumb_size[0] - pil_img.width) // 2, 
                          (thumb_size[1] - pil_img.height) // 2))
            
            ctk_img = ctk.CTkImage(img, size=thumb_size)
            
            # Clickable Image Wrapper
            img_container = ctk.CTkButton(frame, image=ctk_img, text="", fg_color="transparent", 
                                          hover_color="gray30", border_width=2, border_color="transparent",
                                          command=lambda p=path: self.manual_toggle(p))
            img_container.pack(pady=10)

        except Exception as e:
            error_label = ctk.CTkLabel(frame, text="Error Loading\nImage", width=380, height=380, 
                                      text_color="gray", font=("Arial", 12))
            error_label.pack(pady=5)

        # Info Frame
        info_frame = ctk.CTkFrame(frame, fg_color="transparent")
        info_frame.pack(fill="x", pady=(0, 5), padx=10)
        
        # File name (truncated if too long)
        filename = os.path.basename(path)
        if len(filename) > 30:
            filename = filename[:27] + "..."
        ctk.CTkLabel(info_frame, text=filename, font=("Arial", 11, "bold")).pack(anchor="w")
        
        # Date and size
        ctk.CTkLabel(info_frame, text=f"📅 {date_str}", font=("Arial", 10)).pack(anchor="w", pady=(2, 0))
        ctk.CTkLabel(info_frame, text=f"📏 {size_str}", font=("Arial", 10)).pack(anchor="w", pady=(2, 0))
        
        # Path (truncated)
        dir_path = os.path.dirname(path)
        if len(dir_path) > 40:
            dir_path = "..." + dir_path[-37:]
        ctk.CTkLabel(info_frame, text=f"📁 {dir_path}", font=("Arial", 9), text_color="gray").pack(anchor="w", pady=(2, 5))

        # Checkbox (Marked for deletion)
        del_var = ctk.BooleanVar(value=False)
        chk = ctk.CTkCheckBox(frame, text="Mark for Deletion", variable=del_var, 
                              command=lambda p=path: self.handle_checkbox(p, del_var), 
                              checkbox_width=20, checkbox_height=20, 
                              fg_color="#dc3545", hover_color="#a71d2a")
        chk.pack(pady=10)
        
        # Store meta data
        frame.meta_data = {
            "path": path, 
            "var": del_var, 
            "size": size, 
            "mtime": mtime,
            "img_container": img_container if 'img_container' in locals() else None,
            "frame": frame
        }

    def format_size(self, size_bytes):
        if size_bytes == 0:
            return "0 B"
        size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_name[i]}"

    def manual_toggle(self, path):
        # Triggered by clicking image
        for widget in self.gallery_frame.winfo_children()[0].winfo_children():  # Get children of grid_frame
            if hasattr(widget, 'meta_data') and widget.meta_data["path"] == path:
                current_val = widget.meta_data["var"].get()
                widget.meta_data["var"].set(not current_val)
                self.handle_checkbox(path, widget.meta_data["var"])
                break

    def handle_checkbox(self, path, var):
        # Update visual feedback
        for widget in self.gallery_frame.winfo_children()[0].winfo_children():
            if hasattr(widget, 'meta_data') and widget.meta_data["path"] == path:
                if var.get():
                    self.files_to_delete.add(path)
                    widget.configure(border_color="#dc3545")  # Red border for marked files
                    if widget.meta_data["img_container"]:
                        widget.meta_data["img_container"].configure(border_color="#dc3545")
                else:
                    self.files_to_delete.discard(path)
                    widget.configure(border_color="gray")
                    if widget.meta_data["img_container"]:
                        widget.meta_data["img_container"].configure(border_color="transparent")
                break
        
        self.update_delete_btn()

    def update_delete_btn(self):
        count = len(self.files_to_delete)
        self.delete_btn.configure(text=f"Delete Selected ({count})")
        if count > 0:
            self.delete_btn.configure(state="normal")
        else:
            self.delete_btn.configure(state="disabled")

    def smart_select(self, mode):
        if not self.current_group_files or len(self.current_group_files) < 2:
            messagebox.showinfo("No Selection", "Please select a group with duplicates first.")
            return
        
        widgets = [w for w in self.gallery_frame.winfo_children()[0].winfo_children() if hasattr(w, 'meta_data')]
        
        if mode == "clear":
            for w in widgets:
                w.meta_data["var"].set(False)
                self.handle_checkbox(w.meta_data["path"], w.meta_data["var"])
            return

        if mode == "all":
            for w in widgets:
                w.meta_data["var"].set(True)
                self.handle_checkbox(w.meta_data["path"], w.meta_data["var"])
            return

        # Determine which file to KEEP (others will be marked for deletion)
        keep_path = None
        
        if mode == "keep_newest":
            # Keep the newest file (largest mtime)
            keep_path = max(widgets, key=lambda w: w.meta_data["mtime"]).meta_data["path"]
            
        elif mode == "keep_oldest":
            # Keep the oldest file (smallest mtime)
            keep_path = min(widgets, key=lambda w: w.meta_data["mtime"]).meta_data["path"]
            
        elif mode == "keep_largest":
            # Keep the largest file
            keep_path = max(widgets, key=lambda w: w.meta_data["size"]).meta_data["path"]
            
        elif mode == "keep_smallest":
            # Keep the smallest file
            keep_path = min(widgets, key=lambda w: w.meta_data["size"]).meta_data["path"]
        
        # Apply selection: mark all for deletion except the one to keep
        for w in widgets:
            if w.meta_data["path"] == keep_path:
                w.meta_data["var"].set(False)  # Don't delete this one
            else:
                w.meta_data["var"].set(True)  # Delete this one
            self.handle_checkbox(w.meta_data["path"], w.meta_data["var"])

    def confirm_delete(self):
        count = len(self.files_to_delete)
        if count == 0:
            return
            
        # Show confirmation with file list
        file_list = "\n".join([f"• {os.path.basename(p)}" for p in list(self.files_to_delete)[:10]])
        if count > 10:
            file_list += f"\n• ... and {count - 10} more files"
        
        if messagebox.askyesno("Confirm Delete", 
                               f"Permanently delete {count} selected files?\n\n"
                               f"Files to delete:\n{file_list}\n\n"
                               f"This action cannot be undone!"):
            self.perform_deletion()

    def perform_deletion(self):
        errors = []
        deleted = 0
        
        # Create a progress window
        progress_window = ctk.CTkToplevel(self)
        progress_window.title("Deleting Files")
        progress_window.geometry("400x150")
        progress_window.transient(self)
        progress_window.grab_set()
        
        ctk.CTkLabel(progress_window, text="Deleting files...", font=("Arial", 14)).pack(pady=20)
        progress_bar = ctk.CTkProgressBar(progress_window, width=350)
        progress_bar.pack(pady=10)
        progress_bar.set(0)
        
        status_label = ctk.CTkLabel(progress_window, text="")
        status_label.pack(pady=10)
        
        total_files = len(self.files_to_delete)
        
        for i, path in enumerate(list(self.files_to_delete)):
            try:
                progress_bar.set(i / total_files)
                status_label.configure(text=f"Deleting: {os.path.basename(path)}")
                progress_window.update()
                
                os.remove(path)
                deleted += 1
                
                # Remove from current display if it's in the current group
                if path in self.current_group_files:
                    self.current_group_files.remove(path)
                    
            except Exception as e:
                errors.append(f"{os.path.basename(path)}: {str(e)}")
        
        progress_window.destroy()
        
        # Show results
        result_msg = f"Successfully deleted {deleted} files."
        if errors:
            error_list = "\n".join(errors[:5])
            if len(errors) > 5:
                error_list += f"\n... and {len(errors) - 5} more errors"
            result_msg += f"\n\nErrors encountered:\n{error_list}"
        
        messagebox.showinfo("Deletion Complete", result_msg)
        
        # Update UI
        self.status_label.configure(text=f"Deleted {deleted} files. Refresh to see changes.")
        self.files_to_delete = set()
        self.update_delete_btn()
        
        # Reload current group if it still has files
        if self.current_group_files:
            self.load_group(self.current_group_hash, self.current_group_files, self.current_selected_group)


class SortView(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        
        self.source_dir = ctk.StringVar()
        self.dest_dir = ctk.StringVar(value=os.path.expanduser("~/Photos/Organized"))
        self.total_files = 0
        self.processed_files = 0
        
        # Configure grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        
        # Title
        title = ctk.CTkLabel(self, text="Sort Photos by Date", font=ctk.CTkFont(size=24, weight="bold"))
        title.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")
        
        # Description
        desc = ctk.CTkLabel(self, 
                           text="Organize photos into folders by year and month (YYYY-MM) based on creation/modification date.",
                           text_color="gray")
        desc.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="w")
        
        # Source Selection Frame
        source_frame = ctk.CTkFrame(self)
        source_frame.grid(row=2, column=0, padx=20, pady=10, sticky="ew")
        
        ctk.CTkLabel(source_frame, text="Source Folder:", font=("Arial", 14)).pack(anchor="w", padx=10, pady=(10, 5))
        
        source_input_frame = ctk.CTkFrame(source_frame, fg_color="transparent")
        source_input_frame.pack(fill="x", padx=10, pady=5)
        
        self.source_entry = ctk.CTkEntry(source_input_frame, textvariable=self.source_dir, placeholder_text="Select folder containing photos")
        self.source_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        ctk.CTkButton(source_input_frame, text="Browse", command=self.browse_source, width=100).pack(side="right")
        
        # Destination Selection Frame
        dest_frame = ctk.CTkFrame(self)
        dest_frame.grid(row=3, column=0, padx=20, pady=10, sticky="ew")
        
        ctk.CTkLabel(dest_frame, text="Destination Folder:", font=("Arial", 14)).pack(anchor="w", padx=10, pady=(10, 5))
        
        dest_input_frame = ctk.CTkFrame(dest_frame, fg_color="transparent")
        dest_input_frame.pack(fill="x", padx=10, pady=5)
        
        self.dest_entry = ctk.CTkEntry(dest_input_frame, textvariable=self.dest_dir)
        self.dest_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        ctk.CTkButton(dest_input_frame, text="Browse", command=self.browse_dest, width=100).pack(side="right")
        
        # Options Frame
        options_frame = ctk.CTkFrame(self)
        options_frame.grid(row=4, column=0, padx=20, pady=10, sticky="ew")
        
        ctk.CTkLabel(options_frame, text="Options:", font=("Arial", 14)).pack(anchor="w", padx=10, pady=(10, 5))
        
        self.organize_var = ctk.StringVar(value="copy")
        organize_frame = ctk.CTkFrame(options_frame, fg_color="transparent")
        organize_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(organize_frame, text="Action:").pack(side="left", padx=(0, 10))
        ctk.CTkRadioButton(organize_frame, text="Copy files", variable=self.organize_var, value="copy").pack(side="left", padx=(0, 10))
        ctk.CTkRadioButton(organize_frame, text="Move files", variable=self.organize_var, value="move").pack(side="left")
        
        # Progress Frame
        progress_frame = ctk.CTkFrame(self)
        progress_frame.grid(row=5, column=0, padx=20, pady=20, sticky="ew")
        
        self.progress_label = ctk.CTkLabel(progress_frame, text="Ready")
        self.progress_label.pack(pady=10)
        
        self.progress_bar = ctk.CTkProgressBar(progress_frame, width=400)
        self.progress_bar.pack(pady=(0, 10))
        self.progress_bar.set(0)
        
        # Action Buttons
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.grid(row=6, column=0, padx=20, pady=20)
        
        ctk.CTkButton(button_frame, text="Preview Organization", command=self.preview_organization, 
                     width=180, height=40).pack(side="left", padx=10)
        
        ctk.CTkButton(button_frame, text="Start Organizing", command=self.start_organization, 
                     fg_color="#198754", hover_color="#13653f", width=180, height=40).pack(side="left", padx=10)

    def browse_source(self):
        path = filedialog.askdirectory()
        if path:
            self.source_dir.set(path)

    def browse_dest(self):
        path = filedialog.askdirectory()
        if path:
            self.dest_dir.set(path)

    def preview_organization(self):
        source = self.source_dir.get()
        dest = self.dest_dir.get()
        
        if not source or not os.path.isdir(source):
            messagebox.showerror("Error", "Please select a valid source folder.")
            return
            
        if not dest or not os.path.isdir(dest):
            messagebox.showerror("Error", "Please select a valid destination folder.")
            return
            
        # Count files and show structure
        file_count = 0
        month_structure = defaultdict(int)
        
        for root, dirs, files in os.walk(source):
            for file in files:
                if file.lower().endswith(SUPPORTED_EXTENSIONS):
                    file_count += 1
                    path = os.path.join(root, file)
                    try:
                        mtime = os.path.getmtime(path)
                        date = datetime.datetime.fromtimestamp(mtime)
                        month_key = date.strftime("%Y-%m")
                        month_structure[month_key] += 1
                    except:
                        pass
        
        if file_count == 0:
            messagebox.showinfo("Preview", "No supported files found in source folder.")
            return
            
        # Create preview message
        preview_msg = f"Found {file_count} files to organize.\n\n"
        preview_msg += "Folder structure that will be created:\n"
        
        for month in sorted(month_structure.keys()):
            preview_msg += f"  📁 {month}/ - {month_structure[month]} files\n"
        
        preview_msg += f"\nDestination: {dest}\n"
        preview_msg += f"Action: {'Move' if self.organize_var.get() == 'move' else 'Copy'} files"
        
        messagebox.showinfo("Organization Preview", preview_msg)

    def start_organization(self):
        source = self.source_dir.get()
        dest = self.dest_dir.get()
        
        if not source or not os.path.isdir(source):
            messagebox.showerror("Error", "Please select a valid source folder.")
            return
            
        if not dest or not os.path.isdir(dest):
            messagebox.showerror("Error", "Please select a valid destination folder.")
            return
            
        # Confirm action
        action = "move" if self.organize_var.get() == "move" else "copy"
        if not messagebox.askyesno("Confirm", f"Are you sure you want to {action} all files from\n{source}\nto\n{dest}\norganized by month?"):
            return
        
        # Start organization in thread
        self.progress_label.configure(text="Starting organization...")
        self.progress_bar.set(0)
        
        thread = threading.Thread(target=self.organize_files, args=(source, dest, action))
        thread.start()

    def organize_files(self, source, dest, action):
        files_processed = 0
        files_copied = 0
        errors = []
        
        # First, count total files
        self.total_files = 0
        for root, dirs, files in os.walk(source):
            for file in files:
                if file.lower().endswith(SUPPORTED_EXTENSIONS):
                    self.total_files += 1
        
        if self.total_files == 0:
            self.after(0, lambda: messagebox.showinfo("Complete", "No files found to organize."))
            return
        
        for root, dirs, files in os.walk(source):
            for file in files:
                if file.lower().endswith(SUPPORTED_EXTENSIONS):
                    src_path = os.path.join(root, file)
                    
                    try:
                        # Get file modification time
                        mtime = os.path.getmtime(src_path)
                        date = datetime.datetime.fromtimestamp(mtime)
                        
                        # Create destination folder structure
                        year_month = date.strftime("%Y-%m")
                        dest_folder = os.path.join(dest, year_month)
                        os.makedirs(dest_folder, exist_ok=True)
                        
                        # Generate unique filename if needed
                        dest_path = os.path.join(dest_folder, file)
                        counter = 1
                        while os.path.exists(dest_path):
                            name, ext = os.path.splitext(file)
                            dest_path = os.path.join(dest_folder, f"{name}_{counter}{ext}")
                            counter += 1
                        
                        # Copy or move the file
                        if action == "copy":
                            shutil.copy2(src_path, dest_path)
                            files_copied += 1
                        else:  # move
                            shutil.move(src_path, dest_path)
                            files_copied += 1
                            
                    except Exception as e:
                        errors.append(f"{file}: {str(e)}")
                    
                    files_processed += 1
                    
                    # Update progress
                    progress = files_processed / self.total_files
                    self.after(0, self.update_sort_progress, progress, files_processed)
        
        # Show completion message
        self.after(0, self.show_organization_results, files_copied, errors)

    def update_sort_progress(self, progress, processed):
        self.progress_bar.set(progress)
        self.progress_label.configure(text=f"Processed {processed} of {self.total_files} files")

    def show_organization_results(self, files_organized, errors):
        result_msg = f"Successfully organized {files_organized} files."
        if errors:
            error_list = "\n".join(errors[:5])
            if len(errors) > 5:
                error_list += f"\n... and {len(errors) - 5} more errors"
            result_msg += f"\n\nErrors encountered:\n{error_list}"
        
        messagebox.showinfo("Organization Complete", result_msg)
        self.progress_label.configure(text="Ready")
        self.progress_bar.set(0)


if __name__ == "__main__":
    app = PhotoOrganizerApp()
    app.mainloop()