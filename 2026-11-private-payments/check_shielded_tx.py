#!/usr/bin/env python3
"""What does the public see of an Enygma Public payment? Check any testnet transaction yourself.

Usage:  python3 check_shielded_tx.py 0xTXHASH [0xTXHASH ...]

Read-only, standard library only, no wallet or key. For each transaction on the Rayls
Public Chain testnet (chain ID 7295799) it lists:

  - every address that appears anywhere in it: sender, target, contracts that emitted
    events, address-typed event fields, and both sides of every token transfer;
  - every event, with the vault it came from and the token that vault holds;
  - every token transfer with its amount (a public transfer shows its amount; a
    shielded payment has none).

It writes data/<hash>.json and prints a summary. Run it on a shield, a shielded
payment and an unshield to see the difference described in docs.rayls.com
"Who sees what in Enygma Public".
"""
import json, os, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
API = "https://testnet-explorer.rayls.com/api/v2/"
RPC = "https://testnet-rpc.rayls.com"
UA = {"User-Agent": "rayls-verify", "Content-Type": "application/json"}
# Enygma Public testnet contracts (from transactions submitted by the Enygma relayer)
KNOWN = {
    "0xa5f0c684eb49866a9f62f901cd85f98a19da0ac8": "Enygma relayer (run by Rayls)",
    "0xca11bde05977b3631167028862be2a173976ca11": "Multicall3 (bundles a payment with its gas fee)",
    "0x12b6640048deb2e8ffda4bc10bb2a640b70eca6d": "RlsGasForwarder (ERC-2771, charges gas in RLS)",
    "0x1edb224cf8637f92efadaf47ef9e70c044d75584": "Enygma vault 0 (USDr)",
    "0x97b5d78dbe06d8c8c843f87b5aa2d8587b890795": "Enygma vault 1 (RLS)",
    "0x9c5ad5e5ea5b5910e7fd1e1cc7b70ce0e4bf06c2": "Enygma shared vault 2 (any ERC-20)",
    "0x0000000000000000000000000000000000000400": "USDr token (native gas stablecoin)",
    "0x07e17e17e17e17e17e17e17e17e17e17e17e17ea": "RLS token",
}


def get(path):
    with urllib.request.urlopen(urllib.request.Request(API + path, headers=UA), timeout=40) as r:
        return json.load(r)


def rpc(method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    with urllib.request.urlopen(urllib.request.Request(RPC, data=body, headers=UA), timeout=40) as r:
        return json.load(r)["result"]


def label(a):
    return KNOWN.get(a.lower(), "unlabelled")


def check(tx):
    t = get(f"transactions/{tx}")
    logs = get(f"transactions/{tx}/logs").get("items", [])
    transfers = get(f"transactions/{tx}/token-transfers").get("items", [])
    seen = {t["from"]["hash"].lower(): "sender", (t.get("to") or {}).get("hash", "").lower(): "target"}
    events = []
    for l in logs:
        a = l["address"]["hash"].lower()
        seen.setdefault(a, "emitted events")
        d = l.get("decoded") or {}
        params = {p["name"]: p["value"] for p in d.get("parameters") or []}
        for p in d.get("parameters") or []:
            if p["type"] == "address":
                seen.setdefault(p["value"].lower(), f"field {p['name']}")
        events.append({"contract": label(a), "event": (d.get("method_call") or "?").split("(")[0],
                       "vaultId": params.get("vaultId")})
    moved = []
    for x in transfers:
        for side in ("from", "to"):
            seen.setdefault(x[side]["hash"].lower(), f"token transfer {side}")
        dec = int((x.get("total") or {}).get("decimals") or 18)
        moved.append({"token": x["token"]["symbol"], "from": x["from"]["hash"], "to": x["to"]["hash"],
                      "amount": int(x["total"]["value"]) / 10 ** dec})
    out = {"tx": tx, "time_utc": t["timestamp"], "method": t.get("method"), "status": t.get("status"),
           "gas_fee_usdr": int((t.get("fee") or {}).get("value") or 0) / 1e18,
           "addresses": [{"address": a, "role": r, "label": label(a)} for a, r in seen.items() if a],
           "events": events, "token_transfers": moved}
    os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
    json.dump(out, open(os.path.join(HERE, "data", f"{tx}.json"), "w"), indent=1)
    print(f"\n{tx}\n  {out['time_utc']}  method {out['method']}  status {out['status']}  gas {out['gas_fee_usdr']:.6f} USDr")
    print("  addresses that appear:")
    for a in out["addresses"]:
        print(f"    {a['address']}  {a['role']:<22} {a['label']}")
    kinds = {}
    for e in events:
        k = f"{e['contract']}: {e['event']}"
        kinds[k] = kinds.get(k, 0) + 1
    print("  events:", "; ".join(f"{k} x{v}" for k, v in kinds.items()))
    print("  token transfers:", "none" if not moved else "")
    for m in moved:
        print(f"    {m['amount']:,.6f} {m['token']}  {m['from']} -> {m['to']}")
    users = [a for a in out["addresses"] if a["label"] == "unlabelled"]
    print("  => addresses other than Enygma's own contracts and relayer:", len(users))
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for h in sys.argv[1:]:
        check(h)
