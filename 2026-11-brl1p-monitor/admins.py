#!/usr/bin/env python3
"""Who holds ADMIN_ROLE on the six DVN contracts BRL1.p requires, and are those accounts contracts?
Read-only current-state reads. Output: data/dvn_admins.json and runs/<time>-admins.txt"""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import collect as c
ADMIN_ROLE = "a49807205ce4d355092ef5a8a18f56e8913cf4a201fbe287825b095693c21775"
SUSPECTS = ["0xb8ff877ed78ba520ece21b1de7843a8a57ca47cb", "0xb52fa54fc261398058c3ac7b8dd442d7d8b9f0b6"]
DVNS = {"rayls": ["0x396dc0a78f789586e2982fccd830c5954c193f3c", "0x8d77d35604a9f37f488e41d1d916b2a0088f82dd", "0xd01ae6905d48315f7be10c7330aecf8360ef5b12"],
        "polygon": ["0x23de2fe932d9043291f870324b74f820e11dc81a", "0x31f748a368a893bdb5abb67ec95f232507601a73", "0x13feb7234ff60a97af04477d6421415766753ba3"]}
URL = {"rayls": c.RAYLS_RPC, "polygon": c.POLY["tenderly"][0]}
out, lines = {}, [f"DVN admin check, run {c.utc(time.time())}"]
for chain, addrs in DVNS.items():
    for a in addrs:
        d = {}
        for s in SUSPECTS:
            d[s] = int(c.call(URL[chain], a, "0x91d14854" + ADMIN_ROLE + c.w(s)), 16) == 1
        try:
            d["signers_by_isSigner_check"] = "n/a"
        except Exception:
            pass
        out[f"{chain}:{a}"] = d
        lines.append(f"{chain:7s} {a} ADMIN_ROLE: " + ", ".join(f"{s[:10]} {v}" for s, v in d.items() if s.startswith("0x")))
for chain in URL:
    for s in SUSPECTS:
        code = c.rpc(URL[chain], "eth_getCode", [s, "latest"])
        nonce = int(c.rpc(URL[chain], "eth_getTransactionCount", [s, "latest"]), 16)
        out[f"{chain}:{s}:code"] = code[:20]
        out[f"{chain}:{s}:nonce"] = nonce
        lines.append(f"{chain:7s} {s} code {'none (plain account)' if code == '0x' else code[:20] + '...'}  transactions sent {nonce}")
json.dump(out, open(os.path.join(c.HERE, "data", "dvn_admins.json"), "w"), indent=1)
open(os.path.join(c.HERE, "runs", time.strftime("%Y-%m-%dT%H%MZ", time.gmtime()) + "-admins.txt"), "w").write("\n".join(lines) + "\n")
print("\n".join(lines))
