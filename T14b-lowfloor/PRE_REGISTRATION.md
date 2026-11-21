# T14b 预注册：低底噪提案器能否把 D1 升到可判

> 日期 2026-11-20。承接 T14-deep §0/§5：冻结 anchor 后 rho 成外生旋钮、凸塌缩形态复现，但 V1 Pearson 0.8064<0.95、V2 N_eff 跨度 2.4083<3 => D1=DEGRADED_INSTRUMENT，卡点是 rho_bar(rho=0)~0.376 的任务几何底噪。
> 本轨唯一问题：这个底噪能不能靠换提案器构造压下去，使 D1 升 JUDGEABLE。只读复用 T14-deep 的引擎（evaluate_cached / paired_gate / inner_update / verdict），不改原文件。

## 1. 判据（执行前定死，事后不许挑）

矩阵：构造 C ∈ 搜索空间（见 §2）× rho_param ∈ {0,0.1,…,1.0} × N=16 × seeds {1,2,3}，gens=12。

- V1（仪器有效）：rho_bar 对 rho_param 单调不减、rho_bar(0)<=0.40、|rho_bar(1)-1|<=0.002、Pearson>=0.95。
- V2（旋钮推力）：N_eff(rho=0)/N_eff(rho=1) >= 3.0（等价 rho_bar(0) <= 0.2889）。
- 成功判据：存在 C 同时过 V1&V2 => D1=JUDGEABLE，并逐构造报 D1'-shape / D2 / D4。
- fail 判据：所有 C 都 V2 失败 => D1 保持 DEGRADED_INSTRUMENT，降级理由从「anchor 漂移」精确为「任务几何相关下限不可压」。
- D2/D4（不可牺牲）：每个构造都报 rate 翻转与税倍数，若某构造为过 V2 而引入 rate 翻转，单独标记 GAINED_V2_LOST_D2，不算纯净成功。

## 2. 构造搜索空间（每类只测有先验理由的变体）

| id | 变更 | 先验理由 |
|---|---|---|
| C0 | T14-deep 原版（frozen anchor, sqrt(rho), 加性高斯, s=0.5*0.94^g） | 对照基线 |
| C1 | 线性参数化 (rho, 1-rho) 替 sqrt | sqrt 压缩中段，线性可能抬 Pearson |
| C2a/b | 步长 ×2 / ×3 | 幅度大→候选分散→相关性或降 |
| C3 | 独立项按范数归一化到 sqrt(3) | 等方差，去掉幅值抖动带来的相关 |
| C4 | 多 anchor（D2_ANCHORS） | 分散起点 |
| C5 | delta 基线改零向量 | 去掉共同 baseline 贡献 |
| C6a/b | anchor=零 / anchor⊥TRUE_W | 去 anchor 的 TRUE_W 方向偏置 |
| C7 | n_actions=12 | 扩大选择空间，argmax 收敛或减弱 |

禁止项（先验上等于作弊）：把 TRUE_W 直接写进提案器；按实测 rho_bar 反选旋钮取值；事后改 V1/V2 阈值。

## 3. 底噪分解（解释成功或 fail 的必备读数）

对 rho=0、N=16、seed=1 的逐代 delta 矩阵 D（16×128）：
- 跨候选均值向量 m = mean_i delta_i；
- 共同信号强度 common = mean_i pearson(delta_i, m)。
若 rho_bar(0)~0.37 且 common~0.6+，则底噪主要来自「所有独立候选朝同一 TRUE_W 奖励方向收敛」的任务内信号相关，而非仪器缺陷——这是不可压的物理解释。

## 4. 自检（门必须能红）

- S1 evaluate_cached 与原 evaluate 逐值相等（继承 T14）。
- S2 n_eff 端点：n_eff(16,1)=1、n_eff(16,0)=16。
- S3 常量向量 pearson 返回 0（继承 T14 陷阱守卫）。
- S4 注入：把某构造的 rho_bar(0) 人为改 0.01，判定必须从 fail 翻到某构造 V2 pass（证明门能红）；同时注假共同信号必须改变 common 读数。
- S5 各构造 rho=1 时逐代 rho_bar=1（常量向量不得塌成 0）。

## 5. 输出与范围

- lowfloor_probe.py（自测+正式扫描）、lowfloor_probe.json（逐构造逐档 rows + 判决 + 底噪分解）、T14b.md（本报告）。
- 本地 commit，不推送。不外推真实系统；所有解释为 toy 底物机制。
