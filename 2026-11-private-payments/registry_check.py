#!/usr/bin/env python3
"""Does every Enygma Public account really give the auditor a copy of its view key?

Usage:  python3 registry_check.py

Read-only, standard library only. Reads the Enygma Public user registry on the Rayls
Public Chain testnet (UserRegistryProxy 0xA473291FFb33e2276F364fAE169f03c4406719e9):

  - register() takes the account's keys plus mlKemAuditCt and aesAuditCt, the view key
    encrypted to the deployment's auditor key (docs.rayls.com, "How Enygma Public works");
  - for every registered account it reads getAuditCiphertexts(account) and checks that
    both ciphertexts are there and that the ML-KEM part has the size of an ML-KEM-768
    ciphertext (1,088 bytes);
  - it reads the size of the auditor public key (an ML-KEM-768 public key is 1,184 bytes)
    and how many auditor accounts the deployment has.

Only counts and sizes are written (data/registry_check.json); no account addresses or
usernames.
"""
import json, os, urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
RPC = "https://testnet-rpc.rayls.com"
REG = "0xa473291ffb33e2276f364fae169f03c4406719e9"
UA = {"User-Agent": "rayls-verify", "Content-Type": "application/json"}
SEL = {"getUserCount": "0xb5cb15f7", "getAllUsers": "0xe2842d79", "getAuditCiphertexts": "0x08438124",
       "getAuditorAccounts": "0xc9edaba7", "auditorPublicKey": "0x91584d49", "registrationFee": "0x14c44e09"}


def rpc(method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    with urllib.request.urlopen(urllib.request.Request(RPC, data=body, headers=UA), timeout=60) as r:
        j = json.load(r)
    if "error" in j:
        raise RuntimeError(j["error"])
    return j["result"]


def call(data):
    return rpc("eth_call", [{"to": REG, "data": data}, "latest"])[2:]


def words(h):
    return [h[i:i + 64] for i in range(0, len(h), 64)]


def address_array(h):
    w = words(h)
    n = int(w[1], 16)
    return ["0x" + x[-40:] for x in w[2:2 + n]]


def bytes_len_at(h, offset_word):
    """Length of a dynamic `bytes` whose offset is stored in word `offset_word`."""
    off = int(words(h)[offset_word], 16) * 2
    return int(h[off:off + 64], 16)


def main():
    block = rpc("eth_getBlockByNumber", ["latest", False])
    users = address_array(call(SEL["getAllUsers"]))
    count = int(call(SEL["getUserCount"]), 16)
    auditors = address_array(call(SEL["getAuditorAccounts"]))
    pk_len = bytes_len_at(call(SEL["auditorPublicKey"]), 0)
    sizes = {}
    missing = 0
    for u in users:
        h = call(SEL["getAuditCiphertexts"] + u[2:].rjust(64, "0"))
        kem, aes = bytes_len_at(h, 0), bytes_len_at(h, 1)
        if kem == 0 or aes == 0:
            missing += 1
        sizes[(kem, aes)] = sizes.get((kem, aes), 0) + 1
    out = {"block": int(block["number"], 16),
           "time_utc": datetime.fromtimestamp(int(block["timestamp"], 16), timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
           "registry": REG, "registered_accounts": count, "accounts_read": len(users),
           "accounts_without_auditor_copy": missing,
           "auditor_copy_sizes_bytes": [{"ml_kem_ct": k, "aes_ct": a, "accounts": n} for (k, a), n in sorted(sizes.items())],
           "auditor_public_key_bytes": pk_len, "auditor_accounts": len(auditors),
           "registration_fee_wei": int(call(SEL["registrationFee"]), 16)}
    os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
    json.dump(out, open(os.path.join(HERE, "data", "registry_check.json"), "w"), indent=1)
    print(f"read at block {out['block']}, {out['time_utc']}")
    print(f"registered accounts: {count} (read {len(users)})")
    print(f"accounts with no auditor copy of their view key: {missing}")
    for s in out["auditor_copy_sizes_bytes"]:
        print(f"  {s['accounts']} accounts: ML-KEM ciphertext {s['ml_kem_ct']} bytes, AES ciphertext {s['aes_ct']} bytes")
    print(f"auditor public key: {pk_len} bytes (ML-KEM-768 public keys are 1,184 bytes); auditor accounts: {len(auditors)}")


if __name__ == "__main__":
    main()
