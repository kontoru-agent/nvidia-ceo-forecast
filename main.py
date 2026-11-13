#!/usr/bin/env python3
"""NVIDIA CEO forecast entry (Python 3.13, standard library only).

Per market, forecasts the next 240 minutes as five quantiles (5/25/50/75/95%)
from the case's own 1-minute price history (up to 72h, 4320 points).

Method: empirical quantiles of the market's own multi-step price changes,
calibrated on the practice phase (6 cases, 2026-11-12 06:00 UTC to
2026-11-13 06:00 UTC; house baseline 0.363589, this entry 0.321307, better
on all six cases). For knot horizons H in {1,2,4,8,16,32,64,128,240} minutes,
take every H-step change over the last 12 hours of history, sort them, and
read the five quantiles. The median is persistence (last price): prediction
market prices are near-martingales and any drift estimated from the window
hurt the practice score. The spread around the median is the market's own
realised spread, halved: the raw empirical spread is too wide because
sqrt(h) growth overstates long-horizon variance for bounded, mean-reverting
prices, and most minutes are quiet. Quantile offsets for other horizons are
interpolated linearly in sqrt(h). A small volatility floor keeps flat
markets honest. Everything is deterministic; two runs write identical bytes.
"""

import json
import math
import os
from pathlib import Path

INPUT_DIR = os.environ.get("MAKEFUN_INPUT_DIR", "/input")
OUTPUT_DIR = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")

TAUS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.644854, -0.674490, 0.0, 0.674490, 1.644854]
KNOT_H = [1, 2, 4, 8, 16, 32, 64, 128, 240]
WINDOW = int(os.environ.get("MF_WINDOW", "720"))  # minutes of history
MEDIAN_SHRINK = float(os.environ.get("MF_SHRINK", "0"))  # drift shrinkage
SPREAD_SCALE = float(os.environ.get("MF_SPREAD", "0.5"))  # spread multiplier
TAIL_SCALE = float(os.environ.get("MF_TAIL", str(SPREAD_SCALE)))
INNER_SCALE = float(os.environ.get("MF_INNER", str(SPREAD_SCALE)))
SCALE_J = [TAIL_SCALE, INNER_SCALE, 1.0, INNER_SCALE, TAIL_SCALE]
SIGMA_FLOOR = float(os.environ.get("MF_FLOOR", "0.0015"))  # per sqrt(minute)
BASELINE_SIGMA = 0.0025


def price6(x):
    """Clamp to [0, 1] and round to 6 decimals (0, never -0)."""
    return round(min(1.0, max(0.0, x)), 6) + 0.0


def quantile(sorted_vals, tau):
    n = len(sorted_vals)
    if n == 1:
        return sorted_vals[0]
    pos = tau * (n - 1)
    lo = int(pos)
    frac = pos - lo
    if lo + 1 >= n:
        return sorted_vals[-1]
    return sorted_vals[lo] * (1.0 - frac) + sorted_vals[lo + 1] * frac


def knot_offsets(prices):
    """Empirical quantile offsets of H-step changes, per knot horizon.

    Returns a list of (sqrt(H), [q05, q25, q50, q75, q95]) with the median
    shrunk toward zero, or None when the history is too short to learn from.
    """
    n = len(prices)
    w = min(n, WINDOW)
    base = prices[n - w:]
    m = len(base)
    knots = []
    for h in KNOT_H:
        if m - h < 30:
            continue
        changes = sorted(base[t + h] - base[t] for t in range(m - h))
        qs = [quantile(changes, tau) for tau in TAUS]
        med = qs[2]
        adj = [MEDIAN_SHRINK * med + SCALE_J[j] * (qs[j] - med)
               for j in range(5)]
        knots.append((math.sqrt(h), adj))
    return knots or None


def interp_offsets(knots, s):
    """Linear interpolation of the five offsets at sqrt(horizon) = s."""
    if s <= knots[0][0]:
        return list(knots[0][1])
    if s >= knots[-1][0]:
        return list(knots[-1][1])
    for i in range(len(knots) - 1):
        s0, q0 = knots[i]
        s1, q1 = knots[i + 1]
        if s0 <= s <= s1:
            f = (s - s0) / (s1 - s0)
            return [q0[j] * (1.0 - f) + q1[j] * f for j in range(5)]
    return list(knots[-1][1])


def forecast_market(prices, horizon):
    x = prices[-1]
    knots = knot_offsets(prices)
    rows = []
    for h in range(1, horizon + 1):
        s = math.sqrt(h)
        if knots is None:
            offs = [z * BASELINE_SIGMA * s for z in Z]
        else:
            offs = interp_offsets(knots, s)
            for j in range(5):
                if j == 2:
                    continue
                # Floor on the spread magnitude, widening AWAY from the median.
                floor_mag = abs(Z[j]) * SIGMA_FLOOR * s
                if j < 2:
                    offs[j] = min(offs[j], -floor_mag)
                else:
                    offs[j] = max(offs[j], floor_mag)
        row = [price6(x + off) for off in offs]
        # Monotonicity without moving the median: clamp outer quantiles
        # toward the median instead of pushing the median itself.
        row[1] = min(row[1], row[2])
        row[0] = min(row[0], row[1])
        row[3] = max(row[3], row[2])
        row[4] = max(row[4], row[3])
        rows.append(row)
    return rows


def main():
    in_dir = Path(INPUT_DIR)
    out_dir = Path(OUTPUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(f for f in in_dir.iterdir()
                   if f.is_file() and f.name.endswith(".in"))
    for path in files:
        case = json.loads(path.read_text(encoding="utf-8"))
        horizon = int(case["horizon_minutes"])
        forecasts = []
        for m in case["markets"]:
            prices = m["prices"]
            if not prices:
                raise ValueError("market %s has no prices" % m["id"])
            forecasts.append({"id": m["id"],
                              "q": forecast_market(prices, horizon)})
        out = {"forecasts": forecasts}
        (out_dir / (path.stem + ".out")).write_text(
            json.dumps(out) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
