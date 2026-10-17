#!/bin/sh
# Run pipeline stages for one project, in order.
#   ./run.sh projects/<name> prep      split the script + write the clip prompts
#   ./run.sh projects/<name> post      after the clips are in clips/: flatten, words, plan, panel, compose, qa
#   ./run.sh projects/<name> <stage>   one stage: split prompts flatten words plan panel compose qa
set -e
cd "$(dirname "$0")"
P="$1"; shift || true
[ -n "$P" ] && [ -n "$1" ] || { sed -n '2,5p' "$0"; exit 1; }

stage() {
  echo "== $1"
  case "$1" in
    split)   python3 tools/split_script.py "$P" ;;
    prompts) python3 tools/make_prompts.py "$P" ;;
    flatten) python3 tools/flatten_bg.py "$P" ;;
    words)   python3 tools/words.py "$P" ;;
    plan)    python3 tools/build_plan.py "$P" ;;
    panel)   node tools/render_panel.mjs "$P" --workers "${WORKERS:-2}" ;;
    compose) python3 tools/compose.py "$P" ;;
    qa)      python3 tools/qa.py "$P" ;;
    *) echo "unknown stage: $1"; exit 1 ;;
  esac
}

for s in "$@"; do
  case "$s" in
    prep) stage split; stage prompts ;;
    post) for x in flatten words plan panel compose qa; do stage "$x"; done ;;
    *) stage "$s" ;;
  esac
done
