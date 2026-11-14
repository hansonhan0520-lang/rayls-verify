#!/usr/bin/env python3
"""Collect the figures the article and its two images quote into data.json, from the files the
other scripts in this folder wrote (latest data/ files, plus every run log in runs/ and every
portal snapshot in raw/portal/ for the history)."""
import glob, json, os, re
H = os.path.dirname(os.path.abspath(__file__))
L = json.load(open(os.path.join(H, "data", "lock_state.json")))
R = json.load(open(os.path.join(H, "data", "roles_state.json")))
P = json.load(open(os.path.join(H, "data", "powers.json")))
T = json.load(open(os.path.join(H, "data", "token_state.json")))
hist = []
for f in sorted(glob.glob(os.path.join(H, "runs", "*-lock.txt"))):
    t = open(f).read()
    m = re.search(r"held ([\d,\.]+) .*?claimed ([\d,\.]+), burned ([\d,\.]+)", t)
    o = re.search(r"now: (\d+) owners .*?, (\d+) admins", t)
    if m and o:
        hist.append({"run": os.path.basename(f)[:16], "held": m.group(1), "claimed": m.group(2), "burned": m.group(3), "owners": int(o.group(1)), "admins": int(o.group(2))})
roles_hist = []
for f in sorted(glob.glob(os.path.join(H, "runs", "*-roles.txt"))):
    t = open(f).read()
    m = re.search(r"holders now: (\{.*\})", t)
    k = re.search(r"locked in the Ethereum adapter: \{'publicnode': '([\d,\.]+)'.*?RLS supply on Rayls ([\d,\.]+)", t)
    if m:
        roles_hist.append({"run": os.path.basename(f)[:16], "holders": json.loads(m.group(1)),
                           "eth_locked": k.group(1) if k else None, "rayls_supply": k.group(2) if k else None})
portal = []
for d in sorted(glob.glob(os.path.join(H, "raw", "portal", "*"))):
    try:
        o = json.load(open(os.path.join(d, "overview.json")))
    except Exception:
        continue
    s = json.dumps(o)
    g = lambda k: (re.search(rf'"{k}": ([\d\.]+)', s) or [None, None])[1]
    portal.append({"snapshot": os.path.basename(d), "totalBurnedRls": g("totalBurnedRls"), "circulatingSupply": g("circulatingSupply"),
                   "trueCirculatingSupply": g("trueCirculatingSupply"), "totalSupply": g("totalSupply")})
data = {
    "lock": {k: L[k] for k in ("block", "block_time", "token", "unlock_count", "first_unlock", "last_unlock", "isFullyFunded",
                               "created_time", "created_tx", "funders", "funding_in", "tranche_amount", "owners_now", "admins_now", "simulations")},
    "lock_total": f"{L['totalAmount'] / 1e18:,.0f}", "lock_held": f"{L['actualBalance'] / 1e18:,.0f}",
    "lock_roles_now": L["roles_now"],
    "mints_5_aug": T["mints"],
    "rayls_rls_roles": R["rayls_role_holders"], "rayls_rls_role_kinds": R["rayls_role_holder_kinds"],
    "powers": P, "rayls_adapter": R["rayls_adapter"], "eth_adapter": R["eth_adapter"], "safe_owners": R.get("safe_owners"),
    "eth_locked": R["eth_locked_in_adapter"]["publicnode"], "rayls_supply": R["rayls_rls_supply"], "bsc_supply": R.get("bsc_rls_supply"),
    "hub_surplus": R.get("hub_locked_minus_rayls_and_bsc"), "eth_total_supply": R["eth_rls_total_supply"]["publicnode"],
    "eth_rls_impl_slot": R["eth_rls_implementation_slot"],
    "history_lock": hist, "history_roles": roles_hist, "history_portal": portal,
}
json.dump(data, open(os.path.join(H, "data.json"), "w"), indent=1)
print(len(hist), "lock runs;", len(roles_hist), "role runs;", len(portal), "portal snapshots")
print(json.dumps({k: data[k] for k in ("lock_total", "eth_locked", "rayls_supply", "bsc_supply", "hub_surplus")}))
print(set(json.dumps(r["holders"], sort_keys=True) for r in roles_hist).__len__(), "distinct role sets")
print([(h["run"], h["held"], h["owners"], h["admins"]) for h in hist])
