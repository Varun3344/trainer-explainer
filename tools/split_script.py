#!/usr/bin/env python3
"""Split <project>/script.txt into clips of whole sentences -> <project>/scenes.json.

    python3 tools/split_script.py projects/<name>

Sentences are never cut. Each clip gets the shortest length from config "clip_lengths" (seconds) whose word budget
(length x "words_per_second") fits its text. A blank line in script.txt forces a new clip.
"""
import re
import sys

from common import die, load_project, write_json

SENTENCE = re.compile(r"(?<=[.?!])[\"'”’)]*\s+(?=[\"'“‘(]?[A-Z0-9₹])")


def sentences(paragraph):
    text = " ".join(paragraph.split())
    return [s.strip() for s in SENTENCE.split(text) if s.strip()]


def main():
    if len(sys.argv) != 2:
        die(__doc__.strip().splitlines()[2].strip())
    P = load_project(sys.argv[1])
    src = P["dir"] / "script.txt"
    if not src.exists():
        die(f"missing {src}")
    lengths = sorted(P["clip_lengths"])
    wps = P["words_per_second"]
    budget = {L: int(L * wps) for L in lengths}
    longest = lengths[-1]

    clips = []
    for para in re.split(r"\n\s*\n", src.read_text(encoding="utf-8")):
        cur = []
        for s in sentences(para):
            n = len(s.split())
            if cur and len(" ".join(cur + [s]).split()) > budget[longest]:
                clips.append(cur)
                cur = []
            cur.append(s)
            if n > budget[longest]:
                print(f"warning: sentence has {n} words (> {budget[longest]} for {longest} s), shorten it: {s[:60]}...")
        if cur:
            clips.append(cur)

    scenes = []
    for i, parts in enumerate(clips, 1):
        text = " ".join(parts)
        n = len(text.split())
        seconds = next((L for L in lengths if n <= budget[L]), longest)
        scenes.append({"id": f"c{i:02d}", "seconds": seconds, "words": n, "dialogue": text})

    write_json(P["dir"] / "scenes.json", {"title": P["title"], "scenes": scenes})
    total = sum(s["seconds"] for s in scenes)
    for s in scenes:
        print(f"{s['id']}  {s['seconds']:>2} s  {s['words']:>2} words  {s['dialogue'][:70]}")
    print(f"{len(scenes)} clips, about {total // 60}:{total % 60:02d} -> {P['dir'] / 'scenes.json'}")


if __name__ == "__main__":
    main()
