#!/usr/bin/env bash
# Ежечасный dry-run бидера. Боевая запись: AVITO_BID_APPLY=1
set -euo pipefail
cd "$(dirname "$0")"
if [[ "${AVITO_BID_APPLY:-0}" == "1" ]]; then
  exec python3 avito_autobidder.py --days 60 --apply
else
  exec python3 avito_autobidder.py --days 60
fi
