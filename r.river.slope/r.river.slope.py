#!/usr/bin/env python3
# %module
# % description: Samples river-to-ridge slope and relief along transects and writes GRASS rasters.
# % keyword: raster
# % keyword: vector
# % keyword: geomorphology
# %end
# %option G_OPT_R_INPUT
# % key: dem
# % description: Input DEM raster
# %end
# %option G_OPT_V_INPUT
# % key: river
# % description: Input river vector line map
# %end
# %option G_OPT_R_OUTPUT
# % key: output
# % description: Output slope raster name
# %end
# %option G_OPT_R_OUTPUT
# % key: relief_output
# % required: no
# % description: Output relief (dh, m) raster name
# %end
# %option
# % key: along
# % type: double
# % required: no
# % answer: 100.0
# % description: Step along river [m]
# %end
# %option
# % key: reach
# % type: double
# % required: no
# % answer: 1000.0
# % description: How far out to look [m]
# %end

import sys
import numpy as np
import grass.script as gs
from grass.script import array as garray
from grass.pygrass.gis.region import Region
from grass.pygrass.vector import VectorTopo


def get_line_info(river):
    vec = VectorTopo(river)
    vec.open(mode="r")
    line = vec.next()
    length = line.length()
    cat = line.cat
    vec.close()
    return length, cat


def make_segment_points(river, along, pts):
    length, cat = get_line_info(river)
    n = int(np.floor(length / along))
    if n < 1:
        gs.fatal("river shorter than one step")

    rules = "\n".join(f"P {i + 1} {cat} {min(i * along, length)}" for i in range(n + 1))
    gs.write_command(
        "v.segment",
        input=river,
        output=pts,
        rules="-",
        overwrite=True,
        quiet=True,
        stdin=rules,
    )


def read_points(pts):
    data = gs.read_command(
        "v.out.ascii", input=pts, format="point", separator="|", quiet=True
    ).strip()
    if not data:
        gs.fatal("no points from v.segment output")

    points = []
    for line in data.splitlines():
        f = line.split("|")
        if len(f) >= 2:
            points.append((float(f[0]), float(f[1])))

    if len(points) < 2:
        gs.fatal("river too short")
    return points


def main():
    opts, _ = gs.parser()
    dem = opts["dem"]
    river = opts["river"]
    out_rast = opts["output"]
    relief_rast = opts.get("relief_output") or None
    along = float(opts["along"])
    reach = float(opts["reach"])

    gs.run_command("g.region", raster=dem, quiet=True)

    reg = Region()
    reg.read()
    dem_res = reg.nsres
    dem_xmin = reg.west
    dem_ymax = reg.north
    dem_rows = reg.rows
    dem_cols = reg.cols

    dem_arr = garray.array(dem)

    out_res = along
    gs.run_command("g.region", res=out_res, flags="a", quiet=True)
    reg = Region()
    reg.read()
    res = reg.nsres
    xmin = reg.west
    ymax = reg.north
    rows = reg.rows
    cols = reg.cols

    pts = "tmp_river_pts"
    make_segment_points(river, along, pts)
    points = read_points(pts)

    def dem_rc(x, y):
        c = int((x - dem_xmin) / dem_res)
        r = int((dem_ymax - y) / dem_res)
        return r, c

    def rc(x, y):
        c = int((x - xmin) / res)
        r = int((ymax - y) / res)
        return r, c

    def elev(x, y):
        r, c = dem_rc(x, y)
        if 0 <= r < dem_rows and 0 <= c < dem_cols:
            v = dem_arr[r, c]
            return v if not np.isnan(v) else np.nan
        return np.nan

    out = np.full((rows, cols), np.nan, dtype=np.float32)
    relief = np.full((rows, cols), np.nan, dtype=np.float32)

    for i, (px, py) in enumerate(points):
        if i == 0:
            dx = points[1][0] - px
            dy = points[1][1] - py
        elif i == len(points) - 1:
            dx = px - points[i - 1][0]
            dy = py - points[i - 1][1]
        else:
            dx = points[i + 1][0] - points[i - 1][0]
            dy = points[i + 1][1] - points[i - 1][1]

        nrm = np.hypot(dx, dy)
        if nrm == 0:
            continue
        nx, ny = -dy / nrm, dx / nrm

        h0 = elev(px, py)
        if np.isnan(h0):
            continue

        ts = np.linspace(-reach, reach, int(2 * reach / dem_res) + 1)

        for sign in (-1, 1):
            tt = ts[ts * sign > 0]
            if len(tt) == 0:
                continue
            vals = np.array([elev(px + t * nx, py + t * ny) for t in tt])
            if np.all(np.isnan(vals)):
                continue

            imax = np.nanargmax(vals)
            d = abs(tt[imax])
            if d == 0 or np.isnan(vals[imax]):
                continue
            dz = vals[imax] - h0
            slope = np.degrees(np.arctan(dz / d))
            for t in tt:
                # only to the highest point
                if sign * t > sign * tt[imax]:
                    continue
                r, c = rc(px + t * nx, py + t * ny)
                if 0 <= r < rows and 0 <= c < cols:
                    if np.isnan(out[r, c]):
                        out[r, c] = slope
                        relief[r, c] = dz

    if not np.isfinite(out).any():
        gs.fatal("no valid cells")

    gr = garray.array()
    gr[...] = out
    gr.write(out_rast, overwrite=True)

    if relief_rast:
        gr_r = garray.array()
        gr_r[...] = relief
        gr_r.write(relief_rast, overwrite=True)

    gs.run_command("g.remove", flags="f", type="vector", name=pts, quiet=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
