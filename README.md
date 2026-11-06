# rayls-verify

[English](#english) · [中文](#中文)

---

## English

Reproducible on-chain checks behind my articles about Rayls.

Each article gets its own folder named `YYYY-MM-topic`. A folder contains the script that produced the numbers, the data file the article and its images were built from, and the raw evidence (run logs and explorer screenshots) with timestamps. Articles link to a specific commit of this repository, so what you see at that link is exactly what was run.

Every script here is read-only. It only sends `eth_call` and log queries to public RPC endpoints and explorer APIs. It needs no wallet, no private key and no API key.

### Index

| Date | Question | Folder | Article |
|---|---|---|---|
| 2026-11-06 | Is one snapshot enough to trust a bridged stablecoin's "1:1"? Every transfer paired by LayerZero GUID, a merged timeline, recovered DVN signers, checks every 6 hours (BRL1.p follow-up) | [`2026-11-brl1p-monitor`](2026-11-brl1p-monitor/) | Binance Square |
| 2026-10-17 | How can an ordinary user verify a bridged stablecoin's "1:1 backing"? (BRL1.p on Rayls) | [`2026-10-brl1p-backing`](2026-10-brl1p-backing/) | [Binance Square](https://www.binance.com/zh-CN/square/post/378201716555838) · [X thread](https://x.com/hanson0520/status/2111378823787016491) |
| 2026-10-08 | How much compute does one zero-knowledge private transfer need? (Rayls Enygma prover) | separate repo: [`enygma-bench`](https://github.com/hansonhan0520-lang/enygma-bench) | Binance Square |

### Ground rules

- Numbers in an article come from one recorded run, saved in that folder's `evidence/` with its UTC timestamp. Live values move after that.
- What was read on-chain and what is my inference are labelled separately in each folder's README.
- Nothing here is investment advice.

---

## 中文

这里存放我写 Rayls 相关文章时用到的链上核查工具和证据，任何人都可以复现。

每篇文章一个文件夹，按 `年-月-主题` 命名。文件夹里有三类东西：产出文章数字的脚本；文章和配图共用的数据文件；带时间戳的原始证据，包括运行日志和区块浏览器截图。文章引用的是本仓库某一次提交（commit）的固定链接，所以你打开链接看到的，就是我当时实际运行的那一版。

这里所有脚本都是只读的，只向公共 RPC 节点和浏览器接口发送 `eth_call` 和日志查询，不需要钱包、私钥或 API 密钥。

### 目录

| 日期 | 问题 | 文件夹 | 文章 |
|---|---|---|---|
| 2026-11-06 | 跨链稳定币的"1:1"，查一次够吗？用 LayerZero 消息编号逐笔对账、两链合并时间线、还原验证方签名人，每 6 小时自动复查（BRL1.p 后续） | [`2026-11-brl1p-monitor`](2026-11-brl1p-monitor/) | 币安广场 |
| 2026-10-17 | 跨链桥稳定币说"1:1 背书"，普通人怎么自己验证？（以 Rayls 上的 BRL1.p 为例） | [`2026-10-brl1p-backing`](2026-10-brl1p-backing/) | [币安广场](https://www.binance.com/zh-CN/square/post/378201716555838) · [X 线程](https://x.com/hanson0520/status/2111378823787016491) |
| 2026-10-08 | 一笔零知识隐私转账需要多少算力？（Rayls Enygma 证明器） | 独立仓库：[`enygma-bench`](https://github.com/hansonhan0520-lang/enygma-bench) | 币安广场 |

### 约定

- 文章里的数字都来自一次有记录的运行，日志存在对应文件夹的 `evidence/` 里，并标注 UTC 时间。链上数值之后会变化。
- 每个文件夹的 README 会分开写明：哪些是链上直接读出的，哪些是我的推断。
- 本仓库内容不构成投资建议。
