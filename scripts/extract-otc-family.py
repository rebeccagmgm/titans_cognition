# 查看指标快照记录结构 + 提取核心指标族（CompScal/DealScal/NomPrin 系列）
import json, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

path = r'E:\02_area\股衍数据-Cookbook\.evidence-cache\indicator-dictionary-snapshots\20260812-refresh\indicators.jsonl'

# 1. 打印主角指标完整记录，了解字段结构
with open(path, encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        if rec.get('indexId') == 'ind2024070561739587':
            print('=== 主角指标完整记录字段 ===')
            for k, v in rec.items():
                s = str(v)
                print(f'{k}: {s[:200]}')
            print()
            break

# 2. 核心族筛选：CompScal / DealScal / NomPrin 且含 OtcDeri 或 RgstComp
CORE = ['CompScal', 'DealScal', 'NomPrin', 'DynaNomPrin']
hits = []
with open(path, encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        en = rec.get('englishName', '') or ''
        if en.startswith('grp1_') and any(k in en for k in CORE) and ('OtcDeri' in en or 'RgstComp' in en):
            hits.append(rec)

print(f'=== 核心指标族（CompScal/DealScal/NomPrin × OtcDeri/RgstComp）: {len(hits)} 个 ===')
for r in hits:
    # 找中文名：尝试多个字段
    name = (r.get('indexName') or r.get('name') or r.get('chineseName') or
            r.get('indexNameCn') or r.get('displayName') or '?')
    busi = (r.get('caliberDesc') or r.get('caliber') or r.get('busiDesc') or r.get('definition') or '')
    print(f"{r.get('indexId')} | {r.get('englishName')} | 中文: {name} | 口径: {busi[:100]}")
