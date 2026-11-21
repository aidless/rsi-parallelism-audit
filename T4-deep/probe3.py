import re, pathlib, html
d=pathlib.Path('analyses/tracks/rsi-after/T4-deep')
for name in ['idea_abs','coral_abs']:
    s=(d/(name+'.html')).read_text(encoding='utf-8',errors='replace')
    t=html.unescape(re.sub(r'<[^>]+>',' ',re.sub(r'<script.*?</script>|<style.*?</style>',' ',s,flags=re.S|re.I)))
    t=re.sub(r'\s+',' ',t)
    print('====',name,'====')
    for p in [r'KDD',r'10\.1145[^\s<]*',r'Journal ref[^;]*',r'Submitted on[^;]*',r'Authors[^;]*',r'2604\.01658',r'2411\.02429']:
        m=re.search(p,t,re.I)
        if m: print(' ',p,'=>',t[max(0,m.start()-60):m.end()+120])
    print(' head:',t[:700])
