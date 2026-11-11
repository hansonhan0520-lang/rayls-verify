#!/usr/bin/env python3
"""Probe: save the transparency pages and every script they load, list the data endpoints
those scripts call, and read the Parfin lock-up contract from the Rayls explorer API.
Read-only. Output goes to raw/probe/ and runs/<time>-probe.txt."""
import json, os, re, time, urllib.parse, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "raw", "probe")
os.makedirs(OUT, exist_ok=True); os.makedirs(os.path.join(HERE, "runs"), exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (rayls-verify-monitor)", "Accept": "*/*"}
LOG = []
def log(s): LOG.append(s); print(s, flush=True)
def get(u, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=40) as r:
                return r.status, r.geturl(), r.read()
        except urllib.error.HTTPError as e:
            if e.code in (429, 502, 503) and i < tries - 1: time.sleep(2 ** i); continue
            return e.code, u, e.read()
        except Exception as e:
            if i < tries - 1: time.sleep(2); continue
            return -1, u, str(e).encode()
safe = lambda u: re.sub(r"[^A-Za-z0-9._-]+", "_", u.split("//", 1)[-1])[:120]
log(f"probe {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
endpoints, addrs = set(), set()
for page in ["https://transparency.rayls.com/", "https://dapp.rayls.com/transparency"]:
    st, final, b = get(page)
    log(f"page {page} -> {st} {final} {len(b)} bytes")
    open(os.path.join(OUT, safe(page) + ".html"), "wb").write(b)
    html = b.decode("utf-8", "replace")
    scripts = set(urllib.parse.urljoin(final, s) for s in re.findall(r'<script[^>]+src="([^"]+)"', html))
    scripts |= set(urllib.parse.urljoin(final, s) for s in re.findall(r'"(/[^"]+\.js)"', html))
    texts = [html]
    for s in sorted(scripts)[:80]:
        st2, f2, b2 = get(s)
        if st2 == 200:
            open(os.path.join(OUT, safe(s)), "wb").write(b2)
            texts.append(b2.decode("utf-8", "replace"))
        log(f"   script {s[:140]} -> {st2} {len(b2)}")
    for t in texts:
        for m in re.findall(r'https?://[A-Za-z0-9._-]+(?:/[^"\'`\s<>)\\]*)?', t):
            if re.search(r"api|graphql|rpc|explorer|supply|transpar|rayls|etherscan|coingecko|subgraph|dune|supabase|firebase", m, re.I) and not re.search(r"\.(png|svg|jpg|woff2?|css)$", m):
                endpoints.add(m)
        addrs |= set(a.lower() for a in re.findall(r"0x[a-fA-F0-9]{40}\b", t))
log("\nendpoints referenced:")
for e in sorted(endpoints): log("   " + e[:200])
log(f"\naddresses referenced ({len(addrs)}):")
for a in sorted(addrs): log("   " + a)
LOCK = "0x1463889D3a5EAAEE3f066d1CF438A8957F7Db98E"
API = "https://explorer.rayls.com/api/v2"
for path in [f"/addresses/{LOCK}", f"/smart-contracts/{LOCK}", f"/addresses/{LOCK}/token-balances",
             f"/addresses/{LOCK}/token-transfers", f"/addresses/{LOCK}/logs", f"/addresses/{LOCK}/transactions",
             "/stats", "/search?q=RLS", "/tokens?q=RLS"]:
    st, final, b = get(API + path)
    open(os.path.join(OUT, "explorer" + safe(path) + ".json"), "wb").write(b)
    log(f"explorer {path} -> {st} {len(b)} bytes  {b[:200].decode('utf-8','replace')!r}")
open(os.path.join(HERE, "runs", time.strftime("%Y-%m-%dT%H%MZ", time.gmtime()) + "-probe.txt"), "w").write("\n".join(LOG) + "\n")
