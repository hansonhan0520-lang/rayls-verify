"""Render the TokenOne article images from the fixed publication data."""
from decimal import Decimal
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.environ.get("BRANDKIT_DIR", "."))
import brandkit as bk

LOGO = os.environ.get("RAYLS_LOGO", "logo.png")
with open(os.path.join(HERE, "..", "data.json"), encoding="utf-8") as f:
    d = json.load(f)

r = d["tkone01_reconciliation"]
num = lambda s: Decimal(s.replace(",", ""))
assert num(r["withdrawn"]) == num(r["burned"]) + num(r["returned"]) + num(r["manager_balance"])
assert d["vault_reconciliation_checks_passed"] is True
block = f'{d["rayls_block"]:,}'
checks = d["vault_reconciliation_checks"]

# Cover: separate the three evidence classes instead of repeating the article.
cards = [
    (
        "链上账本",
        f'{d["debenture_supply_total"]} 枚债券代币',
        "供应量、持有地址、权限与交易",
        bk.PURPLE,
    ),
    (
        "管理方报告",
        "deployedCapital",
        "报告值不等于金库合约余额",
        bk.PURPLE,
    ),
    (
        "链下待证",
        "应收账款与偿付",
        "仍需发行文件和结算记录",
        bk.YELLOW,
    ),
]
W, H, y0, gap, margin = 460, 214, 318, 40, 80
body = ""
for i, (title, big, small, colour) in enumerate(cards):
    x = margin + i * (W + gap)
    body += bk.rr(x, y0, W, H, 18, bk.BOX, colour, 3 if i == 2 else 2)
    body += bk.text(x + 30, y0 + 55, title, colour, 27, 800)
    big_size = 31 if i == 1 else 38
    body += bk.text(x + 30, y0 + 120, big, bk.WHITE, big_size, 800)
    body += bk.text(x + 30, y0 + 174, small, bk.GRAY, 23, 600)

footnote = (
    f'{d["vault_explorer_logs_total"]} 条金库事件｜'
    f'{d["vault_capital_event_rows"]} 条资本事件｜'
    f'{checks}／{checks} 项对账通过'
)
bk.render_cover(
    os.path.join(HERE, "cover.png"),
    title="RWA 上链后，投资人能核对什么？",
    subtitle=f'3 只 TokenOne 债券 + {d["vault_count"]} 个 RwaVaultV3 金库实测｜{d["run_utc"].split()[0]}',
    body=body,
    footnote=footnote,
    logo_path=LOGO,
    title_size=54,
)

# In-body image: the equation closes on-chain, while the last card shows where
# public-chain evidence stops. Every figure comes from the same fixed snapshot.
b = ""
b += bk.rr(90, 430, 900, 160, 20, bk.BOX, bk.PURPLE, 2)
b += bk.text(122, 480, "01｜链上账本", bk.PURPLE, 28, 800)
b += bk.text(122, 540, f'提取 {r["withdrawn"]} {r["asset_symbol"]}', bk.WHITE, 39, 800)
b += bk.text(958, 480, "事件与经理收款匹配", bk.GRAY, 23, 600, "end")

b += bk.rr(90, 625, 900, 315, 20, bk.BOX, bk.YELLOW, 3)
b += bk.text(122, 680, "02｜经理钱包逐笔对账", bk.YELLOW, 28, 800)
b += bk.text(122, 755, f'{r["withdrawn"]} {r["asset_symbol"]}', bk.YELLOW, 48, 800, font=bk.MONO)
b += bk.text(122, 824, f'= 销毁 {r["burned"]}', bk.WHITE, 34, 700)
b += bk.text(122, 878, f'+ 归还 {r["returned"]} + 当前余额 {r["manager_balance"]}', bk.WHITE, 31, 700)
b += bk.text(122, 920, "提取、归还、销毁与 RPC 当前余额闭合", bk.GRAY, 23, 600)

b += bk.rr(90, 975, 900, 150, 20, bk.BOX, bk.PURPLE, 2)
b += bk.text(122, 1025, "03｜链下仍待证明", bk.PURPLE, 28, 800)
b += bk.text(122, 1080, "销毁 ≠ 某笔应收账款已购买", bk.WHITE, 36, 800)
b += bk.text(958, 1025, "公开链无法单独越过这一步", bk.GRAY, 23, 600, "end")
b += bk.text(90, 1268, f'rayls-verify｜固定提交 e9b4786｜{d["run_utc"]}', bk.GRAY, 23)

bk.render_body(
    os.path.join(HERE, "body.png"),
    title="链上证据，到哪一步结束？",
    subtitle="TKONE01 资金流向闭合，不代表链下资产已证明",
    body=b,
    footnote=f'{checks}／{checks} 项对账通过｜快照区块 {block}',
    source="",
    logo_path=LOGO,
    title_size=54,
)

for name, expected in (("cover.png", (3200, 1280)), ("body.png", (2160, 2700))):
    from PIL import Image
    path = os.path.join(HERE, name)
    with Image.open(path) as image:
        assert image.size == expected, (name, image.size)
    print(name, expected, os.path.getsize(path), "bytes")
