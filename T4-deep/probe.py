import pathlib, re, sys
d = pathlib.Path('analyses/tracks/rsi-after/T4-deep')
def probe(name, pats, win=160, cap=6):
    t=(d/(name+'.txt')).read_text(encoding='utf-8')
    print('==== '+name+' ====')
    for p in pats:
        ms=list(re.finditer(p,t,re.I))
        print(' PAT',repr(p),'COUNT',len(ms))
        for m in ms[:cap]:
            a=max(0,m.start()-win); b=min(len(t),m.end()+win)
            print('   ...'+t[a:b].replace('\n',' ')+'...')
probe('nature', [r'Methods', r'Supplementary', r'co-evolution', r'co-design', r'11,000', r'subscription', r'Table 1', r'Data availability'], win=120, cap=3)
