#!/usr/bin/env python3
"""TokenOne pilot vault on the Rayls Public Chain: follow a deposit from wallet to invoice fund.

Read-only, standard library only. No wallet, no key. Reads public state from the official
Rayls RPC and event history from the Rayls explorer, and writes:

  data/state.json        both layers right now, and whether they add up
  data/history.jsonl     one line per run (the scheduled job appends)
  data/vault_events.csv  the Lagoon vault's NAV updates, requests, settlements and claims
  data/fund_events.csv   the TokenOne fund's deposits, capital moves and value reports
  runs/<time>-vault.txt  human-readable log

Depositor addresses are never written. For depositor actions only time, amount and the
function used are kept; transaction hashes are kept for operator actions only.

The path a deposit takes (see README):
  wallet -> Lagoon vault "Rayls Token One 02" (RLSTKONE02): requestDeposit, BRL1.p waits in
  a pending silo -> daily: the valuation manager proposes the vault's value, the vault Safe
  settles (pending BRL1.p moves to the Safe, shares are minted) and claims the shares for each
  depositor -> the Safe deposits the BRL1.p into the TokenOne fund "TokenOne TIDC02" (TKONE02,
  an ERC-4626 RwaVaultV3) -> the fund's manager withdraws capital to finance receivables; the
  fund's oracle reports that capital's value, which is what moves the price.
"""
import csv, json, os, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
RPC = "https://mainnet-rpc.rayls.com"
API = "https://explorer.rayls.com/api/v2"
VAULT = "0x1811630b90e6966573e809270a5e9316a25de6fe"   # Lagoon v0.6.0 proxy, RLSTKONE02
FUND = "0x870c2c4cfaf895f55163385813164e5808ae7029"    # TokenOne TIDC02 (TKONE02), RwaVaultV3
BRL = "0xa069d3798feab32994ac5d98a9f011da6024f334"     # BRL1.p
SILO = "0xe8ccad69bbef1ceac3e559fb8fd41dc3f4df5779"    # the vault's pending silo
UA = {"User-Agent": "rayls-verify-monitor", "Content-Type": "application/json"}
# 4-byte selectors (keccak256 of the signature), precomputed so the script needs no packages
S = {"name()": "0x06fdde03", "symbol()": "0x95d89b41", "version()": "0x54fd4d50",
     "totalAssets()": "0x01e1d114", "totalSupply()": "0x18160ddd",
     "maxCap()": "0x23548b8b", "paused()": "0x5c975abb", "isTotalAssetsValid()": "0x0c2b5b91",
     "isAsyncOnly()": "0xb38cf715", "feeRates()": "0x7688c584", "safe()": "0x186f0354",
     "convertToAssets(uint256)": "0x07a2d13a", "balanceOf(address)": "0x70a08231",
     "idleAssets()": "0xe16b03a3", "deployedCapital()": "0xb0c660ee", "reportedAt()": "0x0a64cc54",
     "maxReportAge()": "0xc45e0d24", "maxReportDeviationBps()": "0x87251ff3"}
VAULT_EVENTS = ("NewTotalAssetsUpdated", "TotalAssetsUpdated", "DepositRequest", "DepositSync", "SettleDeposit",
                "Deposit", "RedeemRequest", "SettleRedeem", "Withdraw", "DepositRequestCanceled")
OPERATOR = ("NewTotalAssetsUpdated", "TotalAssetsUpdated", "SettleDeposit", "SettleRedeem",
            "CapitalWithdrawn", "CapitalReturned", "DeployedCapitalReported", "ReportGuardsSet")
LOG = []


def log(s=""):
    LOG.append(s)
    print(s, flush=True)


def utc(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def http(url, body=None, tries=6):
    data = json.dumps(body).encode() if body is not None else None
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=UA), timeout=40) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            if i < tries - 1 and not (isinstance(e, urllib.error.HTTPError) and e.code in (400, 404)):
                time.sleep(1.5 * 2 ** i)
                continue
            raise


