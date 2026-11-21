import re, html, pathlib
d = pathlib.Path('analyses/tracks/rsi-after/T4-deep')
for name in ['coral_abs','idea_abs','nature','coral_html','idea_html']:
    s = (d/(name+'.html')).read_text(encoding='utf-8', errors='replace')
    m = re.search(r'<title[^>]*>(.*?)</title>', s, re.S|re.I)
    title = html.unescape(re.sub(r'\s+',' ',m.group(1))).strip() if m else 'NO-TITLE'
    txt = re.sub(r'<script.*?</script>|<style.*?</style>', ' ', s, flags=re.S|re.I)
    txt = html.unescape(re.sub(r'<[^>]+>', ' ', txt))
    txt = re.sub(r'\s+',' ',txt)
    (d/(name+'.txt')).write_text(txt, encoding='utf-8')
    print(name, '| TITLE:', title[:200], '| txtlen:', len(txt))
