#!/usr/bin/env bash
# Cuts a miman release: pushes main + creates a GitHub Release tagged
# miman-vX.Y.Z (spec 03-M §6.3 — the router dispatches miman-cd.yml on this
# prefix; a bare vX.Y.Z tag would route to the upstream PyPI publish path).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VERSION="${VERSION:-}"
TAG="miman-v${VERSION}"

fail() {
  echo "ERROR: $1" >&2
  exit 1
}

require_version() {
  [ -n "$VERSION" ] || fail "VERSION is required, for example VERSION=1.2.3"
  echo "$VERSION" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.]+)?$' \
    || fail "VERSION must be semver X.Y.Z (optionally -rcN etc) without a leading v"
}

require_main() {
  local branch
  branch="$(git -C "$REPO_ROOT" branch --show-current)"
  [ "$branch" = "main" ] || fail "release-all must run from main"
}

require_clean_tree() {
  if ! git -C "$REPO_ROOT" diff --quiet || ! git -C "$REPO_ROOT" diff --cached --quiet; then
    fail "working tree must be clean before release-all"
  fi

  if [ -n "$(git -C "$REPO_ROOT" status --short)" ]; then
    fail "working tree has untracked files before release-all"
  fi
}

require_synced_origin_main() {
  git -C "$REPO_ROOT" fetch origin main --tags >/dev/null 2>&1

  local head_sha origin_sha
  head_sha="$(git -C "$REPO_ROOT" rev-parse HEAD)"
  origin_sha="$(git -C "$REPO_ROOT" rev-parse origin/main)"
  [ "$head_sha" = "$origin_sha" ] || fail "HEAD must equal origin/main before release-all"
}

require_new_tag() {
  if git -C "$REPO_ROOT" rev-parse -q --verify "refs/tags/${TAG}" >/dev/null; then
    fail "local tag ${TAG} already exists"
  fi

  if git -C "$REPO_ROOT" ls-remote --exit-code --tags origin "refs/tags/${TAG}" >/dev/null 2>&1; then
    fail "remote tag ${TAG} already exists on origin"
  fi
}

run_deploy_check() {
  make -C "$REPO_ROOT" miman-deploy-check
}

publish_release() {
  git -C "$REPO_ROOT" push origin main
  gh release create "$TAG" \
    --repo LetA-Tech/miman \
    --title "$TAG" \
    --generate-notes \
    --target main
}

require_version
require_main
require_clean_tree
require_synced_origin_main
run_deploy_check
require_new_tag
publish_release

echo "Release ${TAG} published."
echo "The release router (release.yml) dispatches miman-cd.yml, which builds and pushes the immutable image to DOCR."
echo "No deployment was performed."
