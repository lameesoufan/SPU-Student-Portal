#!/usr/bin/env bash
set -euo pipefail

PROFILE="${1:-baseline}"
HOST_URL="${2:-http://127.0.0.1:8000}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

case "$PROFILE" in
  baseline|stress|spike|soak) ;;
  *) echo "Profile must be baseline, stress, spike, or soak" >&2; exit 2 ;;
esac

export LOAD_PROFILE="$PROFILE"
export LOAD_TEST_HOST="$HOST_URL"
mkdir -p "$SCRIPT_DIR/results"

python "$SCRIPT_DIR/prepare_load_users.py"
python -m locust \
  -f "$SCRIPT_DIR/profile_load.py" \
  --host "$HOST_URL" \
  --headless \
  --csv "$SCRIPT_DIR/results/$PROFILE" \
  --html "$SCRIPT_DIR/results/$PROFILE.html"
