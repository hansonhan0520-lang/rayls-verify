# Following one deposit through the TokenOne pilot vault · 跟着一笔存款走一遍 TokenOne 试点金库

[English](#english) · [中文](#中文)

---

## English

**Question:** When you put BRL1.p into the Rayls TokenOne pilot vault, where does the money go, when does it turn into vault shares, what sets the share price, and what decides when you can take it out?

**Case:** one real deposit of 4,720.200991 BRL1.p, moved into the vault from the launch programme with the dapp's "Move to vault" button on 2026-11-19 13:39:10 UTC (request id 3). The depositor's address is not published here; `check_my_request.py` lets anyone check their own.

Everything is read-only: public RPC calls and the public explorer API. No wallet, no key. [`.github/workflows/vault-walkthrough-monitor.yml`](../.github/workflows/vault-walkthrough-monitor.yml) runs `vault.py` every 6 hours and once just after the daily settlement, and commits the results, so each run is a dated reading in git history. Depositor addresses and depositor transaction hashes are never written; operator transactions keep their hashes.

### Scripts

| Script | Output | What it answers |
|---|---|---|
| `vault.py` | `data/state.json`, `data/history.jsonl`, `data/vault_events.csv`, `data/fund_events.csv`, `runs/*-vault.txt` | Both layers' current state, every NAV update, request, settlement and claim, the fund's capital moves and value reports, and whether the two layers add up |
| `check_my_request.py 0xYOURADDRESS` | screen only | Your own pending deposit, settled-but-unclaimed amount, shares, and redemption requests |
| `abi/LagoonVault_v0.6.0.json` | | The vault implementation's ABI, saved from the explorer |

### How the money moves (readings 2026-11-18 to 2026-11-19 14:25 UTC)

**Layer 1: the Lagoon vault.** "Rayls Token One 02" (`RLSTKONE02`) at `0x1811630B90e6966573e809270a5e9316A25DE6fe`, a Lagoon v0.6.0 vault (ERC-7540 asynchronous deposits and redemptions on top of ERC-4626). Asset BRL1.p, cap 300,000.

1. *Request.* `moveToVault` (or `requestDeposit`) sends BRL1.p to the vault's pending silo `0xe8CCAd69…5779`. No shares yet; the request can still be cancelled.
2. *Valuation.* Once a day the valuation manager proposes the vault's value (`updateNewTotalAssets`): 2026-11-18 13:00:13 and 2026-11-19 13:00:10 UTC.
3. *Settlement.* Seconds later the vault's Safe settles (`settleDeposit`): the proposed value is applied, pending BRL1.p moves from the silo to the Safe, and shares are minted at that price. On 19 Nov a 1 BRL1.p request made at 12:56:00 was settled at 13:00:16 into 0.999375 shares (1 ÷ 1.000625).
4. *Claim.* 8 seconds later, at 13:00:24, the operator called `claimSharesOnBehalf`, which put the shares in the depositor's wallet. Nobody had to press a claim button.
5. *Investment.* The Safe then deposits the BRL1.p into layer 2 (18 Nov 18:24, 19 Nov 13:00:31 UTC).

A request made after a day's valuation waits for the next one. Request 3 (4,720.200991 BRL1.p, 13:39:10 UTC) came 39 minutes after the 19 Nov valuation; at 14:25 UTC it was still pending, with 99,548.98 BRL1.p in the silo in total.

**Layer 2: the TokenOne fund.** "TokenOne TIDC02" (`TKONE02`) at `0x870c2c4cfAf895f55163385813164E5808AE7029`, an ERC-4626 `RwaVaultV3`, source verified on the Rayls explorer. Its own source comment says: total assets is the idle balance in the contract, which anyone can verify, plus deployed capital, a number reported by an oracle; "that second part is the product's trust assumption and is made explicit here, not hidden".

- Total assets 21.058179 = idle 11.004000 (on-chain) + deployed 10.054179 (reported 2026-11-19 12:11:09 UTC). Share price 1.003681.
- Built-in guards: deposits and withdrawals stop if the last report is older than 24 hours; one report can move deployed capital by at most 10%; only the oracle report moves the price (moving capital out or back does not); withdrawals can only be paid from idle balance; the compliance gate never blocks a redemption.
- The vault's Safe held 10.969870 TKONE02. At the fund's price that is 11.010255 BRL1.p, exactly layer 1's total assets. **The layers add up** (difference 0.000000 at 14:25 UTC).

**Fees and exit.** On-chain fee rates: management 0, performance 0, entry 0, haircut 0, exit 50 basis points (0.5%, matching the announcement). The Lagoon contract has no 60-day timer: a redemption is a request that the Safe settles. The 60 days is the curator's stated rule, and it fits the fund's design: invoices mature in 30 to 60 days, and the fund can only pay out from idle balance.

### Predictions to check (written 2026-11-19 14:30 UTC)

1. Request 3 settles at the next daily valuation, expected around 2026-11-20 13:00 UTC.
2. It becomes about 4,720.2 ÷ (the share price then) shares, about 4,717 at today's price.
3. The shares arrive in the depositor's wallet without a claim click, within a minute of settlement.
4. Afterwards the vault's total assets still equals the Safe's TKONE02 at the fund price plus any idle BRL1.p.

The monitor's 13:25 UTC run on 20 Nov will record the result here.

### Read on-chain vs. not visible

Read directly: every balance, event, time, fee rate, guard setting and the reconciliation above. Not visible on-chain: the invoices themselves, the value behind the oracle's report, the 20% first-loss position, KYC decisions, and when the launch programme's RLS reward is paid.

### Sources

- Rayls explorer API: https://explorer.rayls.com/api/v2
- Lagoon v0.6.0 source (verified on the explorer at implementation `0xd04DeaBa7fD06634764CbFfe140011C69063aC77`)
- TokenOne RwaVaultV3 source (verified at `0x870c2c4cfAf895f55163385813164E5808AE7029`)
- Rayls vault dapp: https://dapp.rayls.com

---

## 中文

**问题：** 把 BRL1.p 存进 Rayls 的 TokenOne 试点金库后，钱去了哪里、什么时候变成金库份额、份额价格由什么决定、什么时候能取出来？

**案例：** 一笔真实存款 4,720.200991 BRL1.p，2026-11-19 13:39:10 UTC 在 dapp 上点"Move to vault"从启动计划转入金库（请求编号 3）。这里不公开存款人地址；任何人都可以用 `check_my_request.py` 查自己的。

全部只读：公开 RPC 和公开的区块浏览器接口，不需要钱包和私钥。工作流 [`.github/workflows/vault-walkthrough-monitor.yml`](../.github/workflows/vault-walkthrough-monitor.yml) 每 6 小时、以及每天结算后跑一次 `vault.py` 并提交结果。不记录任何存款人地址和存款人的交易哈希；运营方的交易保留哈希。

### 钱怎么走（读数 2026-11-18 至 2026-11-19 14:25 UTC）

**第一层：Lagoon 金库。** "Rayls Token One 02"（`RLSTKONE02`），地址 `0x1811630B90e6966573e809270a5e9316A25DE6fe`，Lagoon v0.6.0（在 ERC-4626 上加了 ERC-7540 异步存取）。资产 BRL1.p，上限 30 万。

1. *申请。* `moveToVault`（或 `requestDeposit`）把 BRL1.p 转进金库的待处理仓 `0xe8CCAd69…5779`，此时还没有份额，可以撤回。
2. *估值。* 每天一次，估值账户提交金库总价值（`updateNewTotalAssets`）：11-18 13:00:13、11-19 13:00:10 UTC。
3. *结算。* 几秒后金库的 Safe 结算（`settleDeposit`）：采用这个估值，把待处理的 BRL1.p 从待处理仓转到 Safe，按当时价格铸造份额。11 月 19 日 12:56:00 的一笔 1 BRL1.p 申请，在 13:00:16 结算成 0.999375 份（1 ÷ 1.000625）。
4. *领取。* 8 秒后（13:00:24）运营方调用 `claimSharesOnBehalf`，份额直接进了存款人钱包，不需要自己点领取。
5. *投资。* 之后 Safe 把 BRL1.p 存进第二层（11-18 18:24、11-19 13:00:31 UTC）。

在当天估值之后才提交的申请，要等下一次。请求 3（4,720.200991 BRL1.p，13:39:10 UTC）比 19 日的估值晚 39 分钟；14:25 UTC 时仍在等待，待处理仓里合计 99,548.98 BRL1.p。

**第二层：TokenOne 基金。** "TokenOne TIDC02"（`TKONE02`），地址 `0x870c2c4cfAf895f55163385813164E5808AE7029`，ERC-4626 合约 `RwaVaultV3`，源码已在 Rayls 浏览器验证。源码注释写明：总资产 = 合约里的闲置余额（任何人可验证）+ 已投出的资本（由预言机报告的数字），"第二部分是这个产品的信任前提，在这里明确写出，而不是藏起来"。

- 总资产 21.058179 = 链上闲置 11.004000 + 已投出 10.054179（2026-11-19 12:11:09 UTC 报告）。份额价格 1.003681。
- 内置保护：上一次报告超过 24 小时，存取全部暂停；单次报告最多让已投出资本变动 10%；只有预言机报告会改变价格（资金转出或转回不会）；取款只能从闲置余额支付；合规闸门永远不会挡住赎回。
- 金库的 Safe 持有 10.969870 TKONE02，按基金价格合 11.010255 BRL1.p，正好等于第一层的总资产。**两层账对得上**（14:25 UTC 差额 0.000000）。

**费用与退出。** 链上费率：管理费 0、业绩费 0、申购费 0、折价 0、退出费 50 个基点（0.5%，与公告一致）。Lagoon 合约里没有 60 天的计时器：赎回是一个由 Safe 结算的申请。60 天是管理方公布的规则，也和基金的设计相符：发票 30 到 60 天到期，而基金只能用闲置余额付款。

### 待验证的预测（2026-11-19 14:30 UTC 写下）

1. 请求 3 在下一次每日估值时结算，预计 2026-11-20 13:00 UTC 左右。
2. 换成约 4,720.2 ÷ 届时份额价格 份，按今天价格约 4,717 份。
3. 份额在结算后一分钟内自动到账，不需要点领取。
4. 结算后，金库总资产仍等于 Safe 持有的 TKONE02 按基金价格折算，再加上闲置的 BRL1.p。

11 月 20 日 13:25 UTC 的自动运行会把结果记在这里。

### 链上读取 vs. 看不到的

直接读取：上面所有余额、事件、时间、费率、保护参数和对账。链上看不到：发票本身、预言机报告背后的价值、20% 劣后仓位、KYC 审核，以及启动计划 RLS 奖励的发放时间。

### 来源

见英文部分。
