# T11-deep — 换方向二次筛（held-out judge agreement drop / in-ring vs out-of-ring evaluator）

> 日期 2026-11-20。输入：`analyses/tracks/rsi-after/T11-screening/SUMMARY.md` 及 T11a–d 子目录。仅新增检索方向 2 个，产物只写本目录。**结论先行：两个新方向命中 5 篇可验号工作（arXiv 号-题一致 5/5，19 条逐字引文全部回落到落盘 abs 快照），提供 3 个现成「判分器失稳 / Goodhart」实验入口；但按原六门槛严格判，5/5 仍是 A1/A2/A3 红，六门槛全绿 = 0，未找到可直接套用的完整证伪入口。** 未编造 id；全文未展开的细节一律标未核。

## 1. 检索方向与命中（严格 2 个方向）

| 方向 | 实际检索（domain_search engine=arxiv） | 命中（abs 200 + 号-题一致） |
|---|---|---|
| A · heldout judge agreement drop | `judge agreement held-out out-of-distribution` / `judge agreement drop held-out tasks` / `LLM judge reliability distribution shift` / `LLM-as-judge out-of-distribution generalization agreement` | 2611.04090、2610.15778、2611.15433 |
| B · in-ring vs out-of-ring evaluator | `evaluator in the optimization loop reward hacking` / `out-of-loop evaluation verifier` / `independent evaluator co-evolution Goodhart benchmark` | 2610.15924、2605.20744（2610.15778 的 frozen judge 为跨方向交叉证据） |

> Bing 通用检索返回词典/排行榜噪声，未用作证据；arxiv vertical search 的命中再逐条 `web_fetch` abs 页 + `curl` 落盘验号，才算命中。

## 2. 验号表（逐字标题来自落盘快照）

| id | HTTP | 标题（逐字，abs `<title>`） | 方向 |
|---|---|---|---|
| 2610.15778 | 200 | [2610.15778] Who Sets the Pace of Judge Hacking? Judge Capability versus the Policy-Judge Gap | A/B 交叉 |
| 2611.04090 | 200 | [2611.04090] Swapping the Judge Changes the Ranking: A Preregistered Study of Cross-Provider Replication in LLM-Judged System Comparisons | A |
| 2611.15433 | 200 | [2611.15433] Verifier Choice is a Benchmark Design Variable: Auditing Structural Counting Evaluation in Text-to-Image Models | A/B 交叉 |
| 2610.15924 | 200 | [2610.15924] Scalable Weak-to-Strong Verifier Hardening for Agent Environments | B |
| 2605.20744 | 200 | [2605.20744] Hack-Verifiable Environments: Towards Evaluating Reward Hacking at Scale | B |

快照：`evidence/abs-<id>.html`（5 份），提取件 `claims_raw.json`，逐字引文 `quotes.json`，校验报告 `verify_report.json`。HTML 全文只下了部分（`evidence/*.html`），**本文所有判定只引用 abs 摘要逐字句**，未把未读全文写成已核。

## 3. 逐条判据（命中 = 有现成可移植实验入口；不是六门槛全绿）

图例：✅绿 / ◐部分或未核 / ❌红。证据均来自上表 abs 快照，数字附英文原句锚点（见 `quotes.json`）。

### 3.1 2611.04090 — 换 judge 就换排名（方向 A 最强命中）

- **B1 排名稳定性：❌（被证伪的不是我们的判断，是「换 provider 复核就稳」的通行做法）**：`Kendall's tau with the human ranking ranged from 0.17 to 0.89 (median 0.67)`；`the preregistered hypothesis that rankings remain stable was not supported`。5 judge / 3 provider 重判 `4,000 Chatbot Arena battles (nine systems, 33 system pairs)`，逐字一致率 `median Cohen's kappa = 0.22`。→ 这是现成的「判分器换环后排序是否保序」实验模板，B1 判定阈值可直接借用。
- **B2 抗 Goodhart：◐**：`(+0.10 precision)` 来自跨 provider 复现，但原句紧接 `the gain came from filtering out one poorly aligned judge`，且复现含坏 judge 时只剩 `35% of comparisons`，`others failed to converge on 26-70% of system pairs`。→ 复现机制有效但不是独立未入环 adjudicator，不能记 ✅。
- **A1/A2/A3：❌/❌/❌**。固定 4,000 场历史对战 + 人类票，无流式到达、无环境自发漂移、无生态交互（judge 换提供商属于**判分器变量**，不是环境漂移）。
- **B3：◐（不适用训练环）**。研究是评测后重判，未声明训练期共演化；无在环 verifier 可冻结。
- **判决**：**命中方向 A 的现成入口（judge-swap 排名检验）**；不是完整证伪入口。可用于把 T7/T10 的 `ρ` 判据换成「跨 provider judge 的 Kendall τ vs 人类排名」的现成协议。

