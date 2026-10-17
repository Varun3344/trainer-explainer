#!/usr/bin/env python3
"""Compose the final 16:9 video: presenter clips on the right, panel frames over everything, voice + music.

    python3 tools/compose.py projects/<name>

Pass 1 -> out/base.mkv: cream canvas, the clips (flat ones when present) cut one after another into the presenter box
          (x = panel_width .. width, scaled to cover it), voice track, cream hold for the tail.
Pass 2 -> out/<title>.mp4: panel frames (out/frames) on top, optional music bed ducked under the voice, loudness
          normalised to config "loudness" LUFS.
"""
import sys

from common import clip_for, die, load_project, read_json, run, scene_ids


def main():
    if len(sys.argv) != 2:
        die("usage: python3 tools/compose.py projects/<name>")
    P = load_project(sys.argv[1])
    out = P["dir"] / "out"
    tl_path = out / "timeline.json"
    frames = out / "frames"
    if not tl_path.exists():
        die("no out/timeline.json (run tools/build_plan.py)")
    if not (frames / "f00000.png").exists():
        die("no out/frames (run tools/render_panel.mjs)")
    tl = read_json(tl_path)
    W, H, fps, pw = P["width"], P["height"], P["fps"], P["panel_width"]
    bw = W - pw
    dur = tl["duration"]
    bg = P["theme"]["bg"].lstrip("#")
    cy = float(P["presenter_crop_y"])

    clips = [clip_for(P, sid) for sid in scene_ids(P)]
    for c in clips:
        if not c.exists():
            die(f"missing clip {c}")

    # pass 1: base picture + voice
    ins, parts, pairs = [], [], []
    for i, c in enumerate(clips):
        ins += ["-i", c]
        parts.append(f"[{i}:v]fps={fps},scale=w={bw}:h={H}:force_original_aspect_ratio=increase:flags=lanczos,"
                     f"crop={bw}:{H}:(iw-{bw})/2:(ih-{H})*{cy},setsar=1[v{i}]")
        parts.append(f"[{i}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[a{i}]")
        pairs.append(f"[v{i}][a{i}]")
    n = len(clips)
    parts.append(f"{''.join(pairs)}concat=n={n}:v=1:a=1[pv][voice]")
    parts.append(f"color=c=0x{bg}:s={W}x{H}:r={fps}:d={dur}[bg]")
    parts.append(f"[bg][pv]overlay={pw}:0:eof_action=pass,format=yuv420p[base]")
    parts.append(f"[voice]apad=whole_dur={dur}[va]")
    base = out / "base.mkv"
    print(f"pass 1: {n} clips -> {base}")
    run(["ffmpeg", "-y", "-v", "error", *ins, "-filter_complex", ";".join(parts), "-map", "[base]", "-map", "[va]",
         "-t", f"{dur}", "-c:v", "libx264", "-crf", "14", "-preset", "medium", "-c:a", "pcm_s16le", base])

    # pass 2: panel frames + music + loudness
    ins = ["-i", base, "-framerate", str(fps), "-i", frames / "f%05d.png"]
    parts = [f"[1:v]fps={fps},format=rgba[ov]", "[0:v][ov]overlay=0:0:eof_action=pass:format=auto,format=yuv420p[v]"]
    music = P.get("music")
    loud = f"loudnorm=I={P['loudness']}:TP=-1.5:LRA=11,aresample=48000"
    if music:
        mpath = (P["dir"] / music) if not str(music).startswith("/") else music
        ins += ["-stream_loop", "-1", "-i", mpath]
        parts += ["[0:a]asplit=2[vo][sc]",
                  f"[2:a]aresample=48000,aformat=channel_layouts=stereo,volume={P['music_volume']},atrim=0:{dur}[m]",
                  "[m][sc]sidechaincompress=threshold=0.03:ratio=6:attack=30:release=500[md]",
                  f"[vo][md]amix=inputs=2:duration=first:normalize=0,{loud}[a]"]
    else:
        parts.append(f"[0:a]{loud}[a]")
    final = out / f"{P['title']}.mp4"
    print(f"pass 2: panel frames{' + music' if music else ''} -> {final}")
    run(["ffmpeg", "-y", "-v", "error", *ins, "-filter_complex", ";".join(parts), "-map", "[v]", "-map", "[a]",
         "-t", f"{dur}", "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-profile:v", "high",
         "-pix_fmt", "yuv420p", "-r", str(fps), "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", final])
    print(f"done: {final}")


if __name__ == "__main__":
    main()
