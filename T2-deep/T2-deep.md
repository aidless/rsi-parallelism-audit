T2-deep — §5.4 两项外部缺口的正文级闭合

核查日期 2026-11-20。目标：把 T2.md §5.4 的第 1、2 项从「摘要级/无 PDF」升到正文级；第 3、4 项不在本轮范围。

结论（先给）：Hyperagents v2（2026-11-01）的 §6/§7 没有改写 fixed task distribution 与 no-terminal/S0 判据，两处仍逐字保留；唯一实质增量是附录 E.5 的 preliminary 结果——父选择机制可被自改（0.030→0.491，仍低于手工 0.532，p>0.05，5 runs），故 T2.md §3 的「外环全冻结」需局部改成「父选择有 preliminary 自改证据，评估协议与任务分布仍冻结」。MetaShare 与 SwarmRSI 正文均显示主对照不是等算力：MetaShare 明说 "not a token-efficiency claim"（token 比 0.6×/1.2×/2.4×），SwarmRSI 是等任务时间预算/等硬件/等骨干但 token 不配平，作者把 token 消耗作为资源报告。两方向均用正文取证，没有把摘要级证据写成正文级。

判决口径

- A = 取到正文级证据，T2.md 原判断成立/得到闭合。
- B = 取到正文级证据，原判断需要局部改写（写明改写点）。
- 未核 = 未取到正文级证据，按 §5.4 停该方向。本轮两方向均取到正文，无「未核」项。

号-题验号（abs 页 HTTP 200；标题逐字抄页面）

| id | 标题 | 版本史（abs 页 Submission history） | 正文载体 |
|---|---|---|---|
| 2603.19461 | Hyperagents | v1 Thu, 19 Mar 2026；v2 Sun, 1 Nov 2026 | v2 PDF 8,657,413 B（与 HEAD Content-Length 一致），63 页，pdftotext 得 222,843 B |
| 2610.21887 | MetaShare: Failure-Aware Collective Self-Improvement for Open-Ended Agents | v1 Thu, 15 Oct 2026 | arXiv HTML v1 757,811 B（与 HEAD Content-Length 一致） |
| 2610.20431 | SwarmRSI: Recursive Self-Improvement through Evolving Scientific Agent Swarm | v1 14 Oct；v2 19 Oct；v3 Mon, 2 Nov 2026 | arXiv HTML v3 488,057 B（与 HEAD 一致） |

v2 无 HTML（/html/2603.19461v2 返回 No HTML for 2603.19461v2），正文证据全部来自 8.6MB PDF 的文本层。

方向① Hyperagents v2 §6/§7 是否改写判据

| # | 待判问题 | 判 | 正文级证据（逐字） |
|---|---|---|---|
| 1.1 | §6 Safety 是否改写 fixed-task/终止判据 | A | §6 仍写 Moreover, evaluation is performed using predefined tasks and metrics, and human oversight is maintained throughout all experiments. 新增的是 Test tasks are unavailable to the task and meta agents and are used only for final evaluation, which prevents direct test leakage but does not eliminate gaming of the training proxy.——是测试隔离与 gaming 警告，判据本身未动。 |
| 1.2 | §7 fixed task distribution 是否被改写 | A | §7 逐字：First, it operates with a fixed task distribution. 紧接 One direction is to co-evolve the task distribution by generating new tasks and curricula that adapt to the agent capabilities——co-evolve 仍是 future direction。（原文为 agent’s，此处排版省略撇号，逐字串见 claims.json 的 H-FIXED2。） |
| 1.3 | §7 外环固定是否被改写 | B（局部） | §7 仍写 Second, components of the open-ended exploration loop (e.g., parent selection, evaluation protocols) remain fixed. 与 Although hyperagents can modify their self-improvement mechanisms, they cannot alter the outer process that determines which agents are selected or how they are evaluated.；但新增 Our preliminary results suggest such extensions are feasible (Appendix E.5).。附录 E.5 实跑：主实验 In all other experiments (Section 5), the DGM-H uses a fixed parent selection strategy that is roughly proportional to each agent’s performance score and inversely proportional to the number of its children that successfully compiled (score-child-prop) (Appendix A.2).；放开后 5 runs，random 0.030→0.428、modifiable 0.491、handcrafted 0.532，While these differences are not statistically significant (p > 0.05), they reveal a consistent qualitative trend: enabling meta-level modification of parent selection yields improvements over random selection, but does not yet surpass a carefully engineered mechanism (Figures 11 and 12). |
| 1.4 | no-terminal / S0 归类是否仍成立 | A | v2 实验仍是 50 / 100 / 200 iterations（§5: After 200 iterations, the best discovered agent achieves a test-set score of 0.700, outperforming ProofAutoGrader’s score of 0.670）；附录 F：We measure progress in outer-loop iterations, which count opportunities to generate a new agent rather than a fixed amount of compute, since evolved agents are free to use more or fewer FM calls within each iteration (bounded by a timeout); we report cost estimates in Appendix D.2, and comparing methods under matched compute (e.g., tokens, monetary cost, CPU/GPU usage, wall-clock time) is a natural extension.。附录 G：In this work, objectives are specified through fixed benchmarks and evaluation criteria. The DGM-H does not alter the underlying task definitions; instead, it optimizes performance with respect to the provided objectives. 终点仍由作者常数 T 与环境外的冻结 benchmark 决定，S0 归类对 v2 成立。 |

