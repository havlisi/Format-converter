# converter/app.py
import os
import tkinter as tk
from tkinter import filedialog, ttk, messagebox

from batch import scan_folder, run_batch, find_collisions
from core.dispatch import SUPPORTED_EXTS, ext_of, output_path_for

FILETYPES = [("Supported files", " ".join(f"*.{e}" for e in SUPPORTED_EXTS))]

# A small, self-contained palette — no external theme package required, just
# ttk's built-in "clam" base (the one theme that actually honors color
# overrides on Windows; the native "vista" theme ignores most of them).
BG = "#f4f5f7"
PANEL = "#ffffff"
BORDER = "#e2e4e9"
TEXT = "#1f2328"
SUBTEXT = "#6b7280"
ACCENT = "#3462eb"
ACCENT_HOVER = "#2b52c7"
ACCENT_TEXT = "#ffffff"
GHOST_HOVER = "#eceefb"
ROW_ALT = "#fafbfc"
DONE = "#1a7f37"
ERROR = "#cf222e"
SKIP = "#9a6700"
BUSY = "#3462eb"


class ConverterApp:
    def __init__(self, root):
        self.root = root
        root.title("Format Converter")
        root.geometry("760x520")
        root.minsize(560, 380)
        root.configure(bg=BG)

        self._build_style()

        header = tk.Frame(root, bg=BG)
        header.pack(fill="x", padx=20, pady=(18, 10))
        tk.Label(
            header, text="Format Converter", bg=BG, fg=TEXT,
            font=("Segoe UI Semibold", 16),
        ).pack(anchor="w")
        tk.Label(
            header, text="PDF, XLSX, DOCX, CSV — drop files in, pick a target, convert.",
            bg=BG, fg=SUBTEXT, font=("Segoe UI", 9),
        ).pack(anchor="w")

        toolbar = tk.Frame(root, bg=BG)
        toolbar.pack(fill="x", padx=20, pady=(0, 10))
        ttk.Button(toolbar, text="Add Files…", style="Ghost.TButton", command=self.add_files).pack(side="left")
        ttk.Button(toolbar, text="Add Folder…", style="Ghost.TButton", command=self.add_folder).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(toolbar, text="Clear", style="Ghost.TButton", command=self.clear_list).pack(
            side="left", padx=(8, 0)
        )
        self.count_label = tk.Label(toolbar, text="No files queued", bg=BG, fg=SUBTEXT, font=("Segoe UI", 9))
        self.count_label.pack(side="right")

        # Card housing the file list, so it visually separates from the plain
        # window background instead of the tree sitting flush against it.
        card = tk.Frame(root, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        self.tree = ttk.Treeview(
            card, columns=("status",), show="tree headings", style="Files.Treeview", selectmode="extended"
        )
        self.tree.heading("#0", text="File", anchor="w")
        self.tree.heading("status", text="Status", anchor="w")
        self.tree.column("#0", width=420, anchor="w")
        self.tree.column("status", width=260, anchor="w")
        vsb = ttk.Scrollbar(card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(1, 0), pady=1)
        vsb.pack(side="right", fill="y", pady=1)

        self.row_ids = {}  # path -> treeview item id

        self.tree.tag_configure("even", background=PANEL)
        self.tree.tag_configure("odd", background=ROW_ALT)
        self.tree.tag_configure("done", foreground=DONE)
        self.tree.tag_configure("error", foreground=ERROR)
        self.tree.tag_configure("skipped", foreground=SKIP)
        self.tree.tag_configure("busy", foreground=BUSY)

        self.empty_hint = tk.Label(
            card, text="Nothing queued yet — Add Files or Add Folder to get started",
            bg=PANEL, fg=SUBTEXT, font=("Segoe UI", 9, "italic"),
        )
        self._refresh_empty_hint()

        bottom = tk.Frame(root, bg=BG)
        bottom.pack(fill="x", padx=20, pady=(0, 18))
        tk.Label(bottom, text="Convert to", bg=BG, fg=TEXT, font=("Segoe UI", 9)).pack(side="left")
        self.target_var = tk.StringVar(value=SUPPORTED_EXTS[0])
        ttk.Combobox(
            bottom, textvariable=self.target_var, values=list(SUPPORTED_EXTS),
            state="readonly", width=8, style="Target.TCombobox",
        ).pack(side="left", padx=(8, 0))
        ttk.Button(bottom, text="Convert All", style="Accent.TButton", command=self.convert_all).pack(
            side="right"
        )

    def _build_style(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")

        style.configure("Ghost.TButton", background=BG, foreground=TEXT, borderwidth=1,
                         relief="solid", bordercolor=BORDER, focusthickness=0, padding=(12, 6),
                         font=("Segoe UI", 9))
        style.map("Ghost.TButton", background=[("active", GHOST_HOVER)], bordercolor=[("active", ACCENT)])

        style.configure("Accent.TButton", background=ACCENT, foreground=ACCENT_TEXT, borderwidth=0,
                         focusthickness=0, padding=(16, 8), font=("Segoe UI Semibold", 9))
        style.map("Accent.TButton", background=[("active", ACCENT_HOVER), ("disabled", BORDER)])

        style.configure("Target.TCombobox", padding=4)

        style.configure(
            "Files.Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT,
            borderwidth=0, rowheight=26, font=("Segoe UI", 9),
        )
        style.configure(
            "Files.Treeview.Heading", background=BG, foreground=SUBTEXT, borderwidth=0,
            font=("Segoe UI Semibold", 9), relief="flat",
        )
        style.map("Files.Treeview.Heading", background=[("active", BG)])
        style.map("Files.Treeview", background=[("selected", "#dbe4ff")], foreground=[("selected", TEXT)])
        style.layout("Files.Treeview", style.layout("Treeview"))

    def _refresh_empty_hint(self):
        if self.row_ids:
            self.empty_hint.place_forget()
        else:
            self.empty_hint.place(relx=0.5, rely=0.5, anchor="center")

    def _refresh_count(self):
        n = len(self.row_ids)
        self.count_label.config(text="No files queued" if n == 0 else f"{n} file{'s' if n != 1 else ''} queued")

    def _add_path(self, path):
        if path in self.row_ids:
            return
        tag = "even" if len(self.row_ids) % 2 == 0 else "odd"
        item = self.tree.insert("", "end", text=os.path.basename(path), values=("queued",), tags=(tag,))
        self.row_ids[path] = item
        self._refresh_empty_hint()
        self._refresh_count()

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
        self._refresh_empty_hint()
        self._refresh_count()

    def _status_tag(self, status):
        if status.startswith("done"):
            return "done"
        if status.startswith("error"):
            return "error"
        if status.startswith("skipped"):
            return "skipped"
        if status.startswith("converting"):
            return "busy"
        return ()

    def convert_all(self):
        if not self.row_ids:
            return
        target_ext = self.target_var.get()

        collisions = find_collisions(list(self.row_ids.keys()), target_ext)
        if collisions:
            lines = "\n".join(
                f"{os.path.basename(a)} and {os.path.basename(b)} -> {os.path.basename(out)}"
                for a, b, out in collisions
            )
            messagebox.showerror(
                "Conflicting output files",
                "These queued files would overwrite each other's output "
                f"and cannot be converted together:\n{lines}\n\n"
                "Rename one of each pair or convert them separately.",
            )
            return

        overwrite_paths = []
        for path in self.row_ids:
            if ext_of(path) == target_ext:
                continue
            candidate = output_path_for(path, target_ext)
            if os.path.exists(candidate):
                overwrite_paths.append(candidate)
        if overwrite_paths:
            names = "\n".join(os.path.basename(p) for p in overwrite_paths)
            if not messagebox.askyesno("Overwrite files?", f"These files already exist and will be overwritten:\n{names}"):
                return

        def on_update(path, status):
            item = self.row_ids[path]
            base_tag = "even" if list(self.row_ids).index(path) % 2 == 0 else "odd"
            status_tag = self._status_tag(status)
            tags = (base_tag, status_tag) if status_tag else (base_tag,)
            self.tree.item(item, tags=tags)
            self.tree.set(item, "status", status)
            self.root.update_idletasks()

        run_batch(list(self.row_ids.keys()), target_ext, on_update)


if __name__ == "__main__":
    root = tk.Tk()
    ConverterApp(root)
    root.mainloop()
