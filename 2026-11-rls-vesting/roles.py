#!/usr/bin/env python3
"""Who can act on the RLS the lock holds, from outside the lock.

The lock contract cannot pay out early. But the tokens it holds are RLS on Rayls, an
upgradeable token (OpenZeppelin UUPS) with roles: DEFAULT_ADMIN, UPGRADER, MINTER, BURNER,
PAUSER. In its source, `burnFrom` lets a MINTER or BURNER burn any account's balance without
an allowance. This script lists every role grant and revoke, checks who holds each role now,
simulates a 1 RLS `burnFrom` on the lock's balance from each role holder, and reads the
LayerZero bridge both ways (Rayls adapter, Ethereum adapter, the RLS locked on Ethereum).

Read-only; simulations use eth_call. Output: data/roles_state.json, data/rls_roles.csv,
raw/roles/, runs/<time>-roles.txt
"""
import csv, json, os, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
RAYLS = "https://mainnet-rpc.rayls.com"
ETH = {"publicnode": "https://ethereum-rpc.publicnode.com", "tenderly": "https://mainnet.gateway.tenderly.co"}
API = "https://explorer.rayls.com/api/v2"
RLS = "0x07e17e17e17e17e17e17e17e17e17e17e17e17ea"
RLS_ETH = "0xb5f7b021a78f470d31d762c1dda05ea549904fbd"
LOCK = "0x1463889d3a5eaaee3f066d1cf438a8957f7db98e"
ADAPTER_RAYLS = "0x3147be1cd913fe9ea5df7505ffe704a8313b20b0"   # LayerZero receiver of the 5 August mints
ADAPTER_ETH = "0x3ea6bac7d4138bcc126d0f17ae10122b3620aba6"     # LayerZero sender of the 5 August mints
EID_ETH, EID_RAYLS = 30101, 30415
ROLES = {"DEFAULT_ADMIN": "0x" + "0" * 64,
         "UPGRADER": "0x189ab7a9244df0848122154315af71fe140f3db0fe014031783b0946b8c9d2e3",
         "MINTER": "0x9f2df0fed2c77648de5860a4cc508cd0818c85b8b8a1ab4ceeef8d981c8956a6",
         "BURNER": "0x3c11d16cbaffd01df69ce1c404f6340ee057498f5f00246190ea54220576a848",
         "PAUSER": "0x65d7a28e3265b37a6474929f336521b332c1681b933f6cb9f3376673440d862a"}
RNAME = {v: k for k, v in ROLES.items()}
T_GRANT = "0x2f8788117e7eff1d82e926ec794901d17c78024a50270940304540a733656f0d"
T_REVOKE = "0xf6391f5c32d9c69d2a47ea670b442974b53935d1edc7fd64eb21e047a839171b"
T_UPGRADED = "0xbc7cd75a20ee27fd9adebab32041f755214dbc6bffa90cc0225b39da2e5c2d3b"
SLOT_IMPL = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
UA = {"User-Agent": "rayls-verify-monitor", "Content-Type": "application/json"}
LOG = []
OWNERS_OF = {}
EXTRA = ["0x0e301beef8daad28f8e38d9fce09112b78fe3161", "0x8699069568402ce9b9a08a425db157202ca4b4c5", "0x6b205d256e8a153cba8057e5655db56e0e47a511",
         "0xd5ad7b125796870ac729e644cd43646ccf716a3e", "0x5dd644b83afc71ac224aca6aa7c03b1adfe8d44d", "0xd04004a3715f8428674a01ffde2069c181d4b0fd",
         "0x633ac5e2315b973417e8caa6b3ad2162e0461ce1", "0xab5309be3d6e228288da1f68df3f993a550dec7c", "0xe4854d190146cdfe82040b495aba43872a17f609",
         "0x3147be1cd913fe9ea5df7505ffe704a8313b20b0", "0x60f0e09e51704ea6e472f877f849269eede76309"]


def log(s=""):
    LOG.append(s)
    print(s, flush=True)


def utc(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def http(url, body=None, tries=6):
    data = json.dumps(body).encode() if body is not None else None
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=UA), timeout=40) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and i < tries - 1:
                time.sleep(1.5 * 2 ** i)
                continue
            raise RuntimeError(f"HTTP {e.code} {url[:90]}")
        except Exception:
            if i < tries - 1:
                time.sleep(2)
                continue
            raise


