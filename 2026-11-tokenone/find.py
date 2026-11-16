#!/usr/bin/env python3
"""Find TokenOne's NF01, NF02 and NF03 debenture tokens on the Rayls Public Chain.
Read-only. Searches the Rayls explorer, saves every candidate's token record, contract record
and verified source, and greps the current transparency-page bundle for token addresses.
Output: raw/find/, runs/<time>-find.txt"""
import json, os, re, time, urllib.parse, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "raw", "find")
os.makedirs(OUT, exist_ok=True); os.makedirs(os.path.join(HERE, "runs"), exist_ok=True)
API = "https://explorer.rayls.com/api/v2"
UA = {"User-Agent": "Mozilla/5.0 (rayls-verify-monitor)", "Accept": "application/json"}
LOG = []
def log(s): LOG.append(s); print(s, flush=True)
def get(u, raw=False):
    for i in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=40) as r:
                b = r.read()
                return b if raw else json.loads(b)
        except urllib.error.HTTPError as e:
            if e.code in (429, 502, 503) and i < 4: time.sleep(2 ** i); continue
            return {"error": e.code}
        except Exception as e:
            if i < 4: time.sleep(2); continue
            return {"error": str(e)[:100]}
cands = {}
for q in ["NF01", "NF02", "NF03", "TokenOne", "Token One", "debenture", "Debenture", "NF0"]:
    for path in (f"/search?q={urllib.parse.quote(q)}", f"/tokens?q={urllib.parse.quote(q)}"):
        j = get(API + path)
        json.dump(j, open(os.path.join(OUT, re.sub(r'[^A-Za-z0-9]+', '_', path)[:80] + ".json"), "w"))
        for it in (j.get("items") or []) if isinstance(j, dict) else []:
            a = (it.get("address_hash") or it.get("address") or "")
            if isinstance(a, dict): a = a.get("hash", "")
            if a:
                cands[a.lower()] = {"name": it.get("name"), "symbol": it.get("symbol"), "type": it.get("type"), "query": q}
log(f"candidates from search: {len(cands)}")
for a, v in cands.items():
    log(f"   {a} {v}")
# the transparency page bundle may now list the RWA tokens
st = get("https://dapp.rayls.com/transparency", raw=True)
html = st.decode("utf-8", "replace") if isinstance(st, bytes) else ""
for s in set(re.findall(r'src="(/assets/[^"]+\.js)"', html)):
    b = get("https://dapp.rayls.com" + s, raw=True)
    if isinstance(b, bytes):
        t = b.decode("utf-8", "replace")
        open(os.path.join(OUT, "bundle_" + os.path.basename(s)), "w").write(t)
        for m in re.finditer(r'(NF0\d|TokenOne|tokenone|debenture)', t):
            log(f"   bundle mention: {t[max(0, m.start() - 160):m.start() + 200]!r}")
            addrs = re.findall(r"0x[a-fA-F0-9]{40}", t[max(0, m.start() - 600):m.start() + 600])
            for a in addrs:
                cands.setdefault(a.lower(), {"query": "bundle"})
for a in list(cands):
    for path, nm in ((f"/tokens/{a}", "token"), (f"/smart-contracts/{a}", "contract"), (f"/addresses/{a}", "address"),
                     (f"/tokens/{a}/holders", "holders"), (f"/tokens/{a}/transfers", "transfers")):
        j = get(API + path)
        json.dump(j, open(os.path.join(OUT, f"{a[:12]}_{nm}.json"), "w"))
        if nm == "token" and isinstance(j, dict) and "error" not in j:
            log(f"   token {a}: {j.get('name')} {j.get('symbol')} supply {j.get('total_supply')} decimals {j.get('decimals')} holders {j.get('holders_count') or j.get('holders')}")
        if nm == "contract" and isinstance(j, dict) and "error" not in j:
            log(f"   contract {a}: {j.get('name')} verified {j.get('is_verified')} proxy {j.get('proxy_type')}")
open(os.path.join(HERE, "runs", time.strftime("%Y-%m-%dT%H%MZ", time.gmtime()) + "-find.txt"), "w").write("\n".join(LOG) + "\n")
