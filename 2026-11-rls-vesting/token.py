#!/usr/bin/env python3
"""What the lock's RLS actually is: the RLS token on Rayls, how it got there, and what backs it.

The lock holds RLS on the Rayls Public Chain. That RLS is a LayerZero bridged token: it is
minted on Rayls when RLS is locked on Ethereum (the hub). So the lock is only as strong as
(a) the RLS contract on Rayls, which is a proxy, and (b) the bridge and the Ethereum-side lock.

Read-only, standard library only. Output: data/token_state.json, raw/token/, runs/<time>-token.txt
"""
import json, os, time, urllib.error, urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
RAYLS = "https://mainnet-rpc.rayls.com"
ETH = {"publicnode": "https://ethereum-rpc.publicnode.com", "tenderly": "https://mainnet.gateway.tenderly.co"}
BSC = "https://bsc-rpc.publicnode.com"
API = "https://explorer.rayls.com/api/v2"
LZ = "https://scan.layerzero-api.com/v1"
RLS_RAYLS = "0x07e17e17e17e17e17e17e17e17e17e17e17e17ea"
RLS_ETH = "0xb5f7b021a78f470d31d762c1dda05ea549904fbd"
RLS_BSC = "0x17ea10b6ae4fde59fdbf471bd28ab9710f508816"
EP = "0x1a44076050125825900e736c501f859c50fe728c"
EID = {"ethereum": 30101, "bsc": 30102, "rayls": 30415}
FUNDER = "0xab5309be3d6e228288da1f68df3f993a550dec7c"
MINT_TXS = ["0xd8c91988d1", "0x3192c84a78", "0x98810cd5d3"]  # prefixes, resolved from the funder's transfers
SLOT_IMPL = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
SLOT_ADMIN = "0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103"
UA = {"User-Agent": "rayls-verify-monitor", "Content-Type": "application/json"}
LOG = []


def log(s=""):
    LOG.append(s)
    print(s, flush=True)


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
            raise RuntimeError(f"HTTP {e.code} {url}")
        except Exception:
            if i < tries - 1:
                time.sleep(2)
                continue
            raise


