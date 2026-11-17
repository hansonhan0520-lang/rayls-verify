# Submission description

## English

What can investors actually verify on-chain after a real-world asset is tokenised? This original Chinese Binance Square article answers the question through a read-only audit of three TokenOne debenture tokens and four verified `RwaVaultV3` contracts on Rayls. At the fixed snapshot of 2026-11-17 09:23 UTC and Rayls block 14,661,584, I checked 35,000,000 debenture tokens, paginated 343 vault events, decoded 164 capital events and reconciled 38 manager asset transfers, with all 21 accounting checks passing. The article separates direct contract evidence from `ORACLE_ROLE`-reported `deployedCapital` and off-chain receivables, demonstrates the exact TKONE01 identity of 123,677.784998 BRLT withdrawn equals 123,657.78 burned plus 20 returned plus 0.004998 remaining, and checks TokenOne's CVM platform registration against its own issuance-exemption disclosure. Sources include Rayls, TokenOne, CVM and the Rayls explorer. Fixed public commit `e9b47866d57d4b5c30d5eae4bafbd8e158230466` contains the snapshot, reproduction scripts, run logs and transaction-level CSVs.

## 中文意思

RWA 上链后，投资人究竟能在链上核对什么？这篇原创中文币安广场文章，通过只读核查 Rayls 上的三只 TokenOne 债券代币和四个已验证的 `RwaVaultV3` 合约回答这个问题。在 2026-11-17 09:23 UTC、Rayls 区块 14,661,584 的固定快照中，我核查了 35,000,000 枚债券代币，分页读取 343 条金库事件，解码 164 条资本事件，并逐笔对账 38 条经理资产转账，21 项会计检查全部通过。文章区分了合约直接证据、`ORACLE_ROLE` 报告的 `deployedCapital` 与链下应收账款，展示了 TKONE01 的精确等式：提取 123,677.784998 BRLT，等于销毁 123,657.78、归还 20 和剩余 0.004998 之和；同时把 TokenOne 的 CVM 平台注册记录与其官网的发行豁免说明交叉核对。来源包括 Rayls、TokenOne、CVM 和 Rayls 浏览器。固定公开提交 `e9b47866d57d4b5c30d5eae4bafbd8e158230466` 包含快照、复现脚本、运行日志和逐笔 CSV。
