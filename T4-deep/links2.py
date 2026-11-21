import re, pathlib
d=pathlib.Path('analyses/tracks/rsi-after/T4-deep')
s=(d/'nature.html').read_text(encoding='utf-8',errors='replace')
for anchor in ['MOESM1','MOESM4','MOESM16','Sec30']:
    for m in list(re.finditer(anchor,s))[:2]:
        a=max(0,m.start()-700); b=min(len(s),m.end()+900)
        frag=s[a:b]
        links=re.findall(r'href=["\']([^"\']+)["\']',frag)
        print('==',anchor,'links=',links[:8])
        print(re.sub(r'\s+',' ',re.sub(r'<[^>]+>',' ',frag))[:500])
