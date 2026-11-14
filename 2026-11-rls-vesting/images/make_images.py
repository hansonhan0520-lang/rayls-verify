"""Render the two article images from ../data.json (rayls-verify 2026-11-rls-vesting)."""
import json, os, sys
# needs brandkit.py (Rayls brand helper) and the official logo; neither is in this repo
sys.path.insert(0, os.environ.get("BRANDKIT_DIR", "."))
import brandkit as bk
LOGO = os.environ.get("RAYLS_LOGO", "logo.png")
HERE = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(os.path.join(HERE, "..", "data.json")))
OUT = HERE

# ---------------- cover
cards = [(d["lock_total"], "枚 RLS 锁仓余额，一枚不少", bk.YELLOW, 50),
         ("提前 1 秒", "也取不出，48 个解锁日写死", bk.YELLOW, 56),
         ("1 把钥匙", "可销毁被锁的币，也能增发和升级", bk.PURPLE, 56)]
W, H, y0, gap, M0 = 460, 214, 318, 40, 80
body = ""
for i, (big, small, col, sz) in enumerate(cards):
    x = M0 + i * (W + gap)
    body += bk.rr(x, y0, W, H, 18, bk.BOX, col if i == 2 else "#2E2E36", 3 if i == 2 else 2)
    body += bk.text(x + 32, y0 + 100, big, col, sz, 800)
    body += bk.text(x + 32, y0 + 166, small, bk.WHITE, 26, 700)
bk.render_cover(f"{OUT}/rls-lock-cover.png",
                title="代币锁仓，怎么在链上自己查？",
                subtitle="Parfin 的 10.7 亿枚 RLS 锁仓，从合约查到代币和跨链桥 · 2026-11-14",
                body=body, footnote="锁仓合约、被锁的代币、跨链桥，三层逐一核对 · 代码与每 6 小时的读数全部公开",
                logo_path=LOGO, title_size=54)

# ---------------- body: three layers
sims = d["lock"]["simulations"]
pw = d["powers"]
layers = [
    ("第一层 · 锁仓合约", "RlsTokenLock，不可升级", bk.YELLOW, [
        ("管理员现在取款", "被拒"),
        ("拨到解锁日前 1 秒", "被拒"),
        ("拨到 2027-12-01 当天", "取出 22,301,948.65"),
        ("3 个所有者、5 个管理员", "全是单签钱包"),
    ]),
    ("第二层 · 被锁的 RLS", "Rayls 上的代币，可升级", bk.PURPLE, [
        ("单签钱包 0x0e30…3161", "握有全部 5 种权限"),
        ("销毁锁仓合约里的 1 枚", "成功"),
        ("新铸 1 枚", "成功"),
        ("升级代币合约", "成功"),
    ]),
    ("第三层 · 以太坊和跨链桥", "6 人多签，至少 4 人签", bk.YELLOW, [
        ("以太坊锁着", d["eth_locked"].split(".")[0]),
        ("Rayls + BSC 发行", f"{float(d['rayls_supply'].replace(',', '')) + float(d['bsc_supply'].replace(',', '')):,.0f}"),
        ("多出", f"{float(d['hub_surplus']):,.2f} 枚"),
    ]),
]
y = 410
b = ""
for title, sub, col, rows in layers:
    h = 64 + 40 * len(rows) + 16
    b += bk.rr(90, y, 900, h, 18, bk.BOX, col, 3)
    b += bk.text(122, y + 50, title, col, 32, 800)
    b += bk.text(958, y + 50, sub, bk.GRAY, 24, 700, "end")
    yy = y + 92
    for k, v in rows:
        bad = v in ("成功",) or "全部" in v or "单签" in v
        b += bk.text(122, yy, k, bk.WHITE, 26, 700)
        b += bk.text(958, yy, v, bk.PURPLE if bad else (bk.YELLOW if v in ("被拒",) or "取出" in v else bk.WHITE), 26, 800, "end")
        yy += 40
    y += h + 18
bk.render_body(f"{OUT}/rls-lock-body.png",
               title="锁住了，但锁的是什么？",
               subtitle="用模拟交易逐项试过，2026-11-14 读数",
               body=b,
               footnote="模拟交易只在节点上试算，不上链；结果是能力，不是意图。",
               source="rayls-verify · 2026-11-rls-vesting · lock.py / powers.py / roles.py",
               logo_path=LOGO)
print("ok", y)
