#!/usr/bin/env python3
"""Look at the accounts around the debentures: the two holders, the three deployers, the
compliance module and the role holder. Saves code, proxy slots, explorer records and token
balances. Read-only. Output: data/accounts.json, raw/accounts/, runs/<time>-accounts.txt"""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tokenone as T
H = T.HERE
os.makedirs(os.path.join(H, "raw", "accounts"), exist_ok=True)
ACC = {"holder_NF01_NF02": "0x9b170c46e8f8b9e7706abca1045828de45619e10", "holder_NF03": "0x8b6878e92fc08c89fbd7e36388492de839feedfd",
       "deployer_NF01": "0x2090995517b9a7daab580f97ae7b3cdbeb14fa74", "deployer_NF02": "0xa8f5fa90e9398b39cbc1a141da815b7e826d07a8",
       "deployer_NF03": "0x6db16b948e5938a17ba2ce9530326fda11cc8a81", "compliance_NF01": "0x7aa92401df4c0f52e744bb5c9d96caf5ab07d026",
       "role_holder": "0x14f918b1739e325ef588b725f1ee63c6215db335"}
SLOTS = {"eip1967_impl": "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc",
         "eip1967_admin": "0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103",
         "eip1967_beacon": "0xa3f0ad74e5423aebfd80d3ef4346578335a9a72aeaee59ff6cb3582b35133d50", "slot0": "0x0"}
out, lines = {}, []
for k, a in ACC.items():
    d = {"address": a, "code": T.rpc("eth_getCode", [a, "latest"]), "nonce": int(T.rpc("eth_getTransactionCount", [a, "latest"]), 16),
         "usdr_balance": int(T.rpc("eth_getBalance", [a, "latest"]), 16) / 1e18}
    d["slots"] = {n: T.rpc("eth_getStorageAt", [a, s, "latest"]) for n, s in SLOTS.items()}
    for path, nm in ((f"/addresses/{a}", "address"), (f"/smart-contracts/{a}", "contract"), (f"/addresses/{a}/token-balances", "balances"),
                     (f"/addresses/{a}/transactions", "txs"), (f"/addresses/{a}/token-transfers", "transfers"), (f"/addresses/{a}/internal-transactions", "internal")):
        try:
            j = T.http(T.API + path)
            json.dump(j, open(os.path.join(H, "raw", "accounts", f"{k}_{nm}.json"), "w"))
            if nm == "address":
                d["explorer"] = {x: j.get(x) for x in ("is_contract", "name", "creator_address_hash", "creation_transaction_hash", "implementations", "proxy_type", "has_tokens", "has_token_transfers")}
            if nm == "balances":
                d["tokens"] = [((b.get("token") or {}).get("symbol"), b.get("value")) for b in j] if isinstance(j, list) else j
            if nm == "txs":
                d["recent_txs"] = [(x.get("timestamp"), x.get("method"), (x.get("to") or {}).get("hash")) for x in (j.get("items") or [])[:8]]
            if nm == "contract":
                d["contract_name"], d["verified"] = j.get("name"), j.get("is_verified")
        except Exception as e:
            d[f"{nm}_error"] = str(e)[:80]
    out[k] = d
    lines.append(f"{k} {a}: code {len(d['code']) // 2 - 1} bytes {d['code'][:120]}, nonce {d['nonce']}, USDr {d['usdr_balance']}")
    lines.append(f"    slots {d['slots']}")
    lines.append(f"    explorer {d.get('explorer')} contract {d.get('contract_name')} verified {d.get('verified')}")
    lines.append(f"    tokens {d.get('tokens')}")
    lines.append(f"    recent txs {d.get('recent_txs')}")
json.dump(out, open(os.path.join(H, "data", "accounts.json"), "w"), indent=1)
open(os.path.join(H, "runs", time.strftime("%Y-%m-%dT%H%MZ", time.gmtime()) + "-accounts.txt"), "w").write("\n".join(lines) + "\n")
print("\n".join(lines))
