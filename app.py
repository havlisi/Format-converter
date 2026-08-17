# converter/app.py
import os
import tkinter as tk
from tkinter import filedialog, ttk, messagebox

from batch import scan_folder, run_batch
from core.dispatch import SUPPORTED_EXTS

FILETYPES = [("Supported files", " ".join(f"*.{e}" for e in SUPPORTED_EXTS))]


class ConverterApp:
    def __init__(self, root):
        self.root = root
        root.title("Format Converter")
        root.geometry("500x320")

        btn_frame = tk.Frame(root)
        btn_frame.pack(fill="x", padx=8, pady=8)
        tk.Button(btn_frame, text="Add Files...", command=self.add_files).pack(side="left")
        tk.Button(btn_frame, text="Add Folder...", command=self.add_folder).pack(side="left", padx=6)
        tk.Button(btn_frame, text="Clear", command=self.clear_list).pack(side="left")

        self.tree = ttk.Treeview(root, columns=("status",), show="tree headings", height=10)
        self.tree.heading("#0", text="File")
        self.tree.heading("status", text="Status")
        self.tree.column("#0", width=300)
        self.tree.column("status", width=180)
        self.tree.pack(fill="both", expand=True, padx=8)

        bottom = tk.Frame(root)
        bottom.pack(fill="x", padx=8, pady=8)
        tk.Label(bottom, text="Convert to:").pack(side="left")
        self.target_var = tk.StringVar(value=SUPPORTED_EXTS[0])
        ttk.Combobox(
            bottom, textvariable=self.target_var, values=list(SUPPORTED_EXTS), state="readonly", width=8
        ).pack(side="left", padx=6)
        tk.Button(bottom, text="Convert All", command=self.convert_all).pack(side="right")

        self.row_ids = {}  # path -> treeview item id

    def _add_path(self, path):
        if path in self.row_ids:
            return
        item = self.tree.insert("", "end", text=os.path.basename(path), values=("queued",))
        self.row_ids[path] = item

    def add_files(self):
        paths = filedialog.askopenfilenames(filetypes=FILETYPES)
        for p in paths:
            self._add_path(p)

    def add_folder(self):
        folder = filedialog.askdirectory()
        if not folder:
            return
        for p in scan_folder(folder):
            self._add_path(p)

    def clear_list(self):
        self.tree.delete(*self.tree.get_children())
        self.row_ids.clear()

    def convert_all(self):
        if not self.row_ids:
            return
        target_ext = self.target_var.get()

        overwrite_paths = []
        for path in self.row_ids:
            source_ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
            if source_ext == target_ext:
                continue
            candidate = path.rsplit(".", 1)[0] + "." + target_ext
            if os.path.exists(candidate):
                overwrite_paths.append(candidate)
        if overwrite_paths:
            names = "\n".join(os.path.basename(p) for p in overwrite_paths)
            if not messagebox.askyesno("Overwrite files?", f"These files already exist and will be overwritten:\n{names}"):
                return

        def on_update(path, status):
            self.tree.set(self.row_ids[path], "status", status)
            self.root.update_idletasks()

        run_batch(list(self.row_ids.keys()), target_ext, on_update)


if __name__ == "__main__":
    root = tk.Tk()
    ConverterApp(root)
    root.mainloop()
