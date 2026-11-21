# T6-deep — 两量表独立 cross-check 仪器

## 结论先行

1. **对表通过：109 项逐项比较，mismatches = 0。** 独立实现不 import 原 `arxiv_rsi_lexicon.py` / `verifier_throughput_rsi.py`，只读 T6-measure/outputs 的五个落盘底物，重算 README 的核心数字。
2. **self-test 能红：两处已知错各触发且只触发 1 项 MISMATCH，底物哈希前后不变。** 生产 compare 函数直接用于注入，不是另写一套恒真断言。
3. **一处口径需精确化：** README 写“ARCH/REC 在 2026Q1 跨过 1”，实际 2026Q1 比率 0.992424 仍 <1，2026Q2 才 1.261053 >1；本仪器用 `transition_from=2026Q1`（最后一个 <1 的季度）记录“跨过”的起点，并在 audit 中同时保留 `first_above_1=2026Q2`。数字本身没有错，错的是“在 2026Q1 已跨过”的措辞。

## 产物

- 仪器：[crosscheck_measure.py](analyses/tracks/rsi-after/T6-deep/crosscheck_measure.py)
- 对表报告：[crosscheck_report.json](analyses/tracks/rsi-after/T6-deep/crosscheck_report.json)
- 本说明：[T6-deep.md](analyses/tracks/rsi-after/T6-deep/T6-deep.md)

只读底物（未改动，哈希见下）：

- [README.md](analyses/tracks/rsi-after/T6-measure/outputs/README.md) — `313caf1fdc8e`
- [lexicon_report.csv](analyses/tracks/rsi-after/T6-measure/outputs/lexicon_report.csv) — `ddff9ded0b88`
- [evidence.jsonl](analyses/tracks/rsi-after/T6-measure/outputs/evidence.jsonl) — `62397db392d7`
- [throughput.json](analyses/tracks/rsi-after/T6-measure/outputs/throughput.json) — `ee6d3241cb26`
- [throughput-random.json](analyses/tracks/rsi-after/T6-measure/outputs/throughput-random.json) — `9f7fa41cbbb7`

哈希为文件 SHA-256 前 12 位，写在报告的 `source_sha256_12` 字段。

## 独立实现对表

### 1. ARCH / REC 跨 1

| 季度 | ARCH API | REC API | ARCH/REC |
|---|---:|---:|---:|
| 2025Q4 | 274 | 365 | 0.750685 |
| 2026Q1 | 393 | 396 | 0.992424 |
| 2026Q2 | 599 | 475 | 1.261053 |
| 2026Q3 | 646 | 508 | 1.271654 |

- 最后一个 <1：**2026Q1**；第一个 >1：**2026Q2**。
- 报告字段：`claim.cross_transition_from = 2026Q1`，`audit.cross.first_above_1 = 2026Q2`。
- 判定：**数值 OK**；README 的“在 2026Q1 跨过 1”应改成“2026Q2 首次 >1，跨过发生在 2026Q1→Q2 之间”。

### 2. VER 每万篇 +117%

- 2025Q4：1239 / 15038 × 10000 = **823.91**
- 2026Q3：3580 / 19989 × 10000 = **1790.99**
- 增长：1790.99 / 823.91 − 1 = **117%**
- 判定：**OK**，与 README 一字不差。

### 3. 验证速率 13.376 → 8.619 → 3.231

从 `throughput.json` 的 `per_trial` 逐 trial 取均值（3 seeds × 8 代）：

| N | 平均验证调用 | Δ best | rate/1k | 平均 promoted |
|---:|---:|---:|---:|---:|
| 1 | 29.7 | 0.401056 | **13.376171** | 3.67 |
| 4 | 56.3 | 0.485526 | **8.618745** | 6.33 |
| 16 | 152.7 | 0.493278 | **3.231113** | 6.67 |

README 展示为 13.376 / 8.619 / 3.231，是三位小数取整；报告用 `tolerance_for()` 显式吸收展示取整（rate 5e-4、delta 5e-5、calls 0.05、promoted 0.005），不吸收实质差异。

### 4. 负对照与命中分布

- 随机臂 rate：N=4 **6.233395**、N=16 **2.058105**。
- 速率再降：N=4 **28%**、N=16 **36%**；主 Δ−随机 Δ：N=4 **0.1635**、N=16 **0.1899**。全部 OK。
- evidence.jsonl 共 1018 条：ARCH 357 / REC 374 / VER 287。
- ARCH 命中 `open-ended` **352/357**；VER 命中 `audit` **187/287**、`verifier` **121/287**。全部 OK。
- 本地复核（每季每类抽 100）ARCH 96/90/92/79、REC 86/97/94/97、VER 50/69/84/84，全部 OK。

## 闸与自测

```bash
python3 -m py_compile analyses/tracks/rsi-after/T6-deep/crosscheck_measure.py
python3 analyses/tracks/rsi-after/T6-deep/crosscheck_measure.py --self-test
python3 analyses/tracks/rsi-after/T6-deep/crosscheck_measure.py
```

实际输出（本机，2026-11-20）：

```text
[OK] inject lex.2025Q4.arch_rec_ratio: 0.75->0.76 red=1 red_keys=['lex.2025Q4.arch_rec_ratio']
[OK] inject tp.main.N4.mean_rate: 8.619->8.62 red=1 red_keys=['tp.main.N4.mean_rate']
SELFTEST PASS control_mismatches=0 injected_red=2 source_digests_unchanged=True
PASS=True items=109 mismatches=0 unverified=1 report=analyses/tracks/rsi-after/T6-deep/crosscheck_report.json
```

`mismatches` 是报告里的真实数组字段，不是打印字符串；空数组即通过。self-test 用生产 `compare()` 注入，要求“只红 1 项且 red_keys == {注入键}”，并校验五个底物哈希前后一致。

## 未核（按纪律停该方向）

- README 行：“剔除 `audit`/`evaluator` 后重算 VER API 命中为 1012/1422/2188/2515，即每万篇 672.96/829.77/983.46/1258.19（+87%）”。
- 状态：**未核**。T6-measure 落盘的 CSV / evidence.jsonl / throughput*.json 没有记录“剔除泛词后的 API 计数”；在 `analyses/tracks/rsi-after` 内用多组数字 grep 也未找到生成载体。按工作纪律不把它塞进 mismatches，也不凭记忆补算。
- 报告字段：`unverified[0].key = claim.ver_adjusted_no_generic_terms`，`status = 未核`，并附了原句与原因。

## 遗留问题

1. README 的 2026Q1 措辞需改成“2026Q2 首次 >1”，否则读者会以为 2026Q1 已 >1。
2. 调整后 VER（+87%）仍缺落盘生成载体；要升级为可引用数字，需要原脚本把剔除 audit/evaluator 的计数单独写一份 CSV/JSON。
3. 本仪器只覆盖 README 的核心数字与两张吞吐表；T6 的其他叙述性结论（如“真实 scaling 曲线仍缺”）未做语义核验，不在本仪器范围。
