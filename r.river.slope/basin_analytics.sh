#!/bin/bash
set -euo pipefail

DEM="dem_5m"
BASINS="basins"
SLOPE="main_slope"
SELECTED="selected_basins"
FLOW_ACC="flow_acc"

# ./r.river.slope.py dem="$DEM" river=main output="$SLOPE" along=10 --overwrite
# BASIN_THRESHOLD=40000
# r.watershed elevation="$DEM" threshold="$BASIN_THRESHOLD" accumulation="$FLOW_ACC" drainage=flow_dir basin="$BASINS" --overwrite

SLOPE_CUTOFF=14
STREAM_THRESHOLD=10000

MASK_STEEP="steep_mask"
ZONES="basin_stats"
STREAM_RAST="flow_lines_rast"
STREAM_VEC="flow_lines"
STREAM_DIR="flow_lines_dir"

g.region raster="$BASINS"

r.mapcalc \
	" $MASK_STEEP = if($SLOPE >= $SLOPE_CUTOFF, 1, null()) " \
	--overwrite

r.stats.zonal \
	base="$BASINS" \
	cover="$MASK_STEEP" \
	method=average \
	output="$ZONES" \
	--overwrite

r.mapcalc \
	" $SELECTED = if(isnull($ZONES), null(), $BASINS) " \
	--overwrite

r.mask raster="$SELECTED" --overwrite

r.stream.extract \
	elevation="$DEM" \
	accumulation="$FLOW_ACC" \
	threshold="$STREAM_THRESHOLD" \
	stream_raster="$STREAM_RAST" \
	stream_vector="$STREAM_VEC" \
	direction="$STREAM_DIR" \
	stream_length=3 \
	memory=2000 \
	--overwrite

r.mask -r

g.remove -f type=raster name="$MASK_STEEP","$ZONES","$STREAM_DIR","$STREAM_RAST" --quiet
