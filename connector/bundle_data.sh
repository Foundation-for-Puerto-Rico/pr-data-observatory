#!/usr/bin/env bash
# Copies the data files that observatory_mcp.py reads into connector/data/, then checks the
# connector against that copy. The Tests and Publish site workflows both run it, and Publish site
# deploys the copy with the function (README.md, "How it's hosted").
set -euo pipefail
cd "$(dirname "$0")/.."
rm -rf connector/data && mkdir connector/data
cp site/data/{registry,catalog_index,municipalities,exposure_municipio}.json site/data/*_series.json site/data/dictionary_*.json connector/data/
pip install --quiet "mcp>=2.3,<3"
OBSERVATORY_DATA=connector/data python connector/test_observatory_mcp.py