改写点（仅 1.3）：T2.md §3 表格「判分器｜固定任务分布 + 固定 evaluation protocol」一行补注：父选择在 v2 附录 E.5 已有 preliminary 自改（未超手工策略，p>0.05），evaluation protocols 与任务分布仍冻结；§3 正文「判分权没有一起下放」的整体判断保留。

方向② MetaShare / SwarmRSI 正文实验口径

| # | 待判问题 | 判 | 正文级证据 |
|---|---|---|---|
| 2.1 | MetaShare 主对照是否等算力 | A（非等算力） | Table 1 token 核算：Paper Review (100) DGM-H 83M / Ours 52M ≈0.6×；Polyglot (100) 135M/163M ≈1.2×；IMO-grading (200) 88M/213M ≈2.4×。作者自述 MetaShare is the more expensive method on two of the three domains we account for.；Compute is therefore accounted for in tokens, as in Table 1 of the main paper, rather than in GPU-hours.；totals are medians over five runs to the selected checkpoint；消融段：so this is a quality-and-speed gain, not a token-efficiency claim.。基线并非全部重跑：we did not rerun them, so on these domains our admissibility gate，仅 For Polyglot and audit risk, the baseline is our reimplementation。摘要的 the generation at which the selected best appears falls by 1.7–2.9× 是迭代数比，不是算力比。 |
| 2.2 | MetaShare 是否存在等算力消融 | A（存在，但只在消融） | same gate, temperature spread, budget, and paired runs (last row of Table 2 )—reaches 0.72（val，55 generations），对照 full 0.83 val / 36 generations，即 +0.11 val、少 19 代；这是 paper review 组件消融里的 compute-matched reference，不是五域主对照。 |
| 2.3 | SwarmRSI 主对照是否等算力 | A（等时+等硬件+等骨干，非等 token） | SwarmRSI and rerun baselines use DeepSeek-V4-Pro ( DeepSeek, 2026 ) under matched settings for each benchmark.；We set per-task time limits to 8 hours on OpenProblems ( Turcan et al., 2026 ) , 4 hours on NatureBench ( Wang et al., 2026b ) , and 12 hours on MLE-Bench Lite ( Du et al., 2026 ) .；Within each benchmark, SwarmRSI and rerun baselines share the evaluation protocol and time limit.；SwarmRSI and rerun baselines use the same hardware within each benchmark.；Published results keep the settings of their sources.；Results from our runs in Tables 2 – 3 are averaged over three random seeds.。token 是报告项而非配平项：Token cost sums uncached input and output tokens over all LLM calls in a search.；For Figure 6 , we sum uncached input and output tokens from all LLM calls throughout each task’s search. We report the mean over all tasks in each benchmark and the three seeds, in millions of tokens per task.；as shown in Section B.6 , it uses fewer tokens than TusoAI and Arbor.；跨代 token tokens per task fall from 12.17M to 10.94M。 |

