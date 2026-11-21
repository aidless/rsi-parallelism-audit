import re, pathlib
d=pathlib.Path('analyses/tracks/rsi-after/T4-deep')
for name,pats in [
 ('coral_html',[r'56\.2',r'EurekaBench',r'IdeaBench',r'S[Kk][Ii][Ll][Ll]',r'skills',r'heartbeat',r'OpenReview',r'Qu et al']),
 ('idea_html',[r'DN7',r'DN8',r'2,374',r'23,460',r'Insight Score',r'novelty',r'GPT-4o',r'five citations',r'904',r'736'])]:
    t=(d/(name+'.txt')).read_text(encoding='utf-8')
    print('====',name,'====')
    for p in pats:
        ms=list(re.finditer(p,t,re.I))
        print(' ',p,'COUNT',len(ms))
        for m in ms[:2]:
            print('    ...'+t[max(0,m.start()-110):min(len(t),m.end()+110)]+'...')
