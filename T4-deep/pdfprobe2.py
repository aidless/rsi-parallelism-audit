import re, pathlib
d=pathlib.Path('analyses/tracks/rsi-after/T4-deep')
t=(d/'nature_si.txt').read_text(encoding='utf-8')
for pat in [r'co-evol',r'co-design',r'evol\w* of (?:AI|the AI)',r'iterativ\w+ refin',r'procedure optimi',r'agent.{0,40}evol',r'learn\w+ from (?:feedback|experiment)',r'flexible workflow',r'PaperQA',r'better.{0,30}procedure']:
    ms=list(re.finditer(pat,t,re.I))
    print('PAT',pat,'COUNT',len(ms))
    for m in ms[:4]:
        print('  ...',re.sub(r'\s+',' ',t[max(0,m.start()-180):m.end()+220]))
print('=== S5.2/S5.3 region around p83 ===')
i=t.find('S5.3 Comparison')
print(re.sub(r'\s+',' ',t[i-2500:i+3000]))
