#!/usr/bin/env bash
# Reproduces every number, chart and audit result. About 25 minutes.
set -e
cd "$(dirname "$0")"
bash get_data.sh
cd src
python3 state_panel.py
python3 state_analysis.py
python3 border.py
python3 power.py
python3 figs.py
python3 fig_summary.py
cd ../audit
python3 tests.py
python3 size_test.py
python3 check_post.py
