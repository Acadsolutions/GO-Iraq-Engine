#!/bin/bash
set -euo pipefail
valhalla_service /data/config.json 2 >/dev/null 2>&1 &
engine_pid=$!
python3 /opt/go-iraq/gateway.py &
gateway_pid=$!
trap 'kill "$engine_pid" "$gateway_pid" 2>/dev/null || true' EXIT TERM INT
wait -n "$engine_pid" "$gateway_pid"
exit 1
