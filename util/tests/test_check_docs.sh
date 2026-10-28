#!/usr/bin/env bash
# Tests util/check_docs.py: relative links resolve, every services/* folder is in docs/codemap.md,
# every util/ entry is in util/SCRIPTS.md, and agent pointer files hold only their pointer.
# Run from the repo root (make test-util). Needs bash and python3. Each case builds a small tree.
set -uo pipefail

CHECK=$PWD/util/check_docs.py
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT

# base DIR — a minimal tree that passes every check.
base() {
  mkdir -p "$1/docs" "$1/services/api" "$1/util" "$1/.github" "$1/.agents/rules"
  printf '# Code map\n\n### `services/api/`\n' > "$1/docs/codemap.md"
  printf '# util/ script index\n\n| `reset.sh` | Resets the host |\n' > "$1/util/SCRIPTS.md"
  : > "$1/util/reset.sh"
  printf '# Agents\n\nSee [the code map](docs/codemap.md).\n' > "$1/AGENTS.md"
  printf '@AGENTS.md\n' > "$1/CLAUDE.md"
  printf 'Follow the instructions in [AGENTS.md](../AGENTS.md).\n' > "$1/.github/copilot-instructions.md"
  printf -- '---\ntrigger: always_on\n---\n\n# Antigravity Context\n\n@AGENTS.md\n' > "$1/.agents/rules/main.md"
}

fails=0
# check NAME DIR WANT_EXIT [PATTERN] — run the checker on DIR; compare the exit code and, if given,
# require PATTERN in the output.
check() {
  local name=$1 dir=$2 want=$3 pattern=${4:-} out rc
  out=$(python3 "$CHECK" "$dir" 2>&1); rc=$?
  if [ "$rc" -ne "$want" ]; then
    echo "FAIL $name: want exit $want, got $rc: $out"; fails=$((fails + 1))
  elif [ -n "$pattern" ] && ! grep -qF -- "$pattern" <<<"$out"; then
    echo "FAIL $name: output lacks '$pattern': $out"; fails=$((fails + 1))
  else
    echo "ok   $name"
  fi
}

base "$T/clean"
check "clean tree passes" "$T/clean" 0

base "$T/broken"
printf 'See [missing](docs/nope.md).\n' >> "$T/broken/AGENTS.md"
check "broken relative link fails" "$T/broken" 1 "docs/nope.md"

base "$T/anchors"
printf '[a](docs/codemap.md#services) [b](https://example.org/x.md) [c](#top) [d](mailto:a@b.c)\n' >> "$T/anchors/AGENTS.md"
printf '[e]: docs/codemap.md\n' >> "$T/anchors/AGENTS.md"
check "anchors, external URLs and reference links resolve" "$T/anchors" 0

base "$T/code"
printf '`[x](inline/nope.md)`\n\n```\n[y](fenced/nope.md)\n```\n' >> "$T/code/AGENTS.md"
check "links inside code are ignored" "$T/code" 0

base "$T/artifacts"
mkdir -p "$T/artifacts/docs/artifacts/2026-01-01-000000-x"
printf '[old](gone.md)\n' > "$T/artifacts/docs/artifacts/2026-01-01-000000-x/plan.md"
check "docs/artifacts is skipped" "$T/artifacts" 0

base "$T/template"
mkdir -p "$T/template/docs/decisions"
printf -- '- **Status:** Superseded by [YYYY-MM-DD-title.md](link)\n' > "$T/template/docs/decisions/TEMPLATE.md"
check "TEMPLATE.md placeholders are skipped" "$T/template" 0

base "$T/service"
mkdir -p "$T/service/services/newsvc"
check "service missing from codemap fails" "$T/service" 1 "services/newsvc"

base "$T/prefix"
mkdir -p "$T/prefix/services/api_old"
check "service name prefix doesn't count as listed" "$T/prefix" 1 "services/api_old"

base "$T/util"
: > "$T/util/util/new-script.sh"
check "util entry missing from SCRIPTS.md fails" "$T/util" 1 "new-script.sh"

base "$T/pointer"
printf '@AGENTS.md\n\nAlways use tabs.\n' > "$T/pointer/CLAUDE.md"
check "pointer file with extra content fails" "$T/pointer" 1 "CLAUDE.md"

base "$T/orphan"
mkdir -p "$T/orphan/services/api"
printf '@AGENTS.md\n' > "$T/orphan/services/api/CLAUDE.md"
check "pointer file without a sibling AGENTS.md fails" "$T/orphan" 1 "services/api/CLAUDE.md"

base "$T/copilot"
printf 'Follow AGENTS.md.\nAlso prefer short functions.\n' > "$T/copilot/.github/copilot-instructions.md"
check "copilot pointer with extra content fails" "$T/copilot" 1 "copilot-instructions.md"

echo "$fails failure(s)"
[ "$fails" -eq 0 ]
