#!/usr/bin/env python3
"""Discovery: the vaults the debentures' role holder reports on, and what they hold.
Saves every vault's explorer record, verified source, transactions, token transfers and logs,
the role holder's full transaction list, and the smart-wallet implementation used by the two
debenture holders. Read-only. Output: raw/vaults/, data/vaults_discovery.json, runs/<time>-vaults.txt"""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tokenone as T
H = T.HERE
OUT = os.path.join(H, "raw", "vaults")
os.makedirs(OUT, exist_ok=True)
ROLE = "0x14f918b1739e325ef588b725f1ee63c6215db335"
WALLET_IMPL = "0x68641de71cfea5a5d0d29712449ee254bb1400c2"
COMPLIANCE_IMPL = "0x539381daa5012b8e8cf91b79cd21865020cb7518"
lines = []
def say(s): lines.append(s); print(s, flush=True)
# every transaction the role holder ever sent: which contracts it manages
txs = T.explorer_all(f"/addresses/{ROLE}/transactions")
json.dump(txs, open(os.path.join(OUT, "role_holder_transactions.json"), "w"))
targets = {}
for x in txs:
    to = ((x.get("to") or {}).get("hash") or "").lower()
    created = ((x.get("created_contract") or {}) or {}).get("hash")
    key = to or ("created:" + (created or "?").lower())
    targets.setdefault(key, {}).setdefault(x.get("method") or "?", 0)
    targets[key][x.get("method") or "?"] += 1
say(f"role holder sent {len(txs)} transactions to {len(targets)} targets")
for k, v in sorted(targets.items(), key=lambda kv: -sum(kv[1].values())):
    say(f"   {k}: {v}")
vaults = sorted(k for k, v in targets.items() if "reportDeployedCapital" in v)
disc = {"targets": targets, "vaults": {}}
sel = {"name": "0x06fdde03", "symbol": "0x95d89b41", "asset": "0x38d52e0f", "totalAssets": "0x01e1d114", "totalSupply": "0x18160ddd",
       "decimals": "0x313ce567", "deployedCapital": "0xb0c660ee", "owner": "0x8da5cb5b", "paused": "0x5c975abb", "manager": "0x481c6a75"}
for v in vaults:
    d = {}
    for k, s in sel.items():
        r = T.call(v, s)
        d[k] = r if not r.startswith("0x") else (bytes.fromhex(r[130:]).rstrip(b"\0").decode(errors="replace") if k in ("name", "symbol") and len(r) > 130
                                                   else ("0x" + r[-40:] if k in ("asset", "owner", "manager") else int(r, 16) if r != "0x" else None))
    for path, nm in ((f"/smart-contracts/{v}", "contract"), (f"/addresses/{v}", "address"), (f"/addresses/{v}/token-transfers", "transfers"),
                     (f"/addresses/{v}/token-balances", "balances"), (f"/addresses/{v}/logs", "logs")):
        try:
            j = T.http(T.API + path)
            json.dump(j, open(os.path.join(OUT, f"vault_{v[:10]}_{nm}.json"), "w"))
            if nm == "contract":
                d["contract_name"], d["verified"] = j.get("name"), j.get("is_verified")
            if nm == "address":
                d["implementations"] = j.get("implementations")
            if nm == "balances":
                d["token_balances"] = [((b.get("token") or {}).get("symbol"), (b.get("token") or {}).get("address_hash"), b.get("value")) for b in j] if isinstance(j, list) else j
        except Exception as e:
            d[f"{nm}_error"] = str(e)[:80]
    for impl in (d.get("implementations") or [])[:1]:
        a = impl.get("address_hash")
        try:
            json.dump(T.http(f"{T.API}/smart-contracts/{a}"), open(os.path.join(OUT, f"vault_{v[:10]}_impl.json"), "w"))
        except Exception:
            pass
    disc["vaults"][v] = d
    say(f"vault {v}: {json.dumps({k: d.get(k) for k in list(sel) + ['contract_name', 'verified', 'token_balances']}, default=str)}")
for a, nm in ((WALLET_IMPL, "wallet_impl"), (COMPLIANCE_IMPL, "compliance_impl")):
    try:
        j = T.http(f"{T.API}/smart-contracts/{a}")
        json.dump(j, open(os.path.join(OUT, f"{nm}.json"), "w"))
        say(f"{nm} {a}: {j.get('name')} verified {j.get('is_verified')}")
    except Exception as e:
        say(f"{nm} {a}: {str(e)[:60]}")
json.dump(disc, open(os.path.join(H, "data", "vaults_discovery.json"), "w"), indent=1, default=str)
open(os.path.join(H, "runs", time.strftime("%Y-%m-%dT%H%MZ", time.gmtime()) + "-vaults.txt"), "w").write("\n".join(lines) + "\n")
