#!/usr/bin/env python3
"""Simulate, with eth_call only, what the accounts that control RLS on Rayls can do to the
lock's balance and to supply. Nothing is signed or sent; each call runs against current state
and is discarded. Output: data/powers.json, runs/<time>-powers.txt"""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import roles as R

HERE = R.HERE
MINTER = "0xe4854d190146cdfe82040b495aba43872a17f609"    # ElevatedMinterBurner, holds MINTER on Rayls RLS
EOA = "0x0e301beef8daad28f8e38d9fce09112b78fe3161"       # holds every role on Rayls RLS directly
LOCK, RLS, RAYLS = R.LOCK, R.RLS, R.RAYLS
DEPLOYER_ETH = "0x29cc7737bd81c2db11d410bf9b457f8f7b351d12"
SAFE_ETH = "0x60f0e09e51704ea6e472f877f849269eede76309"
ONE = format(10**18, "064x")
BEEF = "0x000000000000000000000000000000000000beef"
w = R.w
out, lines = {"run_utc": R.utc(time.time())}, []
def note(k, v):
    out[k] = v; lines.append(f"{k}: {v}"); print(f"{k}: {v}", flush=True)
res = lambda r: "succeeds" if r.startswith("0x") else r[:160]

# ElevatedMinterBurner: owner and operators
owner = R.addr(R.call(RAYLS, MINTER, "0x8da5cb5b"))
note("minter_owner", owner)
note("minter_owner_kind", R.kind(RAYLS, owner) if owner.startswith("0x") and len(owner) == 42 else "?")
logs = R.explorer_logs(MINTER)
ops = {}
for l in logs:
    if l["topics"][0] == "0x1a594081ae893ab78e67d9b9e843547318164322d32c65369d78a96172d9dc8f":
        ops["0x" + l["topics"][1][-40:]] = int(l["data"][2:66], 16) == 1
note("minter_operator_events", ops)
note("minter_operators_now", {a: R.call(RAYLS, MINTER, "0x13e7c9d8" + w(a)) == "0x" + "0" * 63 + "1" for a in sorted(set(ops) | {R.ADAPTER_RAYLS})})

# what each control path can do (simulated)
note("eoa_burnFrom_lock_1_RLS", res(R.call(RAYLS, RLS, "0x79cc6790" + w(LOCK) + ONE, EOA)))
note("eoa_mint_1_RLS_to_test_address", res(R.call(RAYLS, RLS, "0x40c10f19" + w(BEEF) + ONE, EOA)))
note("eoa_upgradeToAndCall_same_implementation", res(R.call(RAYLS, RLS, "0x4f1ef286" + w("0x07e17e17e17e17e17e17e17e17e17e17e17e17eb") + format(64, "064x") + "0" * 64, EOA)))
note("minter_owner_burn_lock_1_RLS_via_minter", res(R.call(RAYLS, MINTER, "0x9dc29fac" + w(LOCK) + ONE, owner)))
note("minter_owner_mint_1_RLS_via_minter", res(R.call(RAYLS, MINTER, "0x40c10f19" + w(BEEF) + ONE, owner)))
note("stranger_burn_lock_via_minter", res(R.call(RAYLS, MINTER, "0x9dc29fac" + w(LOCK) + ONE, BEEF)))
note("lock_admin_claim_now", res(R.call(RAYLS, LOCK, "0x4e71d92d", EOA)))

# Ethereum hub token: who holds its roles among known accounts
ETH = R.ETH["publicnode"]
R.kind(ETH, SAFE_ETH)
cands = [DEPLOYER_ETH, SAFE_ETH, EOA, "0x633ac5e2315b973417e8caa6b3ad2162e0461ce1", R.ADAPTER_ETH] + R.OWNERS_OF.get(SAFE_ETH, [])
ehold = {}
for r, h in R.ROLES.items():
    if r == "BURNER":
        continue
    ehold[r] = [a for a in cands if R.call(ETH, R.RLS_ETH, "0x91d14854" + h[2:] + w(a)) == "0x" + "0" * 63 + "1"]
note("eth_rls_role_holders_among_known", ehold)
note("eth_rls_implementation_slot_via_1967", R.addr(R.rpc(ETH, "eth_getStorageAt", [R.RLS_ETH, R.SLOT_IMPL, "latest"])))
json.dump(out, open(os.path.join(HERE, "data", "powers.json"), "w"), indent=1)
open(os.path.join(HERE, "runs", time.strftime("%Y-%m-%dT%H%MZ", time.gmtime()) + "-powers.txt"), "w").write("\n".join(lines) + "\n")
