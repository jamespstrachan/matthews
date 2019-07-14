#!/bin/sh
git log | grep -Po '#time (\d+)m' | grep -Po '\d+' | awk '{s+=$1} END {print s / 60, "hours"}'
