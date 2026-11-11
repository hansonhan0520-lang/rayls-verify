#!/usr/bin/env python3
"""Read the Parfin RLS lock-up contract on the Rayls Public Chain and test its rules.

Read-only. Standard library only (selectors are written out below). Every call is an
eth_call or a GET; simulated transactions (claim, burn, sweep, addAdmin) are run with
eth_call, which executes the code against current state and throws the result away.
Nothing is signed or sent.

Output:
  data/lock_state.json      everything read, plus the simulation results
  data/lock_schedule.csv    the 48 unlock dates and the amount each would pay
  data/lock_roles.csv       every owner/admin change, and who holds each role now
  data/lock_funding.csv     every RLS transfer into or out of the lock
  raw/lock/                 raw explorer responses
  runs/<time>-lock.txt      human-readable log
"""
import csv, json, os, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
RPC = "https://mainnet-rpc.rayls.com"
API = "https://explorer.rayls.com/api/v2"
LOCK = "0x1463889d3a5eaaee3f066d1cf438a8957f7db98e"
RLS = "0x07e17e17e17e17e17e17e17e17e17e17e17e17ea"
UA = {"User-Agent": "rayls-verify-monitor", "Content-Type": "application/json"}
LOG = []

SEL = {"totalAmount": "0x1a39d8ef", "unlockTimes": "0x0b486603", "ownerCount": "0x0db02622", "adminCount": "0x2b7832b3",
       "isOwner": "0x2f54bf6e", "isAdmin": "0x24d7806c", "totalClaimed": "0xd54ad2a1", "totalBurned": "0xd89135cd",
       "isFullyFunded": "0xaebc34e4", "actualBalance": "0x39d1f908", "claimable": "0xaf38d757", "stillLocked": "0x36e8078b",
       "nextUnlockTime": "0xf8737bc0", "tranchesClaimed": "0x22ef97ca", "scheduleBasis": "0x11a9aa22", "token": "0xfc0c546a",
       "claim": "0x4e71d92d", "burn": "0x42966c68", "sweep": "0x35faa416", "addAdmin": "0x70480275",
       "getOwners": "0xa0e67e2b", "getThreshold": "0xe75235b8", "totalSupply": "0x18160ddd", "balanceOf": "0x70a08231"}
ERR = {"0xdb6a0954": "NotYetVested(uint256)", "0x17a84242": "NotAdmin(address)", "0x245aecd3": "NotOwner(address)",
       "0xcb8aa1aa": "ScheduleNotSettled(uint256)", "0x969bf728": "NothingToClaim()", "0x91ad6d68": "NotFullyFunded(uint256,uint256)"}
STRANGER = "0x000000000000000000000000000000000000beef"


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
            raise
        except Exception:
            if i < tries - 1:
                time.sleep(2)
                continue
            raise


