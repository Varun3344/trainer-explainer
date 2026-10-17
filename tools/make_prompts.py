#!/usr/bin/env python3
"""Write one video-generation prompt per clip -> <project>/prompts.md.

    python3 tools/make_prompts.py projects/<name>

Paste each prompt into your video model (Veo / Flow or similar) at the clip's length, 9:16, and save the result as
<project>/clips/<id>.mp4. Start every clip after c01 from c01's first frame so the face, outfit and framing stay the same.
"""
import sys

from common import die, load_project, scene_ids

TEMPLATE = (
    "Vertical 9:16 video, {seconds} seconds, one continuous shot. {presenter}. The presenter stands in front of a "
    "{backdrop}. Medium shot from the knees up, centred, the whole body inside the frame, steady locked-off camera, "
    "no zoom, no camera movement. The presenter speaks directly to the camera in a clear, warm, energetic teaching "
    "voice with natural hand gestures, and says exactly: \"{dialogue}\" No text on screen, no subtitles, no music."
)


def main():
    if len(sys.argv) != 2:
        die("usage: python3 tools/make_prompts.py projects/<name>")
    P = load_project(sys.argv[1])
    scene_ids(P)
    presenter = P["presenter"][0].upper() + P["presenter"][1:]
    lines = [f"# {P['title']}: clip prompts", ""]
    for s in P["scenes"]:
        lines += [f"## {s['id']} ({s['seconds']} s)", "",
                  TEMPLATE.format(seconds=s["seconds"], presenter=presenter, backdrop=P["backdrop"],
                                  dialogue=s["dialogue"]), ""]
    out = P["dir"] / "prompts.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(P['scenes'])} prompts -> {out}")


if __name__ == "__main__":
    main()
