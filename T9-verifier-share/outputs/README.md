# T9 — 验证器作为独立贡献的占比（Verifier-as-Contribution Share）

新量表，量的问题不是「摘要提没提 verifier」，而是「verifier 是不是论文的主要贡献」。目录内所有产物只在本目录，未改其他文件、未做 git 操作。

## 交付物

- `verifier_share.py`：量表脚本（arXiv API + 本地判据 + self-test + 一致率重算）
- `outputs/verifier_share.csv`：四季度主表（total / P1 / P2 / P3 / per_10k + Wilson 95% 区间）
- `outputs/evidence.jsonl`：P1/P2 命中证据 + 少量 P3 对照（id、标题、判据命中、摘要片段）
- `outputs/sample.jsonl`：四季度共 800 条随机抽样逐条分档结果（含被判 NONE 的 API 噪声，供复算）
- `outputs/review_sample.jsonl` + `outputs/review_labels.json`：40 条本地人工复核样本与标签
- `outputs/run.log`：本次实跑日志

## 复现命令

```bash
cd analyses/tracks/rsi-after/T9-verifier-share
python3 verifier_share.py --self-test
python3 verifier_share.py --quarters 2025Q4 2026Q1 2026Q2 2026Q3 \
    --out outputs --sleep 5 --page 200
python3 verifier_share.py --agreement outputs/review_sample.jsonl outputs/review_labels.json
```

`--seed` 默认 `t9`，抽样偏移由 `Random("t9|<quarter>")` 决定，可复现。请求间隔 5 s；429 时指数退避（20/40/60/…/90 s）。

## 判据（互斥，优先级 P1 > P2 > P3）

- **P1 标题级**：标题含 `verifier|evaluator|judge|reward model|critic|rubric`（含复数/连字符）。
- **P2 贡献句级**，满足其一：
  1. 摘要中出现 `we … (propose|introduce|present|develop|build)`，且其**直接宾语中心名词**是 verifier 类词；宾语中出现 `benchmark/dataset/framework/pipeline/system/...` 等竞争中心名词即否；
  2. `a/the <verifier 类词> that|which …` 同位语/定语从句，且不被 `use/rely/require/with/via` 等使用类谓语支配。
- **P3 配角级**：摘要提到 verifier 类词，但不满足 P1/P2。
- **NONE**：API 命中但本地正则未命中（arXiv 词干/短语展开噪声），单列不并入任何档位。

## 四季度结果（每万篇）

| 季度 | total | P1 估计 [95% CI] | P1/万 | P2 估计 [95% CI] | P2/万 | P3 估计 | P3/万 | 抽样命中 P1/P2/P3 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2025Q4 | 15038 | 83 [23, 297] | 55.19 | 42 [7, 231] | 27.93 | 374 | 248.70 | 2 / 1 / 9 |
| 2026Q1 | 17135 | 142 [48, 408] | 82.87 | 0 [0, 178] | 0.00 | 1229 | 717.25 | 3 / 0 / 26 |
| 2026Q2 | 22246 | 756 [437, 1285] | 339.84 | 63 [11, 350] | 28.32 | 1134 | 509.75 | 12 / 1 / 18 |
| 2026Q3 | 19989 | 586 [321, 1050] | 293.16 | 0 [0, 221] | 0.00 | 1933 | 967.03 | 10 / 0 / 33 |

估计量 = `union_api × (该档抽样命中数 / 200)`；`union_api` 为 `(cat:cs.AI OR cat:cs.CL) AND submittedDate:[lo TO hi] AND ((ti: 六词 OR) OR (abs: 七词 OR))` 的 totalResults。`per_10k = 10000 × 估计量 / total`。CI 为命中比例的 Wilson 95% 区间乘 `union_api`。

## self-test 与判据修复

- `python3 verifier_share.py --self-test` → **12/12 通过，exit 0**；3 个陷阱样本把「朴素判据（`we+动词` 与 verifier 同句即判 P2）」判红，证明断言能红能绿。
- 真阳：`We propose a verifier that …` → P2；真阴：`Our pipeline uses a verifier …` → P3；`We propose a new benchmark` → NONE。
- **实测漏洞与修复**：初版把 `a/the <verifier> that` 写成不含关系代词的宽模式，导致 `we build a critic network from scratch` 被误判 P2（self-test 真红，exit 2）。修复为强制要求紧随 `that|which`，该样本现判 P3。

## 本地复核

