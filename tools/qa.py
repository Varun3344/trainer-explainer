#!/usr/bin/env python3
"""Check the finished video: streams, size, frame rate, duration, loudness; writes a contact sheet and the first/last
frames next to it for a visual check.

    python3 tools/qa.py projects/<name>
"""
import json
import re
import subprocess
import sys

from common import die, load_project, read_json, run


def main():
    if len(sys.argv) != 2:
        die("usage: python3 tools/qa.py projects/<name>")
    P = load_project(sys.argv[1])
    out = P["dir"] / "out"
    video = out / f"{P['title']}.mp4"
    if not video.exists():
        die(f"no {video} (run tools/compose.py)")
    tl = read_json(out / "timeline.json")
    ok = True

    def check(cond, label):
        nonlocal ok
        print(f"{'PASS' if cond else 'FAIL'}  {label}")
        ok = ok and cond

    info = json.loads(run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", video]).stdout)
    vs = [s for s in info["streams"] if s["codec_type"] == "video"]
    aus = [s for s in info["streams"] if s["codec_type"] == "audio"]
    check(len(vs) == 1 and len(aus) == 1, f"one video + one audio stream ({len(vs)} + {len(aus)})")
    v = vs[0]
    check((v["width"], v["height"]) == (P["width"], P["height"]), f"size {v['width']}x{v['height']}")
    num, den = v["r_frame_rate"].split("/")
    check(abs(float(num) / float(den) - P["fps"]) < 0.01, f"frame rate {v['r_frame_rate']}")
    d = float(info["format"]["duration"])
    check(abs(d - tl["duration"]) < 0.1, f"duration {d:.2f} s (plan {tl['duration']:.2f} s)")

    r = subprocess.run(["ffmpeg", "-nostats", "-i", str(video), "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True)
    summary = r.stderr[r.stderr.rfind("Summary:"):]
    lufs = re.search(r"I:\s+(-?[\d.]+) LUFS", summary)
    peak = re.search(r"Peak:\s+(-?[\d.]+) dBFS", summary)
    if lufs:
        check(abs(float(lufs[1]) - P["loudness"]) <= 1.5, f"loudness {lufs[1]} LUFS (target {P['loudness']})")
    if peak:
        check(float(peak[1]) <= -0.5, f"true peak {peak[1]} dBFS")

    every = max(1.0, d / 12)
    run(["ffmpeg", "-y", "-v", "error", "-i", video, "-vf", f"fps=1/{every:.3f},scale=480:-1,tile=4x3",
         "-frames:v", "1", out / "sheet.jpg"])
    run(["ffmpeg", "-y", "-v", "error", "-i", video, "-frames:v", "1", out / "first.jpg"])
    run(["ffmpeg", "-y", "-v", "error", "-sseof", "-0.2", "-i", video, "-frames:v", "1", "-update", "1",
         out / "last.jpg"])
    print(f"look at: {out / 'sheet.jpg'}, first.jpg, last.jpg")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
