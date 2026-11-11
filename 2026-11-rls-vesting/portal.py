#!/usr/bin/env python3
"""Save what the RLS transparency portal shows, straight from the public endpoints its page calls:
api.rayls.com/v1/dashboard/{overview,series,composition} and the metric-overrides.json file on S3
that the page merges on top. Read-only. Output: raw/portal/<time>/ and runs/<time>-portal.txt"""
import hashlib, json, os, time, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__))
stamp = time.strftime("%Y-%m-%dT%H%MZ", time.gmtime())
OUT = os.path.join(HERE, "raw", "portal", stamp)
os.makedirs(OUT, exist_ok=True); os.makedirs(os.path.join(HERE, "runs"), exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (rayls-verify-monitor)", "Content-Type": "application/json", "Origin": "https://dapp.rayls.com", "Referer": "https://dapp.rayls.com/transparency"}
URLS = {"overview": "https://api.rayls.com/v1/dashboard/overview",
        "series": "https://api.rayls.com/v1/dashboard/series",
        "composition_publicTvl": "https://api.rayls.com/v1/dashboard/composition?metric=publicTvl&include=source%3Arwamonitor",
        "metric_overrides": "https://rayls-public-assets-mainnet.s3.us-east-2.amazonaws.com/rls-transparency-portal/metric-overrides.json"}
lines = [f"portal fetch {stamp}"]
for k, u in URLS.items():
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=40) as r:
            b = r.read(); st = r.status; lm = r.headers.get("Last-Modified")
    except urllib.error.HTTPError as e:
        b = e.read(); st = e.code; lm = None
    except Exception as e:
        b = str(e).encode(); st = -1; lm = None
    open(os.path.join(OUT, k + ".json"), "wb").write(b)
    lines.append(f"{k}: http {st}, {len(b)} bytes, sha256 {hashlib.sha256(b).hexdigest()[:16]}, last-modified {lm}")
    if k in ("overview", "metric_overrides"):
        lines.append("   " + b[:3000].decode("utf-8", "replace"))
open(os.path.join(HERE, "runs", stamp + "-portal.txt"), "w").write("\n".join(lines) + "\n")
print("\n".join(lines))
