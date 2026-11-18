from datetime import datetime, timezone
import math

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.645, -0.674, 0.0, 0.674, 1.645]
BW = 1.0
SD_FLOOR = 0.15


def _epoch_h(ts):
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts).timestamp() / 3600.0


def parse_curves(comparables):
    usable = []
    if not comparables:
        return usable
    for comp in comparables:
        try:
            if not isinstance(comp, dict):
                continue
            ds_h = _epoch_h(comp["day_start"])
            hourly = comp["hourly"]
            if not isinstance(hourly, list):
                continue
            by_hour = {}
            for rec in hourly:
                if not isinstance(rec, dict):
                    continue
                v = rec.get("viewers")
                if v is None:
                    continue
                rec_h = _epoch_h(rec["from"])
                h_idx = round(rec_h - ds_h) + 1
                if 1 <= h_idx <= 24:
                    by_hour[h_idx] = float(v)
            if len(by_hour) == 24 and by_hour[1] > 0:
                usable.append((by_hour[1], [by_hour[h] for h in range(1, 25)]))
        except Exception:
            continue
    return usable


def _weights(curve_h1s, target_h1, bw):
    t_log = math.log(target_h1)
    return [
        math.exp(-0.5 * (((math.log(c) - t_log) / bw) ** 2))
        for c in curve_h1s
    ]


def _ess(weights):
    s1 = sum(weights)
    s2 = sum(w * w for w in weights)
    return (s1 * s1) / s2 if s2 > 0 else 0.0


def _wmean(values, weights):
    sw = sum(weights)
    return sum(v * w for v, w in zip(values, weights)) / sw if sw > 0 else 0.0


def _clean(raw):
    out = []
    for val in raw:
        v = round(max(1.0, min(1e9, val)), 2)
        if out and v < out[-1]:
            v = out[-1]
        out.append(v)
    return out


def forecast(h1_print, usable_curves):
    h1 = max(1.0, float(h1_print))
    n = len(usable_curves) if usable_curves else 0
    if n == 0:
        return {
            h: [h1 * math.exp(z * 0.15 * math.sqrt(h - 1)) for z in Z]
            for h in range(2, 25)
        }
    if n < 5:
        res = {}
        for h in range(2, 25):
            lrs = sorted(math.log(c[1][h - 1] / c[0]) for c in usable_curves)
            med = lrs[len(lrs) // 2]
            raw = [h1 * math.exp(med + z * SD_FLOOR) for z in Z]
            res[h] = _clean(raw)
        return res
    bw = BW
    c_h1s = [c[0] for c in usable_curves]
    w = _weights(c_h1s, h1, bw)
    while _ess(w) < 8 and bw < 3.0:
        bw *= 2.0
        w = _weights(c_h1s, h1, bw)
    x = [math.log(c) for c in c_h1s]
    mx = _wmean(x, w)
    sxx = sum(wi * ((xi - mx) ** 2) for xi, wi in zip(x, w))
    preds, residuals = {}, []
    for h in range(2, 25):
        y = [math.log(c[1][h - 1] / c[0]) for c in usable_curves]
        my = _wmean(y, w)
        sxy = sum(wi * (xi - mx) * (yi - my) for xi, yi, wi in zip(x, y, w))
        b = sxy / sxx if sxx > 1e-9 else 0.0
        a = my - b * mx
        preds[h] = a + b * math.log(h1)
        for xi, yi, wi in zip(x, y, w):
            residuals.append((yi - (a + b * xi), wi))
    var = sum(wi * (r ** 2) for r, wi in residuals) / max(1e-9, sum(wi for _, wi in residuals))
    spread = max(math.sqrt(var), SD_FLOOR)
    return {
        h: _clean([h1 * math.exp(preds[h] + z * spread) for z in Z])
        for h in range(2, 25)
    }
