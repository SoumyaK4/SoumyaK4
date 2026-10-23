#!/usr/bin/env bash
set -euo pipefail

export JEKYLL_ENV=development
exec "$(dirname "${BASH_SOURCE[0]}")/jekyll.sh" serve --livereload --host 127.0.0.1 "$@"
