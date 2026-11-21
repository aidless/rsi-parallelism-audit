## T5-deep：token 计价闭合 T5 §7 遗留 5（结论先行）

**结论（1）**：把 C2 的验证成本从 CPU-ms 换成显式外生 token 计价后，**「边际增益 > 边际验证成本」在任何正汇率 r 下都不翻正**；t_eval=0 时净差为 −3.999519（CPU 口径原值），t_eval=1000、r=1e6 ms/token 时净差为 −1.176e9，方向只会更负。翻正的解析阈值上界在 t_eval>0 时恒为**负数**（t_eval=1000 ⇒ r<−0.00339959 ms/token），即正汇率域内翻正集为空。
**结论（2）**：T5 的 N_eff≈1.05（Kish，ρ̄=0.945,N=16）与 T10 同点的 n_eff=1.4207（曲线反解）**方向一致、非同量复现**：复算 Kish=1.054366，差 +0.366334，比值 1.347445；verdict=`DIRECTION_CONSISTENT_NOT_SAME_QUANTITY`。

### 产物路径

- `analyses/tracks/rsi-after/T5-deep/token_pricing.py` —— 新仪器，纯函数核心 + `--self-test` 反证门 + 正式扫描落盘。
- `analyses/tracks/rsi-after/T5-deep/token_pricing.json` —— 36 行 rate×t_eval 扫描、翻正阈值、对表、裁决，全部数字可机读复算。
- `analyses/tracks/rsi-after/T5-deep/T5-deep.md` —— 本文件。

### 1. 闭合的对象与证据底物

T5.md:238 原文遗留 5：「c 的单位只在 CPU 时间上量过（2.55 ms）；换成 token 计价（2611.13524 的口径）需要另一套 instrument，本轮未做」。本轮只做这一项的**显式外生换算**，不动 CPU 实测值，不冒充 2611.13524 的 token 实测（本地无该数，**未核**）。

A 级底物（逐字锚定在 `T5.md:78,83,118,121-126`，脚本 `load_inputs()` 有字符串断言）：
c_cpu=2.55 ms/次；κ=3；N:4→16；Δ_sel(4)=0.542，Δ_sel(16)=0.549；s(4)=0.825；天花板 Δ_ceil=0.5496；ρ̄=0.945。
B 级补充（同一 `pilot.json` 的 truthful/paired 5 seeds）：Δ(4)=0.447174，Δ(16)=0.487784，pilot-n-sweep truthful/paired N=1 rate=30.4037/1k。

### 2. 计价模型（B 级：显式外生，非实测）

- r = token_rate，单位 **ms/token**（1 token 折合多少 CPU-ms；外生情景参数）。CPU 时间折 token 数 = c_cpu/r。
- t_eval = 单次公开评测的 LLM judge token 数（外生；本机 judge 为 heuristic，真实值 0 token）。
- 附加倍率 `M(r,t) = 1 + t·r/c_cpu`；t=0 ⇒ M=1（self-test 钉死）；r 越大 token 越贵，M 单调上升。
- 主口径 `RHS = 1 + κ·M`（κ 部分由 judge token 定价，基础 actor 评测仍按 CPU 计）。t=0 ⇒ RHS=1+κ=4，与 T5 原 C2 完全同点；`RHS/RHS_cpu = 1`。
- 替代口径 `RHS_repl = 1 + t·r/c_cpu`（κ 被 token 全替换）：t=0 ⇒ RHS_repl=1，此时 LHS=0.00048125 仍 ≪ 1，依旧不翻正。两种口径都落盘，不挑对结论有利的一版。
- 左式 `LHS = s·(Δ_sel(16)−Δ_sel(4))/(16−4) = 0.825×0.007/12 = 0.00048125`；另一路用诚实 paired Δ 得 0.00338415（(0.487784−0.447174)/12），两路都不翻正。
- 旧尺不可能产生的形状差：CPU-ms 口径 C2 只有一个点（RHS=4）；本尺给出 RHS(r,t) 的单调曲面与翻正阈值——这是 token 计价独有的可证伪形状，不是把旧数换个单位重报。

### 3. 扫描结果与翻正阈值（可复算）

| t_eval (token) | r=1e-4 | r=1e-2 | r=1 | r=100 | r=1e4（ms/token） |
|---|---|---|---|---|---|
| 0 | RHS=4 / net=−3.999519 | 4 / −3.999519 | 4 / −3.999519 | 4 / −3.999519 | 4 / −3.999519 |
| 100 | 4.118 / −4.117 | 5.176 / −5.176 | 4.922e2 / −4.922e2 | 1.177e5 / −1.177e5 | 1.176e9 / −1.176e9 |
| 1000 | 4.118 / −4.117 | 15.76 / −15.76 | 1.180e3 / −1.180e3 | 1.177e5 / −1.177e5 | 1.176e7 / −1.176e7 |
| 10000 | 4.118 / −4.117 | 1.177e3 / −1.177e3 | 1.177e5 / −1.177e5 | 1.177e7 / −1.177e7 | 1.176e11 / −1.176e11 |

