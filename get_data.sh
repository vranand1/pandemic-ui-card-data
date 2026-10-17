#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"; mkdir -p data/raw; cd data/raw
B=https://raw.githubusercontent.com/OpportunityInsights/EconomicTracker/main
for f in "data/Affinity - State - Daily.csv" "data/Affinity - County - Daily.csv" "data/UI Claims - State - Weekly.csv" \
         "data/UI Claims - County - Weekly.csv" "data/COVID - State - Daily.csv" "data/GeoIDs - State.csv" \
         "data/GeoIDs - County.csv" "data/Policy Milestones - State.csv" "docs/oi_tracker_data_dictionary.md"; do
  out=$(basename "$f" | tr ' ' '_'); curl -sSfL -o "$out" "$B/$(echo "$f" | sed 's/ /%20/g')"; echo "downloaded $out"
done
curl -sSfL -o county_adjacency.txt https://www2.census.gov/geo/docs/reference/county_adjacency.txt
