#!/bin/bash
# sprint_scaffold.sh — Wire a new Aria sprint folder from the templates/ directory.
#
# Usage:
#   ./sprint_scaffold.sh <sprint-number> <slug> [--dest /path/to/parent]
#
# Examples:
#   ./sprint_scaffold.sh 022 builder_meta
#   ./sprint_scaffold.sh 023 fellows_phase2 --dest ~/projects/sprints/

set -e

usage() {
    cat <<EOF
sprint-scaffold — Scaffold an Aria sprint folder.

Usage:
  $0 <sprint-number> <slug> [--dest DIR]

Args:
  sprint-number    Zero-padded number (e.g. 022)
  slug             Lowercase underscore slug (e.g. builder_meta)
  --dest DIR       Parent dir (default: ./sprints/)

Drops in: spec_charter.md, .claude/agents/pr-review.md, reference/, sql/, HANDOFF_T1_TO_T2.md
EOF
    exit "${1:-0}"
}

if [[ "$1" == "--help" || "$1" == "-h" || -z "$1" ]]; then
    usage 0
fi

NUM="$1"
SLUG="$2"
DEST="./sprints"

shift 2
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dest) DEST="$2"; shift 2 ;;
        *) echo "Unknown arg: $1" >&2; usage 1 ;;
    esac
done

if [[ -z "$NUM" || -z "$SLUG" ]]; then
    usage 1
fi

TEMPLATES="$(dirname "$0")/templates"
TARGET="$DEST/${NUM}_${SLUG}"

if [[ -d "$TARGET" ]]; then
    echo "FATAL: $TARGET already exists" >&2
    exit 2
fi

mkdir -p "$TARGET/.claude/agents" "$TARGET/reference" "$TARGET/sql"
cp "$TEMPLATES/spec_charter.md" "$TARGET/spec_charter.md"
cp "$TEMPLATES/pr-review.md" "$TARGET/.claude/agents/pr-review.md"
cp "$TEMPLATES/HANDOFF_T1_TO_T2.md" "$TARGET/HANDOFF_T1_TO_T2.md"

echo "✓ Sprint ${NUM} scaffolded at $TARGET"
echo "  Next: edit $TARGET/spec_charter.md (P0 items, deliverables, gates)"
