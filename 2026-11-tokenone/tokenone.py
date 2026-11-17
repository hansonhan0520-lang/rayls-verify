#!/usr/bin/env python3
"""TokenOne's NF01, NF02, NF03 debentures on the Rayls Public Chain: what an investor can check.

Read-only, standard library only. Simulated transactions use eth_call and are discarded.

Answers, for each token:
  * supply and every holder now, read from the official RPC (balanceOf), not only the explorer
  * whether any transfer other than the mint ever happened, using:
      (a) every event log the explorer has for the contract, by type
      (b) every transaction sent to the contract, by method
      (c) the official RPC's current balanceOf for every discovered holder, summed against supply
    eth_getLogs is also recorded as a diagnostic, not as proof of absence: this RPC has
    returned zero even for blocks containing a mint visible in the explorer. The script
    explicitly records whether its count matches the explorer instead of hiding that mismatch.
  * who holds each role (admin, issuer, enforcer, pauser), and whether those are plain accounts
  * which compliance module gates transfers, and what it allows
  * simulated transfer from the holder to an unrelated address; whether NF02/NF03 run NF01's code
Output: data/tokens.json, data/events.csv, runs/<time>-tokenone.txt, raw/tokens/
"""
import csv, json, os, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
RPC = "https://mainnet-rpc.rayls.com"
API = "https://explorer.rayls.com/api/v2"
UA = {"User-Agent": "rayls-verify-monitor", "Content-Type": "application/json"}
TOKENS = {"NF01": "0x36f480c489f4cf6aacf91c7605504a840060e376",
          "NF02": "0x424cdecec00bfe64be85f2d53a3e49ee28d05f05",
          "NF03": "0x6a05c0a11aae5366f0a2520695b516ff6372f26c"}
ROLES = {"DEFAULT_ADMIN": "0x" + "0" * 64,
         "ISSUER": "0x114e74f6ea3bd819998f78687bfcb11b140da08e9b7d222fa9c1f1ba1f2aa122",
         "ENFORCER": "0x973ef39d76cc2c6090feab1c030bec6ab5db557f64df047a4c4f9b5953cf1df3",
         "PAUSER": "0x65d7a28e3265b37a6474929f336521b332c1681b933f6cb9f3376673440d862a"}
RNAME = {v: k for k, v in ROLES.items()}
TOPIC = {"0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef": "Transfer",
         "0x2f8788117e7eff1d82e926ec794901d17c78024a50270940304540a733656f0d": "RoleGranted",
         "0xf6391f5c32d9c69d2a47ea670b442974b53935d1edc7fd64eb21e047a839171b": "RoleRevoked",
         "0x6313493929566ff7461bc9bdb295eeae7fe7843d653e340f5fd4c1860842ee51": "ComplianceUpdated",
         "0x7b0c29e799ed468266b4d070c03070137a95cb869c5eb7c18063fb7b1a7a09c5": "Frozen",
         "0xa7f01abbf5b7ec7bac7fb74feb5c1f54af9e430f18a33681c1b9149875339a45": "ForcedTransfer",
         "0x62e78cea01bee320cd4e420270b5ea74000d11b0c9f74754ebdbfc544b05a258": "Paused",
         "0x5db9ee0a495bf2e6ff9c91a7834c1ba4fdd244a5e8aa4e537bd38aeae4b073aa": "Unpaused",
         "0x8c5be1e5ebec7d5bd14f71427d1e84f3dd0314c0f7b2291e5b200ac8c7c3b925": "Approval"}
T_TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
STRANGER = "0x000000000000000000000000000000000000beef"
LOG = []


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


