#!/usr/bin/env bash
# Pin the demo's GitHub repositories to the commits in the committed video.
#
# Usage: scripts/demo/pin-repos.sh DIR
#
# Creates a local mirror of each repository at its pinned commit under DIR and writes
# DIR/gitconfig with `url.<mirror>.insteadOf https://github.com/<repo>` rules. Export
# GIT_CONFIG_GLOBAL=DIR/gitconfig and `git clone https://github.com/JetBrains/ideavim` (and
# therefore skill-atlas) reads the mirror, while the UI still shows the GitHub URL.
set -euo pipefail

dir=$(mkdir -p "$1" && cd "$1" && pwd)
config="$dir/gitconfig"
: > "$config"

# Same patterns as skill_atlas.repo.SPARSE_PATTERNS.
patterns=$(python -c 'from skill_atlas.repo import SPARSE_PATTERNS; print("\n".join(SPARSE_PATTERNS))')

pin() {
  local slug=$1 sha=$2
  local mirror="$dir/${slug//\//-}.git" work="$dir/${slug//\//-}.work"
  rm -rf "$mirror" "$work"
  git init --quiet --bare "$mirror"
  git -C "$mirror" config uploadpack.allowFilter true
  git -C "$mirror" config uploadpack.allowAnySHA1InWant true
  # Blobless, then fetch just the skill files: upload-pack never lazy-fetches missing blobs,
  # so the mirror must hold every blob skill-atlas's sparse checkout asks for.
  git -C "$mirror" remote add origin "https://github.com/$slug"
  git -C "$mirror" config remote.origin.promisor true
  git -C "$mirror" config remote.origin.partialclonefilter blob:none
  git -C "$mirror" fetch --quiet --depth 1 --filter=blob:none origin "$sha"
  git -C "$mirror" update-ref refs/heads/main "$sha"
  git -C "$mirror" symbolic-ref HEAD refs/heads/main
  git -C "$mirror" worktree add --quiet --no-checkout "$work" main
  git -C "$work" sparse-checkout set --no-cone $patterns
  git -C "$work" checkout --quiet
  git -C "$mirror" worktree remove --force "$work"
  # Stop being a partial clone: from now on the mirror only serves what it has.
  git -C "$mirror" remote remove origin
  git -C "$mirror" config --unset extensions.partialclone || true
  git config --file "$config" "url.file://$mirror.insteadOf" "https://github.com/$slug"
  echo "$slug -> $(git -C "$mirror" rev-parse HEAD)"
}

# Commits shown in docs/demo.mp4 (spec/demo-video.md).
pin JetBrains/ideavim 7bd8f1315c8abd5c7371c996386c334f683d878d
pin JetBrains/kotlin 848b4009281f9043612814e22077289d07f5063e