- 抽 40 条（27 P1 + 2 P2 + 11 P3，覆盖四季度），逐条读标题+摘要判「是否符合该档定义」，**一致率 40/40 = 1.000**（P1 27/27、P2 2/2、P3 11/11）。
- 复核口径是「判据符合度」，不是脱离定义的「学术重要性」；3 条边界样本已在 `review_labels.json` 的 note 字段标注（如 `critic-free` 按字面口径仍算标题命中）。
- P2 复核只有 2 条，1.000 的一致率置信度很低，不能解读为「判据准确率 100%」。

## 口径警告（重要）

1. **B 级证据：词频/句式证据，不外推因果。** 本量表只说明「贡献句中的 verifier 表述占比」，不能证明 verifier 方法有效、也不能证明某会议/机构在推动该范式。
2. **P2 是 200 条/季的抽样估计**，四季度中两季抽样命中 0 条 → 报 0 只是「本样本未捕获」，95% CI 上界分别到 178/221 篇，不能当作真实零。
3. **API 宽查询噪声大**：union 查询 200 条抽样里 157–188 条本地判 NONE（arXiv 的 `abs:"LLM judge"` 等短语被展开成 Judgement/Evaluation 等词干命中）。所有比例都按「本地正则复核后的档位」计数，NONE 单列；这是 T6 也存在的 API 词干问题，此处显式披露而不是把噪声当信号。
4. **P1 是标题字面口径**：`critic` 会收到 RL 的 actor-critic、`critic-free` 等工作，不一定是本量表想抓的「验证器」。定义如此，故不改判据；解释数字时要连这层噪声一起读。
5. **P1/P2/P3 互斥但跨季不可直接相减**：各季 union_api 与抽样分布不同，且 2025Q4 另一次全量标题分页试跑得到 159/1132 的标题本地命中率（分母是标题候选集，与这里的 union 抽样分母不同），两次数字不构成矛盾。
6. arXiv 在实跑中出现 429/503，脚本按指数退避重试；`run.log` 保留每次成功的 total/union_total/offset，数字可从 `sample.jsonl` 逐条重算。

**证据等级：B（可复算的词频/句式测量，非因果证据）。**

## P2 扩样本复测（1000 条/季）

扩样脚本仍为 `verifier_share.py`（本轮补齐 `--sample-pages` 的分页累加——原解析存在但从未使用，每季只取 1 页），改为 `--sample-pages 5 --page 200`；输出到 `outputs_p2x/`，原 `outputs/` 原样保留作对照。`sample.jsonl` 的 abstract 改存全量，确保档位可从落盘逐条复算。请求间隔 5 s，arXiv 429/500 指数退避。

### 新表（四季度主表）

| 季度 | 抽样 n | total | union_api | P2 命中 | P2 估计 [95% CI] | P2/万 | P1/万 | P3/万 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2025Q4 | 1000 | 15038 | 8317 | 3 | 25 [8, 73] | 16.62 | 88.44 | 381.70 |
| 2026Q1 | 1000 | 17135 | 9454 | 7 | 66 [32, 136] | 38.52 | 137.73 | 557.34 |
| 2026Q2 | 1000 | 22246 | 12603 | 4 | 50 [20, 129] | 22.48 | 181.16 | 617.64 |
| 2026Q3 | 600 | 19989 | 11718 | 0 | 0 [0, 75] | 0.00（本样本未捕获；CI 上界 37.52/万） | 195.61 | 840.46 |

- **2026Q3 抽样量不同**：该季第 4/5 页（offset ≥ 9969）arXiv 连续返回 HTTP 500（低偏移 8000 可正常取回，属服务端深偏移故障），只取回 600 条；其 P2=0 仅表示**本样本未捕获**，95% CI 上界 75 篇（≈37.52/万），不得写成「真实为零」。
- 其余三季为连续 1000 条块抽样（起点由 `Random("t9|<quarter>")` 决定）：Q4 offset 6496、Q1 3529、Q2 2376。连续块只覆盖季内一个时间切片，Wilson CI 只反映抽样内二项不确定性，不覆盖季内时间聚集——这是本量表跨季比较的残余局限。
- 复算：`python3 recompute_p2x.py`（从 `sample.jsonl` 重算全表并与 CSV 逐格比对，tier 重算 0/3600 不一致）。

### 新旧对比（P2，估计量 / 95% CI，单位：篇）

| 季度 | 旧（200/季）P2 估计 [CI] | 新（1000 或 600）P2 估计 [CI] | 新旧 CI 是否重叠 |
|---|---:|---:|---:|
| 2025Q4 | 42 [7, 231] | 25 [8, 73] | 是 |
| 2026Q1 | 0 [0, 178] | 66 [32, 136] | 是 |
| 2026Q2 | 63 [11, 350] | 50 [20, 129] | 是 |
| 2026Q3 | 0 [0, 221] | 0 [0, 75] | 是 |

