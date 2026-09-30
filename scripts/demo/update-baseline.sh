#!/usr/bin/env bash
# Replace the demo video baseline with the recording from a CI run.
#
# Usage: scripts/demo/update-baseline.sh RUN_ID   (from `gh run list --workflow tests.yml`)
#
# Downloads the run's `demo-video` artifact and copies the new docs/demo.mp4,
# docs/demo.gif, docs/demo-moments.json and tests/demo_frames/*.png into place. Review the changes (git diff --stat, look at the frames), then commit.
set -euo pipefail

run=$1
root=$(git rev-parse --show-toplevel)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

gh run download "$run" --name demo-video --dir "$tmp"
cp "$tmp/demo.mp4" "$root/docs/demo.mp4"
cp "$tmp/demo.gif" "$root/docs/demo.gif"
cp "$tmp/demo-moments.json" "$root/docs/demo-moments.json"
rm -rf "$root/tests/demo_frames"
mkdir -p "$root/tests/demo_frames"
cp "$tmp"/frames/*.png "$root/tests/demo_frames/"
git -C "$root" status --short docs tests/demo_frames
