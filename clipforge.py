#!/usr/bin/env python3
"""ClipForge desktop: paste a YouTube link, get vertical clips with a facecam on top,
gameplay below, hook text, captions, and titles. Runs on your own PC.
Only use this on videos and streams you own or have permission to clip.

Setup (Windows):  pip install yt-dlp numpy faster-whisper     and     winget install ffmpeg
Run:  python clipforge.py "https://www.youtube.com/watch?v=XXXX" --minutes 30 --captions
"""
import argparse, glob, os, re, subprocess, sys
from collections import Counter
import numpy as np

FONT = "C\\:/Windows/Fonts/arialbd.ttf"
HOOKS = {"spike": "Wait for it...", "long": "Watch till the end", "peak": "No way this just happened"}
STOP = set("about would there their which really going those where being because think right".split())


def run(cmd, **kw):
    if subprocess.run(cmd, **kw).returncode:
        sys.exit("Command failed: " + " ".join(str(c) for c in cmd[:4]) + " ...")


def download(url, out, minutes, from_start):
    for f in glob.glob(os.path.join(out, "source.*")):
        os.remove(f)
    from yt_dlp import YoutubeDL
    opts = {"noplaylist": True, "format": "bv*[height<=720]+ba/b[height<=720]", "merge_output_format": "mp4",
            "outtmpl": os.path.join(out, "source.%(ext)s"), "live_from_start": from_start}
    if minutes:
        opts.update(external_downloader="ffmpeg", external_downloader_args={"ffmpeg": ["-t", str(minutes * 60)]})
    print("Recording from the link (a live stream records for", minutes or "all", "minutes)...")
    try:
        YoutubeDL(opts).download([url])
    except Exception as e:
        sys.exit(f"Download failed: {e}")
    found = glob.glob(os.path.join(out, "source.*"))
    if not found:
        sys.exit("Nothing was downloaded. Check the link and that ffmpeg is installed.")
    return found[0]


def find_moments(src, n, gap=25, hop=0.25):
    print("Scanning audio for the best moments...")
    p = subprocess.run(["ffmpeg", "-v", "quiet", "-i", src, "-vn", "-ac", "1", "-ar", "8000", "-f", "s16le", "-"],
                       capture_output=True)
    a = np.frombuffer(p.stdout, dtype=np.int16).astype(np.float32) / 32768
    k = int(8000 * hop)
    m = len(a) // k
    if m < 40:
        sys.exit("The video is too short or has no audio.")
    r = np.sqrt((a[:m * k].reshape(m, k) ** 2).mean(1))
    sd = r.std() or 1e-6
    z = (r - r.mean()) / sd
    on = np.array([(r[i] - r[max(0, i - 16):i].mean()) / sd if i else 0 for i in range(m)])
    c = z + 0.7 * on
    picked = []
    for i in np.argsort(-c):
        if len(picked) >= n:
            break
        if all(abs(i - j) * hop >= gap for j in picked):
            picked.append(int(i))
    out = []
    for i in sorted(picked):
        su = float(z[i:i + 20].mean())
        why = ["very loud burst" if z[i] > 3 else "loud burst" if z[i] > 2 else "energy peak"]
        if on[i] > 2:
            why.append("sudden spike")
        if su > 1:
            why.append("sustained intensity")
        kind = "spike" if on[i] > 2 else "long" if su > 1 else "peak"
        out.append(dict(t=i * hop, score=int(max(30, min(99, 45 + 12 * z[i] + 8 * on[i]))),
                        why=" + ".join(why), hook=HOOKS[kind]))
    return out


def stamp(t):
    return f"{int(t // 3600):02}:{int(t % 3600 // 60):02}:{t % 60:06.3f}".replace(".", ",")


def captions(wav, model):
    segs, _ = model.transcribe(wav, word_timestamps=True)
    words = [w for s in segs for w in (s.words or [])]
    groups = [words[i:i + 3] for i in range(0, len(words), 3)]
    body = "\n".join(f"{k + 1}\n{stamp(g[0].start)} --> {stamp(g[-1].end)}\n"
                     f"{' '.join(w.word.strip() for w in g).upper()}\n" for k, g in enumerate(groups))
    return body, " ".join(w.word for w in words)


def meta(m, text):
    kw = [w for w, _ in Counter(w for w in re.findall(r"[a-z']{5,}", text.lower()) if w not in STOP).most_common(3)]
    tags = " ".join(["#shorts", "#viral", "#clips"] + ["#" + k.replace("'", "") for k in kw])
    k = kw[0].capitalize() if kw else "This"
    return (f"Titles:\n1. {m['hook'].rstrip('.')}...\n2. {k}: the moment nobody saw coming\n"
            f"3. I didn't expect this to happen live\n\nDescription:\n{m['why'].capitalize()}. Watch to the end.\n\n{tags}\n")


