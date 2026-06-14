import customtkinter as ctk
from tkinter import filedialog, messagebox
import os

# Simple working version
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class SimplePhotoOrganizer(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Photo Organizer")
        self.geometry("800x600")
        
        # Simple UI
        self.label = ctk.CTkLabel(self, text="Photo Organizer", font=("Arial", 24))
        self.label.pack(pady=20)
        
        self.button = ctk.CTkButton(self, text="Browse Folder", command=self.browse_folder)
        self.button.pack(pady=10)
        
        self.textbox = ctk.CTkTextbox(self)
        self.textbox.pack(pady=10, padx=20, fill="both", expand=True)
        
    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.textbox.delete("1.0", "end")
            self.textbox.insert("end", f"Selected folder: {folder}\n")
            
            # Count image files
            image_count = 0
            for root, dirs, files in os.walk(folder):
                for file in files:
                    if file.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                        image_count += 1
            
            self.textbox.insert("end", f"Found {image_count} image files\n")

app = SimplePhotoOrganizer()
app.mainloop()