闭合结论：T2.md §4 表中 MetaShare / SwarmRSI 两行的「环境开放否 / 可迁移判分」判断保留；需补注正文口径——MetaShare 主对照按 DGM-H 协议、token 未配平（三域比 0.6/1.2/2.4×），仅 paper review 消融做了 compute-matched；SwarmRSI 是同骨干/同硬件/同时间预算对照，token 作为成本报告，非等算力。

关键数字与可复算命令

| 数字 | 来源 | 复算命令 |
|---|---|---|
| 52/83=0.627、163/135=1.207、213/88=2.420 | MetaShare Table 1 | cd analyses/tracks/rsi-after/T2-deep && python3 -c "print(round(52/83,3),round(163/135,3),round(213/88,3))" |
| 55−36=19 代（compute-matched vs full） | MetaShare §5.1/Table 2 | cd analyses/tracks/rsi-after/T2-deep && python3 -c "print(55-36)" |
| 0.030→0.428 / 0.491 / 0.532，p>0.05，5 runs | Hyperagents v2 附录 E.5 | cd analyses/tracks/rsi-after/T2-deep && python3 extract_context.py evidence/hyperagents-v2.txt 0.030 0.491 0.532 "not statistically significant" |
| 8h / 4h / 12h per-task 时间上限 | SwarmRSI 附录 B.4 | cd analyses/tracks/rsi-after/T2-deep && python3 extract_context.py evidence/swarmrsi-v3.txt "We set per-task time limits" |
| 12.17M→10.94M tokens/task（跨代） | SwarmRSI 附录 C | cd analyses/tracks/rsi-after/T2-deep && python3 extract_context.py evidence/swarmrsi-v3.txt "tokens per task fall from" |

证据门：cd analyses/tracks/rsi-after/T2-deep && python3 evidence_gate.py --self-test && python3 evidence_gate.py

- 自测三向反证：注入错标题 / 伪造引文 / 把 abs 页当 body 源，三种变异均 exit≠0；自测本体 exit 0。
- 实跑：35 条 check（3 条号-题 + 32 条正文引文逐字命中）全过，exit 0。gate 强制 level=body 的引文不得来源于 abs 页，防止摘要级证据冒充正文级。

遗留问题

1. T2.md §5.4 第 3、4 项（lemoz 复现非回归闸的归属、DGM 档案跨代 ρ̄ 未测）不在本轮，保持原状态。
2. Hyperagents v2 附录 E.5 的 p>0.05 与 5 runs 是作者报告，未做独立复现；本轮判据是正文是否改写，不是实验是否可复现。
3. MetaShare Table 1 的 DGM-H baseline self-modification 是作者按 ~33M tokens per 100 iterations 缩放的估算，非三方实测；引用时必须带这个口径。
4. SwarmRSI Figure 6 的 token 数是图，文本层只有定义与 20.19M tokens per task 的 Arbor 参照，未从图上逐点读数；故本报告只引等时/等硬件/等骨干的文字口径与跨代 12.17M→10.94M，未报图上各点数值。

产物路径清单（全部相对工作区）

- analyses/tracks/rsi-after/T2-deep/T2-deep.md（本文件）
- analyses/tracks/rsi-after/T2-deep/claims.json（35 条机读核验声明）
- analyses/tracks/rsi-after/T2-deep/evidence_gate.py（号-题 + 引文 + 分级门，带三向反证 self-test）
- analyses/tracks/rsi-after/T2-deep/extract_context.py（上下文抽取器，带 self-test）
- analyses/tracks/rsi-after/T2-deep/evidence/abs-2603.19461.html、abs-2610.21887.html、abs-2610.20431.html（三个 abs 页）
- analyses/tracks/rsi-after/T2-deep/evidence/hyperagents-2603.19461v2.pdf（v2 正文 PDF，63 页）
- analyses/tracks/rsi-after/T2-deep/evidence/hyperagents-v2.txt、metashare-v1.txt、swarmrsi-v3.txt（正文文本层）
- analyses/tracks/rsi-after/T2-deep/evidence/metashare-2610.21887v1.html、swarmrsi-2610.20431v3.html（正文 HTML 原件）
- analyses/tracks/rsi-after/T2-deep/evidence/extracts/（关键词上下文，含 metashare-compute.txt / swarmrsi-compute.txt / metashare-matched.txt）