def call(to, data, frm=None, block="latest", overrides=None):
    """eth_call. Returns ('ok', hex) or ('revert', decoded error)."""
    tx = {"to": to, "data": data}
    if frm:
        tx["from"] = frm
    params = [tx, block] + ([{}, overrides] if overrides else [])
    j = http(RPC, {"jsonrpc": "2.0", "id": 1, "method": "eth_call", "params": params})
    if "error" in j:
        e = j["error"]
        d = e.get("data") or ""
        if isinstance(d, dict):
            d = d.get("data", "")
        name = ERR.get(d[:10], d[:10] or e.get("message", ""))
        args = [int(d[10 + 64 * i:74 + 64 * i], 16) for i in range((len(d) - 10) // 64)] if d.startswith("0x") else []
        return "revert", {"error": name, "args": args, "message": e.get("message", "")}
    return "ok", j["result"]


w = lambda a: a.lower().replace("0x", "").rjust(64, "0")
num = lambda h: int(h, 16)
rls = lambda wei: f"{wei / 10**18:,.6f}"


def explorer_all(path):
    out, nxt, pages = [], None, 0
    while True:
        q = ("&" if "?" in path else "?") + urllib.parse.urlencode(nxt) if nxt else ""
        j = http(f"{API}{path}{q}")
        out += j.get("items", [])
        nxt = j.get("next_page_params")
        pages += 1
        if not nxt or pages > 100:
            return out


def main():
    stamp = time.strftime("%Y-%m-%dT%H%MZ", time.gmtime())
    for d in ("data", "raw/lock", "runs"):
        os.makedirs(os.path.join(HERE, d), exist_ok=True)
    head = int(http(RPC, {"jsonrpc": "2.0", "id": 1, "method": "eth_blockNumber", "params": []})["result"], 16)
    now = int(http(RPC, {"jsonrpc": "2.0", "id": 1, "method": "eth_getBlockByNumber", "params": [hex(head), False]})["result"]["timestamp"], 16)
    log(f"RLS lock check, run {utc(time.time())}, Rayls block {head} ({utc(now)})")
    S = {"run_utc": utc(time.time()), "block": head, "block_time": utc(now)}

    # ---- terms and state
    for k in ("totalAmount", "ownerCount", "adminCount", "totalClaimed", "totalBurned", "actualBalance", "claimable",
              "stillLocked", "nextUnlockTime", "tranchesClaimed", "scheduleBasis"):
        S[k] = num(call(LOCK, SEL[k])[1])
    S["isFullyFunded"] = num(call(LOCK, SEL["isFullyFunded"])[1]) == 1
    S["token"] = "0x" + call(LOCK, SEL["token"])[1][-40:]
    raw = call(LOCK, SEL["unlockTimes"])[1][2:]
    n = int(raw[64:128], 16)
    times = [int(raw[128 + 64 * i:192 + 64 * i], 16) for i in range(n)]
    S["unlock_count"] = n
    S["first_unlock"], S["last_unlock"] = utc(times[0]), utc(times[-1])
    S["balance_via_token"] = num(call(RLS, SEL["balanceOf"] + w(LOCK))[1])
    code = http(RPC, {"jsonrpc": "2.0", "id": 1, "method": "eth_getCode", "params": [LOCK, "latest"]})["result"]
    S["runtime_code_bytes"] = (len(code) - 2) // 2
    open(os.path.join(HERE, "raw", "lock", "runtime_code.hex"), "w").write(code)
    log(f"\n[1] Terms: token {S['token']}, totalAmount {rls(S['totalAmount'])} RLS, {n} unlock dates, "
        f"{S['first_unlock']} to {S['last_unlock']}")
    log(f"    held {rls(S['actualBalance'])} (token balanceOf {rls(S['balance_via_token'])}), fully funded {S['isFullyFunded']}, "
        f"claimed {rls(S['totalClaimed'])}, burned {rls(S['totalBurned'])}, claimable now {rls(S['claimable'])}, "
        f"next unlock {utc(S['nextUnlockTime'])}")

    # schedule table: what each date pays if nothing is burned or skipped (equal shares)
    with open(os.path.join(HERE, "data", "lock_schedule.csv"), "w", newline="") as f:
        cw = csv.writer(f)
        cw.writerow(["tranche", "unlock_unix", "unlock_utc", "amount_rls_if_claimed_monthly", "cumulative_rls"])
        basis, cum = S["scheduleBasis"], 0
        for i, t in enumerate(times):
            owed = basis - cum
            amt = owed if i == n - 1 else owed // (n - i)
            cum += amt
            cw.writerow([i + 1, t, utc(t), rls(amt), rls(cum)])
    gaps = sorted(set(round((times[i] - times[i - 1]) / 86400) for i in range(1, n)))
    months = sorted(set(datetime.fromtimestamp(t, timezone.utc).strftime("%d %H:%M") for t in times))
    log(f"    gaps between dates (days): {gaps}; day-of-month and time: {months}")
    S["tranche_amount"] = rls(S["scheduleBasis"] // n)

    # ---- roles: every change, then who holds what now
    logs = explorer_all(f"/addresses/{LOCK}/logs")
    json.dump(logs, open(os.path.join(HERE, "raw", "lock", "logs.json"), "w"))
    txs = explorer_all(f"/addresses/{LOCK}/transactions")
    json.dump(txs, open(os.path.join(HERE, "raw", "lock", "transactions.json"), "w"))
    roles, people = [], set()
    for l in sorted(logs, key=lambda x: (x["block_number"], x.get("index", 0))):
        dec = l.get("decoded") or {}
        name = (dec.get("method_call") or "").split("(")[0]
        p = {x["name"]: x["value"] for x in dec.get("parameters") or []}
        if name in ("OwnerAdded", "OwnerRemoved", "AdminAdded", "AdminRemoved"):
            who = (p.get("owner") or p.get("admin")).lower()
            people.add(who)
            roles.append({"block": l["block_number"], "tx": l["transaction_hash"], "event": name, "account": who, "by": p["by"].lower()})
        elif name == "LockCreated":
            S["created_block"], S["created_tx"] = l["block_number"], l["transaction_hash"]
    for r in roles:
        r["time"] = utc(int(http(RPC, {"jsonrpc": "2.0", "id": 1, "method": "eth_getBlockByNumber", "params": [hex(r["block"]), False]})["result"]["timestamp"], 16))
    S["created_time"] = utc(int(http(RPC, {"jsonrpc": "2.0", "id": 1, "method": "eth_getBlockByNumber", "params": [hex(S["created_block"]), False]})["result"]["timestamp"], 16))
    now_roles = []
    for a in sorted(people):
        o = num(call(LOCK, SEL["isOwner"] + w(a))[1]) == 1
        ad = num(call(LOCK, SEL["isAdmin"] + w(a))[1]) == 1
        c = http(RPC, {"jsonrpc": "2.0", "id": 1, "method": "eth_getCode", "params": [a, "latest"]})["result"]
        nonce = int(http(RPC, {"jsonrpc": "2.0", "id": 1, "method": "eth_getTransactionCount", "params": [a, "latest"]})["result"], 16)
        kind = "plain account" if c == "0x" else "contract"
        extra = ""
        if c != "0x":
            st, r = call(a, SEL["getThreshold"])
            if st == "ok":
                st2, r2 = call(a, SEL["getOwners"])
                k = int(r2[130:194], 16) if st2 == "ok" else "?"
                kind, extra = "Safe-style multisig", f"threshold {num(r)} of {k}"
        now_roles.append({"account": a, "owner_now": o, "admin_now": ad, "kind": kind, "multisig": extra, "rayls_tx_count": nonce})
    with open(os.path.join(HERE, "data", "lock_roles.csv"), "w", newline="") as f:
        cw = csv.DictWriter(f, fieldnames=["time", "block", "event", "account", "by", "tx"])
        cw.writeheader()
        cw.writerows(roles)
    S["roles_now"] = now_roles
    S["owners_now"] = [r["account"] for r in now_roles if r["owner_now"]]
    S["admins_now"] = [r["account"] for r in now_roles if r["admin_now"]]
    log(f"\n[2] Created {S['created_time']} (block {S['created_block']}, tx {S['created_tx']}); {len(roles)} role changes")
    for r in roles:
        log(f"    {r['time']}  {r['event']:12s} {r['account']} by {r['by']}")
    log(f"    now: {S['ownerCount']} owners {S['owners_now']}, {S['adminCount']} admins {S['admins_now']}")
    for r in now_roles:
        log(f"    {r['account']}: owner {r['owner_now']}, admin {r['admin_now']}, {r['kind']} {r['multisig']}, {r['rayls_tx_count']} txs sent")

    # ---- funding: every RLS transfer in or out
    tt = explorer_all(f"/addresses/{LOCK}/token-transfers")
    json.dump(tt, open(os.path.join(HERE, "raw", "lock", "token_transfers.json"), "w"))
    fund = [{"time": x["timestamp"], "from": x["from"]["hash"].lower(), "to": x["to"]["hash"].lower(),
             "token": x["token"]["address_hash"].lower(), "amount": rls(int(x["total"]["value"])), "tx": x["transaction_hash"]} for x in tt]
    fund.sort(key=lambda x: x["time"])
    with open(os.path.join(HERE, "data", "lock_funding.csv"), "w", newline="") as f:
        cw = csv.DictWriter(f, fieldnames=["time", "from", "to", "token", "amount", "tx"])
        cw.writeheader()
        cw.writerows(fund)
    ins = sum(int(x["total"]["value"]) for x in tt if x["to"]["hash"].lower() == LOCK and x["token"]["address_hash"].lower() == RLS)
    outs = sum(int(x["total"]["value"]) for x in tt if x["from"]["hash"].lower() == LOCK)
    S["funding_in"], S["funding_out"], S["funders"] = rls(ins), rls(outs), sorted(set(x["from"] for x in fund if x["to"] == LOCK))
    log(f"\n[3] RLS transfers: {len(fund)}; in {rls(ins)}, out {rls(outs)}; from {S['funders']}")
    for x in fund:
        log(f"    {x['time']} {x['from']} -> {x['to']} {x['amount']} tx {x['tx']}")

    # ---- simulations: try to break the lock
    admin = S["admins_now"][0]
    owner = S["owners_now"][0]
    sims = {}
    sims["claim_now_as_admin"] = call(LOCK, SEL["claim"], admin)
    sims["claim_now_as_stranger"] = call(LOCK, SEL["claim"], STRANGER)
    sims["sweep_now_as_admin"] = call(LOCK, SEL["sweep"], admin)
    sims["burn_1_rls_as_stranger"] = call(LOCK, SEL["burn"] + format(10**18, "064x"), STRANGER)
    sims["burn_1_rls_as_admin"] = call(LOCK, SEL["burn"] + format(10**18, "064x"), admin)
    sims["add_admin_as_stranger"] = call(LOCK, SEL["addAdmin"] + w(STRANGER), STRANGER)
    sims["add_admin_as_owner"] = call(LOCK, SEL["addAdmin"] + w(STRANGER), owner)
    # one second before and exactly at the first date, by overriding the block timestamp
    for label, ts in (("claim_as_admin_1s_before_first_date", times[0] - 1), ("claim_as_admin_at_first_date", times[0]),
                      ("claim_as_admin_at_12th_date", times[11]), ("claim_as_admin_at_last_date", times[-1])):
        try:
            sims[label] = call(LOCK, SEL["claim"], admin, overrides={"time": hex(ts)})
        except Exception as e:
            sims[label] = ("unsupported", str(e)[:120])
    S["admin_used_for_simulation"], S["owner_used_for_simulation"] = admin, owner
    S["simulations"] = {}
    log(f"\n[4] Simulations (eth_call, nothing sent). admin used: {admin}, owner used: {owner}")
    for k, (st, r) in sims.items():
        if st == "ok":
            v = num(r) if r not in ("0x", "") else None
            shown = f"succeeds, returns {rls(v)} RLS" if v is not None and "claim" in k else "succeeds"
        elif st == "revert":
            shown = f"reverts {r['error']} {[utc(a) if 1.7e9 < a < 2.1e9 else (rls(a) if a > 10**15 else a) for a in r['args']]}"
        else:
            shown = f"{st}: {r}"
        S["simulations"][k] = shown
        log(f"    {k:40s} {shown}")

    # ---- the token itself
    S["rls_total_supply_on_rayls"] = rls(num(call(RLS, SEL["totalSupply"])[1]))
    S["lock_share_of_rayls_supply"] = round(S["actualBalance"] / num(call(RLS, SEL["totalSupply"])[1]) * 100, 2)
    log(f"\n[5] RLS on Rayls: total supply {S['rls_total_supply_on_rayls']}; the lock holds {S['lock_share_of_rayls_supply']}% of it")
    for path, name in ((f"/tokens/{RLS}", "rls_token.json"), (f"/smart-contracts/{RLS}", "rls_contract.json"),
                       (f"/addresses/{S['funders'][0]}", "funder.json"), (f"/addresses/{S['funders'][0]}/token-transfers?type=ERC-20", "funder_transfers.json"),
                       ("/smart-contracts?q=RlsTokenLock", "search_rlstokenlock.json")):
        try:
            json.dump(http(API + path), open(os.path.join(HERE, "raw", "lock", name), "w"))
        except Exception as e:
            log(f"    {path}: {str(e)[:80]}")
    json.dump(S, open(os.path.join(HERE, "data", "lock_state.json"), "w"), indent=1)
    log(f"\nfinished {utc(time.time())}")
    open(os.path.join(HERE, "runs", f"{stamp}-lock.txt"), "w").write("\n".join(LOG) + "\n")


if __name__ == "__main__":
    main()
