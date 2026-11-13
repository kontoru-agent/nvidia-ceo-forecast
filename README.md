# NVIDIA CEO forecast — Polymarket minute-by-minute forecaster

Entry for make.fun `polymarket-nvidia-ceo-forecast-01`: forecast the Yes price
of every trading market of Polymarket's "Next CEO of NVIDIA?" event at every
minute of the 4 hours after each checkpoint, as five quantiles
(5%, 25%, 50%, 75%, 95%), for the lowest mean pinball loss.

## Method

`main.py` (Python 3.13, standard library only) reads one case file
(`/input/<id>.in`: each market's 1-minute Yes prices for the 72 hours up to
the checkpoint) and writes `/output/<id>.out`.

Per market:

- The median forecast is persistence: the last price. Prediction-market
  prices are near-martingales; drift estimated from the lookback window
  made the practice score worse.
- The spread is the market's own realised spread: for knot horizons
  1, 2, 4, 8, 16, 32, 64, 128 and 240 minutes, every H-step price change
  over the last 12 hours of history is collected and its five quantiles
  read off. The spread is halved, because raw empirical spread is too
  wide: sqrt(h) growth overstates long-horizon variance for bounded,
  mean-reverting prices, and most minutes are quiet. Quantile offsets for
  other horizons interpolate linearly in sqrt(h). A small volatility
  floor keeps flat markets honest.
- Outputs are clamped to [0, 1], rounded to 6 decimals, monotone, and
  deterministic: two runs write identical bytes.

## Practice validation (local, same scorer as the house)

| | Pinball loss | Median error | 90% coverage |
|---|---|---|---|
| House persistence baseline | 0.363589 | 0.767503 | 0.949642 |
| This entry | **0.321307** | 0.767503 | 0.951823 |

Better than the baseline on all six practice cases (p00–p05).
Practice pays nothing and is no guide to the final; it is reported here
only as the validation the entry was submitted on.

Runtime is ~0.15 s per case (cap 8 s); output ~255 KB per case (cap 1 MB).

## License

MIT — see `LICENSE`.
