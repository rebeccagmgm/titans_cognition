from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = next(ROOT.glob("output/**/review/catalog-tree-visualization.html"))
SNAPSHOT = (
    ROOT.parents[1]
    / "股衍数据-Cookbook"
    / ".evidence-cache"
    / "indicator-dictionary-snapshots"
    / "20260812-refresh"
    / "indicators.jsonl"
)
UNCATALOGUED_PATH = "分类>指标标签目录>未分类"


def extract_const(text: str, name: str, next_name: str | None = None) -> tuple[str, int, int]:
    marker = f"const {name} = "
    start = text.index(marker) + len(marker)
    if next_name:
        match = re.search(rf";\r?\n    const {re.escape(next_name)}", text[start:])
        if not match:
            raise ValueError(f"could not find next const {next_name}")
        end = start + match.start()
    else:
        match = re.search(r";\r?\n", text[start:])
        if not match:
            raise ValueError(f"could not find end of const {name}")
        end = start + match.start()
    return text[start:end], start, end


def normalize_indicator(row: dict) -> dict:
    return {
        "indexId": row.get("indexId", ""),
        "chineseName": row.get("chineseName", ""),
        "englishName": row.get("englishName", ""),
        "status": row.get("status", ""),
        "indexType": row.get("indexType", ""),
        "dataLevel": row.get("dataLevel", ""),
        "dataSetConfigName": row.get("dataSetConfigName", ""),
        "busiCycle": row.get("busiCyc", ""),
        "techDirector": row.get("techDirector", ""),
        "businessDefinition": row.get("businessDefinition", ""),
        "abbreviation": row.get("abbreviation", ""),
        "dbName": row.get("dbName", ""),
        "engTblName": row.get("engTblName", ""),
        "indexGran": row.get("indexGran", ""),
        "horaeTaskId": row.get("horaeTaskId", ""),
        "indicatorUnit": row.get("indicatorUnit", ""),
        "includeGroupTypes": row.get("includeGroupTypes", ""),
        "includeTags": row.get("includeTags", ""),
        "createTime": row.get("createTime", ""),
        "lastUpdateTime": row.get("lastUpdateTime", ""),
        "catalog": row.get("catalog") or [],
    }