（完整 36 行见 `token_pricing.json` 的 `sweep`；每行含 multiplier / rhs_ms / benefit_cost_ratio / flipped / net_honest_norm。表中 `flipped` 全为 false。）

解析翻正条件 `LHS > 1 + κ(1 + t·r/c)` 给出上界 `r < c·(LHS−1−κ)/(κ·t)`：
- t=100 ⇒ r < −0.03399591 ms/token；t=1000 ⇒ r < −0.00339959；t=10000 ⇒ r < −0.00033996（全负 ⇒ 正汇率域无解）。
- t=0 ⇒ RHS 与 r 无关，翻正需 LHS > 4，即 `Δ_sel(16)−Δ_sel(4) > 4×12/0.825 = 58.1818` 分，而任务天花板只有 0.5496 分——物理上不可能（`impossible: true`）。
- 诚实 paired Δ 口径同样不翻正：上界 t=1000 ⇒ −0.00339665 ms/token。

因此遗留 5 的闭合答案是：**token 计价不提供 C2 翻正通道；它只是把原本已负的净差按汇率放大。** 结论方向与 T5 §2.3「左≪右」一致，但现在是带可扫描汇率与解析阈值的独立仪器，而非同一数字换单位。

### 4. T5 N_eff ≈1.05 与 T10 ρ̄=0.945 点对表（只判方向）

| 项 | T5（Kish） | T10（曲线反解） |
|---|---|---|
| 定义 | N/(1+(N−1)ρ̄) | 在 δ(ρ=0,N) 曲线上反解 δ(ρ=0.945,N=16)=0.197282 |
| ρ̄ / N | 0.945 / 16 | 0.945 / 16 |
| 读数 | 发布 1.05；复算 **1.054366** | 发布/落盘 **1.4207** |
| 差 / 比 | — | +0.366334 / 1.347445 |

- 方向：两者都 ≪2，均指向「高相关下端有效独立度塌缩」⇒ **方向一致**。
- 同量性：定义不同（Kish 等效样本数 vs 曲线反解候选数），差 35%，**不是同一量的复现**；只记方向，不把 1.4207 当成 T5 数的纠正值，也不把 1.05 当成 T10 数的近似。
- 锚点：`T10-independence/independence.json` 的 `summary[rho=0.945].n_eff_at_16=1.4207`、`delta_n16=0.197282`；语义碰撞说明见 `T10-independence/T10.md:98-115` 与 `T5.md` §10 第 9 条。`mismatches=[]`（点、发布值、尺别均逐项对上）。

### 5. 反证门（`--self-test`，12/12 PASS，exit 0）

- 钉退化：`t_eval=0 ⇒ multiplier=1、RHS/RHS_cpu=1（RHS=4.000000）`。
- 钉方向：`r=1e6,t=1000 ⇒ net=−1.176e9 且 flipped=False`；net(r) 随 r 单调不增。
- 能红（不是装饰）：注入 `LHS=5` ⇒ flipped=True、net=+1，翻正上界转为 +0.00085；注入 `T10 n_eff=5.0` ⇒ 对表 verdict 翻为 DIRECTION_INCONSISTENT；注入 `ρ=0` ⇒ Kish=16 与发布 1.05 的失配被记入 `mismatches`。
- 复算命令（亚分钟、零 GPU）：
  `cd analyses/tracks/rsi-after/T5-deep && python3 token_pricing.py --self-test && python3 token_pricing.py`
  `cd analyses/tracks/rsi-after/T5-deep && python3 -c "import json;d=json.load(open('token_pricing.json'));print(d['honest_pilot_marginal'],d['neff_crosswalk'],d['flip_thresholds_sel'])"`

### 6. 遗留问题（诚实边界）

1. **真实 token 数未核**：2611.13524 的 judge token/次与 token↔ms 汇率均未在本地输入中给出；r 与 t_eval 是情景网格，本仪器标 B 级，不升级为实测成本结论。两个检索方向上限内无新增落盘证据可核，停该方向。
2. **κ 的构成未分解**：κ≈3 只从「闸约 3× 向量比较开销」得来（T5.md:78），是否全部由 judge token 构成未测；主/替代两口径都报，不择一。
3. **N_eff 语义碰撞仍在**：T5 Kish 与 T10 反解不是同量，本轮只做方向对表；跨轨统一口径需另立仪器，未在本目录内改动 T10/T5 原文。
4. **T5 §7 其余遗留未动**：ρ̄ 多样性外推、none 自指、Δ_sel 形状外推仍 open；本轮不冒充已闭合。
