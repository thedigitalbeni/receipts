#!/usr/bin/env bash
# warmup.sh — Render Free-Tier Cold Start Mitigation
#
# Render free tier spins down instances after 15 minutes of inactivity.
# The first request after spin-down takes 30-60 seconds (cold start).
# This is expected behavior, NOT a bug.
#
# Run this script MANUALLY before:
#   1. Demo recording
#   2. Final submission testing
#
# Do NOT schedule this script to run automatically/recurringly.
#
# Usage: ./warmup.sh [BACKEND_URL]
#   Default BACKEND_URL: https://receipts-api.onrender.com

set -euo pipefail

BACKEND_URL="${1:-https://receipts-api.onrender.com}"

echo "🔥 Warming up Render backend at: ${BACKEND_URL}"
echo "   (This may take 30-60 seconds if the instance is cold...)"
echo ""

# First request wakes the instance
start_time=$(date +%s)
response=$(curl -s -o /dev/null -w "%{http_code}" --max-time 90 "${BACKEND_URL}/health" || echo "000")
end_time=$(date +%s)
elapsed=$((end_time - start_time))

if [ "$response" = "200" ]; then
  echo "✅ Backend is warm! (HTTP ${response}, took ${elapsed}s)"
else
  echo "❌ Backend health check failed (HTTP ${response}, took ${elapsed}s)"
  echo "   Check that the Render service is deployed and the URL is correct."
  exit 1
fi

# Second request confirms it's responsive at normal speed
response2=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "${BACKEND_URL}/health")
if [ "$response2" = "200" ]; then
  echo "✅ Confirmed responsive on follow-up request."
else
  echo "⚠️  Follow-up request returned HTTP ${response2} — may need more time."
fi

echo ""
echo "🎬 Ready for demo!"