def make_clip(src, m, i, a, model):
    name = f"clip{i}"
    start = max(0, m["t"] - a.lead)
    srt, text = None, ""
    if model:
        wav = os.path.join(a.out, name + ".wav")
        run(["ffmpeg", "-y", "-v", "quiet", "-ss", str(start), "-t", str(a.length), "-i", src,
             "-vn", "-ac", "1", "-ar", "16000", wav])
        body, text = captions(wav, model)
        os.remove(wav)
        with open(os.path.join(a.out, name + ".srt"), "w", encoding="utf-8") as fh:
            fh.write(body)
        srt = name + ".srt"
    z = a.camsize / 100
    x = "iw-out_w" if a.cam[1] == "r" else "0"
    y = "ih-out_h" if a.cam[0] == "b" else "0"
    f = (f"[0:v]split=3[a][b][c];"
         f"[a]crop=w=iw*{z}:h=iw*{z}*512/720:x={x}:y={y},scale=720:512[cam];"
         f"[b]scale=720:768:force_original_aspect_ratio=increase,crop=720:768,gblur=sigma=25[bg];"
         f"[c]scale=720:-2[g];[bg][g]overlay=0:(H-h)/2[bot];[cam][bot]vstack[v0]")
    fx = []
    if os.name == "nt":
        fx.append(f"drawtext=fontfile='{FONT}':text='{m['hook']}':fontsize=60:fontcolor=white:box=1:"
                  f"boxcolor=0xE5365A:boxborderw=22:x=(w-text_w)/2:y=90:enable='lt(t,2.5)'")
    if srt:
        fx.append(f"subtitles={srt}:force_style='Alignment=2,MarginV=360,FontSize=20,Bold=1,Outline=3,Shadow=0'")
    f += ";" + ("[v0]" + ",".join(fx) + "[v]" if fx else "[v0]null[v]")
    run(["ffmpeg", "-y", "-v", "error", "-ss", str(start), "-t", str(a.length), "-i", os.path.relpath(src, a.out),
         "-filter_complex", f, "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "21", "-c:a", "aac", "-b:a", "160k", name + ".mp4"], cwd=a.out)
    with open(os.path.join(a.out, name + ".txt"), "w", encoding="utf-8") as fh:
        fh.write(f"Score {m['score']}/100 at {int(m['t'] // 60)}:{int(m['t'] % 60):02} ({m['why']})\n\n{meta(m, text)}")


def main():
    p = argparse.ArgumentParser(description="ClipForge: YouTube link to vertical clips")
    p.add_argument("url", nargs="?", help="YouTube link (live or normal video)")
    p.add_argument("--file", help="use a video file you already have instead of a link")
    p.add_argument("--minutes", type=int, default=30, help="minutes to record from a live stream (0 = whole video)")
    p.add_argument("--from-start", action="store_true", help="record a live stream from its beginning")
    p.add_argument("--clips", type=int, default=8)
    p.add_argument("--length", type=int, default=30, help="clip length in seconds")
    p.add_argument("--lead", type=float, default=2, help="seconds before the peak (hook-first)")
    p.add_argument("--cam", default="tr", choices=["tl", "tr", "bl", "br"], help="facecam corner in the video")
    p.add_argument("--camsize", type=int, default=25, help="facecam width as %% of the video")
    p.add_argument("--captions", action="store_true", help="add automatic captions (Whisper)")
    p.add_argument("--model", default="base", help="Whisper size: tiny, base, small, medium")
    p.add_argument("--out", default="clipforge_out")
    a = p.parse_args()
    if not (a.url or a.file):
        p.error("give a YouTube link or --file")
    os.makedirs(a.out, exist_ok=True)
    src = os.path.abspath(a.file) if a.file else os.path.abspath(download(a.url, a.out, a.minutes, a.from_start))
    model = None
    if a.captions:
        from faster_whisper import WhisperModel
        model = WhisperModel(a.model, compute_type="int8")
    moms = find_moments(src, a.clips)
    print(f"Found {len(moms)} moments. Building clips in '{a.out}'...")
    for i, m in enumerate(sorted(moms, key=lambda q: -q["score"]), 1):
        print(f"  clip{i}: score {m['score']} at {int(m['t'] // 60)}:{int(m['t'] % 60):02} - {m['why']}")
        make_clip(src, m, i, a, model)
    print("Done. Open the folder:", os.path.abspath(a.out))


if __name__ == "__main__":
    main()