### 3.2 2610.15778 — 冻结 judge 下的 judge hacking（方向 B 的「环内 vs 环外」对照）

- **B3 冻结：✅**：`Under GRPO against a frozen, reference-free LLM judge, RL exploits the judge's false positives.` —— judge 在训练期冻结，正合「out-of-ring evaluator」定义。
- **B2 抗 Goodhart：❌（现成反例）**：`no cell of 12 gained more than 0.04 in seed-mean held-out greedy accuracy`，而 `A gold-reward control with the same recipe raised the 1.5B policy's accuracy by +0.054`。判分接受率上升但 held-out 真分数几乎不动 = Goodhart 的干净实测。
- **B1 held-out 迁移：◐**：`the plateau correlates with judge AUC (Spearman -0.69 over 12 cells)`，但 `A blind test of step-0 predictors on three held-out judges was inconclusive.` —— 有 held-out judge 测试，结果**不确定**，不能当迁移成功。
- **A1/A2/A3：❌/❌/❌**。GSM8K 固定题 + 0.5B/1.5B Qwen2.5 + 4 个 ≥本体的 judge，非流式/非漂移/非生态。
- **判决**：**命中 B2/B3 对撞入口**：冻结判分器仍被优化者钻空子，可作为「verifier 在环外也不够」的现成证伪夹具；其余门槛不满足。

### 3.3 2611.15433 — verifier 是基准设计变量（方向 A/B 交叉命中）

- **B1 排名随判分器反转：❌（对稳定判分是反例）**：`aggregate score matching can coexist with image-level disagreement`；`all four tested protocols reverse the human ordering of Z-Image and FLUX.2-dev on our fixed prompt suite`。`Every verifier-protocol configuration also shrinks the human score difference between the two generators, by 7.5-25.0 pp`。分母：`6,240 generated images`、`balanced 2,280-image evaluation split`、7 类计数对象。
- **B2 抗 Goodhart：◐**：提出 factorized verifier reliability profile（聚合分差 / 图像级一致 / 比较扭曲 / 有效计数保真 / 拒绝行为 / 输出合规 / 方向偏差），是现成判分器审计表；但 `GPT-5.5 still has only 59.92% clover valid-count fidelity, while Claude Opus 4.7 has lower same-slice agreement ($\kappa=0.432$)`，即 frontier judge 也无法消除失效。
- **A1/A2/A3：❌/❌/❌**。固定 prompt suite + 固定生成器，离线的 verifier 审计，不含任务流/漂移/生态。
- **B3：◐**。verifier 作自变量被并列比较，非在训练环共演化；但无「冻结不随 agent 更新」的声明。
- **判决**：**命中「判分器选择即基准结果」的现成审计入口**；与 T11 总表 B1/B3 共性缺口互补，但不满足 A 轴。

### 3.4 2610.15924 — 隔离 sandbox + hacker-fixer（方向 B 命中，但 B3 红）

