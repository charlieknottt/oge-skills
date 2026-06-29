#!/usr/bin/env bash
# bootstrap.sh - one-time setup + smoke test for the world-graph-builder skill.
#
# Verifies Python, installs the optional doc-parsing deps (best effort), and runs
# the deterministic validators against the two bundled example graphs as a smoke
# test. If the examples validate clean, the box is healthy and the output schema
# is locked. Safe to re-run.
#
# Usage:  bash scripts/bootstrap.sh
set -u

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPTS="$SKILL_DIR/scripts"
EXAMPLES="$SKILL_DIR/examples"

echo "== world-graph-builder bootstrap =="
echo "skill dir: $SKILL_DIR"

# 1. Python version
if ! command -v python3 >/dev/null 2>&1; then
  echo "FAIL: python3 not found on PATH"; exit 1
fi
PYV="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
echo "python3: $PYV"

# 2. Optional deps for doc parsing (validators themselves need no third-party deps)
echo "installing optional doc-parsing deps (PyPDF2, python-docx)..."
python3 -m pip install --quiet PyPDF2 python-docx >/dev/null 2>&1 \
  && echo "  deps installed" \
  || echo "  WARN: could not install deps (validators still work; parse_docs.py may not)"

# 3. Smoke test: validators must pass clean on both example graphs
rc=0
for g in gordian_knot_graph taiwan_strait_graph; do
  echo "-- validating $g.json --"
  python3 "$SCRIPTS/validate_graph.py" "$EXAMPLES/$g.json" || rc=1
done

if [ "$rc" -eq 0 ]; then
  echo "SMOKE TEST PASSED: both example graphs validate clean."
else
  echo "SMOKE TEST FAILED: see errors above."
fi
exit "$rc"
