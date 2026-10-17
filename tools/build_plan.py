#!/usr/bin/env python3
"""Resolve <project>/cues.json (anchored on spoken words) into <project>/out/timeline.json for the panel page.

    python3 tools/build_plan.py projects/<name>

Anchors (see README "Cues"):
    "c02:start"  "c02:end"  "c02:3.5s"  "c02:-1.5s" (1.5 s before the clip ends)
    "c02:written statement"     first occurrence of the phrase (start of its first word)
    "c02:plaint#2"              second occurrence
    "c02:plaint+0.3s"           shifted by +0.3 s (any anchor)
    "tail"                      the hold after the last clip (for the endcard)
A cue's "in" sets t0. "out" sets t1; without it a main-area cue (title, points, quote, stamp, compare) runs until the
next main-area cue starts, any other cue until its clip ends. Every "at" inside a cue (items, sub_at, ...) becomes a time.
"""
import re
import sys

from common import clip_for, die, load_project, probe_duration, read_json, scene_ids, write_json

MAIN = {"title", "points", "quote", "stamp", "compare"}
SHIFT = re.compile(r"^(?P<base>.*?)(?P<shift>[+-]\d+(?:\.\d+)?)s$")
SECONDS = re.compile(r"^-?\d+(?:\.\d+)?s$")


def norm(w):
    return re.sub(r"[^0-9a-z₹]+", "", w.lower())


class Clock:
    def __init__(self, P):
        self.offset, self.length, self.words = {}, {}, {}
        t = 0.0
        for sid in scene_ids(P):
            clip = clip_for(P, sid)
            if not clip.exists():
                die(f"{sid}: no clip at {clip}")
            d = probe_duration(clip)
            self.offset[sid], self.length[sid] = t, d
            wf = P["dir"] / "words" / f"{sid}.json"
            self.words[sid] = read_json(wf)["words"] if wf.exists() else None
            t += d
        self.clips_end = t
        self.duration = t + float(P["tail_seconds"])

    def find(self, sid, phrase, nth):
        words = self.words[sid]
        if words is None:
            die(f"anchor '{sid}:{phrase}' needs words/{sid}.json (run tools/words.py)")
        want = [norm(w) for w in phrase.split() if norm(w)]
        seen = 0
        for i in range(len(words) - len(want) + 1):
            if all(norm(words[i + j]["word"]) == want[j] for j in range(len(want))):
                seen += 1
                if seen == nth:
                    return words[i]["start"]
        heard = " ".join(w["word"] for w in words)
        die(f"anchor '{sid}:{phrase}' (#{nth}) not found. {sid} says: {heard}")

    def at(self, anchor):
        anchor = anchor.strip()
        shift = 0.0
        m = SHIFT.match(anchor)
        if m and not SECONDS.match(anchor.split(":", 1)[-1]):
            anchor, shift = m["base"].strip(), float(m["shift"])
        if anchor == "tail":
            return self.clips_end + shift
        if ":" not in anchor:
            die(f"bad anchor '{anchor}' (expected clip:word, clip:3.2s, clip:start/end or tail)")
        sid, ref = (s.strip() for s in anchor.split(":", 1))
        if sid not in self.offset:
            die(f"anchor '{anchor}': no clip {sid} in scenes.json")
        off, length = self.offset[sid], self.length[sid]
        if ref == "start":
            t = off
        elif ref == "end":
            t = off + length
        elif SECONDS.match(ref):
            v = float(ref[:-1])
            t = off + (v if v >= 0 else length + v)
        else:
            phrase, _, nth = ref.partition("#")
            t = off + self.find(sid, phrase, int(nth or 1))
        return round(t + shift, 3)

    def clip_end_of(self, anchor):
        sid = anchor.split(":", 1)[0].strip()
        if sid == "tail" or sid not in self.offset:
            return self.duration
        return self.offset[sid] + self.length[sid]


def resolve_ats(node, clock):
    """Every 'at' key -> 't', every 'xxx_at' -> 'xxx_t', recursively."""
    if isinstance(node, list):
        return [resolve_ats(n, clock) for n in node]
    if not isinstance(node, dict):
        return node
    out = {}
    for k, v in node.items():
        if k == "at" and isinstance(v, str):
            out["t"] = clock.at(v)
        elif k.endswith("_at") and isinstance(v, str):
            out[k[:-3] + "_t"] = clock.at(v)
        else:
            out[k] = resolve_ats(v, clock)
    return out


def main():
    if len(sys.argv) != 2:
        die("usage: python3 tools/build_plan.py projects/<name>")
    P = load_project(sys.argv[1])
    clock = Clock(P)
    spec = read_json(P["dir"] / "cues.json")
    cues = []
    for i, c in enumerate(spec["cues"]):
        if "in" not in c or "type" not in c:
            die(f"cue {i} needs 'type' and 'in': {c}")
        r = resolve_ats({k: v for k, v in c.items() if k not in ("in", "out")}, clock)
        r["t0"] = clock.at(c["in"])
        r["_out"] = c.get("out")
        r["_in"] = c["in"]
        cues.append(r)

    main_starts = sorted(c["t0"] for c in cues if c["type"] in MAIN)
    for c in cues:
        if c["_out"]:
            c["t1"] = clock.at(c["_out"])
        elif c["type"] in MAIN:
            later = [t for t in main_starts if t > c["t0"]]
            c["t1"] = later[0] if later else clock.clips_end
        else:
            c["t1"] = clock.clip_end_of(c["_in"])
        if c["type"] == "endcard" and not c["_out"]:
            c["t1"] = clock.duration
        c["t1"] = round(c["t1"], 3)
        if c["t1"] <= c["t0"]:
            die(f"{c['type']} cue at {c['_in']} ends before it starts ({c['t0']} -> {c['t1']})")
        del c["_out"], c["_in"]
    cues.sort(key=lambda c: c["t0"])

    mains = [c for c in cues if c["type"] in MAIN]
    for a, b in zip(mains, mains[1:]):
        if b["t0"] < a["t1"] - 0.01:
            print(f"warning: {a['type']} ({a['t0']}-{a['t1']}) overlaps {b['type']} starting {b['t0']}")

    timeline = {
        "title": P["title"], "brand": P["brand"], "topic": P.get("topic", ""),
        "width": P["width"], "height": P["height"], "fps": P["fps"], "panel_width": P["panel_width"],
        "duration": round(clock.duration, 3), "clips_end": round(clock.clips_end, 3),
        "theme": P["theme"], "cues": cues,
    }
    out = P["dir"] / "out" / "timeline.json"
    write_json(out, timeline)
    print(f"{len(cues)} cues, {clock.duration:.2f} s ({clock.clips_end:.2f} s of clips + tail) -> {out}")


if __name__ == "__main__":
    main()
