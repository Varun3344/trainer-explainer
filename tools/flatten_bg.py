#!/usr/bin/env python3
"""Bring each clip's studio backdrop to the page colour so presenter and panel read as one screen.

    python3 tools/flatten_bg.py projects/<name> [c01 c02 ...] [--force]

The backdrop colour is sampled from two boxes at the clip's left and right edges (config flatten.sample = [x, y, w, h]
as fractions of the frame for the left box; the right box mirrors it). A per-channel tone curve then maps that colour
to theme.bg while black and white stay put, so dark suits and hair barely move and nothing on the presenter is keyed
out. Writes <project>/flat/<id>.mp4 (audio copied).
"""
import subprocess
import sys

from common import die, flat_clip, hex_rgb, load_project, probe_video, raw_clip, run, scene_ids


def sample_colour(path, box, w, h):
    bw, bh = max(2, int(box[2] * w)), max(2, int(box[3] * h))
    xs = (int(box[0] * w), w - int(box[0] * w) - bw)
    y = int(box[1] * h)
    rgb = []
    for x in xs:
        r = subprocess.run(["ffmpeg", "-v", "error", "-ss", "0.5", "-i", str(path), "-frames:v", "1",
                            "-vf", f"crop={bw}:{bh}:{x}:{y},scale=1:1:flags=area", "-f", "rawvideo",
                            "-pix_fmt", "rgb24", "pipe:"], capture_output=True)
        if r.returncode != 0 or len(r.stdout) < 3:
            die(f"could not sample the backdrop of {path}")
        rgb.append(r.stdout[:3])
    return tuple((a + b) // 2 for a, b in zip(*rgb))


def curves(src_rgb, dst_rgb):
    pts = []
    for ch, s, d in zip("rgb", src_rgb, dst_rgb):
        s, d = min(max(s, 8), 247) / 255, min(max(d, 8), 247) / 255
        pts.append(f"{ch}='0/0 {s:.4f}/{d:.4f} 1/1'")
    return "curves=" + ":".join(pts)


def flatten(P, sid, force=False):
    src, dst = raw_clip(P, sid), flat_clip(P, sid)
    if not src.exists():
        print(f"{sid}: no clip at {src}, skipped")
        return
    if dst.exists() and not force:
        print(f"{sid}: already flat (use --force to redo)")
        return
    w, h, _ = probe_video(src)
    key = sample_colour(src, P["flatten"]["sample"], w, h)
    bg = hex_rgb(P["theme"]["bg"])
    dst.parent.mkdir(parents=True, exist_ok=True)
    run(["ffmpeg", "-y", "-v", "error", "-i", src, "-vf", f"{curves(key, bg)},format=yuv420p", "-map", "0:v",
         "-map", "0:a?", "-c:v", "libx264", "-crf", "14", "-preset", "medium", "-c:a", "copy", dst])
    print(f"{sid}: backdrop #{bytes(key).hex()} -> {P['theme']['bg']}  {dst}")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        die("usage: python3 tools/flatten_bg.py projects/<name> [c01 c02 ...] [--force]")
    P = load_project(args[0])
    for sid in args[1:] or scene_ids(P):
        flatten(P, sid, force="--force" in sys.argv)


if __name__ == "__main__":
    main()
