#!/usr/bin/env python3
"""Word timings for every clip with OpenAI Whisper -> <project>/words/<id>.json.

    OPENAI_API_KEY=... python3 tools/words.py projects/<name> [c01 c02 ...] [--force]

The cue plan anchors every on-screen element on a spoken word, so each clip needs its word list. Calls the API with
curl (some Python installs have no CA bundle). The clip's script line is sent as the prompt to help spelling.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from common import clip_for, die, load_project, probe_duration, run, scene_ids, write_json

API = "https://api.openai.com/v1/audio/transcriptions"


def transcribe(audio, prompt, key):
    r = subprocess.run(["curl", "-sS", "--fail-with-body", API, "-H", f"Authorization: Bearer {key}",
                        "-F", f"file=@{audio}", "-F", "model=whisper-1", "-F", "response_format=verbose_json",
                        "-F", "timestamp_granularities[]=word", "--form-string", f"prompt={prompt}"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        die(f"transcription failed: {r.stdout[-500:] or r.stderr[-500:]}")
    return json.loads(r.stdout)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        die("usage: python3 tools/words.py projects/<name> [c01 c02 ...] [--force]")
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        die("set OPENAI_API_KEY")
    P = load_project(args[0])
    scenes = {s["id"]: s for s in P["scenes"]}
    for sid in args[1:] or scene_ids(P):
        out = P["dir"] / "words" / f"{sid}.json"
        if out.exists() and "--force" not in sys.argv:
            print(f"{sid}: words exist (use --force to redo)")
            continue
        clip = clip_for(P, sid)
        if not clip.exists():
            print(f"{sid}: no clip, skipped")
            continue
        with tempfile.TemporaryDirectory() as tmp:
            audio = Path(tmp) / "a.mp3"
            run(["ffmpeg", "-y", "-v", "error", "-i", clip, "-vn", "-ac", "1", "-ar", "16000", "-b:a", "64k", audio])
            res = transcribe(audio, scenes.get(sid, {}).get("dialogue", ""), key)
        words = [{"word": w["word"], "start": w["start"], "end": w["end"]} for w in res.get("words", [])]
        write_json(out, {"clip": str(clip.relative_to(P["dir"])), "id": sid, "duration": probe_duration(clip),
                         "text": res.get("text", "").strip(), "words": words})
        print(f"{sid}: {len(words)} words  {res.get('text', '').strip()[:80]}")


if __name__ == "__main__":
    main()
