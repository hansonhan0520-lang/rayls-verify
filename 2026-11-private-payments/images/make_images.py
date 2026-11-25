"""Render the two article images from rayls-verify 2026-11-private-payments/data/ (needs the Rayls brand kit)."""
import json, os, sys
sys.path.insert(0, "/mnt/skills/plugins/rayls-rail-quest/scripts")
import brandkit as bk
LOGO = "/mnt/skills/plugins/rayls-rail-quest/assets/logo.png"
HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "..", "data")
PAY = "0x5a84068136fbc126a59cea8b0dc008ccf95c05de78d906395c3ed1db2190f450"
OUTX = "0x74ea2ef5269beb130229d087b91a2f517815e2b0dd97d0bcf3901da377d12338"
pay = json.load(open(f"{D}/{PAY}.json"))
out = json.load(open(f"{D}/{OUTX}.json"))
reg = json.load(open(f"{D}/registry_check.json"))
users_in_pay = sum(1 for a in pay["addresses"] if a["label"] == "unlabelled")
ok = reg["accounts_read"] - reg["accounts_without_auditor_copy"]

# ---------------- cover
cards = [(f"{users_in_pay} 个", "隐私 USDr 付款里出现的用户地址", bk.YELLOW),
         (f"{ok} / {reg['accounts_read']}", "注册账户都把查看密钥副本交给审计方", bk.YELLOW),
         ("能读不能花", "审计方的权限，也不能冻结", bk.PURPLE)]
W, H, y0, gap, M0 = 460, 214, 318, 40, 80
body = ""
for i, (big, small, col) in enumerate(cards):
    x = M0 + i * (W + gap)
    body += bk.rr(x, y0, W, H, 18, bk.BOX, col if i == 2 else "#2E2E36", 3 if i == 2 else 2)
    body += bk.text(x + 32, y0 + 100, big, col, 56, 800)
    body += bk.text(x + 32, y0 + 166, small, bk.WHITE, 24, 700)
bk.render_cover(os.path.join(HERE, "pp-cover.png"),
                title="隐私稳定币支付，监管还能审计吗？",
                subtitle="How can I make private stablecoin payments that regulators can still audit?",
                body=body, footnote="Rayls Enygma Public 测试网试点 · 只读核查 · 2026-11-25",
                logo_path=LOGO, title_size=52)

# ---------------- body: who sees what, for one shielded USDr payment
y, b = 392, ""
def box(y, title, col, lines):
    h = 96 + 38 * (len(lines) - 1) + 32
    dim = col == "#3A3A44"
    s = bk.rr(90, y, 900, h, 16, bk.BOX, col, 2 if dim else 3)
    s += bk.text(122, y + 46, title, bk.WHITE if dim else col, 29, 800)
    for i, (k, v, c2) in enumerate(lines):
        s += bk.text(122, y + 94 + i * 38, k, bk.WHITE, 25, 700)
        s += bk.text(958, y + 94 + i * 38, v, c2, 25, 800, "end")
    return s, h + 16
for title, col, lines in [
    ("公众：区块浏览器上看到的", "#3A3A44", [
        ("付款发生了，提交者是中继器", "看得到", bk.GRAY),
        ("1 个作废标记 · 2 个承诺值 · 2 条加密票据", "看得到", bk.GRAY),
        ("付款人 · 收款人", f"用户地址 {users_in_pay} 个", bk.YELLOW),
        ("金额", f"转账记录 {len(pay['token_transfers'])} 条", bk.YELLOW)]),
    ("审计方（据 Rayls 文档）：用托管的查看密钥解密", bk.PURPLE, [
        ("谁付给谁 · 金额 · 代币", "读得到", bk.PURPLE),
        ("转走或冻结资金", "做不到", bk.PURPLE),
        ("测试网上的审计方", "Rayls", bk.WHITE)]),
    ("对照：取出（unshield）是公开的", "#3A3A44", [
        ("收款地址", "看得到", bk.GRAY),
        ("金额", f"{out['token_transfers'][0]['amount']:.2f} USDr", bk.GRAY)]),
    (f"注册合约：{reg['accounts_read']} 个账户逐个核查", bk.YELLOW, [
        ("交给审计方的查看密钥副本", f"{ok} / {reg['accounts_read']}", bk.YELLOW),
        ("每份 ML-KEM-768 密文", f"{reg['auditor_copy_sizes_bytes'][0]['ml_kem_ct']:,} 字节", bk.WHITE)])]:
    s2, dy = box(y, title, col, lines)
    b += s2
    y += dy
bk.render_body(os.path.join(HERE, "pp-body.png"),
               title="一笔隐私 USDr 付款，谁看到了什么",
               subtitle="Rayls 测试网 · 交易 0x5a84…f450 · 2026-11-24",
               body=b, footnote="",
               source="rayls-verify · 2026-11-private-payments · check_shielded_tx.py, registry_check.py",
               logo_path=LOGO)
print("ok", y)