def rpc(method, params):
    j = http(RPC, {"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
    if "error" in j:
        raise RuntimeError(str(j["error"])[:160])
    return j["result"]


def call(to, sig, arg=""):
    return rpc("eth_call", [{"to": to, "data": S[sig] + arg}, "latest"])


def num(to, sig, arg=""):
    return int(call(to, sig, arg), 16)


def word(addr):
    return addr.lower()[2:].rjust(64, "0")


def text(h):
    n = int(h[66:130], 16)
    return bytes.fromhex(h[130:130 + 2 * n]).decode(errors="replace")


def logs(address):
    out, nxt = [], None
    while True:
        j = http(f"{API}/addresses/{address}/logs" + ("?" + urllib.parse.urlencode(nxt) if nxt else ""))
        out += j.get("items", [])
        nxt = j.get("next_page_params")
        if not nxt:
            return sorted(out, key=lambda x: (x["block_number"], x.get("index", 0)))


BLOCK_T, TX_M = {}, {}


def btime(b):
    if b not in BLOCK_T:
        BLOCK_T[b] = int(rpc("eth_getBlockByNumber", [hex(b), False])["timestamp"], 16)
    return BLOCK_T[b]


def method(tx):
    """Name of the function the transaction called (e.g. moveToVault, claimSharesOnBehalf)."""
    if tx not in TX_M:
        TX_M[tx] = http(f"{API}/transactions/{tx}").get("method") or ""
    return TX_M[tx]


def rows_for(address, wanted, amount_keys):
    rows = []
    for l in logs(address):
        d = l.get("decoded") or {}
        name = (d.get("method_call") or "").split("(")[0]
        if name not in wanted:
            continue
        p = {x["name"]: x["value"] for x in d.get("parameters") or []}
        r = {"time_utc": utc(btime(l["block_number"])), "block": l["block_number"], "event": name,
             "via": method(l["transaction_hash"])}
        for k in amount_keys:
            r[k] = f"{int(p[k]) / 1e18:.6f}" if k in p else ""
        r["request_id"] = p.get("requestId") or p.get("epochId") or ""
        r["tx"] = l["transaction_hash"] if name in OPERATOR else ""  # no depositor tx hashes
        rows.append(r)
    return rows


def write_csv(path, rows, fields):
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main():
    stamp = time.strftime("%Y-%m-%dT%H%MZ", time.gmtime())
    for d in ("data", "runs"):
        os.makedirs(os.path.join(HERE, d), exist_ok=True)
    head = int(rpc("eth_blockNumber", []), 16)
    now = int(rpc("eth_getBlockByNumber", [hex(head), False])["timestamp"], 16)
    safe = "0x" + call(VAULT, "safe()")[-40:]
    fr = call(VAULT, "feeRates()")
    v = {"name": text(call(VAULT, "name()")), "symbol": text(call(VAULT, "symbol()")),
         "lagoon_version": text(call(VAULT, "version()")),
         "total_assets": num(VAULT, "totalAssets()") / 1e18, "total_shares": num(VAULT, "totalSupply()") / 1e18,
         "share_price": num(VAULT, "convertToAssets(uint256)", format(10 ** 18, "064x")) / 1e18,
         "max_cap": num(VAULT, "maxCap()") / 1e18, "paused": num(VAULT, "paused()") == 1,
         "nav_valid_now": num(VAULT, "isTotalAssetsValid()") == 1, "async_only": num(VAULT, "isAsyncOnly()") == 1,
         "fee_rates_bps": dict(zip(["management", "performance", "entry", "exit", "haircut"],
                                   [int(fr[2 + 64 * i:66 + 64 * i], 16) for i in range(5)])),
         "pending_deposits_in_silo": num(BRL, "balanceOf(address)", word(SILO)) / 1e18,
         "safe_brl1p": num(BRL, "balanceOf(address)", word(safe)) / 1e18,
         "safe_fund_shares": num(FUND, "balanceOf(address)", word(safe)) / 1e18}
    rep = num(FUND, "reportedAt()")
    f = {"name": text(call(FUND, "name()")), "symbol": text(call(FUND, "symbol()")),
         "total_assets": num(FUND, "totalAssets()") / 1e18, "total_shares": num(FUND, "totalSupply()") / 1e18,
         "share_price": num(FUND, "convertToAssets(uint256)", format(10 ** 18, "064x")) / 1e18,
         "idle_on_chain": num(FUND, "idleAssets()") / 1e18, "deployed_reported": num(FUND, "deployedCapital()") / 1e18,
         "reported_at": utc(rep), "report_age_hours": round((now - rep) / 3600, 2),
         "max_report_age_hours": num(FUND, "maxReportAge()") / 3600,
         "max_report_change_bps": num(FUND, "maxReportDeviationBps()"), "paused": num(FUND, "paused()") == 1}
    # does layer 1 add up to layer 2? vault value vs the Safe's fund shares at the fund's price + its idle BRL1.p
    implied = v["safe_fund_shares"] * f["share_price"] + v["safe_brl1p"]
    check = {"vault_total_assets": v["total_assets"], "safe_position_at_fund_price": implied,
             "difference": v["total_assets"] - implied,
             "note": "The vault's total assets is fixed at each settlement; the fund price moves with each oracle "
                     "report, so a small gap between settlements is expected."}

    vrows = rows_for(VAULT, VAULT_EVENTS, ("assets", "shares", "totalAssets"))
    for r in vrows:
        r["assets"] = r["assets"] or r.pop("totalAssets", "")
    frows = rows_for(FUND, ("Deposit", "Withdraw", "CapitalWithdrawn", "CapitalReturned", "DeployedCapitalReported",
                            "ReportGuardsSet"), ("assets", "shares", "amount", "previous", "current"))
    write_csv(os.path.join(HERE, "data", "vault_events.csv"), vrows,
              ["time_utc", "block", "event", "via", "assets", "shares", "request_id", "tx"])
    write_csv(os.path.join(HERE, "data", "fund_events.csv"), frows,
              ["time_utc", "block", "event", "via", "assets", "shares", "amount", "previous", "current", "tx"])

    # settlement rhythm: NAV proposal -> settlement -> automatic claim
    cycles = []
    for r in vrows:
        if r["event"] == "NewTotalAssetsUpdated":
            cycles.append({"nav_proposed": r["time_utc"], "settled": None, "deposits_settled": "0",
                           "claimed_for_depositors": None})
        elif r["event"] == "TotalAssetsUpdated" and cycles and not cycles[-1]["settled"]:
            cycles[-1]["settled"] = r["time_utc"]
        elif r["event"] == "SettleDeposit" and cycles:
            cycles[-1]["deposits_settled"] = r["assets"]
        elif r["event"] == "Deposit" and r["via"] == "claimSharesOnBehalf" and cycles:
            cycles[-1]["claimed_for_depositors"] = r["time_utc"]
    s = {"run_utc": utc(time.time()), "block": head, "block_time": utc(now), "vault": v, "fund": f,
         "layers_add_up": check, "settlement_cycles": cycles,
         "vault_event_counts": {k: sum(1 for r in vrows if r["event"] == k) for k in sorted({r["event"] for r in vrows})},
         "addresses": {"vault": VAULT, "vault_safe": safe, "pending_silo": SILO, "fund": FUND, "asset": BRL}}
    json.dump(s, open(os.path.join(HERE, "data", "state.json"), "w"), indent=1)
    with open(os.path.join(HERE, "data", "history.jsonl"), "a") as fh:
        fh.write(json.dumps({"run_utc": s["run_utc"], "block": head, "vault_share_price": v["share_price"],
                             "vault_total_assets": v["total_assets"], "pending_in_silo": v["pending_deposits_in_silo"],
                             "fund_share_price": f["share_price"], "fund_idle": f["idle_on_chain"],
                             "fund_deployed": f["deployed_reported"], "fund_report_age_h": f["report_age_hours"],
                             "last_cycle": cycles[-1] if cycles else None}) + "\n")

    log(f"block {head}, {s['block_time']}")
    log(f"LAYER 1  {v['name']} ({v['symbol']}, Lagoon {v['lagoon_version']})")
    log(f"  share price {v['share_price']:.6f} BRL1.p; total assets {v['total_assets']:,.6f}; shares {v['total_shares']:,.6f}; cap {v['max_cap']:,.0f}")
    log(f"  waiting in the pending silo: {v['pending_deposits_in_silo']:,.6f} BRL1.p")
    log(f"  fees (basis points): {v['fee_rates_bps']}; NAV valid now {v['nav_valid_now']}; paused {v['paused']}")
    log(f"  vault Safe holds {v['safe_fund_shares']:,.6f} {f['symbol']} and {v['safe_brl1p']:,.6f} BRL1.p")
    log(f"LAYER 2  {f['name']} ({f['symbol']}, RwaVaultV3)")
    log(f"  share price {f['share_price']:.6f}; total assets {f['total_assets']:,.6f} = idle on-chain {f['idle_on_chain']:,.6f} + deployed (reported) {f['deployed_reported']:,.6f}")
    log(f"  last report {f['reported_at']} ({f['report_age_hours']} h ago); deposits and withdrawals stop if older than {f['max_report_age_hours']:.0f} h; one report may move it at most {f['max_report_change_bps'] / 100:.0f}%")
    log(f"CHECK  vault total assets {check['vault_total_assets']:,.6f} vs Safe position at fund price {implied:,.6f} (difference {check['difference']:+.6f})")
    for c in cycles:
        log(f"  cycle: NAV proposed {c['nav_proposed']}, settled {c['settled']} ({c['deposits_settled']} BRL1.p), shares claimed for depositors {c['claimed_for_depositors']}")
    open(os.path.join(HERE, "runs", f"{stamp}-vault.txt"), "w").write("\n".join(LOG) + "\n")


if __name__ == "__main__":
    main()