def rpc(url, method, params):
    j = http(url, {"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
    if "error" in j:
        raise RuntimeError(str(j["error"])[:160])
    return j["result"]


def call(url, to, data):
    try:
        return rpc(url, "eth_call", [{"to": to, "data": data}, "latest"])
    except Exception as e:
        return "ERR " + str(e)[:100]


w = lambda a: a.lower().replace("0x", "").rjust(64, "0")
u32 = lambda n: format(n, "064x")
addr = lambda h: "0x" + h[-40:] if isinstance(h, str) and h.startswith("0x") else h
num = lambda h: int(h, 16) if isinstance(h, str) and h.startswith("0x") and len(h) > 2 else h
rls = lambda wei: f"{wei / 10**18:,.6f}" if isinstance(wei, int) else wei


def decode_uln(h):
    if not isinstance(h, str) or not h.startswith("0x"):
        return h
    t = [h[2 + i:66 + i] for i in range(0, len(h) - 2, 64)][3:]
    rs, os_ = int(t[4], 16) // 32, int(t[5], 16) // 32
    return {"confirmations": int(t[0], 16), "required": int(t[1], 16), "optional": int(t[2], 16), "threshold": int(t[3], 16),
            "dvns": ["0x" + t[rs + 1 + i][-40:] for i in range(int(t[rs], 16))],
            "optional_dvns": ["0x" + t[os_ + 1 + i][-40:] for i in range(int(t[os_], 16))]}


def oapp_view(url, oapp, remote_eids, label):
    v = {"owner": addr(call(url, oapp, "0x8da5cb5b")), "endpoint": addr(call(url, oapp, "0x5e280f11"))}
    v["delegate"] = addr(call(url, EP, "0x587cde1e" + w(oapp)))
    code = rpc(url, "eth_getCode", [v["owner"], "latest"]) if v["owner"].startswith("0x") and len(v["owner"]) == 42 else "?"
    v["owner_kind"] = "plain account" if code == "0x" else ("contract" if code != "?" else "?")
    if v["owner_kind"] == "contract":
        th = call(url, v["owner"], "0xe75235b8")
        if th.startswith("0x"):
            ow = call(url, v["owner"], "0xa0e67e2b")
            v["owner_kind"] = f"Safe-style multisig, threshold {num(th)} of {int(ow[130:194], 16) if ow.startswith('0x') else '?'}"
    v["implementation"] = addr(rpc(url, "eth_getStorageAt", [oapp, SLOT_IMPL, "latest"]))
    v["proxy_admin_slot"] = addr(rpc(url, "eth_getStorageAt", [oapp, SLOT_ADMIN, "latest"]))
    for name, eid in remote_eids.items():
        p = call(url, oapp, "0xbb0b6a53" + u32(eid))
        v[f"peer_{name}"] = addr(p) if isinstance(p, str) and p.startswith("0x") and int(p, 16) else "none"
        rl = call(url, EP, "0x402f8468" + w(oapp) + u32(eid))
        sl = call(url, EP, "0xb96a277f" + w(oapp) + u32(eid))
        if isinstance(rl, str) and rl.startswith("0x"):
            v[f"receive_from_{name}"] = decode_uln(call(url, EP, "0x2b3197b9" + w(oapp) + w(addr(rl[:66])) + u32(eid) + u32(2)))
        if isinstance(sl, str) and sl.startswith("0x"):
            v[f"send_to_{name}"] = decode_uln(call(url, EP, "0x2b3197b9" + w(oapp) + w(addr(sl)) + u32(eid) + u32(2)))
    log(f"    {label}: {json.dumps(v)}")
    return v


def main():
    stamp = time.strftime("%Y-%m-%dT%H%MZ", time.gmtime())
    for d in ("data", "raw/token", "runs"):
        os.makedirs(os.path.join(HERE, d), exist_ok=True)
    S = {"run_utc": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())}
    log(f"RLS token and bridge check, run {S['run_utc']}")

    # ---- Rayls side
    log("\n[1] RLS on Rayls")
    S["rayls_supply"] = num(call(RAYLS, RLS_RAYLS, "0x18160ddd"))
    S["rayls"] = oapp_view(RAYLS, RLS_RAYLS, {"ethereum": EID["ethereum"], "bsc": EID["bsc"]}, "Rayls RLS")
    impl = S["rayls"]["implementation"]
    for path, name in ((f"/smart-contracts/{impl}", "rayls_rls_implementation.json"), (f"/addresses/{RLS_RAYLS}/logs", "rayls_rls_logs_page1.json"),
                       (f"/smart-contracts/{S['rayls']['proxy_admin_slot']}", "rayls_rls_proxy_admin.json")):
        try:
            json.dump(http(API + path), open(os.path.join(HERE, "raw", "token", name), "w"))
        except Exception as e:
            log(f"    {path}: {str(e)[:80]}")
    try:
        src = json.load(open(os.path.join(HERE, "raw", "token", "rayls_rls_implementation.json")))
        S["rayls_impl_name"] = src.get("name")
        S["rayls_impl_verified"] = src.get("is_verified")
        log(f"    implementation {impl}: {src.get('name')} verified {src.get('is_verified')}")
    except Exception:
        pass
    # upgrade history from the proxy's own logs
    ups = []
    try:
        for l in http(f"{API}/addresses/{RLS_RAYLS}/logs").get("items", []):
            if l["topics"][0] == "0xbc7cd75a20ee27fd9adebab32041f755214dbc6bffa90cc0225b39da2e5c2d3b":
                ups.append({"block": l["block_number"], "tx": l["transaction_hash"], "implementation": "0x" + l["topics"][1][-40:]})
    except Exception as e:
        log(f"    logs: {str(e)[:80]}")
    S["rayls_upgrades_on_first_log_page"] = ups

    # ---- how the lock's RLS arrived: the three LayerZero deliveries to the funder on 5 August
    log("\n[2] The 5 August mints to the funder, traced through LayerZero Scan")
    tt = http(f"{API}/addresses/{FUNDER}/token-transfers?type=ERC-20")["items"]
    mints = [x for x in tt if x["from"]["hash"] == "0x0000000000000000000000000000000000000000" and x["token"]["address_hash"].lower() == RLS_RAYLS]
    S["mints"] = []
    for x in mints:
        m = {"rayls_tx": x["transaction_hash"], "time": x["timestamp"], "amount": rls(int(x["total"]["value"]))}
        try:
            j = http(f"{LZ}/messages/tx/{x['transaction_hash']}")
            d = (j.get("data") or [{}])[0]
            m.update(guid=d.get("guid"), status=(d.get("status") or {}).get("name"),
                     src_chain=(d.get("pathway") or {}).get("srcEid"), src_tx=((d.get("source") or {}).get("tx") or {}).get("txHash"),
                     src_from=((d.get("source") or {}).get("tx") or {}).get("from"), sender_oapp=((d.get("pathway") or {}).get("sender") or {}).get("address"))
            json.dump(j, open(os.path.join(HERE, "raw", "token", f"lz_{x['transaction_hash'][:12]}.json"), "w"))
        except Exception as e:
            m["lz_error"] = str(e)[:80]
        S["mints"].append(m)
        log(f"    {m}")

    # ---- Ethereum hub and BSC
    log("\n[3] Ethereum hub")
    eth = {}
    for n, url in ETH.items():
        try:
            eth[n] = {"rls_total_supply": num(call(url, RLS_ETH, "0x18160ddd"))}
        except Exception as e:
            eth[n] = {"error": str(e)[:80]}
    S["eth_total_supply"] = {n: rls(v.get("rls_total_supply")) for n, v in eth.items()}
    adapter = S["rayls"].get("peer_ethereum")
    S["eth_adapter"] = adapter
    url = ETH["publicnode"]
    if adapter and adapter.startswith("0x"):
        S["eth_adapter_token"] = addr(call(url, adapter, "0xfc0c546a"))
        S["eth_adapter_locked"] = {n: rls(num(call(u, RLS_ETH, "0x70a08231" + w(adapter)))) for n, u in ETH.items()}
        S["eth_adapter_view"] = oapp_view(url, adapter, {"rayls": EID["rayls"], "bsc": EID["bsc"]}, "Ethereum adapter")
        S["eth_rls_token_implementation"] = addr(rpc(url, "eth_getStorageAt", [RLS_ETH, SLOT_IMPL, "latest"]))
        S["eth_rls_token_owner"] = addr(call(url, RLS_ETH, "0x8da5cb5b"))
        code = rpc(url, "eth_getCode", [RLS_ETH, "latest"])
        S["eth_rls_token_code_bytes"] = (len(code) - 2) // 2
    log(f"    RLS total supply on Ethereum: {S['eth_total_supply']}")
    log(f"    adapter {adapter}: token {S.get('eth_adapter_token')}, locked {S.get('eth_adapter_locked')}")
    log(f"    Ethereum RLS token: implementation slot {S.get('eth_rls_token_implementation')}, owner() {S.get('eth_rls_token_owner')}")

    log("\n[4] BSC")
    try:
        S["bsc_supply"] = rls(num(call(BSC, RLS_BSC, "0x18160ddd")))
        S["bsc_peer_ethereum"] = addr(call(BSC, RLS_BSC, "0xbb0b6a53" + u32(EID["ethereum"])))
    except Exception as e:
        S["bsc_error"] = str(e)[:100]
    log(f"    RLS on BSC: supply {S.get('bsc_supply')}, peer on Ethereum {S.get('bsc_peer_ethereum')}")

    # ---- the invariant: what is minted on spokes must not exceed what the hub has locked
    try:
        locked = float(S["eth_adapter_locked"]["publicnode"].replace(",", ""))
        spokes = S["rayls_supply"] / 1e18 + float(S.get("bsc_supply", "0").replace(",", ""))
        S["hub_locked_minus_spokes"] = f"{locked - spokes:,.6f}"
        log(f"\n[5] Hub locked {locked:,.6f} vs Rayls + BSC supply {spokes:,.6f}: difference {S['hub_locked_minus_spokes']}")
    except Exception as e:
        log(f"\n[5] invariant not computed: {e}")
    S["rayls_supply"] = rls(S["rayls_supply"])
    json.dump(S, open(os.path.join(HERE, "data", "token_state.json"), "w"), indent=1, default=str)
    log(f"\nfinished {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}")
    open(os.path.join(HERE, "runs", f"{stamp}-token.txt"), "w").write("\n".join(LOG) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        LOG.append(traceback.format_exc())
        os.makedirs(os.path.join(HERE, "runs"), exist_ok=True)
        open(os.path.join(HERE, "runs", time.strftime("%Y-%m-%dT%H%MZ", time.gmtime()) + "-token-FAILED.txt"), "w").write("\n".join(LOG) + "\n")
        raise
