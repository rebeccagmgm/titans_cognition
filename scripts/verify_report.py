# -*- coding: utf-8 -*-
"""验证 HTML 报告完整性。"""
p = 'output/titans-collection-20260815/stats/titans-collection-report.html'
with open(p, encoding='utf-8') as f:
    content = f.read()
print('大小:', len(content), '字符')
checks = {
    '标题': 'TITANS 采集链路全景统计' in content,
    '13 schema 小节': '13 个源 schema' in content,
    '任务TOP含244357': '244357' in content,
    'UNKNOWN含email_finbd': 'email_finbd_airbagx_liquidation_detail' in content,
    '结尾完整': content.strip().endswith('</html>'),
    '卡片数=5': content.count('class="card"') == 5,
    'bar-row>20': content.count('bar-row') > 20,
}
for k, v in checks.items():
    print(f'  {k}: {v}')
print('全部通过:', all(checks.values()))
