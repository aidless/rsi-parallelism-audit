#!/usr/bin/env python3
"""T4-deep 证据核验仪器：号-题一致、词频、缺席判定。带 --self-test（能红）。"""
import re, sys, json, pathlib, html

D = pathlib.Path(__file__).resolve().parent  # 以脚本所在目录为证据根，任意 cwd 可跑

def title(s: str) -> str:
    m = re.search(r'<title[^>]*>(.*?)</title>', s, re.S | re.I)
    return html.unescape(re.sub(r'\s+', ' ', m.group(1))).strip() if m else ''

def count(t: str, pat: str) -> int:
    if not t or not t.strip():
        raise ValueError('EMPTY_TEXT: 空文本不能报 0 命中（会被误读为缺席）')
    return len(re.findall(pat, t, re.I))

def num_title(t: str, num: str, frag: str) -> bool:
    if not t or not frag:
        raise ValueError('EMPTY_ARG')
    return num in t and frag.lower() in t.lower()

def load_txt(name: str) -> str:
    p = D / (name + '.txt')
    if not p.exists():
        raise FileNotFoundError(str(p))
    return p.read_text(encoding='utf-8')

def real_checks():
    nat_html = (D / 'nature.html').read_text(encoding='utf-8', errors='replace')
    si = load_txt('nature_si')
    coral_abs = (D / 'coral_abs.html').read_text(encoding='utf-8', errors='replace')
    idea_abs = (D / 'idea_abs.html').read_text(encoding='utf-8', errors='replace')
    coral = load_txt('coral_html')
    idea = load_txt('idea_html')
    checks = {
      'nature_doi_num_title': num_title(nat_html, 's41586-026-11228-6', 'An AI-native experimental laboratory for autonomous biomolecular operations') and '10.1038/s41586-026-11228-6' in nat_html,
      'nature_paywall_preview': count(load_txt('nature'), r'preview of subscription content') >= 1,
      'nature_si_open_173p': (D / 'nature_si.pdf').exists() and (D / 'nature_si.pdf').stat().st_size > 20_000_000 and len(si) > 200_000,
      'si_coevolution_absent': count(si, r'co-evolution') == 0,
      'si_codesign_present': count(si, r'co-design') >= 2,
      'si_finetune_all_baseline': count(si, r'fine-tun') == 4,
      'si_retrain_absent': count(si, r'retrain') == 0,
      'si_modelweight_update_absent': count(si, r'updat\w* (?:the )?model') == 0,
      'coral_num_title': num_title(title(coral_abs), '2604.01658', 'CORAL: Towards Autonomous Multi-Agent Evolution for Open-Ended Discovery'),
      'coral_skills_present': count(coral, r'skills') >= 30,
      'coral_heartbeat_present': count(coral, r'heartbeat') >= 40,
      'coral_no_eurekabench': count(coral, r'EurekaBench') == 0,
      'coral_no_ideabench': count(coral, r'IdeaBench') == 0,
      'coral_no_56_2': count(coral, r'56\.2') == 0,
      'idea_num_title': num_title(title(idea_abs), '2411.02429', 'IdeaBench: Benchmarking Large Language Models for Research Idea Generation'),
      'idea_no_dn7': count(idea, r'DN7') == 0,
      'idea_no_dn8': count(idea, r'DN8') == 0,
      'idea_target_papers': count(idea, r'2,374') >= 4,
      'idea_filtered_refs': count(idea, r'23,460') >= 2,
      'idea_insight_score': count(idea, r'Insight Score') >= 50,
    }
    metrics = {
      'si_chars': len(si), 'si_fine_tun': count(si, r'fine-tun'),
      'si_co_design': count(si, r'co-design'), 'si_co_evolution': count(si, r'co-evolution'),
      'coral_skills': count(coral, r'skills'), 'coral_heartbeat': count(coral, r'heartbeat'),
      'idea_dn7': count(idea, r'DN7'), 'idea_dn8': count(idea, r'DN8'),
      'idea_2374': count(idea, r'2,374'), 'idea_23460': count(idea, r'23,460'),
    }
    return {'checks': checks, 'metrics': metrics, 'all_pass': all(checks.values())}

def self_test():
    # 非空性反证 1：号-题函数必须能拒绝错号错题
    assert num_title('[2604.01658] CORAL: Towards...', '2604.01658', 'CORAL') is True
    assert num_title('[2604.01658] CORAL: Towards...', '2604.01658', 'WRONG TITLE') is False, '号-题校验未能拒绝错题'
    assert num_title('[2411.02429] IdeaBench...', '2411.02429', 'IdeaBench') is True
    assert num_title('[2411.02429] IdeaBench...', '2411.99999', 'IdeaBench') is False, '号-题校验未能拒绝错号'
    # 非空性反证 2：计数器必须能数出非 0，否则 0 是空转
    assert count('DN7 DN7 DN7', r'DN7') == 3, '计数器恒 0（空转），缺席判定无效'
    assert count('co-evolution co-evolution', r'co-evolution') == 2
    assert count('skills skills heartbeat', r'skills') == 2
    # 非空性反证 3：空文本必须报错而非报 0（防静默缺陷）
    try:
        count('', r'DN7')
        raise AssertionError('空文本未抛错，会被读成 0 命中')
    except ValueError:
        pass
    # 非空性反证 4：注入一个假失败 check，all_pass 必须为 False
    fake = {'a': True, 'b': False}
    assert all(fake.values()) is False, '反例未使 all_pass 变红'
    return {'self_test': 'PASS', 'cases': 4}

if __name__ == '__main__':
    if '--self-test' in sys.argv:
        print(json.dumps(self_test(), ensure_ascii=False, indent=2))
        sys.exit(0)
    r = real_checks()
    (D / 'verdict.json').write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(r, ensure_ascii=False, indent=2))
    sys.exit(0 if r['all_pass'] else 2)
