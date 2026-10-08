#!/usr/bin/env bash
# Gate 3/4/5 smoke test against a running gateway. Usage: KEY=... BASE=http://dashboard.urumi.local ./smoke.sh
set -euo pipefail
BASE=${BASE:-http://localhost:8000}
rpc(){ curl -s -X POST $BASE/mcp -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' -d "$1"; echo; }
rpc '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"smoke","version":"0"}}}'
rpc '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'
rpc '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"woocommerce__list_products","arguments":{}}}'
