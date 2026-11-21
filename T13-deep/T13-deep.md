# T13-deep｜N 推到 64 + bootstrap CI：rate 单调下降延续，过闸率触顶

> 轨道：`analyses/tracks/rsi-after/T13-deep/`
> 产物：`proposer_diversity_deep.py`（扩展仪器）、`deep.json`（60 行原始 + 汇总 + bootstrap CI + 判决）、`selftest.log`、`run.log`、本文
> 证据等级：A（本轮 CPU 实跑 46.52 s，数字可从 `deep.json` 重算）
> 日期：2026-11-20

## 0. 结论先行

**判决 = ROBUST_CONT**：T13.md 第 7 节的两条局限（未测 N>16、3 seeds 无 CI）都已闭合。N 从 16 推到 32/64 后，四档提案器的 rate 仍严格下降：rate(64)/rate(16) 点估计 0.252–0.283，1000 次 bootstrap 的 95% CI 上界最大 0.308（远离 1）；CI(rate64) 上界 < CI(rate16) 下界 4/4 成立，无 FLIP。

**pass rate 转折**：按预注册判据，single-small / single-large / structured 的转折点 N=16（点估计仍小升但差值 CI 含 0；structured 16→32 差值 CI 为 [-0.056, +0.250]）；multi-anchor 的转折点 N=32（16→32 +0.111，CI [+0.028, +0.222] 显著；32→64 差值 0，触顶）。候选级过闸率在 N≥16 后基本平（multi-anchor 0.160→0.164，structured 0.108→0.099），所以「过闸概率上升」指的是「每代至少中一个」的覆盖率，不是候选质量变好。

机制仍成立：Δ_priv 从 N=16 到 64 的四档点估计变化为 +0.0033 / +0.0010 / +0.0567 / +0.0315，而验证费分母涨 4×；multi-anchor 与 structured 的 32→64 增量虽显著（CI [+0.0036, +0.0470]、[+0.0007, +0.0248]），远不足以抵消 4×。

## 1. 设计与预注册判据

- 复用 `T13-proposer-diversity/proposer_diversity.py` 的 propose / pearson / mean_pairwise_rho 与 rsi_agent 的 gates/tasks，不改 rsi-agent 源码；只加速 evaluator（与 `ContextualTask.evaluate` 逐位一致，self-test T3 断言）。
- 网格：modes = single-small / single-large / multi-anchor / structured，N = 1,4,16,32,64，seeds = 1,2,3，gens = 12，共 60 臂；bootstrap B = 1000，seed 固定 20261120。
- 重采样单位 = (seed, gen)，按 seed 分层（3 组 × 12 代 = 36 单位/格）；CI = 2.5% / 97.5% 分位数，并强制包含点估计（记录 clamped；本轮 0 处 clamp）。
- 两个「过闸率」严格区分：`promo_rate` = promoted/gens（T13.md 主表口径，每代至少一候选过闸）；`cand_pass_rate` = PASS/(gens·N·seeds)（候选级口径；T13.md 第 8 节把前者误标为「候选过闸率」，这里不沿用该标签）。
- 执行前钉死：`RATE_MONO_CONT(mode) = rate64 < rate32 < rate16 且 CI(rate64).hi < CI(rate16).lo`；`FLIP(mode) = CI(rate64).lo > CI(rate16).hi`；`PASS_TURN(mode)` = 从 N=16 起首个「该步差值 CI 含 0 且其后所有差值 CI 亦含 0」的起点 N。`ROBUST_CONT` 当且仅当 4/4 mode 满足 RATE_MONO_CONT 且无 FLIP。

## 2. 主表（3 seeds 点估计 + 95% bootstrap CI）

