# converter/app.py
import json
import os

import webview

from batch import scan_folder, run_batch, find_collisions
from core.dispatch import SUPPORTED_EXTS, ext_of, output_path_for

UI_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "index.html")
FILE_TYPE_FILTER = f"Supported files ({';'.join('*.' + e for e in SUPPORTED_EXTS)})"


class Api:
    """Bridges the glass-UI frontend (ui/index.html) to the existing batch-
    conversion logic in batch.py / core.dispatch — unchanged from the previous
    Tkinter app, just called from JS instead of a Tk callback."""

    def __init__(self):
        # Underscore-prefixed: pywebview builds the JS-callable API by walking
        # every *public* attribute on this object with dir()/getattr(), recursing
        # into anything non-callable — a plain `self.window` would have it walk
        # straight into the native WinForms window object, and from there into
        # raw .NET COM properties (window.native.AccessibilityObject.Bounds...),
        # which cycles back on itself indefinitely (Rectangle.Empty exposes its
        # own .Empty, forever) and hangs the window before it ever opens.
        # pywebview explicitly skips underscore-prefixed names during that walk,
        # so this is the actual fix, not a workaround.
        self._window = None  # set once the window exists, see main()

    def add_files(self):
        result = self._window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=True, file_types=(FILE_TYPE_FILTER,))
        return list(result) if result else []

    def add_folder(self):
        result = self._window.create_file_dialog(webview.FOLDER_DIALOG)
        if not result:
            return []
        return scan_folder(result[0])

    def get_targets(self):
        return list(SUPPORTED_EXTS)

    def check_conflicts(self, paths, target_ext):
        collisions = find_collisions(paths, target_ext)
        collision_error = None
        if collisions:
            lines = "\n".join(
                f"{os.path.basename(a)} and {os.path.basename(b)} -> {os.path.basename(out)}"
                for a, b, out in collisions
            )
            collision_error = (
                "These queued files would overwrite each other's output and cannot be "
                f"converted together:\n{lines}\n\nRename one of each pair or convert them separately."
            )

        overwrites = []
        for path in paths:
            if ext_of(path) == target_ext:
                continue
            candidate = output_path_for(path, target_ext)
            if os.path.exists(candidate):
                overwrites.append(candidate)

        return {"collision_error": collision_error, "overwrites": overwrites}

    def run_conversion(self, paths, target_ext):
        def on_update(path, status):
            self._window.evaluate_js(f"setStatus({json.dumps(path)}, {json.dumps(status)})")

        run_batch(paths, target_ext, on_update)


def main():
    api = Api()
    window = webview.create_window(
        "Format Converter", UI_PATH, js_api=api, width=780, height=560, min_size=(580, 400),
        background_color="#14101f",
    )
    api._window = window
    webview.start()


if __name__ == "__main__":
    main()
