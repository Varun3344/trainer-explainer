# Trainer explainer

Makes 16:9 course videos with a trainer and a panel of explanations that animates in time with what the trainer says.

- The **trainer** stands in the right third of the frame (x 1280–1920). They come from short 9:16 clips made with a video model (Veo / Google Flow or similar), one clip per few sentences.
- The **panel** on the left two thirds (x 0–1280) shows titles, numbered points, quotes, stamps, citations and an end card. Each element appears on a spoken word.
- The clip backdrops are shifted to the page colour, so trainer and panel read as one screen.

```
script.txt ─► scenes.json ─► prompts.md ─► (make clips in your video tool) ─► clips/c01.mp4 …
                                                                                     │
      cues.json ──► build_plan ◄── words/ ◄── words.py ◄── flat/ ◄── flatten_bg ◄────┘
                        │
                        ▼
              out/timeline.json ─► render_panel (panel.html → PNG frames) ─► compose ─► out/<title>.mp4 ─► qa
```

## Requirements

- Python 3.9+ (standard library only)
- ffmpeg + ffprobe 5 or newer on the PATH
- Node 18+ and Google Chrome (or Playwright's Chromium)
- An OpenAI API key for word timings (`OPENAI_API_KEY`)

```sh
npm install            # Playwright; add PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 if you render with installed Chrome
```

## Quick start

```sh
mkdir -p projects/my-video
# 1. write projects/my-video/script.txt (blank line = start a new clip) and optionally project.json
./run.sh projects/my-video prep          # -> scenes.json (whole-sentence clips) + prompts.md (one prompt per clip)

# 2. make each clip from prompts.md in your video tool (9:16, the clip's length) and save it as
#    projects/my-video/clips/c01.mp4, c02.mp4, …   Start every clip from c01's first frame to keep the same face.

# 3. write projects/my-video/cues.json (see "Cues"), then:
export OPENAI_API_KEY=...
./run.sh projects/my-video post          # flatten, words, plan, panel, compose, qa
```

The finished video is `projects/my-video/out/<title>.mp4`. QA writes `sheet.jpg`, `first.jpg` and `last.jpg` next to it.
`projects/demo` is a small worked example with a script, prompts and cues. Add your own clips to render it.

Run a single stage with `./run.sh projects/<name> <stage>`. The stages are `split prompts flatten words plan panel compose qa`.
While you edit cues, check the layout without rendering everything:

```sh
python3 tools/build_plan.py projects/my-video
node tools/render_panel.mjs projects/my-video --preview 2,8.5,15     # -> out/preview_<t>.png
```

## Project folder

| Path | What |
|---|---|
| `script.txt` | The words the trainer says. |
| `project.json` | Overrides for `config.json` (`title`, `topic`, `presenter`, `music`, `theme`, …). |
| `scenes.json` | Clips: `id`, `seconds`, `dialogue`. Written by `split_script.py`, safe to hand-edit. |
| `prompts.md` | One video prompt per clip. |
| `clips/` | Your rendered clips, `c01.mp4` … |
| `flat/` | Clips with the backdrop shifted to the page colour. |
| `words/` | Word timings per clip (Whisper). |
| `cues.json` | What the panel shows and when. |
| `out/` | `timeline.json`, panel `frames/`, `base.mkv`, the final video, QA images. |

## Cues

`cues.json` is `{ "cues": [ … ] }`. Every cue has a `type` and an `in` anchor. `out` is optional. Without it, a main-area cue (title, points, quote, stamp, compare) stays until the next one starts, and other cues stay until their clip ends.

Anchors point at the spoken words:

| Anchor | Meaning |
|---|---|
| `"c02:start"`, `"c02:end"` | start / end of clip c02 |
| `"c02:3.5s"`, `"c02:-1.5s"` | 3.5 s into c02 / 1.5 s before it ends |
| `"c02:written statement"` | when that phrase is first said in c02 |
| `"c02:plaint#2"` | the second time "plaint" is said |
| `"c02:plaint+0.3s"` | shift any anchor |
| `"tail"` | the hold after the last clip (end card) |

Any `at` field inside a cue (list items, columns) and any `xxx_at` field takes an anchor too.
If a word isn't found, `build_plan.py` stops and prints what the clip actually says.

| Type | Fields |
|---|---|
| `title` | `kicker`, `text`, `sub`, `sub_at` |
| `points` | `head`, `items: [{text, at}]`. Items build one by one and the newest is highlighted. |
| `quote` | `text`, `by`, `by_at` |
| `stamp` | `text`, `sub`, `sub_at`. A big stamped word or number. |
| `compare` | `head`, `columns: [{title, text, at, highlight}]` |
| `cite` | `text`. A caption bar at the bottom of the panel. |
| `lowerthird` | `name`, `role`. Shown on the trainer's side. |
| `endcard` | `title` (default: brand), `cta`, `url`. Covers the whole frame. |

```json
{ "type": "points", "in": "c02:start", "head": "A plaint tells the court",
  "items": [ { "text": "Who is suing whom", "at": "c02:who" },
             { "text": "What relief is asked for", "at": "c02:relief" } ] }
```

To add a cue type, add a builder to `builders` in `panel/panel.html`. It gets the cue (with `t0`, `t1` and resolved times) and returns `update(t)`. Pose everything from `t`, never with CSS animations, so that frames can be rendered in any order.

## Settings (`config.json`, override per project in `project.json`)

| Key | Default | |
|---|---|---|
| `panel_width` | 1280 | panel width; the trainer box is the rest of the 1920 px frame |
| `presenter_crop_y` | 0.5 | where to crop the scaled clip vertically (0 = keep the top, 1 = keep the bottom) |
| `tail_seconds` | 3 | hold after the last clip for the end card |
| `theme` | cream / ink / copper | page colours (`bg` is also the colour the backdrops are shifted to) |
| `words_per_second`, `clip_lengths` | 2.6, [6, 8, 10] | how the script is split into clips |
| `presenter`, `backdrop` | | text used in the prompts |
| `flatten.sample` | [0.02, 0.3, 0.08, 0.2] | backdrop sample box (fractions of the frame) at the left edge, mirrored on the right |
| `music`, `music_volume` | null, 0.15 | optional music bed (path relative to the project), ducked under the voice |
| `loudness` | -16 | target LUFS |

## Tips

- Keep the backdrop plain and lit evenly, and keep the outfit clearly darker or more colourful than the backdrop.
- Fill each clip: about 2.4–2.9 words per second. Short lines invite the model to add words.
- Check each clip's transcript in `words/` against the script before you build the plan. Re-make any clip that drops or adds words.
- Use a locked-off camera with no zoom. If the trainer's size changes between clips, the cut is noticeable.
