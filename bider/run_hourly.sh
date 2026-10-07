#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ "${AVITO_BID_APPLY:-0}" == "1" ]]; then
  exec python3 avito_autobidder.py --days 60 --top-n 50 --apply --apply-top 30
else
  exec python3 avito_autobidder.py --days 60 --top-n 50
fi