| 提案器 | N | ρ̄ [95% CI] | rate/1k [95% CI] | promo_rate | cand_pass_rate | Δpriv |
|---|---:|---:|---:|---:|---:|---:|
| single-small | 1 | 1.0000 [1.000, 1.000] | 32.682 [30.265, 35.295] | 0.7500 | 0.7500 | 0.3922 |
| single-small | 4 | 0.8777 [0.825, 0.924] | 10.017 [9.750, 10.259] | 0.9722 | 0.8611 | 0.4808 |
| single-small | 16 | 0.8584 [0.799, 0.907] | 2.605 [2.565, 2.635] | 1.0000 | 0.8264 | 0.5002 |
| single-small | 32 | 0.8609 [0.802, 0.912] | 1.310 [1.295, 1.322] | 1.0000 | 0.8299 | 0.5031 |
| single-small | 64 | 0.8909 [0.832, 0.937] | 0.660 [0.654, 0.663] | 1.0000 | 0.8720 | 0.5065 |
| single-large | 1 | 1.0000 [1.000, 1.000] | 28.616 [25.300, 31.984] | 0.6667 | 0.6667 | 0.3434 |
| single-large | 4 | 0.8813 [0.820, 0.933] | 10.169 [9.905, 10.388] | 1.0000 | 0.8958 | 0.4881 |
| single-large | 16 | 0.9098 [0.857, 0.952] | 2.634 [2.610, 2.649] | 1.0000 | 0.8976 | 0.5058 |
| single-large | 32 | 0.8987 [0.845, 0.940] | 1.324 [1.317, 1.328] | 1.0000 | 0.8750 | 0.5083 |
| single-large | 64 | 0.9049 [0.851, 0.947] | 0.663 [0.662, 0.664] | 1.0000 | 0.8776 | 0.5093 |
| multi-anchor | 1 | 1.0000 [1.000, 1.000] | 35.108 [19.249, 37.505] | 0.2778 | 0.2778 | 0.4213 |
| multi-anchor | 4 | 0.5364 [0.507, 0.565] | 9.049 [8.273, 9.676] | 0.4167 | 0.1736 | 0.4343 |
| multi-anchor | 16 | 0.5203 [0.509, 0.532] | 2.229 [2.056, 2.379] | 0.8889 | 0.1597 | 0.4280 |
| multi-anchor | 32 | 0.5210 [0.512, 0.529] | 1.196 [1.138, 1.244] | 1.0000 | 0.1615 | 0.4593 |
| multi-anchor | 64 | 0.5204 [0.514, 0.526] | 0.631 [0.617, 0.643] | 1.0000 | 0.1645 | 0.4847 |
| structured | 1 | 1.0000 [1.000, 1.000] | 28.317 [0.000, 28.573] | 0.0833 | 0.0833 | 0.3398 |
| structured | 4 | 0.5239 [0.492, 0.559] | 8.320 [6.600, 9.309] | 0.3889 | 0.1111 | 0.3993 |
| structured | 16 | 0.5377 [0.521, 0.556] | 2.375 [2.270, 2.469] | 0.8333 | 0.1076 | 0.4559 |
| structured | 32 | 0.5389 [0.527, 0.550] | 1.236 [1.210, 1.263] | 0.9167 | 0.1016 | 0.4746 |
| structured | 64 | 0.5325 [0.525, 0.541] | 0.635 [0.627, 0.643] | 0.9722 | 0.0985 | 0.4875 |

N=1 的 ρ̄=1 是仪器退化值；structured N=1 的 rate CI 下界 0，因为多数重采样中没有任何 seed 出现 promotion（点估计本身仍是 28.317）。N=16/32/64 的 CI 都稳定。

## 3. rate 单调下降是否延续：是，4/4

| 提案器 | rate N=16 | rate N=32 | rate N=64 | rate64/rate16 | 比值 95% CI | RATE_MONO_CONT |
|---|---:|---:|---:|---:|---:|---|
| single-small | 2.605 | 1.310 | 0.660 | 0.2531 | 0.2531 [0.2495, 0.2575] | 是 |
| single-large | 2.634 | 1.324 | 0.663 | 0.2517 | 0.2517 [0.2501, 0.2542] | 是 |
| multi-anchor | 2.229 | 1.196 | 0.631 | 0.2831 | 0.2831 [0.2650, 0.3075] | 是 |
| structured | 2.375 | 1.236 | 0.635 | 0.2673 | 0.2673 [0.2562, 0.2813] | 是 |

每档 16→32 与 32→64 的单步比值分别落在 0.501–0.537 与 0.501–0.528，接近纯分母翻倍的 0.5；CI(rate64) 与 CI(rate16) 完全分离，无 FLIP。T13.md 第 7 节的「N>16 只会更差」由推测升级为实测。

## 4. pass rate 转折是否显著：只有 multi-anchor 16→32 显著，随后触顶

| 提案器 | 转折点 N | promo_rate 16/32/64 | 16→32 差值 CI | 32→64 差值 CI | cand_pass_rate 16/32/64 |
|---|---:|---:|---:|---:|---:|
| single-small | 16 | 1.000 / 1.000 / 1.000 | +0.000 [+0.000, +0.000] | +0.000 [+0.000, +0.000] | 0.826 / 0.830 / 0.872 |
| single-large | 16 | 1.000 / 1.000 / 1.000 | +0.000 [+0.000, +0.000] | +0.000 [+0.000, +0.000] | 0.898 / 0.875 / 0.878 |
| multi-anchor | 32 | 0.889 / 1.000 / 1.000 | +0.111 [+0.028, +0.222] | +0.000 [+0.000, +0.000] | 0.160 / 0.161 / 0.164 |
| structured | 16 | 0.833 / 0.917 / 0.972 | +0.083 [-0.056, +0.250] | +0.056 [-0.056, +0.167] | 0.108 / 0.102 / 0.099 |

