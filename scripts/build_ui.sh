#!/bin/bash
# Builds the front end (frontend/) and puts it where the API serves it (ui/).
set -e
cd "$(dirname "$0")/../frontend"
[ -d node_modules ] || npm ci
npm run build
rm -rf ../ui && cp -r dist ../ui
echo "UI built into $(cd .. && pwd)/ui. Reload the page; restart the API only if the backend changed."
