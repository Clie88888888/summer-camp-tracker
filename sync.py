#!/usr/bin/env python3
"""
夏令营投递记录 → 网页生成器
读取桌面上的 夏令营投递记录.md，生成漂亮的HTML网页并自动推送到GitHub Pages
"""

import re
import os
import subprocess
import sys
from datetime import date

# === 路径配置 ===
# 先尝试工作区副本，没有则读桌面原文件
MD_WORK = os.path.expanduser("~/.openclaw/workspace/camp-tracker/record.md")
MD_DESKTOP = os.path.expanduser("~/Desktop/夏令营投递记录.md")
MD_PATH = MD_WORK if os.path.exists(MD_WORK) else MD_DESKTOP
HTML_PATH = os.path.expanduser("~/.openclaw/workspace/camp-tracker/index.html")
REPO_DIR = os.path.expanduser("~/.openclaw/workspace/camp-tracker")

# === 学校颜色映射 ===
SCHOOL_COLORS = {
    "清华大学": {"emoji": "🎓", "accent": "#2563eb"},
    "北京大学": {"emoji": "🏛️", "accent": "#7c3aed"},
    "浙江大学": {"emoji": "🏫", "accent": "#dc2626"},
    "其他":     {"emoji": "🏢", "accent": "#0891b2"},
}

# === 状态对应的 CSS class ===
STATUS_CLASS = {
    "🎉": "badge-accepted",
    "✅": "badge-submitted",
    "⏳": "badge-pending",
    "❌": "badge-rejected",
}

STATUS_LABEL = {
    "🎉": "🎉 入营",
    "✅": "✅ 已提交",
    "❌": "❌ 未入营",
    "⏳": "⏳ 待处理",
}