def rpc(url, method, params):
    j = http(url, {"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
    if "error" in j:
        e = j["error"]
        d = e.get("data") or ""
        raise RuntimeError(f"{e.get('message', '')} {d if isinstance(d, str) else json.dumps(d)}"[:200])
    return j["result"]


def call(url, to, data, frm=None):
    tx = {"to": to, "data": data}
    if frm:
        tx["from"] = frm
    try:
        return rpc(url, "eth_call", [tx, "latest"])
    except Exception as e:
        return "REVERT " + str(e)[:150]


w = lambda a: a.lower().replace("0x", "").rjust(64, "0")
u32 = lambda n: format(n, "064x")
addr = lambda h: ("0x" + h[-40:]) if isinstance(h, str) and h.startswith("0x") and len(h) >= 42 else h
rls = lambda wei: f"{wei / 10**18:,.6f}"


def kind(url, a):
    code = rpc(url, "eth_getCode", [a, "latest"])
    if code == "0x":
        n = int(rpc(url, "eth_getTransactionCount", [a, "latest"]), 16)
        return f"plain account ({n} txs sent)"
    th = call(url, a, "0xe75235b8")
    if th.startswith("0x") and len(th) == 66:
        ow = call(url, a, "0xa0e67e2b")
        cnt = int(ow[66:130], 16) if ow.startswith("0x") else "?"
        owners = ["0x" + ow[130 + 64 * i:194 + 64 * i][-40:] for i in range(cnt)] if isinstance(cnt, int) else []
        OWNERS_OF[a] = owners
        return f"Safe multisig, {int(th, 16)} of {cnt}"
    return f"contract ({(len(code) - 2) // 2} bytes)"


def decode_uln(h):
    if not isinstance(h, str) or not h.startswith("0x") or len(h) < 2 + 64 * 9:
        return h
    t = [h[2 + i:66 + i] for i in range(0, len(h) - 2, 64)][3:]
    rs, os_ = int(t[4], 16) // 32, int(t[5], 16) // 32
    return {"confirmations": int(t[0], 16), "required": int(t[1], 16), "optional": int(t[2], 16),
            "dvns": ["0x" + t[rs + 1 + i][-40:] for i in range(int(t[rs], 16))]}


def oapp(url, a, eid, label):
    v = {"address": a, "owner": addr(call(url, a, "0x8da5cb5b")), "endpoint": addr(call(url, a, "0x5e280f11")),
         "token": addr(call(url, a, "0xfc0c546a")), "peer": addr(call(url, a, "0xbb0b6a53" + u32(eid)))}
    if isinstance(v["owner"], str) and v["owner"].startswith("0x") and len(v["owner"]) == 42:
        v["owner_kind"] = kind(url, v["owner"])
    ep = v["endpoint"] if isinstance(v["endpoint"], str) and len(v["endpoint"]) == 42 else None
    if ep:
        v["delegate"] = addr(call(url, ep, "0x587cde1e" + w(a)))
        rl = call(url, ep, "0x402f8468" + w(a) + u32(eid))
        sl = call(url, ep, "0xb96a277f" + w(a) + u32(eid))
        if rl.startswith("0x"):
            v["receive_uln"] = decode_uln(call(url, ep, "0x2b3197b9" + w(a) + w(addr(rl[:66])) + u32(eid) + u32(2)))
        if sl.startswith("0x"):
            v["send_uln"] = decode_uln(call(url, ep, "0x2b3197b9" + w(a) + w(addr(sl)) + u32(eid) + u32(2)))
    log(f"    {label}: " + json.dumps(v))
    return v


def explorer_logs(a):
    out, nxt, pages = [], None, 0
    while True:
        q = ("?" + urllib.parse.urlencode(nxt)) if nxt else ""
        j = http(f"{API}/addresses/{a}/logs{q}")
        out += j.get("items", [])
        nxt = j.get("next_page_params")
        pages += 1
        if not nxt or pages > 300:
            return out


def main():
    stamp = time.strftime("%Y-%m-%dT%H%MZ", time.gmtime())
    for d in ("data", "raw/roles", "runs"):
        os.makedirs(os.path.join(HERE, d), exist_ok=True)
    S = {"run_utc": utc(time.time())}
    log(f"RLS roles and bridge, run {S['run_utc']}")

    # ---- every role change on Rayls RLS, from the proxy's own logs
    logs = explorer_logs(RLS)
    json.dump([l for l in logs if l["topics"][0] in (T_GRANT, T_REVOKE, T_UPGRADED)], open(os.path.join(HERE, "raw", "roles", "rls_role_logs.json"), "w"))
    changes, people = [], set()
    for l in logs:
        t0 = l["topics"][0]
        if t0 in (T_GRANT, T_REVOKE):
            acct = "0x" + l["topics"][2][-40:]
            people.add(acct)
            people.add("0x" + l["topics"][3][-40:])
            changes.append({"block": l["block_number"], "tx": l["transaction_hash"], "event": "RoleGranted" if t0 == T_GRANT else "RoleRevoked",
                            "role": RNAME.get(l["topics"][1], l["topics"][1]), "account": acct, "by": "0x" + l["topics"][3][-40:]})
        elif t0 == T_UPGRADED:
            changes.append({"block": l["block_number"], "tx": l["transaction_hash"], "event": "Upgraded", "role": "",
                            "account": "0x" + l["topics"][1][-40:], "by": ""})
    for c in changes:
        c["time"] = utc(int(rpc(RAYLS, "eth_getBlockByNumber", [hex(c["block"]), False])["timestamp"], 16))
    changes.sort(key=lambda c: c["block"])
    with open(os.path.join(HERE, "data", "rls_roles.csv"), "w", newline="") as f:
        cw = csv.DictWriter(f, fieldnames=["time", "block", "event", "role", "account", "by", "tx"])
        cw.writeheader()
        cw.writerows(changes)
    log(f"\n[1] Rayls RLS: {len(logs)} logs scanned, {len(changes)} role/upgrade events")
    for c in changes:
        log(f"    {c['time']} {c['event']:11s} {c['role']:13s} {c['account']} by {c['by']}")
    people |= set(EXTRA)
    holders = {}
    for r, h in ROLES.items():
        holders[r] = [a for a in sorted(people) if call(RAYLS, RLS, "0x91d14854" + h[2:] + w(a)) == "0x" + "0" * 63 + "1"]
    S["rayls_role_holders"] = holders
    S["rayls_role_holder_kinds"] = {a: kind(RAYLS, a) for a in sorted(set(sum(holders.values(), [])))}
    S["rayls_rls_implementation"] = addr(rpc(RAYLS, "eth_getStorageAt", [RLS, SLOT_IMPL, "latest"]))
    S["rayls_rls_paused"] = call(RAYLS, RLS, "0x5c975abb")
    S["rayls_rls_bridge_paused"] = call(RAYLS, RLS, "0x6ccf20d5")
    log(f"    holders now: {json.dumps(holders)}")
    for a, k in S["rayls_role_holder_kinds"].items():
        log(f"    {a}: {k}")
    log(f"    implementation {S['rayls_rls_implementation']}")

    # ---- can a role holder burn the lock's RLS? simulate burnFrom(lock, 1 RLS)
    S["burnFrom_simulations"] = {}
    log("\n[2] Simulated burnFrom(lock, 1 RLS), eth_call only")
    for a in sorted(set(holders["MINTER"] + holders["BURNER"] + holders["DEFAULT_ADMIN"])) + ["0x000000000000000000000000000000000000beef"]:
        r = call(RAYLS, RLS, "0x79cc6790" + w(LOCK) + format(10**18, "064x"), a)
        S["burnFrom_simulations"][a] = "succeeds" if r.startswith("0x") else r
        log(f"    from {a}: {S['burnFrom_simulations'][a]}")

    # ---- the bridge: Rayls adapter, Ethereum adapter, RLS locked on Ethereum
    log("\n[3] LayerZero bridge for RLS")
    S["rayls_adapter"] = oapp(RAYLS, ADAPTER_RAYLS, EID_ETH, "Rayls adapter")
    S["eth_adapter"] = oapp(ETH["publicnode"], ADAPTER_ETH, EID_RAYLS, "Ethereum adapter")
    S["eth_locked_in_adapter"] = {n: rls(int(call(u, RLS_ETH, "0x70a08231" + w(ADAPTER_ETH)), 16)) for n, u in ETH.items()}
    S["eth_rls_total_supply"] = {n: rls(int(call(u, RLS_ETH, "0x18160ddd"), 16)) for n, u in ETH.items()}
    S["eth_rls_implementation_slot"] = addr(rpc(ETH["publicnode"], "eth_getStorageAt", [RLS_ETH, SLOT_IMPL, "latest"]))
    S["rayls_rls_supply"] = rls(int(call(RAYLS, RLS, "0x18160ddd"), 16))
    bsc = call("https://bsc-rpc.publicnode.com", "0x17ea10b6ae4fde59fdbf471bd28ab9710f508816", "0x18160ddd")
    S["bsc_rls_supply"] = rls(int(bsc, 16)) if bsc.startswith("0x") else bsc
    try:
        f = lambda x: float(x.replace(",", ""))
        S["hub_locked_minus_rayls_and_bsc"] = f"{f(S['eth_locked_in_adapter']['publicnode']) - f(S['rayls_rls_supply']) - f(S['bsc_rls_supply']):,.6f}"
    except Exception as e:
        S["hub_locked_minus_rayls_and_bsc"] = str(e)[:80]
    log(f"    RLS on BSC {S['bsc_rls_supply']}; Ethereum adapter locked minus (Rayls + BSC supply): {S['hub_locked_minus_rayls_and_bsc']}")
    eh = {}
    for r, h in ROLES.items():
        cands = sorted(set(sum(holders.values(), [])) | {ADAPTER_ETH})
        eh[r] = [a for a in cands if call(ETH["publicnode"], RLS_ETH, "0x91d14854" + h[2:] + w(a)) == "0x" + "0" * 63 + "1"]
    S["eth_role_holders_among_rayls_holders"] = eh
    log(f"    RLS locked in the Ethereum adapter: {S['eth_locked_in_adapter']}; RLS supply on Rayls {S['rayls_rls_supply']}")
    log(f"    Ethereum RLS total supply {S['eth_rls_total_supply']}, implementation slot {S['eth_rls_implementation_slot']}")
    log(f"    Ethereum RLS roles held by the same accounts: {json.dumps(eh)}")
    S["safe_owners"] = OWNERS_OF
    log(f"    Safe owners: {json.dumps(OWNERS_OF)}")
    # the MINTER contract on Rayls: its code and verified source, if any
    m = holders["MINTER"]
    for a in m:
        try:
            json.dump(http(f"{API}/smart-contracts/{a}"), open(os.path.join(HERE, "raw", "roles", f"minter_{a[:10]}.json"), "w"))
        except Exception as e:
            log(f"    source of {a}: {str(e)[:80]}")
        json.dump(http(f"{API}/addresses/{a}"), open(os.path.join(HERE, "raw", "roles", f"minter_{a[:10]}_address.json"), "w"))
        open(os.path.join(HERE, "raw", "roles", f"minter_{a[:10]}_code.hex"), "w").write(rpc(RAYLS, "eth_getCode", [a, "latest"]))
    # Ethereum-side token and adapter source, from Sourcify if it has them
    for a, nm in ((RLS_ETH, "eth_rls"), (ADAPTER_ETH, "eth_adapter")):
        for u in (f"https://sourcify.dev/server/v2/contract/1/{a}?fields=all", f"https://sourcify.dev/server/files/any/1/{a}"):
            try:
                json.dump(http(u), open(os.path.join(HERE, "raw", "roles", f"sourcify_{nm}.json"), "w"))
                log(f"    sourcify {nm}: saved")
                break
            except Exception as e:
                log(f"    sourcify {nm}: {str(e)[:60]}")
        open(os.path.join(HERE, "raw", "roles", f"{nm}_code.hex"), "w").write(rpc(ETH["publicnode"], "eth_getCode", [a, "latest"]))
    json.dump(S, open(os.path.join(HERE, "data", "roles_state.json"), "w"), indent=1)
    log(f"\nfinished {utc(time.time())}")
    open(os.path.join(HERE, "runs", f"{stamp}-roles.txt"), "w").write("\n".join(LOG) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        LOG.append(traceback.format_exc())
        os.makedirs(os.path.join(HERE, "runs"), exist_ok=True)
        open(os.path.join(HERE, "runs", time.strftime("%Y-%m-%dT%H%MZ", time.gmtime()) + "-roles-FAILED.txt"), "w").write("\n".join(LOG) + "\n")
        raise
