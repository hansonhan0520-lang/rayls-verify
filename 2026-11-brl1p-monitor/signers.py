#!/usr/bin/env python3
"""Recover which keys signed each DVN verification, and check the Rayls side from the
official RPC alone (no explorer).

Runs after collect.py and dvn.py and reads data/transfers.csv and data/dvn_verifications.csv.
Read-only. Needs pycryptodome for keccak256 (pip install pycryptodome); the secp256k1
signature recovery is written out below so nothing else is needed.

How a DVN verification is authorised (LayerZero-v2, messagelib/contracts/uln/dvn/DVN.sol and
MultiSig.sol): an account holding ADMIN_ROLE calls DVN.execute(ExecuteParam[]). For each param
the contract computes keccak256(abi.encodePacked(vid, target, expiration, callData)), wraps it
as an Ethereum signed message, and requires exactly `quorum` signatures from distinct addresses
in its signer set. Only then does it call target (the receive library) with callData.

Outputs:
  data/dvn_signers.csv   one row per verification: submitting account, recovered signer(s),
                         and whether each recovered signer is in the DVN's current signer set
  data/rayls_inputs.csv  for every Rayls transaction, whether its input data (from the official
                         RPC) carries the GUID or amount and recipient that the table claims
  runs/<time>-signers.txt
"""
import csv, json, os, sys, time
from Crypto.Hash import keccak
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import collect as c

HERE = c.HERE
LOG = []


def log(s=""):
    LOG.append(s)
    print(s, flush=True)


def k256(b):
    h = keccak.new(digest_bits=256)
    h.update(b)
    return h.digest()


# ---- secp256k1 public key recovery (standard ecrecover)
P = 2**256 - 2**32 - 977
N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
G = (0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798,
     0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8)


def add(a, b):
    if a is None:
        return b
    if b is None:
        return a
    if a[0] == b[0] and (a[1] + b[1]) % P == 0:
        return None
    if a == b:
        l = 3 * a[0] * a[0] * pow(2 * a[1], -1, P) % P
    else:
        l = (b[1] - a[1]) * pow(b[0] - a[0], -1, P) % P
    x = (l * l - a[0] - b[0]) % P
    return (x, (l * (a[0] - x) - a[1]) % P)


def mul(k, pt):
    r = None
    while k:
        if k & 1:
            r = add(r, pt)
        pt = add(pt, pt)
        k >>= 1
    return r