def parse_markdown():
    """解析 markdown 文件，返回结构化数据"""
    with open(MD_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()

    schools = []
    current_school = None
    current_table_header = None
    in_table = False

    for line in lines:
        line = line.rstrip()

        # 学校标题：## 🎓 清华大学
        m = re.match(r'^##\s+(\S.*)$', line)
        if m and not line.startswith("###"):
            title = m.group(1).strip()
            if current_school:
                schools.append(current_school)
            current_school = {
                "title": title,
                "entries": [],
                "has_school_col": False,  # "其他"部分有学校列
            }
            in_table = False
            continue

        if current_school is None:
            continue

        # 表格行
        if line.startswith("|"):
            cells = [c.strip() for c in line.split("|")[1:-1]]

            # 表头行检测
            if cells[0] == "序号":
                # 在列中找各关键列的位置
                has_entry_col = any("学院" in c or "专业" in c for c in cells)
                has_school_col = any("学校" in c for c in cells)
                has_deadline = any("截止" in c for c in cells)
                has_status = any("状态" in c for c in cells)
                if has_entry_col and (has_deadline or has_status):
                    current_table_header = cells
                    current_school["has_school_col"] = has_school_col
                    in_table = True
                    continue

            # 分隔行
            if re.match(r'^\|[\s\-:]+\|', line):
                continue

            # 数据行
            if in_table and len(cells) >= 4:
                entry = {}
                if current_school["has_school_col"] and len(cells) >= 5:
                    entry["school"] = cells[1]
                    entry["name"] = cells[2]
                    entry["deadline"] = cells[3]
                    entry["status_raw"] = cells[4]
                    entry["note"] = cells[5] if len(cells) >= 6 else ""
                else:
                    entry["name"] = cells[1]
                    entry["deadline"] = cells[2]
                    entry["status_raw"] = cells[3]
                    entry["note"] = cells[4] if len(cells) >= 5 else ""

                # 解析状态
                status_text = entry["status_raw"]
                if status_text.startswith("🎉"):
                    entry["status_icon"] = "🎉"
                    rest = status_text[1:].strip()
                    if rest and rest != "入营":
                        entry["status_label"] = f"🎉 {rest}"
                    else:
                        entry["status_label"] = "🎉 入营"
                elif status_text.startswith("✅"):
                    entry["status_icon"] = "✅"
                    entry["status_label"] = "✅ 已提交"
                elif status_text.startswith("❌"):
                    entry["status_icon"] = "❌"
                    entry["status_label"] = "❌ 未入营"
                elif status_text.startswith("⏳"):
                    entry["status_icon"] = "⏳"
                    rest = status_text[1:].strip()
                    if rest:
                        entry["status_label"] = f"⏳ {rest}"
                    else:
                        entry["status_label"] = "⏳ 待处理"
                else:
                    entry["status_icon"] = "⏳"
                    entry["status_label"] = status_text

                # 状态CSS class
                entry["status_class"] = STATUS_CLASS.get(entry["status_icon"], "badge-pending")
                if "面试" in entry.get("status_label", "") or "等待" in entry.get("status_label", ""):
                    entry["status_class"] = "badge-interview"

                current_school["entries"].append(entry)

    if current_school:
        schools.append(current_school)

    return schools


def compute_stats(schools):
    """计算统计数字"""
    stats = {"🎉": 0, "✅": 0, "⏳": 0, "❌": 0}
    for school in schools:
        for entry in school["entries"]:
            icon = entry["status_icon"]
            if icon in stats:
                stats[icon] += 1
    return stats


def escape_html(text):
    """HTML转义"""
    return (text.replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;"))


def render_html(schools, stats):
    """生成完整 HTML"""
    today = date.today().strftime("%Y年%m月%d日")

    # 生成学校区块
    school_html_parts = []

    for school in schools:
        entries = school["entries"]
        if not entries:
            continue

        count = len(entries)
        school_emoji = "🏫"
        school_accent = "#6366f1"
        for keyword, info in SCHOOL_COLORS.items():
            if keyword in school["title"]:
                school_emoji = info["emoji"]
                school_accent = info["accent"]
                break

        title_display = school["title"].replace("（含深研院SIGS）", "")

        # 表头
        if school["has_school_col"]:
            headers = ["学校", "学院/专业", "截止日期", "状态", "备注"]
        else:
            headers = ["学院/专业", "截止日期", "状态", "备注"]

        rows_html = ""
        for entry in entries:
            cols = []
            if school["has_school_col"]:
                cols.append(f'<td class="col-name">{escape_html(entry.get("school",""))}</td>')
            cols.append(f'<td class="col-name">{escape_html(entry["name"])}</td>')
            cols.append(f'<td class="col-deadline">{escape_html(entry["deadline"])}</td>')
            cols.append(f'<td><span class="badge {entry["status_class"]}">{escape_html(entry["status_label"])}</span></td>')
            note = escape_html(entry["note"])
            if not note or note == "—":
                note = "—"
            cols.append(f'<td class="col-note">{note}</td>')

            rows_html += f"<tr>{''.join(cols)}</tr>\n"

        school_html_parts.append(f"""
  <div class="school-section">
    <div class="school-title" style="--school-accent: {school_accent}">
      {escape_html(title_display)}
      <span class="badge-count">{count}</span>
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            {"".join(f"<th>{h}</th>" for h in headers)}
          </tr>
        </thead>
        <tbody>
          {rows_html}
        </tbody>
      </table>
    </div>
  </div>""")

    school_html = "\n".join(school_html_parts)

    # 统计摘要
    stats_html = f"""
      <div class="stat-item" style="--stat-color: #10b981">🎉 入营 <span class="num">{stats["🎉"]}</span></div>
      <div class="stat-item" style="--stat-color: #3b82f6">✅ 已提交 <span class="num">{stats["✅"]}</span></div>
      <div class="stat-item" style="--stat-color: #f59e0b">⏳ 待处理 <span class="num">{stats["⏳"]}</span></div>
      <div class="stat-item" style="--stat-color: #ef4444">❌ 未入营 <span class="num">{stats["❌"]}</span></div>"""

    # 完整 HTML 模板
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>陈立业 · 夏令营投递追踪</title>
<style>
  :root {{
    --bg: #f5f7fa;
    --card: #ffffff;
    --text: #1a1a2e;
    --muted: #6b7280;
    --border: #e5e7eb;
    --accent: #6366f1;
    --accent-light: #eef2ff;
    --green: #10b981;
    --green-bg: #ecfdf5;
    --red: #ef4444;
    --red-bg: #fef2f2;
    --amber: #f59e0b;
    --amber-bg: #fffbeb;
    --blue: #3b82f6;
    --blue-bg: #eff6ff;
    --gray: #9ca3af;
    --gray-bg: #f3f4f6;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans SC", sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    padding: 20px;
  }}
  .container {{ max-width: 920px; margin: 0 auto; }}

  /* Header */
  .header {{
    text-align: center;
    padding: 32px 20px 24px;
  }}
  .header h1 {{
    font-size: 28px;
    font-weight: 700;
    letter-spacing: -0.5px;
  }}
  .header h1 span {{ color: var(--accent); }}
  .header p {{
    color: var(--muted);
    font-size: 14px;
    margin-top: 6px;
  }}
  .header .stats {{
    display: flex;
    justify-content: center;
    gap: 16px;
    margin-top: 18px;
    flex-wrap: wrap;
  }}
  .stat-item {{
    background: var(--card);
    border-radius: 12px;
    padding: 10px 18px;
    box-shadow: 0 1px 3px rgba(0,0,0,.06);
    font-size: 14px;
    display: flex;
    align-items: center;
    gap: 6px;
  }}
  .stat-item .num {{
    font-weight: 700;
    font-size: 18px;
    color: var(--stat-color, var(--accent));
  }}

  /* Section */
  .school-section {{ margin-bottom: 28px; }}
  .school-title {{
    font-size: 20px;
    font-weight: 700;
    padding: 16px 0 12px;
    border-bottom: 2px solid var(--border);
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  .school-title .badge-count {{
    font-size: 12px;
    background: var(--accent-light);
    color: var(--accent);
    padding: 2px 10px;
    border-radius: 20px;
    font-weight: 600;
  }}

  /* Table */
  .table-wrap {{
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    border-radius: 12px;
    border: 1px solid var(--border);
    background: var(--card);
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    min-width: 580px;
  }}
  thead th {{
    background: #f9fafb;
    padding: 12px 14px;
    font-size: 12px;
    font-weight: 600;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    text-align: left;
    border-bottom: 1px solid var(--border);
  }}
  tbody td {{
    padding: 12px 14px;
    font-size: 14px;
    border-bottom: 1px solid #f3f4f6;
    vertical-align: middle;
  }}
  tbody tr:last-child td {{ border-bottom: none; }}
  tbody tr:hover {{ background: #fafbfc; }}
  .col-name {{ font-weight: 600; }}
  .col-deadline {{ white-space: nowrap; color: var(--muted); font-size: 13px; }}

  /* Badges */
  .badge {{
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
    white-space: nowrap;
  }}
  .badge-accepted {{ background: var(--green-bg); color: #065f46; }}
  .badge-submitted {{ background: var(--blue-bg); color: #1e40af; }}
  .badge-rejected {{ background: var(--red-bg); color: #991b1b; }}
  .badge-pending {{ background: var(--amber-bg); color: #92400e; }}
  .badge-draft {{ background: var(--gray-bg); color: #4b5563; }}
  .badge-interview {{ background: #f0f9ff; color: #0369a1; }}
  .col-note {{ color: var(--muted); font-size: 13px; max-width: 200px; }}

  /* Footer */
  .footer {{
    text-align: center;
    padding: 32px 0 20px;
    color: var(--muted);
    font-size: 13px;
  }}
  .footer .update-info {{
    display: inline-flex;
    align-items: center;
    gap: 4px;
    background: var(--card);
    padding: 6px 14px;
    border-radius: 20px;
    box-shadow: 0 1px 3px rgba(0,0,0,.06);
  }}

  @media (max-width: 640px) {{
    body {{ padding: 12px; }}
    .header h1 {{ font-size: 22px; }}
    .school-title {{ font-size: 17px; }}
    table {{ min-width: 480px; }}
    tbody td {{ padding: 10px 10px; font-size: 13px; }}
    thead th {{ padding: 10px; font-size: 11px; }}
    .col-note {{ max-width: 140px; font-size: 12px; }}
  }}
</style>
</head>
<body>
<div class="container">

  <div class="header">
    <h1>🏫 <span>陈立业</span> · 夏令营投递</h1>
    <p>📋 记录每一个机会</p>
    <div class="stats">
      {stats_html}
    </div>
  </div>

  {school_html}

  <div class="footer">
    <div class="update-info">🕐 最后更新：{today}</div>
  </div>

</div>
</body>
</html>"""
    return html


def build_and_deploy():
    """读取md → 生成html → git add/commit/push"""
    print("📖 读取 markdown 文件...")
    schools = parse_markdown()
    total = sum(len(s["entries"]) for s in schools)
    print(f"   解析到 {len(schools)} 个学校，共 {total} 条记录")

    stats = compute_stats(schools)
    acc, sub, pend, rej = stats["🎉"], stats["✅"], stats["⏳"], stats["❌"]
    print(f"   统计：🎉{acc} ✅{sub} ⏳{pend} ❌{rej}")

    print("🎨 生成 HTML...")
    html = render_html(schools, stats)

    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"   ✅ HTML 已写入 {HTML_PATH}")

    print("📦 Git 提交...")
    result = subprocess.run(
        ["git", "-C", REPO_DIR, "add", "index.html"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"   ⚠️ git add 失败: {result.stderr}")
        return False

    result = subprocess.run(
        ["git", "-C", REPO_DIR, "diff", "--cached", "--quiet"],
        capture_output=True
    )
    if result.returncode == 0:
        print("   ℹ️  没有变更，跳过提交")
        return True

    result = subprocess.run(
        ["git", "-C", REPO_DIR, "commit", "-m", "🔄 auto: 更新夏令营投递记录"],
        capture_output=True, text=True
    )
    print(f"   {result.stdout.strip()}")
    if result.returncode != 0:
        print(f"   ⚠️ commit 失败: {result.stderr}")
        return False

    print("☁️ 推送到 GitHub...")
    result = subprocess.run(
        ["git", "-C", REPO_DIR, "push"],
        capture_output=True, text=True
    )
    print(f"   {result.stdout.strip()}")
    if result.returncode != 0:
        print(f"   ⚠️ push 失败: {result.stderr}")
        # 尝试用 token 推
        return False

    print("✅ 部署完成！")
    return True


if __name__ == "__main__":
    if not os.path.exists(MD_PATH):
        print(f"❌ 找不到文件: {MD_PATH}")
        sys.exit(1)

    if len(sys.argv) > 1 and sys.argv[1] == "--watch":
        print("🔄 文件监听模式启动中...")
    else:
        if build_and_deploy():
            sys.exit(0)
        else:
            sys.exit(1)
