"""ClipForge app: a simple window for clipforge.py (keep both files in the same folder).
Only clip videos and streams you own or have permission to use."""
import os, shutil, subprocess, sys, threading
import tkinter as tk
from tkinter import filedialog, scrolledtext, ttk

FROZEN = getattr(sys, "frozen", False)
HERE = os.path.dirname(sys.executable) if FROZEN else os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "clipforge.py")
os.environ["PATH"] = HERE + os.pathsep + os.environ.get("PATH", "")
if len(sys.argv) > 1 and sys.argv[1] == "--worker":  # the installed app runs its own engine this way
    import clipforge
    sys.argv = [sys.argv[0]] + sys.argv[2:]
    clipforge.main()
    sys.exit(0)
CORNERS = {"Top right": "tr", "Top left": "tl", "Bottom right": "br", "Bottom left": "bl"}
BG, PANEL, INK, MUTED, ACCENT = "#0b1020", "#141b36", "#eef1ff", "#9aa5cc", "#7c5cff"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ClipForge")
        self.geometry("780x700")
        self.minsize(700, 620)
        self.configure(bg=BG)
        self.proc = None
        self.out = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "Videos", "ClipForge"))
        self.link, self.file = tk.StringVar(), tk.StringVar()
        self.minutes, self.clips, self.length = tk.IntVar(value=30), tk.IntVar(value=8), tk.IntVar(value=30)
        self.corner, self.camsize = tk.StringVar(value="Top right"), tk.IntVar(value=25)
        self.caps, self.model = tk.BooleanVar(value=True), tk.StringVar(value="base")
        self.style_widgets()
        self.build()

    def style_widgets(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure(".", background=BG, foreground=INK, fieldbackground=PANEL, font=("Segoe UI", 10))
        s.configure("TFrame", background=BG)
        s.configure("Card.TFrame", background=PANEL)
        s.configure("TLabel", background=BG, foreground=INK)
        s.configure("Card.TLabel", background=PANEL, foreground=MUTED)
        s.configure("H.TLabel", font=("Segoe UI", 22, "bold"))
        s.configure("TCheckbutton", background=PANEL, foreground=INK)
        s.configure("TButton", background=PANEL, foreground=INK, padding=8, borderwidth=0)
        s.map("TButton", background=[("active", "#1d2750")])
        s.configure("Go.TButton", background=ACCENT, foreground="white", font=("Segoe UI", 11, "bold"), padding=10)
        s.map("Go.TButton", background=[("active", "#6a49f0"), ("disabled", "#3a3566")])
        s.configure("TProgressbar", troughcolor=PANEL, background=ACCENT, borderwidth=0)

    def row(self, parent, label, widget, r, c=0):
        ttk.Label(parent, text=label, style="Card.TLabel").grid(row=r, column=c, sticky="w", padx=(0, 8), pady=6)
        widget.grid(row=r, column=c + 1, sticky="ew", pady=6, padx=(0, 18))

    def build(self):
        top = ttk.Frame(self, padding=(22, 18, 22, 6))
        top.pack(fill="x")
        ttk.Label(top, text="ClipForge", style="H.TLabel").pack(anchor="w")
        ttk.Label(top, text="Paste a YouTube link. Get vertical clips with a facecam, captions and titles.").pack(anchor="w")

        card = ttk.Frame(self, style="Card.TFrame", padding=18)
        card.pack(fill="x", padx=22, pady=10)
        card.columnconfigure(1, weight=1)
        card.columnconfigure(3, weight=1)
        self.row(card, "YouTube link", ttk.Entry(card, textvariable=self.link), 0)
        card.grid_slaves(row=0, column=1)[0].grid(columnspan=3)
        f = ttk.Frame(card, style="Card.TFrame")
        ttk.Entry(f, textvariable=self.file).pack(side="left", fill="x", expand=True)
        ttk.Button(f, text="Browse", command=self.browse).pack(side="left", padx=(6, 0))
        self.row(card, "Or a video file", f, 1)
        f.grid(columnspan=3)
        self.row(card, "Minutes to record (live)", ttk.Spinbox(card, from_=0, to=600, textvariable=self.minutes, width=8), 2)
        self.row(card, "Number of clips", ttk.Spinbox(card, from_=1, to=30, textvariable=self.clips, width=8), 2, 2)
        self.row(card, "Clip length (seconds)", ttk.Spinbox(card, from_=10, to=90, textvariable=self.length, width=8), 3)
        self.row(card, "Facecam corner", ttk.Combobox(card, textvariable=self.corner, values=list(CORNERS), state="readonly", width=14), 3, 2)
        self.row(card, "Facecam size (%)", ttk.Spinbox(card, from_=12, to=50, textvariable=self.camsize, width=8), 4)
        self.row(card, "Caption quality", ttk.Combobox(card, textvariable=self.model, values=["tiny", "base", "small", "medium"], state="readonly", width=14), 4, 2)
        ttk.Checkbutton(card, text="Add automatic captions", variable=self.caps).grid(row=5, column=0, columnspan=2, sticky="w", pady=4)
        f2 = ttk.Frame(card, style="Card.TFrame")
        ttk.Entry(f2, textvariable=self.out).pack(side="left", fill="x", expand=True)
        ttk.Button(f2, text="Change", command=self.pick_out).pack(side="left", padx=(6, 0))
        self.row(card, "Save clips in", f2, 6)
        f2.grid(columnspan=3)

        bar = ttk.Frame(self, padding=(22, 4))
        bar.pack(fill="x")
        self.go = ttk.Button(bar, text="Make clips", style="Go.TButton", command=self.start)
        self.go.pack(side="left")
        self.stop = ttk.Button(bar, text="Stop", command=self.cancel, state="disabled")
        self.stop.pack(side="left", padx=8)
        ttk.Button(bar, text="Open clips folder", command=self.open_out).pack(side="right")
        self.pb = ttk.Progressbar(self, mode="indeterminate")
        self.pb.pack(fill="x", padx=22, pady=(6, 6))
        self.log = scrolledtext.ScrolledText(self, height=12, bg=PANEL, fg=INK, insertbackground=INK,
                                             relief="flat", font=("Consolas", 9), padx=10, pady=8)
        self.log.pack(fill="both", expand=True, padx=22, pady=(0, 18))
        self.say("Ready. Paste a link, then click Make clips.\nOnly use videos and streams you own or have permission to clip.\n")

    def say(self, text):
        self.log.insert("end", text)
        self.log.see("end")

    def browse(self):
        p = filedialog.askopenfilename(filetypes=[("Video", "*.mp4 *.mkv *.mov *.webm *.avi"), ("All files", "*.*")])
        if p:
            self.file.set(p)

    def pick_out(self):
        p = filedialog.askdirectory()
        if p:
            self.out.set(p)

    def open_out(self):
        os.makedirs(self.out.get(), exist_ok=True)
        if os.name == "nt":
            os.startfile(self.out.get())
        else:
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", self.out.get()])

    def start(self):
        if not (self.link.get().strip() or self.file.get().strip()):
            return self.say("Paste a YouTube link or choose a video file first.\n")
        if not shutil.which("ffmpeg"):
            return self.say("ffmpeg was not found. Install it with:  winget install ffmpeg\nThen close and reopen this app.\n")
        cmd = ([sys.executable, "--worker"] if FROZEN else [sys.executable, "-u", SCRIPT]) + ["--out", self.out.get(), "--minutes", str(self.minutes.get()),
               "--clips", str(self.clips.get()), "--length", str(self.length.get()),
               "--cam", CORNERS[self.corner.get()], "--camsize", str(self.camsize.get()), "--model", self.model.get()]
        if self.caps.get():
            cmd.append("--captions")
        if self.file.get().strip():
            cmd += ["--file", self.file.get().strip()]
        else:
            cmd.append(self.link.get().strip())
        self.go.config(state="disabled")
        self.stop.config(state="normal")
        self.pb.start(12)
        self.say("\nStarting...\n")
        threading.Thread(target=self.work, args=(cmd,), daemon=True).start()

    def work(self, cmd):
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        try:
            self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                         encoding="utf-8", errors="replace", env=env, creationflags=flags)
            for line in self.proc.stdout:
                self.after(0, self.say, line)
            code = self.proc.wait()
            msg = "\nFinished. Click Open clips folder.\n" if code == 0 else f"\nStopped with an error (code {code}). Read the lines above.\n"
        except Exception as e:
            msg = f"\nCould not start: {e}\n"
        self.after(0, self.done, msg)

    def done(self, msg):
        self.say(msg)
        self.pb.stop()
        self.go.config(state="normal")
        self.stop.config(state="disabled")
        self.proc = None

    def cancel(self):
        if self.proc:
            if os.name == "nt":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(self.proc.pid)], capture_output=True)
            else:
                self.proc.terminate()
            self.say("\nStopping...\n")


if __name__ == "__main__":
    App().mainloop()
