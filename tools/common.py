"""Shared helpers: project loading, clip lookup, ffmpeg/ffprobe calls."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def die(msg):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def load_project(arg):
    """Root config.json, overridden by <project>/project.json. Adds 'dir' and 'scenes' (if scenes.json exists)."""
    pdir = Path(arg).resolve()
    if not pdir.is_dir():
        die(f"project folder not found: {arg}")
    cfg = read_json(ROOT / "config.json")
    own = pdir / "project.json"
    if own.exists():
        for k, v in read_json(own).items():
            if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                cfg[k] = {**cfg[k], **v}
            else:
                cfg[k] = v
    cfg["dir"] = pdir
    cfg.setdefault("title", pdir.name)
    scenes = pdir / "scenes.json"
    cfg["scenes"] = read_json(scenes)["scenes"] if scenes.exists() else []
    return cfg


def scene_ids(P):
    if not P["scenes"]:
        die(f"no scenes.json in {P['dir']} (run: python3 tools/split_script.py {P['dir']})")
    return [s["id"] for s in P["scenes"]]


def raw_clip(P, sid):
    return P["dir"] / "clips" / f"{sid}.mp4"


def flat_clip(P, sid):
    return P["dir"] / "flat" / f"{sid}.mp4"


def clip_for(P, sid):
    """The flattened clip when there is one, else the raw clip."""
    f = flat_clip(P, sid)
    return f if f.exists() else raw_clip(P, sid)


def run(cmd, quiet=True):
    r = subprocess.run([str(c) for c in cmd], capture_output=quiet, text=True)
    if r.returncode != 0:
        if quiet:
            print(r.stderr[-3000:], file=sys.stderr)
        die(f"command failed: {' '.join(str(c) for c in cmd[:6])} ...")
    return r


def probe_duration(path):
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path])
    return float(r.stdout.strip())


def probe_video(path):
    r = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=width,height,r_frame_rate", "-of", "json", path])
    s = json.loads(r.stdout)["streams"][0]
    num, den = s["r_frame_rate"].split("/")
    return s["width"], s["height"], float(num) / float(den)


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
