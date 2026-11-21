# T12-deep · 把 DSL 原语 9→16、程序长度 4→6 后闭合「主体结论是否加固」

> 日期 2026-11-20。输入：`analyses/tracks/rsi-after/T12-spse/spse.py`、`T12.md`（只读未改）。
> 输出：本目录。证据等级 **B（沙盒内 toy 底物，不外推真实科研 / 真实程序合成 / 定理证明）**。

## 结论先行

**主体结论加固，效应量缩水。** 在 16 原语 / 长度 6 的更难底物上重跑 collision 与 nesurf，(ρ,B) 分区的**方向与符号全部保持**：ρ=1 低预算时 single 在答案端点胜、swarm 在 E/T 端点败、协调税为正；ρ<1 时群体在 E 端点仍以 87.5% 的 seed 胜出（B=64）。**「中等相关迁移红利」在放大难度后仍不成立**：三组 nesurf 的配对差审计全部 `BONUS_NOT_ESTABLISHED`，ρ=1 的增益差 −0.1181（B=128）/ −0.1505（B=512），t≈−15 / −16。代价是效应量整体缩水（税 −42.8%、任务地板 −53.1%、答案端点交叉右移 B≈64→B≈256），所以只能说**方向加固，不能说强度加固**。

## 产物路径清单（均在本目录，相对工作区路径）

| 文件 | 作用 |
|---|---|
| `analyses/tracks/rsi-after/T12-deep/spse_deep.py` | 参数化变体：`--dim` 9→16、`--depth` 4→6、`--max-len` 候选上限、`--tag` 输出命名；带 `--self-test` / `--prove-red` / `--parity` |
| `analyses/tracks/rsi-after/T12-deep/neff_proxy_audit.py` | 从 T12-spse 只读复制的配对差审计器（含 `--self-test`） |
| `analyses/tracks/rsi-after/T12-deep/verify_numbers.py` | 报告 55 个数字的落盘复算闸；带 `--self-test` / `--prove-red` |
| `outputs/collision_c1_d9_l4.json` … `collision_c4_d16_l4.json` | 四组 1120 run 原始记录 + 对应 `*_summary.json` |
| `outputs/collision_c5_d16_l6_bigB.json` | 560 run 预算追赶（B=64/128/256/512） |
| `outputs/nesurf_n1_d9_l4.json`、`nesurf_n2_d16_l6.json`、`nesurf_n3_d16_l6_B512.json` | 2100/2100/840 run 的 ρ 曲面原始记录 |
| `outputs/neff_audit_n1_d9_l4.json`、`neff_audit_n2_d16_l6.json`、`neff_audit_n3_d16_l6_B512.json` | 三组配对差 / Bonferroni 审计结果 |
| `outputs/log_c3.txt`、`log_c4.txt`、`log_c5.txt`、`log_n1.txt`…`log_n3.txt` | 各次运行的控制台留痕 |
| `analyses/tracks/rsi-after/T12-deep/T12-deep.md` | 本报告 |

**未改原件**：`T12-spse/spse.py`、`T12.md`、`neff_proxy_audit.py`（仅复制到本目录）全部保持原样；未写 `SUMMARY.md`，未 git add/commit/push。

## 参数化怎么做的（只动难度轴）

1. 原语库 9→16：前 9 个与原件逐字同序，后 7 个为 `abs/add5/mulmod17/mod3/take2/drop1/sortdesc`；`--dim 9` 时 RNG 消耗序列与原件一致。
2. 真值程序长度 4→6：`--depth` 控制 shared 长度与逐位置 rho 混合的槽数。
3. 候选长度上限 `--max-len`：默认等于 depth，`0` 表示不设上限（=原版行为）。**实测该上限在 B≤256 惰性**：dim9/L4 最大候选长度 3、dim16/L6 最大 5，从未触顶；因此难度提升完全来自「真值更长 + 原语更多」，不来自搜索限制。
4. 不变：rho 语义、prior 噪声数 `round((1-rho)*3)`、稠密逐元素评分、visible/sealed 切分、single/swarm 部署、A/E/T/B1/B2 定义、`_spearman`。

## 仪器自检（必须能红）

