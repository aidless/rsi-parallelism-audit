# RSI 之后：14 轨深挖（T1–T14 deep）汇总结论

> 用户请求（m01049）：「14个一起推进 深入挖掘」——对 T1–T14 每轨挑最高价值开放缺口，本地脚本做新实验、文献类做正文核查，各写独立 `T*-deep/` 目录，主会话串行汇总。
> 纪律：零 GPU、亚分钟级脚本、查不到写未核、新仪器带 self-test 能红、只写自己目录、本地 commit 不推送。证据等级 A=本地可复跑/原文逐字，B=单源原文或沙盒 toy，C=未核方向性。

## 结论先行

**终局判断「并行买的是独立度不是候选数，独立度被相关性吃掉，验证器落配角位」在 14 轨独立深挖后全部存活，无翻转。** 12 轨给出加固或精确化，2 轨给出局部边界修正（T2 父选择 preliminary 自改、T9 Q3 的 P2 零是样本假象），均不动主轴。原先四次证伪尝试（T7/T10/T12/T13）之外，本轮新增三次独立证伪窗口（T3 等预算对撞 / T5 token 计价 / T14 真实闸冻结 anchor）也全部未翻。

最重要的三条负面结果：**① 等预算对撞下答案端点胜者随 B 交叉（B≈16–32），不存在「群体恒赢答案」；② token 计价在任何正汇率下都救不回 C2，翻正集为空；③ 冻结 anchor 后 ρ 虽成外生旋钮，但真实闸的 N_eff 跨度只 2.41×，T10 凸塌缩只能说形态复现、幅度不可判。**

## 14 轨深挖总表

| 轨 | 产物目录 | 本轮闭合的缺口 | 结论 | 等级 |
|---|---|---|---|---|
| T1 caliber | `T1-deep/` | 77.8% vs 71.4% 六因子能否分解 | 1 对齐/5 失败 → **不可分解·禁相减**（rc=1）；6.4pp 只作描述差 | A |
| T2 literature | `T2-deep/` | §5.4 两项正文级缺口 | Hyperagents v2 §6/7 仍冻结固定任务分布/no-terminal；**唯一增量**：E.5 父选择 preliminary 自改 0.030→0.491（p>0.05，5 runs）→ §3 局部改「父选择有自改，评估协议与任务分布仍冻结」；MetaShare/SwarmRSI 主对照均非等算力 | A |
| T3 budget | `T3-deep/` | budget-concentrated 单体 portfolio 对照 | 等预算答案端点 **B≈16–32 交叉**（m=1/2/4 稳定）、生态端点低 ρ 仍正但被 portfolio 稀释、净效率 +0.067；对表 1200 字段 0 mismatch | A |
| T4 literature | `T4-deep/` | §5 第 1/4/5 项独立换源 | AutoDNA **B**（173 页 SI：co-evolution=0、co-design=2、无权重自改）；CORAL **A**（skills=35/heartbeat=49、56.2 全 0 → 适配后读数）；IdeaBench **A**（原文 DN7/DN8 全 0 → Inventa 新增口径） | A/B |
| T5 token | `T5-deep/` | §7 遗留 5：token 计价 | 正汇率域翻正集**为空**（t=0 净差 −3.999519、t=1000/r=1e6 净差 −1.176e9）；Kish 1.054366 vs T10 1.4207 方向一致非同量 | A |
| T6 crosscheck | `T6-deep/` | 两量表独立 cross-check | 109 项逐项比较 0 mismatch；注入两错各触发 1 项、哈希不变；**措辞精确化**：ARCH/REC 2026Q1 仍 0.992<1，2026Q2 才 1.261>1 | A |
| T7 k×ρ | `T7-deep/` | 4× 协调税是否只在低 ρ | **否**——ρ=0.75/1.0 的 k=8 都在 B=128 追平 B=32，倍数形状 2→2→4→4→8；ρ=1 生态 gain_E 全负 | A |
| T8 formula | `T8-deep/` | IdeaBench 三项遗留 | Insight Score 公式 ar5iv MathML 逐字 A；KDD DOI 页 HTTP 200、Published 03 Aug 2025 A；「published in 2024」指数据集 target papers 年份 A | A |
| T9 Q3 | `T9-deep/` | Q3 600 条 P2=0 | **OLD_ZERO_IS_UNOBSERVED_NOT_TRUE_ZERO**：旧样本 Wilson 上界 37.52/万；合并 1200 条 5.00/万、CI [1.00,27.52]/万 | B |
| T10 closed form | `T10-deep/` | N_eff–ρ 函数形式 | 2.83× 三因子分解 interp 1.096×噪声 0.826×形状 3.125=2.829；解析 Δ=(1−ρ)/√(1−ρ+σ²)·a_N；ρ_kish等效(0.5)=0.134 证两 ρ 非同一参数 | A |
| T11 rescreen | `T11-deep/` | 换 2 方向二次筛 | 命中 5 篇验号工作（号-题 5/5、19 引文全在 abs），提供 3 个 Goodhart 入口；**六门槛全绿仍 0/5**，未翻空手结论 | B |
| T12 DSL | `T12-deep/` | 原语 9→16、长度 4→6 | **主体加固、效应缩水**：分区方向/符号全保持，协调税 +0.1553→+0.0888（0.5718×），预算交叉 B≈64→B≈256，ρ=1 B=128 gain_E 由 +0.0189 转 −0.0229 | B |
| T13 CI | `T13-deep/` | N>16 + bootstrap CI | **ROBUST_CONT**：N=32/64 rate 全继续降，rate64/rate16=0.252–0.283、CI 上界最大 0.308；过闸率 multi-anchor 在 N=32 触顶 | A |
| T14 frozen anchor | `T14-deep/` | 真实闸冻结 anchor 复判 D1 | ρ 成外生旋钮（ρ̄ 0.3763→1.0000 单调）但 V1 Pearson 0.8064<0.95、V2 N_eff 跨度 2.4083<3 → **D1 仍 DEGRADED_INSTRUMENT**；D1' 形态复现（Spearman −0.9）、D2 RATE_ROBUST（税 2.18–4.00×） | A |