def ecrecover(digest, sig):
    r, s, v = int.from_bytes(sig[:32], "big"), int.from_bytes(sig[32:64], "big"), sig[64]
    if v >= 27:
        v -= 27
    x = r
    y = pow((x * x * x + 7) % P, (P + 1) // 4, P)
    if y % 2 != v:
        y = P - y
    z = int.from_bytes(digest, "big")
    ri = pow(r, -1, N)
    q = add(mul(s * ri % N, (x, y)), mul((-z * ri) % N, G))
    pub = q[0].to_bytes(32, "big") + q[1].to_bytes(32, "big")
    return "0x" + k256(pub)[-20:].hex()


# ---- minimal ABI reading for execute((uint32,address,bytes,uint256,bytes)[])
def word(b, i):
    return int.from_bytes(b[i:i + 32], "big")


def dyn_bytes(b, off):
    ln = word(b, off)
    return b[off + 32:off + 32 + ln]


def decode_execute(inp):
    b = bytes.fromhex(inp[10:])
    arr = word(b, 0)
    n = word(b, arr)
    out = []
    for i in range(n):
        t = arr + 32 + word(b, arr + 32 + 32 * i)
        vid = word(b, t)
        target = "0x" + b[t + 32:t + 64][-20:].hex()
        call = dyn_bytes(b, t + word(b, t + 64))
        exp = word(b, t + 96)
        sigs = dyn_bytes(b, t + word(b, t + 128))
        out.append(dict(vid=vid, target=target, callData=call, expiration=exp, signatures=sigs))
    return out


EXECUTE = "0xb143044b"  # execute((uint32,address,bytes,uint256,bytes)[])


def main():
    assert "0x" + k256(b"execute((uint32,address,bytes,uint256,bytes)[])")[:4].hex() == EXECUTE
    stamp = time.strftime("%Y-%m-%dT%H%MZ", time.gmtime())
    ver = list(csv.DictReader(open(os.path.join(HERE, "data", "dvn_verifications.csv"))))
    rows = list(csv.DictReader(open(os.path.join(HERE, "data", "transfers.csv"))))
    contracts = json.load(open(os.path.join(HERE, "data", "dvn_contracts.json")))
    p_url = c.POLY["tenderly"][0]
    log(f"Signer recovery, run {c.utc(time.time())}: {len(ver)} verifications")
    out = []
    for v in ver:
        chain = "rayls" if v["direction"] == "P->R" else "polygon"
        url = c.RAYLS_RPC if chain == "rayls" else p_url
        tx = c.rpc(url, "eth_getTransactionByHash", [v["verify_tx"]])
        row = {"direction": v["direction"], "nonce": v["nonce"], "dvn": v["dvn"], "dvn_name": v["dvn_registry_name_now"],
               "verify_time": v["verify_time"], "verify_tx": v["verify_tx"], "submitted_by": tx["from"].lower(),
               "tx_to": (tx["to"] or "").lower()}
        signers, note = [], ""
        if tx["input"][:10] == EXECUTE and row["tx_to"] == v["dvn"]:
            for prm in decode_execute(tx["input"]):
                if v["payload_hash"][2:] not in prm["callData"].hex():
                    continue
                h = k256(prm["vid"].to_bytes(4, "big") + bytes.fromhex(prm["target"][2:]) +
                         prm["expiration"].to_bytes(32, "big") + prm["callData"])
                digest = k256(b"\x19Ethereum Signed Message:\n32" + h)
                sg = prm["signatures"]
                signers = [ecrecover(digest, sg[i:i + 65]) for i in range(0, len(sg), 65)]
                row["vid"] = prm["vid"]
        else:
            note = f"input {tx['input'][:10]} to {row['tx_to']}: not a direct DVN.execute call"
        cur = contracts.get(f"{chain}:{v['dvn']}", {}).get("signers", [])
        row["recovered_signers"] = " ".join(signers)
        row["signers_in_current_set"] = " ".join(str(s in [x.lower() for x in cur]) for s in signers)
        row["note"] = note
        out.append(row)
    with open(os.path.join(HERE, "data", "dvn_signers.csv"), "w", newline="") as f:
        cw = csv.DictWriter(f, fieldnames=["direction", "nonce", "dvn", "dvn_name", "verify_time", "verify_tx", "submitted_by",
                                           "tx_to", "vid", "recovered_signers", "signers_in_current_set", "note"])
        cw.writeheader()
        cw.writerows(out)
    log(f"recovered signers for {sum(1 for o in out if o['recovered_signers'])} of {len(out)} verifications")
    for dvn in sorted(set(o["dvn"] for o in out)):
        mine = sorted([o for o in out if o["dvn"] == dvn], key=lambda o: o["verify_time"])
        log(f"\n{dvn} {mine[0]['dvn_name']}  ({len(mine)} verifications)")
        log(f"   submitted by: {sorted(set(o['submitted_by'] for o in mine))}")
        seen = {}
        for o in mine:
            seen.setdefault(o["recovered_signers"], []).append(o["verify_time"])
        for s, ts in seen.items():
            log(f"   signed by {s or '(none recovered)'}: {len(ts)} times, {ts[0]} to {ts[-1]}")
        notes = sorted(set(o["note"] for o in mine if o["note"]))
        if notes:
            log(f"   notes: {notes}")

    # ---- the Rayls side from the official RPC only: does each transaction's input carry what the table says?
    res = []
    for r in rows:
        tx_hash = r["dst_tx"] if r["direction"] == "P->R" else r["src_tx"]
        tx = c.rpc(c.RAYLS_RPC, "eth_getTransactionByHash", [tx_hash])
        inp = tx["input"].lower()
        amount = int(round(float(r["amount_locked_or_burned"].replace(",", "")) * 10**6))   # shared decimals 6
        user = r["user"].lower()[2:]
        o = {"direction": r["direction"], "nonce": r["nonce"], "rayls_tx": tx_hash, "from": tx["from"].lower(), "to": (tx["to"] or "").lower()}
        if r["direction"] == "P->R":
            # LayerZero OFT message = bytes32 sendTo ++ uint64 amountSD, carried in the executor's lzReceive call
            o["input_has_guid"] = r["guid"][2:].lower() in inp
            o["input_has_recipient_and_amount"] = (user.rjust(64, "0") + format(amount, "016x")) in inp
        else:
            # adapter.send(SendParam{dstEid, to, amountLD, minAmountLD, ...}, ...)
            o["input_has_guid"] = "n/a (guid is assigned by the endpoint)"
            o["input_has_recipient_and_amount"] = (user.rjust(64, "0") + format(amount * 10**12, "064x")) in inp
        res.append(o)
    with open(os.path.join(HERE, "data", "rayls_inputs.csv"), "w", newline="") as f:
        cw = csv.DictWriter(f, fieldnames=list(res[0].keys()))
        cw.writeheader()
        cw.writerows(res)
    pr = [o for o in res if o["direction"] == "P->R"]
    rp = [o for o in res if o["direction"] == "R->P"]
    log(f"\nOfficial Rayls RPC, transaction input only:")
    log(f"   Polygon->Rayls deliveries carrying the GUID: {sum(o['input_has_guid'] is True for o in pr)} of {len(pr)}; "
        f"carrying recipient and amount: {sum(o['input_has_recipient_and_amount'] for o in pr)} of {len(pr)}")
    log(f"   Rayls->Polygon sends carrying recipient and amount: {sum(o['input_has_recipient_and_amount'] for o in rp)} of {len(rp)}")
    log(f"   delivery transactions sent from: {sorted(set(o['from'] for o in pr))} to {sorted(set(o['to'] for o in pr))}")
    log(f"\nfinished {c.utc(time.time())}")
    open(os.path.join(HERE, "runs", f"{stamp}-signers.txt"), "w").write("\n".join(LOG) + "\n")


if __name__ == "__main__":
    main()
