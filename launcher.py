import os
import json
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import sys
import urllib.request
import shutil
import zipfile
import tempfile

# Optional Pillow support for banner resizing. If not installed we fall back to Tk's PhotoImage
try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except Exception:
    Image = None
    ImageTk = None
    HAS_PIL = False

# Launcher with vertical tabs and banner images for Season 1 / Season 2

# Theme colors
BG_COLOR = "#07380b"      # dark green background
SIDEBAR_BG = "#0b3d0b"
BTN_BG = "#146114"
BTN_ACTIVE = "#1f7b1f"
BTN_FG = "#ffffff"

APP_DIR = os.path.dirname(os.path.abspath(__file__))

# When bundled as a one-file PyInstaller exe, APP_DIR points to a temporary
# extraction folder that is removed after the process exits. We must not
# store persistent user data there. Prefer a persistent per-user config
# directory when frozen; otherwise keep config next to the script during
# development.
if getattr(sys, 'frozen', False):
    CONFIG_DIR = os.path.join(os.path.expanduser("~"), "Documents", 'MCSM-Launcher')
else:
    CONFIG_DIR = APP_DIR

# Ensure the config directory exists so writes won't fail
try:
    os.makedirs(CONFIG_DIR, exist_ok=True)
except Exception:
    # Non-fatal; save_config will try again before writing
    pass

CONFIG_PATH = os.path.join(CONFIG_DIR, 'launcher_config.json')
ASSETS_DIR = os.path.join(APP_DIR, 'assets')

# Default saves locations inside user's Documents
S1_SAVES_DIR = os.path.join(os.path.expanduser("~"), "Documents", "Telltale Games", "S1")
S2_SAVES_DIR = os.path.join(os.path.expanduser("~"), "Documents", "Telltale Games", "S2")

DEFAULT_CONFIG = {
    "season1_path": "",
    "season2_path": "",
    # save locations (remember user's choice)
    "s1_saves": S1_SAVES_DIR,
    "s2_saves": S2_SAVES_DIR,
}


class LauncherApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Minecraft Story Mode Launcher")
        self.geometry("800x440")
        self.minsize(700, 360)

        self.config = self.load_config()
        self.photo_refs = {}

        # Apply background color
        try:
            self.configure(bg=BG_COLOR)
        except Exception:
            pass

        # Attempt to load and set the application/window icon from assets/Logo.png
        try:
            logo_path = os.path.join(ASSETS_DIR, "Logo.png")
            if os.path.exists(logo_path):
                if HAS_PIL:
                    try:
                        _img = Image.open(logo_path)
                        _tkimg = ImageTk.PhotoImage(_img)
                    except Exception:
                        _tkimg = None
                else:
                    try:
                        _tkimg = tk.PhotoImage(file=logo_path)
                    except Exception:
                        _tkimg = None

                if _tkimg:
                    # keep reference to avoid GC
                    self._logo_img = _tkimg
                    try:
                        # Preferred Tk call to set window icon
                        self.iconphoto(False, self._logo_img)
                    except Exception:
                        try:
                            self.wm_iconphoto(False, self._logo_img)
                        except Exception:
                            pass
        except Exception:
            # non-fatal if icon can't be set
            pass

        # keep track of banner labels so we can refresh them on resize
        # each entry is (label_widget, filename, title_text)
        self.banner_labels = []
        # cache scaled PhotoImage objects: key=(filename, height) -> PhotoImage
        self._banner_cache = {}

        # icon cache key=(filename, size)
        self._icon_cache = {}

        # used for debouncing configure events
        self._resize_after_id = None

        self.create_widgets()

        # Bind resize to schedule banner refresh (debounced)
        self.bind("<Configure>", self._on_resize)

    def load_config(self):
        # Load config from disk if present. If missing, create a default
        # config file at CONFIG_PATH (ensuring parent dirs exist) so that
        # the bundled exe has a persistent config file to modify.
        try:
            if os.path.exists(CONFIG_PATH):
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return {**DEFAULT_CONFIG, **data}
            else:
                # Create parent directory if necessary and write default config
                cfg_dir = os.path.dirname(CONFIG_PATH)
                if cfg_dir and not os.path.isdir(cfg_dir):
                    try:
                        os.makedirs(cfg_dir, exist_ok=True)
                    except Exception:
                        pass
                try:
                    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                        json.dump(DEFAULT_CONFIG, f, indent=2)
                except Exception:
                    # If we can't write the file that's non-fatal; continue
                    pass
                return DEFAULT_CONFIG.copy()
        except Exception:
            pass
        return DEFAULT_CONFIG.copy()

    def save_config(self):
        try:
            # Ensure parent directory exists (important for frozen exe)
            cfg_dir = os.path.dirname(CONFIG_PATH)
            if cfg_dir and not os.path.isdir(cfg_dir):
                try:
                    os.makedirs(cfg_dir, exist_ok=True)
                except Exception:
                    pass
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save config: {e}")

    def create_widgets(self):
        # Use tk.Frame so we can set background color easily
        container = tk.Frame(self, bg=BG_COLOR, padx=8, pady=8)
        container.pack(fill=tk.BOTH, expand=True)

        # Left sidebar for vertical tabs
        sidebar = tk.Frame(container, width=180, bg=SIDEBAR_BG)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)

        # Blocky, bigger tab buttons (use tk.Button for stronger styling control)
        btn_font = (None, 11, "bold")
        def make_tab_button(text, cmd):
            b = tk.Button(sidebar, text=text, command=cmd,
                          bg=BTN_BG, activebackground=BTN_ACTIVE, fg=BTN_FG,
                          relief=tk.RAISED, bd=0, padx=12, pady=12, font=btn_font)
            b.pack(fill=tk.X, pady=8, padx=10)
            return b

        btn_home = make_tab_button("HOME", self.show_home)
        btn_s1 = make_tab_button("SEASON 1", self.show_season1)
        btn_s2 = make_tab_button("SEASON 2", self.show_season2)
        btn_saves = make_tab_button("SAVES", self.show_saves)

        # Main area
        self.main_area = tk.Frame(container, bg=BG_COLOR)
        self.main_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(12, 0))

        # Create tab frames (use tk.Frame so background matches)
        self.home_frame = tk.Frame(self.main_area, bg=BG_COLOR)
        self.s1_frame = tk.Frame(self.main_area, bg=BG_COLOR)
        self.s2_frame = tk.Frame(self.main_area, bg=BG_COLOR)
        self.saves_frame = tk.Frame(self.main_area, bg=BG_COLOR)

        self.create_home(self.home_frame)
        self.create_season_page(self.s1_frame, "Season 1", "S1logo.png", "season1_path")
        self.create_season_page(self.s2_frame, "Season 2", "S2logo.png", "season2_path")
        self.create_saves_page(self.saves_frame)

        # Start on Home
        self.show_home()

    def clear_main(self):
        for f in (self.home_frame, self.s1_frame, self.s2_frame, self.saves_frame):
            f.pack_forget()

    def show_home(self):
        self.clear_main()
        self.home_frame.pack(fill=tk.BOTH, expand=True)

    def show_season1(self):
        self.clear_main()
        self.s1_frame.pack(fill=tk.BOTH, expand=True)

    def show_season2(self):
        self.clear_main()
        self.s2_frame.pack(fill=tk.BOTH, expand=True)

    def show_saves(self):
        self.clear_main()
        self.saves_frame.pack(fill=tk.BOTH, expand=True)

    def load_banner(self, filename):
        path = os.path.join(ASSETS_DIR, filename)
        if not os.path.exists(path):
            return None

        # target locked banner height (pixels)
        MAX_BANNER_HEIGHT = 170

        if HAS_PIL:
            try:
                # Load with PIL and scale to MAX_BANNER_HEIGHT while preserving aspect ratio
                img = Image.open(path)
                w, h = img.size
                if h > MAX_BANNER_HEIGHT:
                    scale = MAX_BANNER_HEIGHT / float(h)
                    new_w = max(1, int(w * scale))
                    new_h = max(1, int(h * scale))
                    img = img.resize((new_w, new_h), Image.LANCZOS)
                # Convert to ImageTk.PhotoImage for Tk
                tkimg = ImageTk.PhotoImage(img)
                self.photo_refs[path] = tkimg
                return tkimg
            except Exception:
                # fallback to PhotoImage if PIL can't handle it
                pass

        try:
            tkimg = tk.PhotoImage(file=path)
            # If image is taller than MAX_BANNER_HEIGHT we attempt a crude subsample
            try:
                h = tkimg.height()
                if h > MAX_BANNER_HEIGHT:
                    factor = max(1, int(h // MAX_BANNER_HEIGHT))
                    tkimg = tkimg.subsample(factor, factor)
            except Exception:
                pass
            self.photo_refs[path] = tkimg
            return tkimg
        except Exception:
            return None

    def load_icon(self, filename, size):
        """Load and return a PhotoImage for an icon (square size px)."""
        path = os.path.join(ASSETS_DIR, filename)
        if not os.path.exists(path):
            return None
        key = (path, size)
        cached = self._icon_cache.get(key)
        if cached:
            return cached

        if HAS_PIL:
            try:
                img = Image.open(path).convert("RGBA")
                img = img.resize((size, size), Image.LANCZOS)
                tkimg = ImageTk.PhotoImage(img)
                self._icon_cache[key] = tkimg
                return tkimg
            except Exception:
                pass

        try:
            tkimg = tk.PhotoImage(file=path)
            try:
                h = tkimg.height()
                if h > size:
                    factor = max(1, int(h // size))
                    tkimg = tkimg.subsample(factor, factor)
            except Exception:
                pass
            self._icon_cache[key] = tkimg
            return tkimg
        except Exception:
            return None

    def _on_resize(self, event):
        # Debounce rapid configure events (windows send many while resizing).
        if self._resize_after_id:
            try:
                self.after_cancel(self._resize_after_id)
            except Exception:
                pass
        # Schedule actual refresh after short delay
        self._resize_after_id = self.after(150, self._refresh_banners)

    def _refresh_banners(self):
        """Refresh all banner labels using cached scaled images where possible."""
        self._resize_after_id = None
        # target locked banner height (pixels)
        MAX_BANNER_HEIGHT = 180
        for entry in list(self.banner_labels):
            try:
                lbl, filename, title_text = entry
            except Exception:
                # backward compatibility if tuple missing title_text
                try:
                    lbl, filename = entry
                except Exception:
                    continue
                title_text = ""
            # Use cache key (filename, MAX_BANNER_HEIGHT)
            key = (filename, MAX_BANNER_HEIGHT)
            img = self._banner_cache.get(key)
            if img is None:
                # load and cache
                img = self.load_banner(filename)
                if img:
                    self._banner_cache[key] = img
            if img:
                lbl.configure(image=img, text="")
                lbl.image = img
            else:
                lbl.configure(image="", text=title_text, anchor="w")

    def _set_banner_on_label(self, label, filename, title_text=""):
        """Set a single banner label using cache or by loading the banner."""
        MAX_BANNER_HEIGHT = 180
        key = (filename, MAX_BANNER_HEIGHT)
        img = self._banner_cache.get(key)
        if img is None:
            img = self.load_banner(filename)
            if img:
                self._banner_cache[key] = img
        if img:
            label.configure(image=img, text="")
            label.image = img
        else:
            label.configure(image="", text=title_text, anchor="w")

    def create_home(self, parent):
        parent.columnconfigure(0, weight=1)
        title = "Welcome to the Minecraft Story Mode Launcher"
        lbl = tk.Label(parent, text=title, font=(None, 16, "bold"), bg=BG_COLOR, fg=BTN_FG)
        lbl.grid(row=0, column=0, sticky=tk.W, pady=(6, 12), padx=6)

        info = (
            "Use the left-hand tabs to choose Season 1 or Season 2.\n"
            "On a season page you can browse to the game's .exe and press Launch.\n\n"
            "If you don't have the game installed, you can download it from archive.org using the provided button.\n\n"
        )
        info_lbl = tk.Label(parent, text=info, wraplength=560, justify=tk.LEFT, bg=BG_COLOR, fg=BTN_FG)
        info_lbl.grid(row=1, column=0, sticky=tk.W, padx=6)

        # Big icon buttons for quick access to seasons
        # Quick actions label and centered icon buttons
        quick_lbl = tk.Label(parent, text="Quick Actions", font=(None, 12, "bold"), bg=BG_COLOR, fg=BTN_FG)
        quick_lbl.grid(row=2, column=0, pady=(12, 6))

        btns_frame = tk.Frame(parent, bg=BG_COLOR)
        # Place the button frame in the grid cell centered (no sticky => center)
        btns_frame.grid(row=3, column=0, pady=(0, 0), padx=6)

        ICON_SIZE = 96
        s1_icon = self.load_icon("S1icon.png", ICON_SIZE)
        s2_icon = self.load_icon("S2icon.png", ICON_SIZE)

        common_btn_opts = dict(bg=BTN_BG, activebackground=BTN_ACTIVE, fg=BTN_FG, relief=tk.RAISED, bd=0, padx=12, pady=8)

        if s1_icon:
            btn1 = tk.Button(btns_frame, text="Season 1", image=s1_icon, compound="top", command=self.show_season1, **common_btn_opts)
            btn1.image = s1_icon
        else:
            btn1 = tk.Button(btns_frame, text="Season 1", command=self.show_season1, **common_btn_opts)
        btn1.pack(side=tk.LEFT, padx=(0, 12))

        if s2_icon:
            btn2 = tk.Button(btns_frame, text="Season 2", image=s2_icon, compound="top", command=self.show_season2, **common_btn_opts)
            btn2.image = s2_icon
        else:
            btn2 = tk.Button(btns_frame, text="Season 2", command=self.show_season2, **common_btn_opts)
        btn2.pack(side=tk.LEFT)

    def create_season_page(self, parent, title_text, banner_filename, config_key):
        parent.columnconfigure(0, weight=1)
        # Banner (use tk.Label so bg can be set)
        banner_label = tk.Label(parent, bg=BG_COLOR)
        banner_label.grid(row=0, column=0, sticky=tk.W+tk.E, pady=(0, 8))
        # store title_text so fallback text can be used when image is missing
        self.banner_labels.append((banner_label, banner_filename, title_text))
        self._set_banner_on_label(banner_label, banner_filename, title_text)

        # Path selection (use tk widgets so background matches)
        path_frame = tk.Frame(parent, bg=BG_COLOR)
        path_frame.grid(row=1, column=0, sticky=tk.EW, padx=6)
        path_frame.columnconfigure(0, weight=1)

        var = tk.StringVar(value=self.config.get(config_key, ""))
        entry = tk.Entry(path_frame, textvariable=var, bg="#ffffff", fg="#000000", insertbackground="#000000")
        entry.grid(row=0, column=0, sticky=tk.EW)

        def on_browse():
            initial = var.get() if var.get() else os.path.expanduser("~")
            p = filedialog.askopenfilename(title=f"Select {title_text} executable",
                                           initialdir=os.path.dirname(initial) if os.path.exists(initial) else initial,
                                           filetypes=[("Executables", "*.exe"), ("All files", "*")])
            if p:
                var.set(p)
                self.config[config_key] = p
                self.save_config()

        def on_launch():
            p = var.get().strip()
            if not p:
                messagebox.showwarning("No path", "Please select the executable path first.")
                return
            if not os.path.exists(p):
                messagebox.showerror("Not found", f"The selected file does not exist:\n{p}")
                return
            try:
                subprocess.Popen([p], cwd=os.path.dirname(p))
            except Exception as e:
                messagebox.showerror("Launch failed", f"Failed to launch the game: {e}")

        btn_frame = tk.Frame(path_frame, bg=BG_COLOR)
        btn_frame.grid(row=0, column=1, sticky=tk.E, padx=(8, 0))

        browse_btn = tk.Button(btn_frame, text="Browse…", command=on_browse, bg=BTN_BG, fg=BTN_FG, activebackground=BTN_ACTIVE)
        browse_btn.pack(side=tk.LEFT)

        # Prominent centered Play button below the path
        launch_btn = tk.Button(parent, text="Play", command=on_launch,
                    bg=BTN_BG, fg=BTN_FG, activebackground=BTN_ACTIVE,
                    font=(None, 13, "bold"), width=24)
        # place in row 2 centered under the path entry
        launch_btn.grid(row=2, column=0, pady=(12, 8))

        # Download from archive.org button + progress
        dl_frame = tk.Frame(parent, bg=BG_COLOR)
        dl_frame.grid(row=3, column=0, sticky=tk.EW, pady=(12, 0), padx=6)

        progress = ttk.Progressbar(dl_frame, orient=tk.HORIZONTAL, length=520, mode='determinate')

        status_lbl = tk.Label(dl_frame, text="", bg=BG_COLOR, fg=BTN_FG)

        # Initially hide progress and status until a download starts
        def show_progress_widget():
            try:
                # pack progress and status if not already packed
                if not getattr(progress, '_packed', False):
                    progress.pack(fill=tk.X, side=tk.TOP, pady=(0, 6))
                    progress._packed = True
                if not getattr(status_lbl, '_packed', False):
                    status_lbl.pack(anchor=tk.W)
                    status_lbl._packed = True
            except Exception:
                pass

        def hide_progress_widget():
            try:
                if getattr(progress, '_packed', False):
                    progress.pack_forget()
                    progress._packed = False
                if getattr(status_lbl, '_packed', False):
                    status_lbl.pack_forget()
                    status_lbl._packed = False
            except Exception:
                pass

        def update_progress(value, text=None):
            # ensure progress widgets are visible
            def cb():
                show_progress_widget()
                try:
                    progress['value'] = value
                except Exception:
                    pass
                if text is not None:
                    status_lbl.config(text=text)
            self.after(0, cb)

        def on_download_click(url, default_folder_name, expected_exe_name):
            # When running as a PyInstaller one-file executable, APP_DIR
            # points to the temporary extraction folder which is ephemeral.
            # In that case prefer a persistent location under the user's
            # Documents folder. Otherwise use the repository/app dir so
            # running from source keeps installs next to the app.
            if getattr(sys, 'frozen', False):
                base_install_dir = os.path.join(os.path.expanduser("~"), "Documents", "MCSM-Launcher")
            else:
                base_install_dir = APP_DIR
            default_dir = os.path.join(base_install_dir, default_folder_name)
            use_default = messagebox.askyesno("Install location",
                                              f"Default install folder will be:\n{default_dir}\n\nUse this location?\n(Choose No to select a different folder)")
            if use_default:
                target_dir = default_dir
            else:
                d = filedialog.askdirectory(title="Select install folder", initialdir=APP_DIR)
                if not d:
                    status_lbl.config(text="Download cancelled.")
                    return
                target_dir = d

            os.makedirs(target_dir, exist_ok=True)
            status_lbl.config(text="Starting download...")
            progress['value'] = 0

            def download_worker():
                try:
                    # Try to use a multi-threaded ranged download when possible.
                    tmp_fd, tmp_path = tempfile.mkstemp(suffix='.zip')
                    os.close(tmp_fd)

                    # First attempt a HEAD request to get content length and range support
                    total = None
                    accept_ranges = False
                    try:
                        head_req = urllib.request.Request(url, method='HEAD')
                        with urllib.request.urlopen(head_req, timeout=15) as head_resp:
                            total_hdr = head_resp.getheader('Content-Length')
                            if total_hdr:
                                total = int(total_hdr)
                            ar = head_resp.getheader('Accept-Ranges')
                            if ar and 'bytes' in ar.lower():
                                accept_ranges = True
                    except Exception:
                        # HEAD might fail; we'll attempt a ranged GET or fallback later
                        pass

                    # If server accepts ranges and file is reasonably large, download in parallel
                    if accept_ranges and total and total > 256 * 1024:
                        # Choose number of threads based on size, cap at 10
                        max_threads = 10
                        part_size = max(256 * 1024, total // max_threads)
                        parts = []
                        ranges = []
                        start = 0
                        while start < total:
                            end = min(total - 1, start + part_size - 1)
                            ranges.append((start, end))
                            start = end + 1

                        downloaded_lock = threading.Lock()
                        downloaded_total = 0
                        part_paths = [f"{tmp_path}.part{i}" for i in range(len(ranges))]

                        def fetch_part(idx, byte_range, out_path):
                            nonlocal downloaded_total
                            start_b, end_b = byte_range
                            req = urllib.request.Request(url)
                            req.add_header('Range', f'bytes={start_b}-{end_b}')
                            try:
                                with urllib.request.urlopen(req, timeout=60) as resp:
                                    with open(out_path, 'wb') as outf:
                                        while True:
                                            chunk = resp.read(16384)
                                            if not chunk:
                                                break
                                            outf.write(chunk)
                                            with downloaded_lock:
                                                downloaded_total += len(chunk)
                                                if total:
                                                    pct = int(downloaded_total * 100 / total)
                                                    update_progress(pct, f"Downloading... {pct}%")
                                                else:
                                                    update_progress(0, f"Downloading... {downloaded_total // 1024} KB")
                            except Exception:
                                # Any exception will be handled by the caller
                                raise

                        threads = []
                        error_during = False
                        try:
                            for i, r in enumerate(ranges):
                                t = threading.Thread(target=fetch_part, args=(i, r, part_paths[i]), daemon=True)
                                threads.append(t)
                                t.start()

                            # wait for threads
                            for t in threads:
                                t.join()
                        except Exception:
                            error_during = True

                        if not error_during:
                            # concatenate parts
                            with open(tmp_path, 'wb') as final_out:
                                for p in part_paths:
                                    with open(p, 'rb') as pf:
                                        shutil.copyfileobj(pf, final_out)
                                    try:
                                        os.remove(p)
                                    except Exception:
                                        pass
                            update_progress(100, "Download complete — extracting...")
                        else:
                            # Clean partial files and fall back to single-stream
                            for p in part_paths:
                                try:
                                    os.remove(p)
                                except Exception:
                                    pass
                            raise Exception("Parallel download failed, falling back")
                    else:
                        # Single-threaded download (fallback)
                        req = urllib.request.urlopen(url, timeout=60)
                        total_hdr = req.getheader('Content-Length')
                        if total_hdr:
                            total = int(total_hdr)
                        chunk_size = 16384
                        downloaded = 0
                        with open(tmp_path, 'wb') as out:
                            while True:
                                chunk = req.read(chunk_size)
                                if not chunk:
                                    break
                                out.write(chunk)
                                downloaded += len(chunk)
                                if total:
                                    pct = int(downloaded * 100 / total)
                                    update_progress(pct, f"Downloading... {pct}%")
                                else:
                                    update_progress(0, f"Downloading... {downloaded // 1024} KB")

                        update_progress(100, "Download complete — extracting...")

                    try:
                        with zipfile.ZipFile(tmp_path, 'r') as z:
                            z.extractall(target_dir)
                    except zipfile.BadZipFile:
                        update_progress(0, "Downloaded file is not a valid zip")
                        os.remove(tmp_path)
                        return

                    os.remove(tmp_path)
                    update_progress(100, "Extract complete — scanning for executable...")

                    # Some season zips contain nested folders. For Season 2 the build
                    # often ends up under a nested path such as:
                    # "S2\Minecraft.Story.Mode.Season.Two\Minecraft Story Mode Season Two"
                    # or similar variations. Detect a likely 'Season Two' folder and
                    # move its contents up into target_dir so the game files aren't
                    # buried several folder levels deep.
                    try:
                        if config_key == 'season2_path':
                            # First, handle the precise nested layout you reported:
                            # S2\Minecraft.Story.Mode.Season.Two\Minecraft Story Mode Season Two
                            precise_candidate = None
                            for root, dirs, files in os.walk(target_dir):
                                parts = os.path.normpath(root).split(os.path.sep)
                                if len(parts) >= 3:
                                    tail3 = [p.lower() for p in parts[-3:]]
                                    if tail3 == ['s2', 'minecraft.story.mode.season.two', 'minecraft story mode season two']:
                                        precise_candidate = root
                                        break

                            if precise_candidate and os.path.isdir(precise_candidate):
                                # Find the nearest ancestor named 'S2' (case-insensitive)
                                dest = None
                                p = precise_candidate
                                while True:
                                    parent = os.path.dirname(p)
                                    if not parent or os.path.normpath(parent) == os.path.normpath(p):
                                        break
                                    if os.path.basename(parent).lower() == 's2':
                                        dest = parent
                                        break
                                    p = parent
                                if dest is None:
                                    # fallback to target_dir
                                    dest = target_dir

                                # Move everything from the deepest folder into the S2 dest
                                for name in os.listdir(precise_candidate):
                                    src = os.path.join(precise_candidate, name)
                                    dst = os.path.join(dest, name)
                                    try:
                                        if os.path.exists(dst):
                                            if os.path.isdir(dst):
                                                shutil.rmtree(dst)
                                            else:
                                                os.remove(dst)
                                        shutil.move(src, dst)
                                    except Exception:
                                        pass
                                try:
                                    shutil.rmtree(precise_candidate, ignore_errors=True)
                                except Exception:
                                    pass
                            else:
                                # Fallback: try flexible matching if the precise pattern wasn't found
                                candidate = None
                                matches = []
                                for root, dirs, files in os.walk(target_dir):
                                    base = os.path.basename(root).lower()
                                    if 'season' in base and 'two' in base and 'story' in base:
                                        matches.append(root)
                                if not matches:
                                    for root, dirs, files in os.walk(target_dir):
                                        base = os.path.basename(root).lower()
                                        if 'minecraft.story.mode' in base or 'minecraft.story.mode.season.two' in base or 'minecraft.st' in base:
                                            matches.append(root)
                                if matches:
                                    candidate = max(matches, key=lambda p: len(p.split(os.path.sep)))
                                    if candidate and os.path.isdir(candidate) and os.path.normpath(candidate) != os.path.normpath(target_dir):
                                        for name in os.listdir(candidate):
                                            src = os.path.join(candidate, name)
                                            dst = os.path.join(target_dir, name)
                                            try:
                                                if os.path.exists(dst):
                                                    if os.path.isdir(dst):
                                                        shutil.rmtree(dst)
                                                    else:
                                                        os.remove(dst)
                                                shutil.move(src, dst)
                                            except Exception:
                                                pass
                                        try:
                                            shutil.rmtree(candidate, ignore_errors=True)
                                        except Exception:
                                            pass
                    except Exception:
                        # non-fatal: continue to normal scan even if moving failed
                        pass

                    found = None
                    for root, dirs, files in os.walk(target_dir):
                        for f in files:
                            if f.lower() == expected_exe_name.lower():
                                found = os.path.join(root, f)
                                break
                        if found:
                            break

                    if found:
                        self.config[config_key] = found
                        self.save_config()
                        update_progress(100, f"Installed and found: {os.path.basename(found)}")
                        def set_entry():
                            entry.delete(0, tk.END)
                            entry.insert(0, found)
                        self.after(0, set_entry)
                        messagebox.showinfo("Install complete", f"Installed to {target_dir}\nFound: {found}")
                    else:
                        update_progress(0, "Install complete — executable not found.")
                        messagebox.showwarning("Install finished", f"Extracted to {target_dir} but did not find {expected_exe_name}")

                    # hide progress widgets after a short delay
                    self.after(700, hide_progress_widget)

                except Exception as e:
                    update_progress(0, "Error during download/install")
                    messagebox.showerror("Error", f"Download/install failed: {e}")
                    self.after(700, hide_progress_widget)

            t = threading.Thread(target=download_worker, daemon=True)
            t.start()

        if config_key == 'season1_path':
            dl_url = 'https://archive.org/download/minecraft-story-mode-s1-2/Minecraft%20Story%20Mode%20S1.zip'
            expected_exe = 'MinecraftStoryMode.exe'
            default_name = 'S1'
        else:
            dl_url = 'https://archive.org/download/minecraft-story-mode-s1-2/Minecraft%20Story%20Mode%20S2.zip'
            expected_exe = 'Minecraft2.exe'
            default_name = 'S2'

        dl_btn = tk.Button(dl_frame, text='Download from archive.org', command=lambda: on_download_click(dl_url, default_name, expected_exe), bg=BTN_BG, fg=BTN_FG, activebackground=BTN_ACTIVE)
        dl_btn.pack(anchor=tk.W, pady=(6, 0))

    def create_saves_page(self, parent):
        parent.columnconfigure(0, weight=1)
        title = tk.Label(parent, text="Saves Manager", font=(None, 14, "bold"), bg=BG_COLOR, fg=BTN_FG)
        title.grid(row=0, column=0, sticky=tk.W, pady=(6, 12), padx=6)

        info = tk.Label(parent, text="Backup or import save slots for Season 1 and Season 2.", bg=BG_COLOR, fg=BTN_FG)
        info.grid(row=1, column=0, sticky=tk.W, padx=6)

        def make_season_block(row, season_name, saves_dir, config_key):
            frame = tk.Frame(parent, bg=BG_COLOR)
            frame.grid(row=row, column=0, sticky=tk.EW, padx=6, pady=(10, 4))
            # Make column 0 (the path label) expand so buttons in columns 1/2 remain visible
            frame.columnconfigure(0, weight=1)

            lbl = tk.Label(frame, text=season_name, font=(None, 12, "bold"), bg=BG_COLOR, fg=BTN_FG)
            lbl.grid(row=0, column=0, sticky=tk.W)

            # allow the user to change the saves directory; track it with a StringVar
            path_var = tk.StringVar(value=self.config.get(config_key, saves_dir))
            path_lbl = tk.Label(frame, textvariable=path_var, bg=BG_COLOR, fg=BTN_FG, wraplength=520, justify=tk.LEFT)
            path_lbl.grid(row=1, column=0, columnspan=1, sticky=tk.W, pady=(4, 8))

            def choose_folder():
                d = filedialog.askdirectory(title=f"Select {season_name} saves folder", initialdir=path_var.get() or os.path.expanduser("~"))
                if d:
                    path_var.set(d)
                    # remember user's choice
                    try:
                        self.config[config_key] = d
                        self.save_config()
                    except Exception:
                        pass

            choose_btn = tk.Button(frame, text="Choose folder…", command=choose_folder, bg=BTN_BG, fg=BTN_FG, activebackground=BTN_ACTIVE)
            choose_btn.grid(row=1, column=1, sticky=tk.E, padx=(8,0))

            def reset_to_default():
                # reset to the original default passed in (saves_dir)
                path_var.set(saves_dir)
                try:
                    self.config[config_key] = saves_dir
                    self.save_config()
                except Exception:
                    pass

            # Keep two buttons: choose (already present) and reset
            reset_btn = tk.Button(frame, text="Reset", command=reset_to_default, bg=BTN_BG, fg=BTN_FG, activebackground=BTN_ACTIVE)
            # move reset to column 2 now that we removed the Open button
            reset_btn.grid(row=1, column=2, sticky=tk.E, padx=(8,0))

            status = tk.Label(frame, text="", bg=BG_COLOR, fg=BTN_FG)
            status.grid(row=2, column=0, columnspan=4, sticky=tk.W)

            def find_save_files():
                """Return list of tuples (fullpath, relpath) for all files under the saves folder."""
                directory = path_var.get()
                if not os.path.isdir(directory):
                    return []
                found = []
                try:
                    for root, dirs, files in os.walk(directory):
                        for name in files:
                            full = os.path.join(root, name)
                            rel = os.path.relpath(full, start=directory)
                            found.append((full, rel))
                except Exception:
                    pass
                return found

            def backup_action():
                files = find_save_files()
                if not files:
                    messagebox.showinfo("No saves", f"No save files found in {path_var.get()}")
                    return

                default_name = f"{season_name.replace(' ', '_')}_saves_backup.zip"
                dest = filedialog.asksaveasfilename(title="Save backup as", defaultextension=".zip", initialfile=default_name, initialdir=APP_DIR, filetypes=[("Zip files","*.zip")])
                if not dest:
                    return

                status.config(text="Backing up saves...")

                def worker():
                    try:
                        total = len(files)
                        with zipfile.ZipFile(dest, 'w', zipfile.ZIP_DEFLATED) as z:
                            for i, (full, rel) in enumerate(files, start=1):
                                # store with relative path so folder structure is preserved
                                z.write(full, arcname=rel)
                                pct = int(i * 100 / total)
                                self.after(0, lambda p=pct, t=f"Backing up... {pct}%": status.config(text=t))
                        self.after(0, lambda: status.config(text=f"Backup complete: {dest}"))
                        messagebox.showinfo("Backup complete", f"Saved backup to {dest}")
                    except Exception as e:
                        self.after(0, lambda: status.config(text="Backup failed"))
                        messagebox.showerror("Error", f"Backup failed: {e}")

                threading.Thread(target=worker, daemon=True).start()

            def import_action():
                zippath = filedialog.askopenfilename(title="Select backup zip", initialdir=APP_DIR, filetypes=[("Zip files","*.zip" )])
                if not zippath:
                    return
                status.config(text="Importing saves...")

                def worker():
                    try:
                        tmpdir = tempfile.mkdtemp()
                        try:
                            with zipfile.ZipFile(zippath, 'r') as z:
                                z.extractall(tmpdir)
                        except zipfile.BadZipFile:
                            self.after(0, lambda: messagebox.showerror("Error", "Selected file is not a valid zip"))
                            shutil.rmtree(tmpdir, ignore_errors=True)
                            self.after(0, lambda: status.config(text=""))
                            return

                        # collect all files extracted from the zip and their relative paths
                        found_files = []
                        for root, dirs, files in os.walk(tmpdir):
                            for name in files:
                                full = os.path.join(root, name)
                                rel = os.path.relpath(full, start=tmpdir)
                                found_files.append((full, rel))

                        if not found_files:
                            shutil.rmtree(tmpdir, ignore_errors=True)
                            self.after(0, lambda: status.config(text="No files found in the zip."))
                            self.after(0, lambda: messagebox.showwarning("No files", "No files were found in the selected zip"))
                            return

                        os.makedirs(path_var.get(), exist_ok=True)

                        # Detect files that would be overwritten (by relative path)
                        overwrites = []
                        for full, rel in found_files:
                            dst = os.path.join(path_var.get(), rel)
                            if os.path.exists(dst):
                                overwrites.append(rel)
                        # If there are existing files, ask the user on the main thread whether to overwrite
                        if overwrites:
                            evt = threading.Event()
                            result = {"allow": False}

                            def ask_overwrite():
                                # show a limited list to avoid giant dialogs
                                display_list = "\n".join(overwrites[:50])
                                if len(overwrites) > 50:
                                    display_list += f"\n... and {len(overwrites)-50} more"
                                msg = (
                                    f"The following save files already exist and will be overwritten in:\n{path_var.get()}\n\n"
                                    f"{display_list}\n\nProceed and overwrite these files?"
                                )
                                allow = messagebox.askyesno("Overwrite existing saves?", msg)
                                result["allow"] = bool(allow)
                                evt.set()

                            # schedule the dialog on the main thread and wait for the user's decision
                            self.after(0, ask_overwrite)
                            evt.wait()
                            if not result.get("allow"):
                                shutil.rmtree(tmpdir, ignore_errors=True)
                                self.after(0, lambda: status.config(text="Import cancelled by user."))
                                return

                        # Perform the copy (this will overwrite any existing files if the user allowed it)
                        copied = 0
                        for full, rel in found_files:
                            try:
                                dst = os.path.join(path_var.get(), rel)
                                dst_dir = os.path.dirname(dst)
                                if not os.path.isdir(dst_dir):
                                    os.makedirs(dst_dir, exist_ok=True)
                                shutil.copy2(full, dst)
                                copied += 1
                                # update status occasionally
                                if copied % 10 == 0:
                                    self.after(0, lambda c=copied: status.config(text=f"Imported {c} files..."))
                            except Exception:
                                # skip individual copy errors
                                pass

                        shutil.rmtree(tmpdir, ignore_errors=True)
                        if copied:
                            self.after(0, lambda: status.config(text=f"Imported {copied} save files."))
                            self.after(0, lambda: messagebox.showinfo("Import complete", f"Imported {copied} save files to {saves_dir}"))
                        else:
                            self.after(0, lambda: status.config(text="No save files were imported."))
                            self.after(0, lambda: messagebox.showwarning("No saves", "No save files were imported from the zip"))
                    except Exception as e:
                        self.after(0, lambda: status.config(text="Import failed"))
                        self.after(0, lambda: messagebox.showerror("Error", f"Import failed: {e}"))

                threading.Thread(target=worker, daemon=True).start()

            btn_backup = tk.Button(frame, text="Backup saves (zip)", command=backup_action, bg=BTN_BG, fg=BTN_FG, activebackground=BTN_ACTIVE)
            btn_backup.grid(row=0, column=3, sticky=tk.E)

            btn_import = tk.Button(frame, text="Import saves (zip)", command=import_action, bg=BTN_BG, fg=BTN_FG, activebackground=BTN_ACTIVE)
            btn_import.grid(row=1, column=3, sticky=tk.E)

        make_season_block(2, "Season 1", S1_SAVES_DIR, "s1_saves")
        make_season_block(4, "Season 2", S2_SAVES_DIR, "s2_saves")


if __name__ == "__main__":
    app = LauncherApp()
    app.mainloop()