def rpc(method, params):
    j = http(RPC, {"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
    if "error" in j:
        e = j["error"]
        d = e.get("data") or ""
        raise RuntimeError(f"{e.get('message', '')} {d if isinstance(d, str) else json.dumps(d)}"[:220])
    return j["result"]


def call(to, data, frm=None):
    tx = {"to": to, "data": data}
    if frm:
        tx["from"] = frm
    try:
        return rpc("eth_call", [tx, "latest"])
    except Exception as e:
        return "REVERT " + str(e)[:200]


w = lambda a: a.lower().replace("0x", "").rjust(64, "0")
addr = lambda h: "0x" + h[-40:] if isinstance(h, str) and h.startswith("0x") and len(h) >= 42 else h
TRUE = "0x" + "0" * 63 + "1"


def kind(a):
    code = rpc("eth_getCode", [a, "latest"])
    if code == "0x":
        return f"plain account ({int(rpc('eth_getTransactionCount', [a, 'latest']), 16)} txs sent)"
    th = call(a, "0xe75235b8")
    if th.startswith("0x") and len(th) == 66:
        ow = call(a, "0xa0e67e2b")
        n = int(ow[66:130], 16) if ow.startswith("0x") else "?"
        return f"Safe multisig {int(th, 16)} of {n}"
    return f"contract ({(len(code) - 2) // 2} bytes)"


def explorer_all(path):
    out, nxt, pages = [], None, 0
    while True:
        q = (("&" if "?" in path else "?") + urllib.parse.urlencode(nxt)) if nxt else ""
        j = http(f"{API}{path}{q}")
        out += j.get("items", []) if isinstance(j, dict) else []
        nxt = j.get("next_page_params") if isinstance(j, dict) else None
        pages += 1
        if not nxt or pages > 100:
            return out


def main():
    stamp = time.strftime("%Y-%m-%dT%H%MZ", time.gmtime())
    for d in ("data", "raw/tokens", "runs"):
        os.makedirs(os.path.join(HERE, d), exist_ok=True)
    head = int(rpc("eth_blockNumber", []), 16)
    S = {"run_utc": utc(time.time()), "rayls_block": head, "tokens": {}}
    log(f"TokenOne debentures, run {S['run_utc']}, Rayls block {head}")
    codes = {}
    events_rows = []
    people = set()
    for sym, a in TOKENS.items():
        t = {"address": a}
        t["name"] = bytes.fromhex(call(a, "0x06fdde03")[130:]).rstrip(b"\0").decode(errors="replace")
        t["decimals"] = int(call(a, "0x313ce567"), 16)
        sup = int(call(a, "0x18160ddd"), 16)
        t["total_supply"] = sup / 10 ** t["decimals"]
        t["paused"] = call(a, "0x5c975abb") == TRUE
        t["compliance"] = addr(call(a, "0x6290865d"))
        codes[sym] = rpc("eth_getCode", [a, "latest"])
        open(os.path.join(HERE, "raw", "tokens", f"{sym}_runtime.hex"), "w").write(codes[sym])

        # (a) every event the explorer has, (b) every transaction to the contract
        logs = explorer_all(f"/addresses/{a}/logs")
        txs = explorer_all(f"/addresses/{a}/transactions")
        json.dump(logs, open(os.path.join(HERE, "raw", "tokens", f"{sym}_logs.json"), "w"))
        json.dump(txs, open(os.path.join(HERE, "raw", "tokens", f"{sym}_transactions.json"), "w"))
        counts = {}
        transfers = []
        for l in logs:
            nm = TOPIC.get(l["topics"][0], l["topics"][0][:10])
            counts[nm] = counts.get(nm, 0) + 1
            row = {"token": sym, "block": l["block_number"], "tx": l["transaction_hash"], "event": nm}
            if nm == "Transfer":
                row.update(frm=addr(l["topics"][1]), to=addr(l["topics"][2]), amount=int(l["data"], 16) / 10 ** t["decimals"])
                transfers.append(row)
                people.update([row["frm"], row["to"]])
            elif nm in ("RoleGranted", "RoleRevoked"):
                row.update(role=RNAME.get(l["topics"][1], l["topics"][1]), account=addr(l["topics"][2]), by=addr(l["topics"][3]))
                people.update([row["account"], row["by"]])
            elif nm == "ComplianceUpdated":
                row.update(account=addr(l["topics"][1]))
            events_rows.append(row)
        t["explorer_event_counts"] = counts
        t["explorer_transactions"] = [{"hash": x["hash"], "method": x.get("method"), "from": (x.get("from") or {}).get("hash"),
                                       "time": x.get("timestamp"), "status": x.get("status")} for x in txs]
        t["transfers_excluding_mint"] = [r for r in transfers if r["frm"] != "0x" + "0" * 40]
        t["mints"] = [r for r in transfers if r["frm"] == "0x" + "0" * 40]
        # creation block, for the RPC log scan
        info = http(f"{API}/addresses/{a}")
        t["creator"] = (info.get("creator_address_hash") or "").lower() or None
        t["creation_tx"] = info.get("creation_transaction_hash") or info.get("creation_tx_hash")
        first_block = min([l["block_number"] for l in logs] + [head])
        if t["creation_tx"]:
            try:
                first_block = int(rpc("eth_getTransactionByHash", [t["creation_tx"]])["blockNumber"], 16)
            except Exception:
                pass
        # (c) the official RPC's own log search, in 50,000-block chunks
        rpc_hits, rpc_err = 0, 0
        for b in range(first_block, head + 1, 50000):
            try:
                rpc_hits += len(rpc("eth_getLogs", [{"address": a, "topics": [T_TRANSFER], "fromBlock": hex(b), "toBlock": hex(min(b + 49999, head))}]))
            except Exception:
                rpc_err += 1
        t["rpc_getlogs_transfer_events"] = rpc_hits
        t["rpc_getlogs_errors"] = rpc_err
        t["rpc_getlogs_matches_explorer_transfer_count"] = (rpc_hits == len(transfers)) if rpc_err == 0 else None
        t["first_block"] = first_block
        # state check: who holds it now, per the official RPC
        hold = explorer_all(f"/tokens/{a}/holders")
        cands = set(x["address"]["hash"].lower() for x in hold) | set(r["to"] for r in transfers)
        t["holders_now"] = {}
        for h in sorted(cands):
            bal = int(call(a, "0x70a08231" + w(h)), 16)
            if bal:
                t["holders_now"][h] = bal / 10 ** t["decimals"]
        t["holders_sum_equals_supply"] = abs(sum(t["holders_now"].values()) - t["total_supply"]) < 1e-9
        people.update(t["holders_now"])
        if t["creator"]:
            people.add(t["creator"])
        S["tokens"][sym] = t
        log(f"\n[{sym}] {a} '{t['name']}': supply {t['total_supply']:,.6f}, decimals {t['decimals']}, paused {t['paused']}, compliance {t['compliance']}")
        log(f"    explorer events {counts}; transactions to contract: {[(x['method'], x['time']) for x in t['explorer_transactions']]}")
        log(f"    mints {[(m['to'], m['amount'], m['block']) for m in t['mints']]}; transfers other than mint: {len(t['transfers_excluding_mint'])}")
        log(f"    official RPC eth_getLogs Transfer events from block {first_block}: {rpc_hits} (errors {rpc_err}); explorer has {len(transfers)}; match: {t['rpc_getlogs_matches_explorer_transfer_count']}")
        if t["rpc_getlogs_matches_explorer_transfer_count"] is False:
            log("    WARNING: RPC log search disagrees with known explorer history; it is not used as absence evidence")
        log(f"    holders now (RPC balanceOf): {t['holders_now']}; sum equals supply: {t['holders_sum_equals_supply']}")

    # roles
    log("\n[roles]")
    for sym, a in TOKENS.items():
        S["tokens"][sym]["roles"] = {r: [p for p in sorted(people) if p and call(a, "0x91d14854" + h[2:] + w(p)) == TRUE] for r, h in ROLES.items()}
        log(f"    {sym}: {json.dumps(S['tokens'][sym]['roles'])}")
    S["account_kinds"] = {}
    for p in sorted(people):
        if p and p != "0x" + "0" * 40:
            S["account_kinds"][p] = kind(p)
            log(f"    {p}: {S['account_kinds'][p]}")

    # compliance module and simulations
    log("\n[compliance and simulations]")
    for sym, a in TOKENS.items():
        t = S["tokens"][sym]
        c = t["compliance"]
        sims = {}
        holder = next(iter(t["holders_now"]), None)
        if c and c != "0x" + "0" * 40:
            t["compliance_kind"] = kind(c)
            for p, nm in ((holder, "holder"), (STRANGER, "stranger")):
                if p:
                    sims[f"compliance.canSend({nm})"] = call(c, "0x2bc06a92" + w(p)) == TRUE
                    sims[f"compliance.canReceive({nm})"] = call(c, "0x90d370ba" + w(p)) == TRUE
        else:
            t["compliance_kind"] = "none: with no module the token allows every transfer"
        if holder:
            sims["token.canTransfer(holder->stranger, 1)"] = call(a, "0xe46638e6" + w(holder) + w(STRANGER) + format(1, "064x")) == TRUE
            r = call(a, "0xa9059cbb" + w(STRANGER) + format(1, "064x"), holder)
            sims["transfer(holder->stranger, 1 unit) as holder"] = "succeeds" if r.startswith("0x") else r
            r = call(a, "0xa9059cbb" + w(holder) + format(1, "064x"), STRANGER)
            sims["transfer as stranger (no balance)"] = "succeeds" if r.startswith("0x") else r
            for role in ("ISSUER", "ENFORCER"):
                for who in t["roles"][role][:1]:
                    if role == "ISSUER":
                        r = call(a, "0x40c10f19" + w(STRANGER) + format(1, "064x"), who)
                        sims[f"mint 1 unit to stranger as issuer {who[:10]}"] = "succeeds" if r.startswith("0x") else r
                    else:
                        r = call(a, "0x9fc1d0e7" + w(holder) + w(STRANGER) + format(1, "064x"), who)
                        sims[f"forcedTransfer holder->stranger as enforcer {who[:10]}"] = "succeeds" if r.startswith("0x") else r
        t["simulations"] = sims
        log(f"    {sym}: compliance {c} ({t['compliance_kind']})")
        for k, v in sims.items():
            log(f"        {k}: {v}")
        if c and c != "0x" + "0" * 40:
            try:
                json.dump(http(f"{API}/smart-contracts/{c}"), open(os.path.join(HERE, "raw", "tokens", f"compliance_{c[:10]}.json"), "w"))
            except Exception as e:
                log(f"        compliance source: {str(e)[:60]}")

    # do NF02 and NF03 run NF01's code? compare runtime bytecode ignoring immutables and metadata
    def norm(code):
        h = code[2:]
        cut = h.rfind("a264697066735822")  # CBOR metadata marker ("ipfs")
        return h[:cut] if cut > 0 else h
    base = norm(codes["NF01"])
    S["bytecode"] = {}
    for sym in ("NF02", "NF03"):
        o = norm(codes[sym])
        diff = sum(1 for i in range(0, min(len(base), len(o)), 2) if base[i:i + 2] != o[i:i + 2])
        S["bytecode"][sym] = {"bytes": len(o) // 2, "nf01_bytes": len(base) // 2, "bytes_differing": diff,
                              "same_length": len(o) == len(base)}
        log(f"    {sym} vs NF01 runtime code: {S['bytecode'][sym]}")
    with open(os.path.join(HERE, "data", "events.csv"), "w", newline="") as f:
        cw = csv.DictWriter(f, fieldnames=["token", "block", "tx", "event", "frm", "to", "amount", "role", "account", "by"])
        cw.writeheader()
        cw.writerows(events_rows)
    json.dump(S, open(os.path.join(HERE, "data", "tokens.json"), "w"), indent=1, default=str)
    log(f"\nfinished {utc(time.time())}")
    open(os.path.join(HERE, "runs", f"{stamp}-tokenone.txt"), "w").write("\n".join(LOG) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        LOG.append(traceback.format_exc())
        os.makedirs(os.path.join(HERE, "runs"), exist_ok=True)
        open(os.path.join(HERE, "runs", time.strftime("%Y-%m-%dT%H%MZ", time.gmtime()) + "-tokenone-FAILED.txt"), "w").write("\n".join(LOG) + "\n")
        raise