四季新旧 95% CI **全部重叠** → 两次估计统计上一致，不存在「样本量不同导致结论翻转」。扩样后 2026Q1 从「0/200 未捕获」变成「66 篇可测」，Q4/Q2 点估计落进旧 CI 内、CI 上界由 231/350 收窄到 73/129。复算：`python3 compare_p2x.py`。

### 本地复核（P2 命中，每季至多 10 条，`Random(f"p2x|{q}")`）

- 复核样本：Q4 3 条、Q1 7 条、Q2 4 条、Q3 0 条，合计 **14 条**（各季 P2 命中均不足 10，全取；文件 `review_p2.jsonl`）。
- 逐条读标题+摘要判「是否符合 P2 定义」，**一致率 10/14 = 0.714**，0 条 `uncertain`。
- 4 条不一致均为「贡献动词宾语中心名词不是 verifier 类词」的边界误判，人工判 P3：
  - `2512.10415v2`：宾语中心名词是 study（evaluator 只是 of 的宾语）；
  - `2602.11570v1`：中心名词是 paradigm，verifier 被 utilize；
  - `2604.24964v1`：中心名词是 metric，rubric 只是修饰；
  - `2604.25872v1`：中心名词是 metrics，reward model 只是修饰。
- 复算：`python3 verifier_share.py --agreement outputs_p2x/review_p2.jsonl outputs_p2x/review_p2_labels.json`。
- 口径：只判「是否落在 P2 字面定义内」，不判学术重要性。上述 4 条说明当前正则对 `study/paradigm/metric(s)` 等中心名词仍漏拦，P2 点估计因此是**偏高上界**（14 条里 4 条为误判 → 精度约 71%）。

### 结论

**P2 的真实量级约为 10–38.5/万（原始正则口径；按复核 71% 精度折减后约 7–27/万），未见随时间单调上升的证据**——四季 95% CI 全部重叠，2026Q1 最高、2026Q3 本轮浅偏移补抓捕获到 1 条（10.01/万，CI 每万 [1.5, 55.0]），不能写成「P2 随时间上升」或「Q3 真实为零」。

> **单位口径校正（八法审计 #8，2026-11-20）**：原文把「估计篇数」写成「/万」——q3retry 的 p2_est=20 是篇数（分母 union_api=11717），p2_per_10k=10.01 才是每万率（分母 total=19989）；CI [3,110] 是篇数区间，每万应为 [1.5, 55.0]。源码 per_10k=10000*est/total（verifier_share.py:380-382）。P1/P3 同错（见下）。审计脚本 q3_unit_audit.py（self-test 5/5）+ 产物 outputs/q3_unit_audit.json，判决 UNIT_MISLABELED。**定性结论「P2 极稀疏、非真实零、落配角位」不受影响**，只是数值量级被误标为大 2 倍。

### 2026Q3 补抓（q3retry，本轮 m01058「继续推进六个」）

旧 p2x 的 2026Q3 因 arXiv 深偏移（offset≥9969）连续 HTTP 500 只取 600 条、P2 未捕获（0 条）。本轮用**浅偏移**（seed 20261119，offset 8953–9353，同样 600 条）补抓，产物在 `outputs_q3retry/`：
- 新 Q3 读数：n=600，P1=19 条（185.6/万，CI 每万 [119.6, 286.7]），**P2=1 条（10.01/万，CI 每万 [1.5, 55.0]）**，P3=93 条（908.5/万）。
  - 口径：括号外「条」是本地命中数，第一名是每万率（分母 total），括注 CI 是每万区间。原文误把「估计篇数」（P1 371 篇 / P2 20 篇 / P3 1816 篇）写成「/万」、把 CI 篇数区间写成每万区间（八法审计 #8）。
- 唯一 P2 命中 `2609.18203v1` Behavior2Value（B2V-Verifier，电商价值测量里的组件级 verifier），属「普通 ML 组件 verifier，与 self-improvement 语境无关」——**P2 档的噪声比 P1 大**，这本身支持「P2 在文献里是配角位」的终局判断。
- 两次 Q3 抽样（旧 offset 9369 / 新 offset 8953）P1 每万率一致（旧 195.6/万、新 185.6/万；旧 est 391 篇、新 est 371 篇），P2 从「未捕获」变成「捕获 1 条」——**P2 不是零，只是极稀疏**；旧样本 0 条是小样本假象（与 Q4/Q1/Q2 的 3/7/4 条命中同量级）。
- 复现：`python3 verifier_share.py --quarters 2026Q3 --out outputs_q3retry --sleep 4 --page 200 --sample-pages 3 --seed 20261119`。
