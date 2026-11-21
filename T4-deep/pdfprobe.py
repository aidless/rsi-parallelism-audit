import fitz, re, pathlib
d=pathlib.Path('analyses/tracks/rsi-after/T4-deep')
doc=fitz.open(str(d/'nature_si.pdf'))
print('PAGES',len(doc))
alltxt=[]
for i,p in enumerate(doc):
    t=p.get_text()
    alltxt.append(t)
whole='\n'.join(alltxt)
(d/'nature_si.txt').write_text(whole,encoding='utf-8')
print('CHARS',len(whole))
for pat in [r'co-evolution',r'co-evolution of AI',r'fine-tun',r'retrain',r'weight',r'updat\w* (?:the )?model',r'HPA',r'EPA',r'HRA',r'knowledge base',r'procedure',r'large language model']:
    ms=list(re.finditer(pat,whole,re.I))
    print('PAT',pat,'COUNT',len(ms))
    for m in ms[:3]:
        pg=0; acc=0
        for i,t in enumerate(alltxt):
            acc+=len(t)+1
            if acc>m.start(): pg=i+1; break
        print('  p.',pg,'...',re.sub(r'\s+',' ',whole[max(0,m.start()-140):m.end()+160]))
