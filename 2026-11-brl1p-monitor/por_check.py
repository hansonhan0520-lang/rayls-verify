#!/usr/bin/env python3
"""Check the token figure in each public BRL1 PoR report against an archive read at the block it names,
from two independent Polygon providers. Output: data/por_check.json and runs/<time>-por.txt"""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import collect as c
REPORTS = [("2025-04-14", 70301795, "5,349,963.000000", "drive_1q6arJKrt3wWta7kYCnppD1awhgzsz8AW.pdf"),
           ("2026-10-01", 94777137, "17,381,384.540000", "drive_1BuRUC6u3UTzf17kOChhKby_L9hE5IU73.pdf")]
out, lines = {"run_utc": c.utc(time.time()), "reports": []}, []
for date, blk, stated, f in REPORTS:
    r = {"report": date, "file": f, "block": blk, "stated_supply": stated}
    for n, url in c.POLY_ARCHIVE.items():
        try:
            r[f"supply_{n}"] = c.fmt(int(c.call(url, c.BRL1, "0x18160ddd", blk), 16))
        except Exception as e:
            r[f"supply_{n}"] = "error " + str(e)[:60]
    r["block_time"] = c.utc(int(c.rpc(c.POLY["tenderly"][0], "eth_getBlockByNumber", [hex(blk), False])["timestamp"], 16))
    r["matches"] = all(r[f"supply_{n}"] == stated for n in c.POLY_ARCHIVE)
    out["reports"].append(r)
    lines.append(f"PoR {date}: block {blk} ({r['block_time']}) stated {stated}, archive {r['supply_drpc']} / {r['supply_tenderly']}, match {r['matches']}")
head = int(c.rpc(c.POLY["tenderly"][0], "eth_blockNumber", []), 16) - 10
out["supply_now"] = c.fmt(int(c.call(c.POLY["tenderly"][0], c.BRL1, "0x18160ddd", head), 16))
out["supply_now_block"] = head
lines.append(f"BRL1 supply now (block {head}): {out['supply_now']}")
json.dump(out, open(os.path.join(c.HERE, "data", "por_check.json"), "w"), indent=1)
open(os.path.join(c.HERE, "runs", time.strftime("%Y-%m-%dT%H%MZ", time.gmtime()) + "-por.txt"), "w").write("\n".join(lines) + "\n")
print("\n".join(lines))
