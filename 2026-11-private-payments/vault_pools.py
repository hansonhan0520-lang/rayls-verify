#!/usr/bin/env python3
"""What the public can see of the Enygma Public vaults as a whole, on the Rayls Public Chain testnet.

Usage:  python3 vault_pools.py

Read-only, standard library only. For each Enygma Public vault it reads which token the
vault holds (getAssetContractAddress, 0x0 for the shared vault) and how much of each known
token sits in it. The public sees the size of each pool; it does not see who owns which
part of it. Writes data/vault_pools.json.
"""
import json, os, time, urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
RPC = "https://testnet-rpc.rayls.com"
UA = {"User-Agent": "rayls-verify", "Content-Type": "application/json"}
VAULTS = {"vault 0": "0x1edb224cf8637f92efadaf47ef9e70c044d75584",
          "vault 1": "0x97b5d78dbe06d8c8c843f87b5aa2d8587b890795",
          "shared vault 2": "0x9c5ad5e5ea5b5910e7fd1e1cc7b70ce0e4bf06c2"}
TOKENS = {"USDr": "0x0000000000000000000000000000000000000400",
          "RLS": "0x07e17e17e17e17e17e17e17e17e17e17e17e17ea"}


def call(to, data):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_call",
                       "params": [{"to": to, "data": data}, "latest"]}).encode()
    with urllib.request.urlopen(urllib.request.Request(RPC, data=body, headers=UA), timeout=40) as r:
        return json.load(r)["result"]


def main():
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_getBlockByNumber", "params": ["latest", False]}).encode()
    with urllib.request.urlopen(urllib.request.Request(RPC, data=body, headers=UA), timeout=40) as r:
        b = json.load(r)["result"]
    out = {"block": int(b["number"], 16),
           "time_utc": datetime.fromtimestamp(int(b["timestamp"], 16), timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
           "vaults": {}}
    for name, v in VAULTS.items():
        asset = "0x" + call(v, "0x32c9b183")[-40:]
        held = {t: int(call(a, "0x70a08231" + v[2:].rjust(64, "0")), 16) / 1e18 for t, a in TOKENS.items()}
        out["vaults"][name] = {"address": v, "asset": asset, "holds": held}
        print(f"{name:15s} {v}  asset {asset}  holds " + ", ".join(f"{x:,.2f} {t}" for t, x in held.items()))
    print(f"read at block {out['block']}, {out['time_utc']}")
    os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
    json.dump(out, open(os.path.join(HERE, "data", "vault_pools.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
