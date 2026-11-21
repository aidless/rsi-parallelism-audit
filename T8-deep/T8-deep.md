# T8-deep：IdeaBench 三项遗留闭合

核验日期：2026-11-19。判定口径沿用 T8.md：A=原文逐字可复算；B=原文可推但需一次组合推断；未核=检索方向内未取得可引用原文。

## 结论（先行）

1. Insight Score 公式：A。ar5iv 渲染原文的 MathML annotation encoding="application/x-tex" 给出逐字公式：I(LLM,q)=\frac{1}{m}\sum_{i=1}^{m}\frac{r_{\text{target}_{i}}|_{q}-1}{n}，并给出 m/n/r 定义与 [0,1] 边界。
2. KDD DOI 页：A。ACM DOI 落地页二次打开成功（HTTP 200），逐字给出 KDD '25: Proceedings of the 31st ACM SIGKDD Conference on Knowledge Discovery and Data Mining V.2 与 **Published**: 03 August 2025。
3. "published in 2024"：A。该短语确在 IdeaBench 原论文 Data Collection 段逐字出现，指数据集 target papers 的发表年份；与文章本身的 arXiv 提交日 2024-10-31、KDD 发表日 2025-08-03 是不同口径。

---

## 1. Insight Score 公式逐字数学形式

**判定：A**

检索方向（上限 2）

- 方向 1：arXiv 原生 HTML。https://arxiv.org/html/2411.02429v1 与 https://arxiv.org/html/2411.02429v1#S4 两次 web_fetch 均返回 ToolCallError: tool call timed out after 30000ms。
- 方向 2：ar5iv 渲染 HTML。https://ar5iv.labs.arxiv.org/html/2411.02429 HTTP 200，命中 MathML，停。

URL：https://ar5iv.labs.arxiv.org/html/2411.02429
证据文件：analyses/tracks/rsi-after/T8-deep/fetch-html-1.txt（length 557877 chars / 558828 bytes）

逐字引文（行号对应证据文件）：

- :305：m: the number of target papers in our dataset.
- :309：n: the number of research ideas an LLM generates per query.
- :313：the ith target paper’s idea’s rank within the corresponding ranked list of ideas given quality indicator q；同行的 LaTeX annotation 为 r_{\text{target}_{i}}|_{q}\in\{1,...,n+1\}。
- :318：We define I(LLM,q) to represent the “Insight Score” for a given LLM based on a specific quality indicator q as follows:
- :323（alttext 与 annotation encoding="application/x-tex" 两处一致）：I(LLM,q)=\frac{1}{m}\sum_{i=1}^{m}\frac{r_{\text{target}_{i}}|_{q}-1}{n}
- :325：<span class="ltx_tag ltx_tag_equation ltx_align_right">(1)</span>，即式 (1)。
- :327：I(LLM,q)\in[0,1]；rank first 时 r_{\text{target}_{i}}|_{q}=1 ⇒ I(LLM,q)=0；rank below all generated ideas 时 r_{\text{target}_{i}}|_{q}=n+1 ⇒ I(LLM,q)=1。

口径说明：r 取值 1..n+1，因此 (r-1)/n ∈ [0,1]；m 项取均值后仍在 [0,1]，与原文边界句一致。T8.md 中「MathML 未提取」由本方向闭合。

---

## 2. KDD DOI 页二次打开

**判定：A**

检索方向（上限 2）

- 方向 1：DOI 跳转 https://doi.org/10.1145/3711896.3737419 → ToolCallError: tool call timed out after 30000ms，未落盘。
- 方向 2：ACM 直链 https://dl.acm.org/doi/10.1145/3711896.3737419 HTTP 200，落盘 fetch-3.txt，停。

URL：https://dl.acm.org/doi/10.1145/3711896.3737419
证据文件：analyses/tracks/rsi-after/T8-deep/fetch-3.txt（length 41249 chars / 41256 bytes）

逐字引文：

