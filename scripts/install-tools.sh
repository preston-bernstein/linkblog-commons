#!/usr/bin/env bash
# Install the tools the gates need into one directory, then print the PATH line to use.
# Python tools install from a hash-locked file. Node tools install from a lockfile.
# Binaries download to a file and must match a pinned SHA-256 before they run.
#
#   install-tools.sh [DIR]     (default: .ci-tools in the current directory; it is git-ignored)
# In GitHub Actions it also adds the tool directories to GITHUB_PATH.
set -euo pipefail

ACTIONLINT_VERSION=1.7.12
ACTIONLINT_SHA256=8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8
SHFMT_VERSION=3.14.1
SHFMT_SHA256=76e77641faa025814b77f153b29796b8e6fa2fca03e0c76a691608b86c7ea7bf
VALE_VERSION=3.27.0
VALE_SHA256=c80d62f6bce87b81843ac5b512a26e63213927b957adba0a64fc594570da2000

log() { echo "install-tools: $*" >&2; }
die() {
  log "$*"
  exit "${2:-1}"
}

need() { command -v "$1" >/dev/null 2>&1 || die "missing tool: $1" 127; }

# fetch URL SHA256 FILE: download to FILE and stop unless the checksum matches.
fetch() {
  local url="$1" sha="$2" file="$3"
  curl --fail --silent --show-error --location --output "$file" "$url"
  echo "$sha  $file" | sha256sum --check --status || die "checksum mismatch for $url"
}

install_binaries() {
  local bin="$1" work="$2"

  fetch "https://github.com/rhysd/actionlint/releases/download/v${ACTIONLINT_VERSION}/actionlint_${ACTIONLINT_VERSION}_linux_amd64.tar.gz" \
    "$ACTIONLINT_SHA256" "$work/actionlint.tar.gz"
  tar -xzf "$work/actionlint.tar.gz" -C "$bin" actionlint

  fetch "https://github.com/mvdan/sh/releases/download/v${SHFMT_VERSION}/shfmt_v${SHFMT_VERSION}_linux_amd64" \
    "$SHFMT_SHA256" "$bin/shfmt"
  chmod +x "$bin/shfmt"

  fetch "https://github.com/vale-cli/vale/releases/download/v${VALE_VERSION}/vale_${VALE_VERSION}_Linux_64-bit.tar.gz" \
    "$VALE_SHA256" "$work/vale.tar.gz"
  tar -xzf "$work/vale.tar.gz" -C "$bin" vale
}

# Global, not local: the EXIT trap runs after main returns, when a local would be gone.
work=""

main() {
  local root dir bin
  root="$(git rev-parse --show-toplevel)"
  dir="${1:-$PWD/.ci-tools}"
  need python3
  need npm
  need curl
  need sha256sum
  mkdir -p "$dir/bin"
  work="$(mktemp -d)"
  trap 'rm -rf "$work"' EXIT
  bin="$dir/bin"

  python3 -m venv "$dir/venv"
  "$dir/venv/bin/python" -m pip install --quiet --require-hashes -r "$root/ci/requirements-tools.txt"

  npm ci --ignore-scripts --no-audit --no-fund --prefix "$root/ci" >/dev/null || die "npm ci failed"
  install_binaries "$bin" "$work"

  if [ -n "${GITHUB_PATH:-}" ]; then
    printf '%s\n' "$bin" "$dir/venv/bin" "$root/ci/node_modules/.bin" >>"$GITHUB_PATH"
  fi
  echo "export PATH=\"$bin:$dir/venv/bin:$root/ci/node_modules/.bin:\$PATH\""
}

main "$@"
