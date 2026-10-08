#!/usr/bin/env bash
# Creates a MEMBER user + key via the gateway admin API. Usage: ADMIN_KEY=... ./seed.sh [base_url]
set -euo pipefail
BASE=${1:-http://dashboard.urumi.local}; H="Authorization: Bearer $ADMIN_KEY"
UID_=$(curl -s -X POST $BASE/api/users -H "$H" -H 'Content-Type: application/json' -d '{"email":"member-b@urumi.local","name":"Member B","role":"MEMBER"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')
curl -s -X POST $BASE/api/users/$UID_/keys -H "$H"; echo
