import re, html, pathlib
d=pathlib.Path('analyses/tracks/rsi-after/T4-deep')
s=(d/'nature.html').read_text(encoding='utf-8',errors='replace')
# find all hrefs near supplementary / pdf / esm
hrefs=re.findall(r'href=["\']([^"\']+)["\']',s)
for h in hrefs:
    if any(k in h.lower() for k in ['supplementary','esm','41586','.pdf','download']):
        print(h)
