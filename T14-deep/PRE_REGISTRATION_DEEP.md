# T14-deep 预注册：冻结 anchor + 可学习内层目标，使 ρ 成为外生旋钮

> 落盘于执行前（2026-11-20），禁止事后挑数。承接 `T14-neff-real/T14.md` §5 的开放问题。

## 1. 问题

T14 实测：完整 outer loop 每代把 anchor 更新为被采纳候选的权重，ρ̄ 被 anchor 漂移压到 0.84–1.00，N_eff 全程 1.00–1.19，T10 的 ρ→N_eff 曲面从未被触发；因此 D1 字面 SHAPE_PRESERVED 只能降级解释。本轨要把「ρ 作为外生旋钮」做成可判：外层 anchor 冻结，内层目标仍可学习。

## 2. 仪器（只换 propose，不改 rsi-agent 源码）

- **outer 冻结**：anchor A = BASELINE.weights = (1,0,0)，在整个 arm、所有代、所有 seed 恒等；gate 的 base_view、Δ 的参照点全部是 A。arm 内记录 anchor_trace，供 S8 断言「确实没动」。
- **inner 可学习**：内层 agent 维护 3 维目标方向 z_t，起点 z_0=(1,0,0)（与 anchor 同向 = 零信息起点）。每代用**自己的探索预算** INNER_PROBES=2 次 public 评测做 REINFORCE 型方向估计：
  probe_j = A + 0.12·(z_t + 0.5·ε_j)，g_j = mean(public(probe_j) − base_public)，v = Σ_j g_j·ε_j，
  z_{t+1} = normalize(z_t + 0.15·v/|v|)。
  `inner_update` 的入参里**没有 ρ**——学习轨迹与 ρ 无关，这是本轨「ρ 外生」的操作定义。
- **提案器**：w_i = A + s_g·(√ρ·z_g + √(1−ρ)·ε_i)，ε_i ~ N(0,1)^3，s_g = max(0.5·0.94^g, 0.04)（与 T14 同 schedule）。ρ=1 全候选相同（= A+s·z_g），ρ=0 无共享信号。**不用 √ρ·anchor+√(1−ρ)·v 那种构造**（T14 已实测反单调）。
- **采纳规则与闸同 T14**：paired_gate(base_view, view_i, floor, alpha_g)，alpha_g = 0.05/max(gens−g,1)；通过者取 public mean 最大者。
- **成本口径**：verifier_calls 同时报 cand-only（= gens·N，与 T14 可比）与 total（+ gens·INNER_PROBES）。D2/D4 主判用 total（诚实成本），cand-only 并列作敏感性。

## 3. 判据（执行前定死）

矩阵：ρ_param ∈ {0, 0.1, …, 1.0}（11 档）× N ∈ {1,4,16} × seeds {1,2,3}，gens=12 → 99 臂。

- **V1（仪器有效性，本轨核心）**：N=16、3 seeds 均值下，实测 ρ̄ 对 ρ_param 严格单调不减、ρ̄(ρ=0) ≤ 0.40、|ρ̄(1)−1.0| ≤ 0.002、Pearson r ≥ 0.95。失败 ⇒ `INSTRUMENT_STILL_DRIFTING`，D1 仍降级。
- **V2（旋钮是否真能推 N_eff）**：N_eff(N=16, ρ=0)/N_eff(N=16, ρ=1) ≥ 3.0。
- **D1'（可判性）**：V1∧V2 通过 ⇒ D1 从「降级解释」升为 `JUDGEABLE`。
- **D1'-shape（T10 凸塌缩是否在真实闸复现）**：N=16 上 Δ_inst(ρ) = mean_gen max_i mean(public_i − base)（过闸前 best-of-N 增益，与 T10 的 Δ 同语义）。Spearman(Δ_inst, ρ) ≤ −0.8 且 Δ_inst(0)−Δ_inst(1) ≥ 0.05 ⇒ `COLLAPSE_REPRODUCED`；≥ +0.8 且差 ≤ −0.05 ⇒ `REVERSED_SIGNAL_DOMINANT`；否则 `MIXED_SHAPE`。
- **D1'-attribution**：并列报 Spearman(Δ_inst, N_eff@16) 与 Spearman(Δ_inst, cos(z_T, TRUE_W))（后者只作事后诊断，TRUE_W 不进提案器/闸）。用于判形状是「相关吃掉独立度」还是「共享信号被学习」。
- **D2**：存在 ρ 使 rate(16) ≥ rate(4)（total）⇒ `RATE_FLIP_ANY`，否则 `RATE_ROBUST_ACROSS_RHO`；cand-only 并列。
- **D4**：tax = rate4/rate16 的 min/max；全档 ≥3 ⇒ `TAX_ROBUST`，某档 <2 ⇒ `TAX_RHO_SENSITIVE`。

## 4. 自检门（每条必须能红）

- S1–S5 同 T14（pearson 端点 / 正交 / Kish 端点 / 单向量 / 全同非常量）。
- **S6 核心单调门**：完整 arm（N=16, seed=1, gens=12）上 ρ_param → 实测 ρ̄ 严格单调、ρ̄(0) ≤ 0.40、ρ̄(1)=1.000。**反证**：`drift` 模式（复刻 T14 逐代 anchor 更新）必须判红。
- S7 常量向量 pearson = 0（防退化构造假报塌缩）。
- **S8 anchor 冻结不变式**：正常 arm 的 anchor_trace 全等于 A；`drift` 模式 trace 出现 ≥2 个不同值 ⇒ 断言能红。
- **S9 内层学习活性**：A+0.12·z_T 的 public mean > A 的 public mean（纯公开证据）；`learn=False`（η=0 冻结内层）复核必须红。
- **S10 仪器对表**：evaluate_cached 与原 `ContextualTask.evaluate` 在 5 策略 × 2 任务上逐值相等；不等即红。

## 5. 执行与归档

```bash
cd analyses/tracks/rsi-after/T14-deep
python3 frozen_anchor.py --self-test
python3 frozen_anchor.py --seeds 1,2,3 --gens 12 --n 1,4,16 --out frozen_anchor.json
```

报告 `T14-deep.md`，一切数字从 `frozen_anchor.json` 复算；只写本目录，不改其他轨、不 push。

## 6. 执行前补丁（self-test 阶段，尚未跑全矩阵）

2026-11-20，全矩阵执行前：S6 首跑暴露 `z_0=(1,0,0)` 与冻结 anchor 平行，rho=1 时候选 delta 向量恒为 0，Pearson 分母为 0 返回 0，导致 `rho_bar(1)=11/12≈0.917` 而非 1.000。这正是 T14 已记录的常量向量陷阱。
**补丁**：`z_0` 改为中性对称方向 `normalize((1,1,1))`（不含 TRUE_W 知识，仍为零信息起点），并在 S6 增加 S6d：rho=1 时逐代 rho_gen 必须全为 1.0。判据与执行矩阵不变；此补丁发生在任何全矩阵读数之前。
