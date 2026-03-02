#!/bin/bash
# Wait for CI to complete and report status
# Usage: ./wait-for-ci.sh [branch] [timeout_minutes]
set -e

BRANCH="${1:-$(git rev-parse --abbrev-ref HEAD)}"
TIMEOUT_MIN="${2:-10}"
COMMIT=$(git rev-parse HEAD | cut -c1-7)

echo "⏳ Waiting for CI to start for $BRANCH @ $COMMIT..."
echo "   (timeout: ${TIMEOUT_MIN} minutes)"
sleep 10  # Give GitHub Actions time to trigger

# Find the latest run for this commit
RUN_ID=$(gh run list --branch "$BRANCH" --limit 10 --json databaseId,headSha \
  --jq ".[] | select(.headSha | startswith(\"$(git rev-parse HEAD)\")) | .databaseId" \
  | head -1)

if [ -z "$RUN_ID" ]; then
  echo "❌ No CI run found for this commit"
  echo "   Check manually: gh run list --branch $BRANCH"
  echo "   CI may not be configured for this branch"
  exit 1
fi

echo "✅ CI run started: $RUN_ID"
echo "   View: https://github.com/$(gh repo view --json nameWithOwner -q .nameWithOwner)/actions/runs/$RUN_ID"
echo ""

# Watch with timeout
echo "📊 Watching CI progress (timeout: ${TIMEOUT_MIN}m)..."
timeout "${TIMEOUT_MIN}m" gh run watch "$RUN_ID" || {
  STATUS=$?
  if [ $STATUS -eq 124 ]; then
    echo "⏱️ Timeout reached (${TIMEOUT_MIN} minutes)"
    echo "   CI is still running, check status manually:"
    echo "   gh run view $RUN_ID"
    exit 1
  fi
  echo "❌ Watch command failed (exit $STATUS)"
  exit 1
}

echo ""

# Check final status
STATUS=$(gh run view "$RUN_ID" --json conclusion --jq '.conclusion')

case "$STATUS" in
  success)
    echo "✅ CI PASSED - All checks successful"
    echo ""
    gh run view "$RUN_ID" --json jobs --jq '.jobs[] | "  ✅ \(.name) (\(.conclusion))"'
    exit 0
    ;;
  failure)
    echo "❌ CI FAILED - Checking logs..."
    echo ""
    gh run view "$RUN_ID" --log-failed
    echo ""
    echo "Fix the failures and push again"
    exit 1
    ;;
  cancelled)
    echo "⚠️ CI was cancelled"
    exit 1
    ;;
  *)
    echo "⚠️ CI status: $STATUS"
    gh run view "$RUN_ID"
    exit 1
    ;;
esac
