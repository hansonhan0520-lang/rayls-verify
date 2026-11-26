import sys
sys.path.insert(0, "/mnt/skills/plugins/rayls-rail-quest/scripts")
import brandkit as bk
LOGO = "/mnt/skills/plugins/rayls-rail-quest/assets/logo.png"
rows = [
    ("Zcash", "公链上的隐私池", "账户持有人自己，分享查看密钥（只读不能花）", "已上线", "#3A3A44"),
    ("Canton Network", "各方节点只存自己的数据", "合约设计：把监管方加为观察者", "已上线", "#3A3A44"),
    ("ZKsync Prividium", "机构自营链，只把证明交到以太坊", "运营方，按授权开放给监管", "已上线", "#3A3A44"),
    ("Circle Arc Privacy", "Arc 链，按需开启", "获授权方可被授予访问权限", "2026-06-10 公布，未定稿", "#3A3A44"),
    ("Rayls Enygma Public", "Rayls 公链上的隐私金库", "内置：注册时就把查看密钥副本交给审计方", "测试网试点", bk.PURPLE),
]
y, b = 392, ""
for name, where, who, status, col in rows:
    h = 152
    hi = col != "#3A3A44"
    b += bk.rr(90, y, 900, h, 16, bk.BOX, col, 3 if hi else 2)
    b += bk.text(122, y + 46, name, bk.PURPLE if hi else bk.WHITE, 29, 800)
    b += bk.text(958, y + 46, status, bk.YELLOW if hi else bk.GRAY, 23, 700, "end")
    b += bk.text(122, y + 88, "结算：" + where, bk.WHITE, 23, 400)
    b += bk.text(122, y + 126, "谁决定审计方看什么：" + who, bk.WHITE, 23, 400)
    y += h + 14
bk.render_body(__import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "pp-table.png"),
               title="隐私支付，谁来决定监管能看什么",
               subtitle="大家熟悉的方案 vs Rayls Enygma Public · 2026-11-25",
               body=b, footnote="",
               source="来源：各项目官方文档，链接见文末来源列表",
               logo_path=LOGO)
print("ok", y)
