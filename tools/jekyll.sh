#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

if ! command -v ruby >/dev/null 2>&1; then
  echo "Ruby is required. On Ubuntu, install ruby-full, ruby-dev and build-essential." >&2
  exit 1
fi

if command -v bundle >/dev/null 2>&1; then
  bundler=bundle
elif command -v "bundle$(ruby -e 'print RUBY_VERSION.split(".").first(2).join(".")')" >/dev/null 2>&1; then
  bundler="bundle$(ruby -e 'print RUBY_VERSION.split(".").first(2).join(".")')"
else
  echo "Bundler is required. Install it with: gem install bundler" >&2
  exit 1
fi

# Keep dependencies inside this repository's ignored vendor directory.
export BUNDLE_PATH="${BUNDLE_PATH:-$PWD/vendor/bundle}"

if ! "$bundler" check >/dev/null 2>&1; then
  "$bundler" install
fi

exec "$bundler" exec jekyll "$@"
