#!/usr/bin/env bash

set -euo pipefail

project_dir="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
make_bin="${AGENT_STOP_HOOK_MAKE_BIN:-make}"

# Hooks run in a plain shell without direnv/mise activation, so tools managed
# by mise (poetry, node) are missing from PATH unless we load its env here.
mise_bin="${AGENT_STOP_HOOK_MISE_BIN:-$HOME/.local/bin/mise}"
if ! command -v poetry >/dev/null 2>&1 && [ -x "$mise_bin" ]; then
  eval "$(cd "$project_dir" && "$mise_bin" env -s bash)" || true
fi
make_target="${AGENT_STOP_HOOK_TARGET:-stop-hook-unit-tests}"
max_lines="${AGENT_STOP_HOOK_MAX_LINES:-200}"

if output="$("$make_bin" -C "$project_dir" --no-print-directory "$make_target" 2>&1)"; then
  exit 0
fi

printf 'Unit tests failed while running `%s`.\n' "$make_target" >&2
printf 'Fix the failing tests before stopping.\n' >&2

trimmed_output="$(printf '%s\n' "$output" | tail -n "$max_lines")"
if [ -n "$trimmed_output" ]; then
  printf '\n%s\n' "$trimmed_output" >&2
fi

exit 2