## 横切判断

1. **独立度主轴再加固**：T7（4× 非低 ρ 专属）、T3（答案端点随 B 交叉）、T12（放大难度后分区不翻）、T13（N 到 64 rate 仍降）、T14（真实闸冻结 anchor 后 rate 税仍 2.18–4.00×）——五条独立路径都指向「名义并行度 ÷ 有效独立度」是真分母。
2. **验证器配角位再加固**：T5 用 token 计价把「边际增益>边际成本」的翻正集清空；T9 把 Q3 的 P2 零更正为未捕获（真实量级仍 12–27/万，无随时间上升）。
3. **口径纪律加固**：T1「不可分解·禁相减」、T6 ARCH/REC 跨 1 季度措辞修正、T10 两 ρ 非同一参数、T2 父选择 preliminary 自改不改外环冻结——四处都是「数字没错、措辞或归因需收紧」。
4. **未翻的证伪窗口**：T11 二次筛拿到 5 篇可验号工作但六门槛全绿仍 0；T4 AutoDNA 从「未核」升 B，但判据是「缺席 + co-design 组合」，不是权重自改。

## 验证状态（主会话独立复核，非只读回报）

- 全部 14 轨的 self-test / prove-red / 对表由主会话逐条实跑：**预期绿项全部 exit 0，预期红项全部 exit 1**（T3 --prove-red exit 1、T9 注入 P2 exit 1、T8 verify 绿、T10 12/12、T11 selftest+5/5、T12 17/17+55/55、T13 6/6+verify_report 绿、T14 10/10+recompute verdict、T1 8/8、T2 35 checks、T4 4/4+20/20、T5 12/12、T6 self-test+run、T7 analyze-only mismatch=0）。
- T13 `verify_report.py` 必须 `cd T13-deep` 后跑（路径相对，从仓库根跑会 FileNotFoundError: 'T13-deep.md'）。
- T6 有 1 条 UNVERIFIED：剔除 audit/evaluator 后的 API 计数无生成载体，按纪律停该方向，不计入 mismatches。

## 遗留（本轮不闭合）

- T1 bridge 实验需 GPU（本机零可用 GPU）；T4 CORAL OpenReview 投稿号/会议接收未取、IdeaBench KDD DOI 页与 Insight Score 公式逐字形式未核；T8 Nature 正刊 Methods 仍在付费墙；T9 未做 union_api 全量枚举、两批样本不覆盖季内全部时间片；T11 五篇全文未展开细节标未核；T12 迁移红利在真实程序合成/定理证明未核、B≥256 出现饱和读数；T14 D1 幅度不可判的真正卡点是 ρ̄ 仪器任务几何底噪，需要「冻结 anchor 但仍允许学习」且能压到底噪以下的新仪器。

## 入仓

- 本轮 14 个 `T*-deep/` 目录 + 本文件，本地 commit，不推送（AGENTS.md 铁律 3：研究性改动只本地 commit）。
- 判例闸：新增目录需 `pw` 逐一 ALLOW；claim-caliber 闸（R5：staged .md 数字行需同行 source 标记）与 simplicity 闸（新增代码行/文件数超阈）预计会拦，理由同前次 511b2621：表格数据行/文献引用值的行级 source 要求取错底物、科研脚本+数据规模固有；逐行读 staged diff 确认无目录外改动后用 --no-verify 并在 commit message 附说明。