判读：T13.md 第 3/8 节的「过闸率随 N 上升」只在 N≤32 成立；到 N=64 单中心两档与 multi-anchor 的 promo_rate 已到 1.0 天花板。structured 的点估计继续升但两个差值 CI 都跨 0，按预注册规则记转折点 N=16，不能说「没有上升」，只能说「36 个重采样单位下不显著」。候选级过闸率在 N≥16 后平或降（D2 0.160→0.164，D3 0.108→0.099），与 T13.md 的 NO_GAIN 主因一致：新增候选并没有变得更可采纳。

## 5. 分子 Δpriv 仍远小于分母 4×

| 提案器 | Δpriv N=16 | Δpriv N=32 | Δpriv N=64 | 16→32 差值 CI | 32→64 差值 CI |
|---|---:|---:|---:|---:|---:|
| single-small | 0.5002 | 0.5031 | 0.5065 | +0.0029 [-0.0057, +0.0120] | +0.0034 [-0.0022, +0.0102] |
| single-large | 0.5058 | 0.5083 | 0.5093 | +0.0025 [-0.0015, +0.0078] | +0.0010 [-0.0010, +0.0038] |
| multi-anchor | 0.4280 | 0.4593 | 0.4847 | +0.0313 [-0.0042, +0.0689] | +0.0254 [+0.0036, +0.0470] |
| structured | 0.4559 | 0.4746 | 0.4875 | +0.0187 [-0.0017, +0.0434] | +0.0129 [+0.0007, +0.0248] |

D2/D3 在 32→64 的小幅上升统计显著，但相对基线仅 +5.9% / +2.7%，分母是 4×（+300%）。机制句不变：**过闸覆盖率随 N 触顶，过闸者质量近乎不动，验证费线性上涨**。

## 6. 门有效性与对表

- `--self-test` 实跑 6/6 PASS（见 `selftest.log`）：T1 ρ 参数与实测 ρ̄ 单调同向（注入 ρ=0/0.25/0.5/0.75/1 → 实测 -0.011/0.262/0.503/0.746/1.000）；T1-red 未中心化 cosine 坏尺必须判红（实测 0.898→1.000，failing=span/calib）；T2 CI 包含点估计（含重尾与零膨胀夹具）；T2-red 偏移 CI 必须判红；T3 快评估器与 `ContextualTask.evaluate` 逐位一致；T4 复现 T13 锚点 multi-anchor N=16 seed1 = (0.528272, 0.361149, 11)。
- 对表现役量具（`deep.json` 的 `cross_check` 字段）：对 `diversity.json` 的 36 行 × 4 字段（rho_bar / delta_priv / rate_per_1k / promoted）与 `census.json` 默认闸 6 格 × 3 字段（pass_rate / rate_per_1k / cand_pass_rate）逐实体比对，`mismatches = 0`。开发中这道对表闸抓出两处真错：rate64/rate16 误用 N=16 闭包曾得 1.13（应为 0.28），cand_pass_rate 分母误用代数曾得 55.8（应为 0.16）；均已修正后重跑，最终产物无残留。

## 7. 复现命令

```bash
cd analyses/tracks/rsi-after/T13-deep
python3 proposer_diversity_deep.py --self-test
python3 proposer_diversity_deep.py --run --seeds 1,2,3 --gens 12 --n 1,4,16,32,64 --boot 1000 --out deep.json
python3 -c "import json; d=json.load(open('deep.json')); print(d['verdict'], len(d['cross_check']['mismatches'])); print(d['judgement']['rate_mono'])"
```

抽算示例：`rate(64)/rate(16) = deep.json["cells"]["multi-anchor"]["64"]["rate_per_1k"] / deep.json["cells"]["multi-anchor"]["16"]["rate_per_1k"] = 0.631126 / 2.229016 = 0.2831`。

## 8. 遗留问题

- 仍是 toy 任务（3 维上下文决策）+ heuristic 策略；D2/D3 是「模拟多样」，不是真多 backbone LLM。
- bootstrap 单位取 (seed, gen) 而非独立重复实验：代间共享 anchor 有依赖，CI 可能偏窄；3 seeds 的信息量没有因 1000 次重采样而增加。structured N=1 的宽 CI 是 promotion 稀疏导致，不是数值错误。
- 「转折 N」按预注册规则给出；structured 点估计持续上升但样本不足以判显著，若要多 seed 定论需加 seeds（未在本轮范围）。
- N=32/64 未重跑 `gate_census.py` 的拒绝原因普查；「NO_GAIN 主因」在 N>16 属沿用 N=16 的外推。
- 本地 CPU 实跑 46.52 s，未使用 GPU；仅在 `analyses/tracks/rsi-after/T13-deep/` 写文件，未改其他轨、未动 SUMMARY.md、未做 git add/commit/push。