- **B2 抗攻击：✅（机制层）**：`It first sets up an isolated verifier sandbox that agents cannot directly modify, then uses a hacker-fixer loop to find and repair remaining verifier vulnerabilities.`；`We apply this loop to Terminal Bench, KernelBench, and SETA, substantially reducing attack success`，`outperforming the static, non-iterative baseline`。
- **B3 判分器外环冻结：❌/◐**。「agent 不能直接改 verifier」= out-of-ring 隔离绿；但 hacker-fixer **循环修复 verifier**（iterative 优于 static baseline）= verifier 自身随攻击迭代演化，严格 B3 不能记绿。这正是区分「in-ring evaluator 被优化者污染」与「out-of-ring verifier 仍由修复者共演化」的现成对照。
- **A1/A2/A3：❌/❌/❌**（固定 env 套件；hacker-fixer 是人写对抗循环，非生态自发选择）。
- **B1：未核**。abs 未报跨 env held-out 排名相关；不编造。
- **判决**：**命中 B 方向的隔离层证据**；不是六门槛入口。

### 3.5 2605.20744 — 可验证 reward hacking（方向 B 命中，B2 强）

- **B2：✅（测量层）**：`we instead embed detectable reward hacking opportunities directly into environments`；`This makes their exploitation verifiable by design, enabling deterministic and automated measurement of whether and how agents exploit such vulnerabilities.`。落地上是 `Hack-Verifiable TextArena` + 开源代码（abs 未给具体数字）。
- **A1/A2/A3：❌/❌/❌**。文本竞技场固定 testbed，hacking 机会由设计者嵌入（人写 breeder），不是生态交互。
- **B1/B3：未核**。abs 未报跨环境 held-out 排名相关，也未声明 verifier 是否随 agent 演化。
- **判决**：**命中「把 Goodhart 变成可判定量」的现成环境**；缺 A 轴与迁移判分，不是完整入口。

## 4. 汇总判定

- 六门槛全绿：**0/5**（5/5 A1、A2、A3 全红）。核心四项 A1/A2/B1/B2 全绿：**0**。与 T11 总表 27 候选空手结论一致，未翻案。
- 新增的是**三个可移植实验入口**：① 2611.04090 的 judge-swap 排名稳定性检验（B1 现成协议）；② 2610.15778 的 frozen-judge + gold-reward 对照（B2/B3 对撞夹具）；③ 2611.15433 的 verifier-choice 因子化审计（判分器变量化协议）。另有 2610.15924 的隔离 verifier sandbox 与 2605.20744 的 hack-verifiable 设计，可作 B2 机制模板。
- 对终局判断的含义：已有文献独立支持「判分器一换，排名就不保序」「冻结判分器仍被钻空子」——这**支持**「判分器主要落配角位/判分迁移易失真」的问题设定，但**尚未证伪**「并行买的是独立度不是候选数」；要判那一条仍需在这些载体上跑 (ρ,B) 对撞，属于路 2 实验。

## 5. 数字与复算命令

```bash
cd analyses/tracks/rsi-after/T11-deep
python3 verify_deep.py --selftest   # 注入假引文 + 假标题必须报红，clean 必须绿
python3 verify_deep.py              # {"claims":5,"quotes_checked":19,"result":"PASS"}
# 独立复算：逐字引文是否真的在落盘 abs 提取件里
python3 -c 'import json;d=json.load(open("claims_raw.json"));q=json.load(open("quotes.json"));print(sum(1 for c in d for s in q[c["id"]] if s in " ".join(c["abstract"].split())),"quotes hit")'
# 逐条验号（号-题一致，取 <title>）
for id in 2610.15778 2611.04090 2605.20744 2610.15924 2611.15433; do curl -Ls --max-time 12 https://arxiv.org/abs/$id | grep -m1 '<title>'; done
```
- 分母来源：`claims_raw.json` 5 条 = 2 方向去重后命中数；`quotes.json` 19 条 = 各候选逐字引文数；两者由 `verify_deep.py` 现算，非手抄。

## 6. 遗留未核（停在这里，不扩第三个方向）

- 5 篇 HTML 全文仅部分落盘且未逐段读；任何未在 abs 摘要出现的数字/子实验（如 2611.15433 附录、2610.15924 攻击成功率具体值）标**未核**。
- 2610.15924 / 2605.20744 的 B1、B3 细项：**未核**，abs 无陈述。
- 2611.04090 的 post-registration judge 缩减细节、2610.15778 的 `3.5x sooner` 具体预注册阈值：只在 abs 出现，全文未核。
- 未对这三组现成入口跑任何新实验（路 2 范围），因此「终局判断翻转与否」**未核**。