| 闸 | 结果 | 证据命令 |
|---|---|---|
| `spse_deep.py --self-test` | **17/17 PASS**（原 T1–T7 语义 + 新 T8–T13 难度轴 + 4 条注入违规） | `python3 analyses/tracks/rsi-after/T12-deep/spse_deep.py --self-test` |
| `spse_deep.py --prove-red` | **4/4 CAUGHT**（重名原语 / 长度越界 / rho=1 语义破坏 / sealed 被污染成 visible） | `python3 analyses/tracks/rsi-after/T12-deep/spse_deep.py --prove-red` |
| `spse_deep.py --parity` | **11/11 PASS**：dim9/L4 下族序列与 prior 逐值一致；3 个 run 的 A/E/T/gain/tax 差 <1e-12 | `python3 analyses/tracks/rsi-after/T12-deep/spse_deep.py --parity` |
| `neff_proxy_audit.py --self-test` | **5/5 PASS**（原件自带闸） | `python3 analyses/tracks/rsi-after/T12-deep/neff_proxy_audit.py --self-test` |
| `verify_numbers.py --self-test` | **55/55 PASS**（tol=5e-4） | `python3 analyses/tracks/rsi-after/T12-deep/verify_numbers.py --self-test` |
| `verify_numbers.py --prove-red` | **CAUGHT**（注入错误期望值必红） | `python3 analyses/tracks/rsi-after/T12-deep/verify_numbers.py --prove-red` |

## 关键数字

### 1. (ρ,B) 分区：四组配置全部同向（40 seeds / cell）

| 配置 | ρ=1,B=8 single 胜 A | ρ=1,B=8 swarm 胜 E | ρ=1,B=8 tax_A | ρ=1,B=16/32 gain_T | ρ=1,B=64 gain_E | ρ<1(0/0.25/0.5/0.75/0.9),B=64 swarm 胜 E |
|---|---|---|---|---|---|---|
| C1 dim9/L4（对照） | 0.725 | 0.00 | +0.1553 | −0.107 / −0.115 | +0.0053 | 0.93 |
| **C2 dim16/L6（目标）** | **0.525** | **0.00** | **+0.0888** | **−0.032 / −0.027** | **−0.0250** | **0.875** |
| C3 dim9/L6（只加长度） | 0.500 | 0.00 | +0.0769 | −0.050 / −0.057 | +0.0006 | 0.905 |
| C4 dim16/L4（只加原语） | 0.675 | 0.00 | +0.2754 | −0.227 / −0.077 | +0.0222 | 0.925 |

读法：ρ=1 且 B≤32 时，四组的 E 与 T 增益全为负、swarm 胜 E 为 0–0.05；ρ<1 在同预算下仍由群体压倒性胜 E。T12 的分区判断**未被放大难度翻转**。效应量确实缩水：C2 相对 C1 的 tax_A 为 0.5718×（−42.8%），任务地板 `E_identity`（空程序在 train 族的可见分）由 0.0578 降到 0.0271（−53.1%）。

### 2. B1 排名迁移与 B2 过拟合：方向同样保持（B=64）

| 配置 | B1(ρ=0) | B1(ρ=0.9) | B1(ρ=1) | gap(ρ=0) | gap(ρ=1) |
|---|---|---|---|---|---|
| C1 | 0.00 | 0.68 | 0.76 | 0.0184 | 0.0297 |
| **C2** | **0.12** | **0.63** | **0.73** | **0.0100** | **0.0284** |

真值越共享，train 上排名越能迁移到 heldout（C2 0.12→0.73）；同时 ρ=1 的 visible−sealed gap 是 ρ=0 的 2.84×（C1 为 1.61×）——「真值一致更容易过拟合可见样例」在更难底物上依旧成立。B1 只说明**迁移可行**，不说明净收益为正（见下）。

### 3. nesurf 审计：「中等相关红利」没有回来

| 配置 | gain_E(ρ=0) | gain_E(ρ=1) | E_single(ρ=0→1) | ρ=1 配对差 vs ρ=0 | t | 逐 seed 胜率 | ρ=0.75 proxy | 判决 |
|---|---|---|---|---|---|---|---|---|
| N1 dim9/L4, B=128 | 0.1832 | +0.0189 | 0.0662→0.3118 | **−0.1643** | −16.26 | 0.06 | 17.17 | `BONUS_NOT_ESTABLISHED` |
| **N2 dim16/L6, B=128** | **0.0952** | **−0.0229** | **0.0374→0.2180** | **−0.1181** | **−15.23** | **0.04** | **17.93** | `BONUS_NOT_ESTABLISHED` |
| N3 dim16/L6, B=512 | 0.1675 | +0.0169 | 0.0391→0.2185 | **−0.1505** | −16.05 | 0.07 | 16.71 | `BONUS_NOT_ESTABLISHED` |