- :1：[skip to main content](https://dl.acm.org/doi/10.1145/3711896.3737419#skip-to-main-content)
- :39：[PDF/eReader](https://dl.acm.org/doi/epdf/10.1145/3711896.3737419 "View online with eReader")
- :282：1. IdeaBench: Benchmarking Large Language Models for Research Idea Generation
- :405：#### Published In
- :409：KDD '25: Proceedings of the 31st ACM SIGKDD Conference on Knowledge Discovery and Data Mining V.2
- :411：August 2025
- :417：DOI:10.1145/3711896（这是 proceedings DOI；文章 DOI 由页面 URL 与 :39 PDF 链接逐字给出为 10.1145/3711896.3737419）
- :448：**Published**: 03 August 2025

口径说明：T8.md 中「DOI = B（检索片段）」升级为 A；KDD '25 与 2025-08-03 是文章正式发表口径，arXiv 2024-10-31 是预印本提交口径，两者并列不冲突。

---

## 3. "published in 2024" 年份表述

**判定：A**

检索方向（上限 2）

- 方向 1：ar5iv 全文 https://ar5iv.labs.arxiv.org/html/2411.02429 HTTP 200，命中逐字短语。
- 方向 2：arXiv abs 页 https://arxiv.org/abs/2411.02429 与 ACM DOI 页元数据，用于区分「数据集年份 / 预印本提交年份 / 会议发表年份」，停。

URL：https://ar5iv.labs.arxiv.org/html/2411.02429 ；https://arxiv.org/abs/2411.02429 ；https://dl.acm.org/doi/10.1145/3711896.3737419

证据文件：fetch-html-1.txt、fetch-0.txt、fetch-3.txt

逐字引文：

- fetch-html-1.txt:182：we meticulously curated a set of high-quality biomedical primary research papers published in 2024.
- 同段继续逐字：in the year 2024 with at least one citation；papers published from other biomedical venues in the year 2024 that have at least 20 citations。
- fetch-0.txt:115：[Submitted on 31 Oct 2024]
- fetch-0.txt:41：<meta name="citation_date" content="2024/10/31" />
- fetch-3.txt:448：**Published**: 03 August 2025

口径说明：原句主语是 biomedical primary research papers，即 IdeaBench 数据集中的 target papers；它证明 Inventa 附录 A.2 的 "papers published in 2024" 转述有原文依据。该句不是「IdeaBench 文章发表于 2024」的表述；文章口径为 arXiv 2024-10-31 提交、KDD 2025-08-03 发表。

---

## 复算命令

    cd "F:\deepseek"
    grep -nF 'I(LLM,q)=\frac{1}{m}\sum_{i=1}^{m}\frac{r_{\text{target}_{i}}|_{q}-1}{n}' analyses/tracks/rsi-after/T8-deep/fetch-html-1.txt
    grep -nF 'published in 2024' analyses/tracks/rsi-after/T8-deep/fetch-html-1.txt
    grep -nF '**Published**: 03 August 2025' analyses/tracks/rsi-after/T8-deep/fetch-3.txt
    grep -nF '[Submitted on 31 Oct 2024]' analyses/tracks/rsi-after/T8-deep/fetch-0.txt
    wc -c analyses/tracks/rsi-after/T8-deep/fetch-0.txt analyses/tracks/rsi-after/T8-deep/fetch-3.txt analyses/tracks/rsi-after/T8-deep/fetch-html-1.txt
    python3 analyses/tracks/rsi-after/T8-deep/verify_t8_deep.py
    python3 analyses/tracks/rsi-after/T8-deep/verify_t8_deep.py --self-test

## 遗留问题

本轮三项均有 A 级原文，T8.md (e) 的「公式逐字 / DOI 页 / published in 2024」三项遗留可闭合；KDD 全文付费墙内的版面/页码未作为本轮判定依据，标为未核但不影响上述三项。未改 T8.md、SUMMARY.md，未 git add/commit/push。
