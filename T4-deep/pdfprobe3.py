import re, pathlib
d=pathlib.Path('analyses/tracks/rsi-after/T4-deep')
t=(d/'nature_si.txt').read_text(encoding='utf-8')
# sections list
print('=== section headers S1..S7 ===')
for m in re.finditer(r'\bS[1-7]\.\d+(\.\d+)?\s+[A-Z][^\n]{0,90}',t):
    print(' ',re.sub(r'\s+',' ',m.group(0))[:110])
print('=== agent evolution / update hints ===')
for pat in [r'Agent',r'evol',r'upgrad',r'optimiz\w+ the (?:agent|workflow|procedure|protocol)',r'hardware abstraction',r'Code and Hardware Agents',r'AI-optimized',r'S2\.\d',r'S3\.\d']:
    ms=list(re.finditer(pat,t,re.I))
    print('PAT',pat,'COUNT',len(ms))
    for m in ms[:2]:
        print('  ',re.sub(r'\s+',' ',t[max(0,m.start()-120):m.end()+180]))
# find co-design context full
i=t.lower().find('the key multi-agent contribution')
print('=== co-design key para ===')
print(re.sub(r'\s+',' ',t[i-200:i+1200]))