三组均 `PROXY_INVALID=True`（ρ=0.75 代理 17.93 > 16）、`LEVEL_CONFOUND=True`（C2 的 E_single 随 ρ 升 5.83×）、`BONUS_ESTABLISHED=False`；`alpha_bonf=0.05/6=0.0083`，无任何正配对差通过。放大难度后 ρ=1 的崩塌**更强**（B=128 时 gain_E 由 +0.0189 转 −0.0229），而不是出现红利。

### 4. 预算追赶：交叉右移，不是符号反转（C2，20 seeds）

| ρ=1 | B=64 | B=128 | B=256 | B=512 |
|---|---|---|---|---|
| gain_E | −0.0303 | −0.0349 | +0.0021 | +0.0021 |
| swarm 胜 E | 0.00 | 0.10 | 0.10 | 0.10 |

对照 C1 的交叉点 B≈64（gain_E +0.0053），放大难度后要到 B≈256 才追平，且追平幅度仅 +0.0021。**预算必须与难度同口径读**：B=128 的负值是群体预算饥饿，B=512 的微小正值不是多样性突然有价值——同一表里 ρ=0 的 gain_E 在 B=512 达 +0.1964，是 ρ=1 的 ~93 倍。

## 复算命令（全部亚分钟级，本机零 GPU）

```bash
cd analyses/tracks/rsi-after/T12-deep
python3 spse_deep.py --self-test && python3 spse_deep.py --prove-red && python3 spse_deep.py --parity
python3 spse_deep.py --collision --dim 9  --depth 4 --tag c1_d9_l4  --families 8 --budgets 8,16,32,64 --rhos 0,0.25,0.5,0.75,0.9,0.945,1.0 --seeds 40
python3 spse_deep.py --collision --dim 16 --depth 6 --tag c2_d16_l6 --families 8 --budgets 8,16,32,64 --rhos 0,0.25,0.5,0.75,0.9,0.945,1.0 --seeds 40
python3 spse_deep.py --collision --dim 9  --depth 6 --tag c3_d9_l6  --families 8 --budgets 8,16,32,64 --rhos 0,0.25,0.5,0.75,0.9,0.945,1.0 --seeds 40
python3 spse_deep.py --collision --dim 16 --depth 4 --tag c4_d16_l4 --families 8 --budgets 8,16,32,64 --rhos 0,0.25,0.5,0.75,0.9,0.945,1.0 --seeds 40
python3 spse_deep.py --collision --dim 16 --depth 6 --tag c5_d16_l6_bigB --families 8 --budgets 64,128,256,512 --rhos 0,0.25,0.5,0.75,0.9,0.945,1.0 --seeds 20
python3 spse_deep.py --nesurf --dim 9  --depth 4 --tag n1_d9_l4 --seeds 300 --budget 128
python3 spse_deep.py --nesurf --dim 16 --depth 6 --tag n2_d16_l6 --seeds 300 --budget 128
python3 spse_deep.py --nesurf --dim 16 --depth 6 --tag n3_d16_l6_B512 --seeds 120 --budget 512
python3 neff_proxy_audit.py --self-test
for t in n1_d9_l4 n2_d16_l6 n3_d16_l6_B512; do python3 neff_proxy_audit.py --in outputs/nesurf_$t.json --out outputs/neff_audit_$t.json; done
python3 verify_numbers.py --self-test && python3 verify_numbers.py --prove-red
```

## 遗留问题（B 级边界，不外推）

1. **迁移红利的实际对象仍未核**：本轮只证明它在「更大 toy DSL / 更长 toy 程序」里依旧不成立；真实程序合成、定理证明里的跨族迁移是否有净收益，未测。B1 的 0.12→0.73 只能读成「排名可迁移」。
2. **agent 仍不是真实 rsi-agent InnerAgent**：候选搜索是锚点局部搜索，预算 B 是评估次数而非 token/成本；接真实 agent 属于另一轮投入。
3. **sealed 与 visible 同源**（同一 ALL_ROWS 切分），gap 只测「过拟合可见切分」，强度弱于环内/环外 judge 差分；A3 仍只部分在场（无 progress-based spawning）。
4. **B≥256 的饱和读数要谨慎**：C5 在 ρ=1 的 B=256 与 B=512 逐值完全相同（gain_E 都是 +0.0021），是搜索收敛/饱和，不能据此声称预算增益。
5. **候选长度上限惰性**：B≤256 从未触顶；若要把「程序长度 ≤L」真正压到搜索侧，需要换搜索算法或大幅提高预算，本轮未做（收敛纪律，两个轴已够）。
