# 并行化买到的是独立度，不是候选数

## ——递归式自我改进（RSI）之后的机制审计：14 轨 + 14 项深挖 + 1 项预注册失败实验

> 2026-11-20。本仓库是 `analyses/tracks/rsi-after/` 全项目的对外开源归档，汇总主六轨（T1–T6）、追加七轨（T7–T13）、T14 真实闸检验、14 项深挖（T1-deep…T14-deep）与 T14b 预注册失败实验。
> 全部读数可从落盘脚本与 JSON 复算；证据分级：**A** = 本地可复跑实验或原文逐字核验，**B** = 单源原文或沙盒 toy 底物，**C** = 未核、仅方向性。
> 纪律：零 GPU、零云通道；所有实验在本机 CPU 亚分钟至分钟级完成；每个仪器带「注入违规必须变红」的 self-test。

完整报告见 [REPORT.md](REPORT.md)，主六轨总览见 [SUMMARY.md](SUMMARY.md)，深挖总览见 [SUMMARY-deep.md](SUMMARY-deep.md)。

---

## 一句话结论

**并行化不替代递归；它买到的是独立度，不是候选数。独立度被候选相关性以凸速率吃掉，而验证器在文献与本地实验里都主要落在配角位。**

拆成三条可执行判据：

1. **先有闸再谈带宽**。没有可失败的验收闸时，扩大候选池是负漂移（本地实测 Δ_priv = −0.458）。
2. **加宽须满足边际收益 > 边际验证成本**。本地实测左边 0.0005、右边 4，净亏；token 计价在任何正汇率下都救不回。
3. **看 N_eff/N，不看 N**。T10 解析曲面上 ρ=0.945 时 16 个名义候选只值 1.42 个；T13 用 Kish 公式的四档提案器即使把 ρ̄ 压到 0.52，N_eff 也只到 1.82——rate 仍随 N 单调降 4×。（两套 N_eff 定义不同、仅塌缩端方向一致，见报告 §8。）

终局判断经历 T7 / T10 / T12 / T13 四次独立证伪尝试，全部存活。

---

## 目录结构

报告与总览：

- `REPORT.md` — 对外技术报告（10 节，正文含机制分组证据总表、五条主证据、七窗口证伪表、复现命令、边界与停止条件）
- `SUMMARY.md` / `SUMMARY-deep.md` — 主六轨 / 深挖轨总览

主六轨（每轨：脚本 + 原始 JSON + 结论 md）：

- `T1-parallel-conv` — 并行 / 卷积：ConvRSI 是递归载体换成隐状态 + 轮内图卷积，非消除
- `T2-open-ended` — 开放式演化：开放 = 搜索空间 / 档案开放，非环境开放
- `T3-collective` — 集体智能：token 计价模型，群体端点优势是理想化产物
- `T4-ai-scientist` — AI 自主科研：严格 RSI 收紧为 2 个，多数改产物不改自身
- `T5-verifier-econ` — 验证器经济学：加宽并行亏、闸 > 带宽、N_eff 是隐藏分母
- `T6-measure` — 可跑量表：词频 ARCH/REC/VER + 吞吐随带宽单调降 4×（文档在 `outputs/README.md`）

追加七轨与真实闸检验：

- `T7-collision` 同预算对撞 / `T8-gaps` 遗留闭合 / `T9-verifier-share` 验证器主贡献量表
- `T10-independence` 独立性曲面 / `T11-screening` 路 1 筛基准 / `T12-spse` 路 2 造 SPSE / `T13-proposer-diversity` 提案器多样性
- `T14-neff-real` 真实闸检验 / `T14b-lowfloor` 预注册失败实验（含 `PRE_REGISTRATION.md`）

深挖轨：`T*-deep/`（T1-deep … T14-deep），逐轨对核心结论做独立证伪与交叉核验。

---

## 复现

全部在本机 CPU 完成，无 GPU、无网络依赖（文献轨除外）。在仓库根目录执行：

    # 核心机制
    python3 T10-independence/independence_surface.py --self-test      # 5/5
    python3 T13-proposer-diversity/proposer_diversity.py --self-test  # 5/5
    python3 T5-verifier-econ/pilot_budget_scaling.py --n 1,2,3,4,6,8,12,16 \
        --out T5-verifier-econ/pilot-n-sweep.json   # 144 行 N 扫描

    # 真实闸与低底噪
    python3 T14-neff-real/neff_real_substrate.py --out T14-neff-real/real_substrate.json  # 63 臂，~35s
    python3 T14b-lowfloor/lowfloor_probe.py --self-test               # S1–S5
    python3 T14b-lowfloor/lowfloor_probe.py --out T14b-lowfloor/lowfloor_probe.json  # 660 臂，~98s
    (cd T14b-lowfloor && python3 verify_t14b.py)                      # 独立复算 + 红证明

    # 文献计量（需相邻的 rsi-agent 语料；无语料时跳过此条）
    python3 T9-verifier-share/verifier_share.py                       # 四季度 P1/P2/P3

有 `--self-test` 开关的脚本必须 exit 0；红电池反证必须抓到注入违规——多数脚本报 `CAUGHT` / `red_ok=True` 并 exit 0，`T9-deep/q3_reconfirm.py --prove-red` 则以 exit 1 表示预期变红。两种返回码都算门有效。

`MANIFEST.sha256` 记录全部纳入文件的 SHA-256，可用 `sha256sum -c MANIFEST.sha256` 校验完整性。

---

## 开源范围

仅收录本研究自身产出：报告 / 结论 md、可复跑脚本、原始 JSON/CSV 数据、运行日志。已排除第三方论文 PDF / HTML 证据缓存、作者邮箱摘录、`__pycache__/` 与大体积采样文件（`sample.jsonl`）；这些原始素材不在本仓库内，报告正文对它们的引用以证据分级标注。

---

## 许可证

MIT License — Copyright (c) 2026 本仓贡献者。详见 [LICENSE](LICENSE)。

第三方论文与数据集的权利归各自权利人所有；本仓库仅收录对其的分析结论与本地复算数据。