def patch_html() -> None:
    text = HTML.read_text(encoding="utf-8")
    rows = [json.loads(line) for line in SNAPSHOT.read_text(encoding="utf-8").splitlines() if line.strip()]
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        indicator = normalize_indicator(row)
        catalog = row.get("catalog") or []
        path = ">".join(catalog) if catalog else UNCATALOGUED_PATH
        grouped.setdefault(path, []).append(indicator)

    data_raw, data_start, data_end = extract_const(text, "data", "indicatorsByPath")
    data = json.loads(data_raw)
    data.setdefault("children", [])
    data["children"] = [
        child
        for child in data["children"]
        if child.get("path") != "分类>指标标签目录>未归类（源数据无目录）"
    ]
    uncatalogued_node = next(
        (child for child in data["children"] if child.get("path") == UNCATALOGUED_PATH),
        None,
    )
    if uncatalogued_node is None:
        data["children"].append(
            {
                "name": "未归类（源数据无目录）",
                "path": UNCATALOGUED_PATH,
                "indicatorCount": len(grouped.get(UNCATALOGUED_PATH, [])),
                "hasIndicators": True,
                "children": [],
            }
        )
    else:
        uncatalogued_node["name"] = "未归类（源数据无目录）"
        uncatalogued_node["indicatorCount"] = len(grouped.get(UNCATALOGUED_PATH, []))
        uncatalogued_node["hasIndicators"] = True
    data["indicatorCount"] = len(rows)
    data_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    text = text[:data_start] + data_json + text[data_end:]

    map_raw, map_start, map_end = extract_const(text, "indicatorsByPath")
    map_json = json.dumps(grouped, ensure_ascii=False, separators=(",", ":"))
    text = text[:map_start] + map_json + text[map_end:]

    text = text.replace(
        """    .detail-row {\n      padding: 6px 8px;\n      border: 1px solid var(--line);\n      border-radius: 8px;\n      background: var(--panel2);\n      font-size: 12px;\n      margin-bottom: 8px;\n      white-space: normal;\n      overflow: visible;\n      text-overflow: clip;\n    }""",
        """    .detail-row {\n      padding: 7px 8px;\n      border: 1px solid var(--line);\n      border-radius: 8px;\n      background: var(--panel2);\n      font-size: 12px;\n      margin-bottom: 8px;\n      white-space: normal;\n      overflow: visible;\n      text-overflow: clip;\n    }\n\n    .detail-row.multiline {\n      white-space: pre-wrap;\n      overflow-wrap: anywhere;\n    }""",
    )

    text = text.replace(
        """      li.dataset.status = indicator.status || '';\n\n      const left""",
        """      li.dataset.status = indicator.status || '';\n      li.dataset.businessDefinition = indicator.businessDefinition || '';\n\n      const left""",
    )

    text = text.replace(
        """    function isDomVisible(el) {
      if (!el) return false;
      const style = getComputedStyle(el);
      return style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
    }""",
        """    function isDomVisible(el) {
      if (!el || el.classList.contains('hidden')) return false;
      return !el.closest('.hidden');
    }""",
        1,
    )

    old_detail = re.compile(r"    function renderIndicatorDetail\(ind\) \{.*?\n    \}\n\n    function buildTree", re.S)
    new_detail = """    function renderIndicatorDetail(ind) {
      indicatorPanel.classList.remove('hidden');
      const title = ind.chineseName || ind.englishName || '(未命名)';
      const fields = [
        ['指标英文名', ind.englishName],
        ['业务定义', ind.businessDefinition],
        ['指标ID', ind.indexId],
        ['状态', ind.status],
        ['类型', ind.indexType],
        ['颗粒度', ind.dataLevel],
        ['指标粒度', ind.indexGran],
        ['周期', ind.busiCycle],
        ['负责人', ind.techDirector],
        ['数据库', ind.dbName],
        ['英文表名', ind.engTblName],
        ['Horae任务ID', ind.horaeTaskId],
        ['指标单位', ind.indicatorUnit],
        ['数据集', ind.dataSetConfigName],
        ['包含组合类型', ind.includeGroupTypes],
        ['包含标签', ind.includeTags],
        ['目录', Array.isArray(ind.catalog) ? ind.catalog.join(' > ') : ind.catalog],
        ['加工SQL', ind.processingSql || '未采集（源快照没有该字段）']
      ];

      const rows = fields
        .map(([key, value]) => {
          const display = value === undefined || value === null || value === '' ? '未采集' : String(value);
          const multiline = display.includes('\\n') || display.length > 100;
          return `<div class="detail-row${multiline ? ' multiline' : ''}"><strong>${escapeHtml(key)}：</strong>${escapeHtml(display)}</div>`;
        })
        .join('');

      indicatorPanelSub.textContent = title;
      indicatorPanelContent.innerHTML = rows + '<div class="copy-note">提示：点击指标项可再次查看该指标；“未采集”表示当前快照没有该字段，不代表业务上不存在。</div>';
    }

    function buildTree"""
    if "function updateVisibleNodeCounts()" not in text:
        text, count = old_detail.subn(new_detail, text, count=1)
        if count != 1:
            raise RuntimeError("could not replace renderIndicatorDetail")
    text = text.replace("display.includes('\n')", "display.includes('\\n')")

    old_summary = """    function refreshSummary(totalLeaves, totalIndicators, matchedLeaves = null, matchedIndicators = null) {\n      if (matchedLeaves == null) {\n        summary.textContent = `树叶节点: ${formatter.format(totalLeaves)} · 指标映射: ${formatter.format(totalIndicators)} 条`;\n      } else if (matchedIndicators == null) {\n        summary.textContent = `检索结果: ${formatter.format(matchedLeaves)} 个可见叶节点`;\n      } else {\n        summary.textContent = `检索结果: ${formatter.format(matchedLeaves)} 个可见叶节点 · ${formatter.format(matchedIndicators)} 条可见指标`;\n      }\n    }"""
    new_summary = """    function refreshSummary(totalLeaves, totalIndicators, matchedLeaves = null, matchedIndicators = null) {\n      if (matchedLeaves == null) {\n        summary.textContent = `目录节点: ${formatter.format(totalLeaves)} · 可见指标: ${formatter.format(totalIndicators)} 条`;\n      } else if (matchedIndicators == null) {\n        summary.textContent = `检索结果: ${formatter.format(matchedLeaves)} 个可见叶节点`;\n      } else {\n        summary.textContent = `检索结果: ${formatter.format(matchedLeaves)} 个可见叶节点 · ${formatter.format(matchedIndicators)} 条可见指标 / ${formatter.format(totalIndicators)} 条`;\n      }\n    }\n\n    function updateVisibleNodeCounts() {\n      root.querySelectorAll('.tree-item').forEach((item) => {\n        const rows = Array.from(item.querySelectorAll('.tree-indicator-item'));\n        if (!rows.length) return;\n        const visible = rows.filter((row) => !row.classList.contains('hidden')).length;\n        const branch = item.querySelector(':scope > details.tree-branch');\n        const badge = branch\n          ? branch.querySelector(':scope > summary .node-indicator .badge')\n          : item.querySelector(':scope > div > .tree-leaf .node-indicator .badge');\n        if (badge) badge.textContent = `${formatter.format(visible)} 个指标`;\n        const detailBadge = branch\n          ? branch.querySelector(':scope > summary .node-indicator .badge:nth-child(2)')\n          : item.querySelector(':scope > div > .tree-indicator-list')?.previousElementSibling?.querySelector('.node-indicator .badge:nth-child(2)');\n        if (detailBadge) detailBadge.textContent = `含明细 ${formatter.format(visible)}`;\n      });\n    }"""
    if "function updateVisibleNodeCounts()" not in text:
        if old_summary not in text:
            raise RuntimeError("could not find refreshSummary")
        text = text.replace(old_summary, new_summary, 1)

    text = text.replace(
        """      if (visibleLeafCount === 0 && visibleIndicatorsCount === 0) {\n        summary.textContent = '未匹配到任何节点';\n      } else {\n        refreshSummary(visibleLeafCount, totalIndicatorCount, visibleLeafCount, visibleIndicatorsCount);\n      }""",
        """      updateVisibleNodeCounts();\n      if (visibleLeafCount === 0 && visibleIndicatorsCount === 0) {\n        summary.textContent = '未匹配到任何节点';\n      } else {\n        refreshSummary(totalLeafCount, totalIndicatorCount, visibleLeafCount, visibleIndicatorsCount);\n      }""",
        1,
    )
    text = text.replace(
        """        refreshSummary(totalLeafCount, totalIndicatorCount);\n        return;""",
        """        updateVisibleNodeCounts();\n        refreshSummary(totalLeafCount, totalIndicatorCount);\n        return;""",
        1,
    )
    text = text.replace(
        """      refreshSummary(totalLeaf, totalIndicators);\n      bindHoverHighlight();""",
        """      refreshSummary(totalLeaf, totalIndicators);\n      updateVisibleNodeCounts();\n      bindHoverHighlight();""",
        1,
    )

    HTML.write_text(text, encoding="utf-8")
    print(f"patched {HTML} with {len(rows)} indicators and {len(grouped)} catalog paths")


if __name__ == "__main__":
    patch_html()
