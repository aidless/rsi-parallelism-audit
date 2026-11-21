# T8-deep 抓取日志

核验日期：2026-11-19。所有路径相对工作区；URL 为 web_fetch 实际请求地址。字符数来自 web_fetch 返回的 `length`，字节数来自本地文件 `wc -c`；两者可能因 UTF-8 多字节字符不同。

| 落盘文件 | URL | web_fetch 状态 | length(chars) | bytes | 备注 |
|---|---|---|---:|---:|---|
| `fetch-0.txt` | https://arxiv.org/abs/2411.02429 | HTTP 200 | 44038 | 44038 | arXiv abs 页，号-题一致 |
| `fetch-3.txt` | https://dl.acm.org/doi/10.1145/3711896.3737419 | HTTP 200 | 41249 | 41256 | KDD DOI 落地页，二次打开成功 |
| `fetch-html-1.txt` | https://ar5iv.labs.arxiv.org/html/2411.02429 | HTTP 200 | 557877 | 558828 | ar5iv 渲染全文，含 MathML annotation |

超时/未落盘尝试（同一方向最多 2 次，另一方向成功即停）：

- `fetch-1.txt` 未产生：https://arxiv.org/html/2411.02429v1 → `ToolCallError: tool call timed out after 30000ms`（第 1 次）。
- `fetch-html-0.txt` 未产生：https://arxiv.org/html/2411.02429v1#S4 → 同上（第 2 次；公式方向改走 ar5iv）。
- `fetch-2.txt` 未产生：https://doi.org/10.1145/3711896.3737419 → 同上（DOI 跳转方向；改走 ACM 直链）。

复算命令：

```bash
cd "F:\deepseek"
wc -c analyses/tracks/rsi-after/T8-deep/fetch-0.txt analyses/tracks/rsi-after/T8-deep/fetch-3.txt analyses/tracks/rsi-after/T8-deep/fetch-html-1.txt
python3 -c 'from pathlib import Path; [print(p.name, len(Path(p).read_text(encoding="utf-8"))) for p in ["analyses/tracks/rsi-after/T8-deep/fetch-0.txt","analyses/tracks/rsi-after/T8-deep/fetch-3.txt","analyses/tracks/rsi-after/T8-deep/fetch-html-1.txt"]]'
```
