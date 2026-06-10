import os
import re
import json
import sys
import io
from datetime import datetime, timedelta

# Enforce UTF-8 for Windows terminal environments
if sys.platform.startswith('win'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

VAULT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'obsidian', 'stock_log'))
DASHBOARD_PATH = os.path.join(VAULT_DIR, '09_decision_journal', 'metacognitive_dashboard.md')
ALERTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'picks', 'alerts'))
ACTIVITY_JSON_PATH = os.path.join(ALERTS_DIR, 'metacognitive_activity.json')

EXCLUDE_DIRS = {'.makemd', '.obsidian', '.smart-env', '.space', '_templates', '.git', '99_archive'}

def parse_frontmatter(content):
    if not content.startswith('---'):
        return None, content
    parts = content.split('---', 2)
    if len(parts) >= 3:
        frontmatter_text = parts[1]
        body = parts[2]
        properties = {}
        for line in frontmatter_text.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if ':' in line:
                key, val = line.split(':', 1)
                key = key.strip()
                val = val.strip()
                # Clean quotes and lists
                if val.startswith('[') and val.endswith(']'):
                    val = [x.strip().strip('"').strip("'") for x in val[1:-1].split(',')]
                elif val.startswith('"') and val.endswith('"'):
                    val = val[1:-1]
                elif val.startswith("'") and val.endswith("'"):
                    val = val[1:-1]
                properties[key] = val
        return properties, body
    return None, content

def get_category_from_path(rel_path):
    parts = rel_path.split('/')
    if not parts or len(parts) < 2:
        return "Other"
    
    dir_name = parts[0]
    if 'daily_logs' in dir_name:
        return "Daily Logs (대화/일지)"
    elif 'stock_analysis' in dir_name:
        return "Stock Analysis (주식 분석)"
    elif 'market_news' in dir_name:
        return "Market News (시장 뉴스)"
    elif 'decision_journal' in dir_name:
        return "Decision Journal (의사결정)"
    elif 'execution_logs' in dir_name:
        return "Execution Logs (실행 로그)"
    elif 'todos' in dir_name:
        return "Todos (할 일)"
    elif 'strategy_playbooks' in dir_name:
        return "Strategy Playbooks (전략)"
    elif 'calendar' in dir_name:
        return "Calendar (캘린더)"
    else:
        return f"Miscellaneous ({dir_name})"

def scan_activities(scan_all=False):
    print(f"[Metacognitive Scan] Scanning Vault: {VAULT_DIR}")
    
    cutoff_time = datetime.now() - timedelta(hours=24)
    activities = []
    high_priority_items = []
    scanned_count = 0
    
    # regex patterns
    priority_pattern = re.compile(r'#priority/high', re.IGNORECASE)
    
    for root, dirs, files in os.walk(VAULT_DIR):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for file in files:
            if not file.endswith('.md'):
                continue
                
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, VAULT_DIR).replace('\\', '/')
            
            # Skip dashboard itself to prevent self-recursion
            if os.path.abspath(file_path) == os.path.abspath(DASHBOARD_PATH):
                continue
                
            # Get file modification time
            mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
            is_recent = mtime >= cutoff_time
            
            if not scan_all and not is_recent:
                continue
                
            scanned_count += 1
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception as e:
                print(f"[WARN] Failed to read {rel_path}: {e}")
                continue
                
            properties, body = parse_frontmatter(content)
            properties = properties or {}
            
            # Identify high priority
            is_high_priority = False
            priority_reason = ""
            
            # Check Frontmatter for priority
            if 'priority' in properties:
                val = str(properties['priority']).lower()
                if val == 'high' or val == '1' or val == 'critical':
                    is_high_priority = True
                    priority_reason = f"Frontmatter priority: {properties['priority']}"
            elif 'importance' in properties:
                val = str(properties['importance']).lower()
                if val == 'high' or val == '1' or val == 'critical':
                    is_high_priority = True
                    priority_reason = f"Frontmatter importance: {properties['importance']}"
            
            # Check Body for #priority/high tag
            if not is_high_priority and priority_pattern.search(body):
                is_high_priority = True
                priority_reason = "Contains #priority/high in body text"
                
            category = get_category_from_path(rel_path)
            ticker = properties.get('ticker', '')
            evidence_type = properties.get('evidence_type', properties.get('type', ''))
            
            activity_entry = {
                "file_name": file,
                "rel_path": rel_path,
                "category": category,
                "ticker": ticker,
                "evidence_type": evidence_type,
                "modified_time": mtime.strftime("%Y-%m-%d %H:%M:%S"),
                "is_new": is_recent, # simple approximation
                "priority_status": "HIGH" if is_high_priority else "NORMAL"
            }
            
            activities.append(activity_entry)
            
            if is_high_priority:
                high_priority_items.append({
                    "file_name": file,
                    "rel_path": rel_path,
                    "ticker": ticker,
                    "reason": priority_reason,
                    "modified_time": mtime.strftime("%Y-%m-%d %H:%M:%S")
                })
                
    # Sort activities by modified time descending
    activities.sort(key=lambda x: x["modified_time"], reverse=True)
    
    return activities, high_priority_items, scanned_count

def update_dashboard(activities, high_priority_items):
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # Generate metadata block
    lines = [
        "---",
        "title: Metacognitive Activity Dashboard",
        f"date: {today_str}",
        "type: decision-journal",
        "tags:",
        "  - stock-orchestrator",
        "  - metacognition",
        "  - dashboard",
        "---",
        "",
        "# 🧭 메타인지 기록 및 중요 활동 대시보드",
        f"마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 💡 추후 시스템 반영 필요 항목 (High Priority)",
        "노트 내 `#priority/high` 태그 혹은 Frontmatter `priority: high`로 분류된 시스템 개선 및 주요 추적 목록입니다. 이 분석 및 의견들은 사실 검증을 거친 후 추후 시스템 알고리즘 및 규칙에 자동 반영되도록 정리해 놓아야 합니다.",
        ""
    ]
    
    if not high_priority_items:
        lines.append("🟢 현재 수집된 중요도 상향 반영 후보 항목이 없습니다.")
    else:
        lines.append("| Ticker | 파일명 | 감지 사유 | 수정 일시 |")
        lines.append("|---|---|---|---|")
        for item in high_priority_items:
            file_link = f"[{item['file_name']}](file:///{os.path.join(VAULT_DIR, item['rel_path']).replace('\\', '/')})"
            ticker_str = f"`{item['ticker']}`" if item['ticker'] else "-"
            lines.append(f"| {ticker_str} | {file_link} | {item['reason']} | {item['modified_time']} |")
            
    lines.append("")
    lines.append("## 📊 오늘의 기록 활동 현황 (최근 24시간)")
    lines.append("오늘 수집 및 작성된 뉴스, 주식 분석, 대화, 의사결정 기록들을 메타데이터와 함께 분류 정리했습니다.")
    lines.append("")
    
    if not activities:
        lines.append("ℹ️ 최근 24시간 내에 기록되거나 수정된 활동이 없습니다.")
    else:
        # Group by category
        categories = {}
        for act in activities:
            cat = act["category"]
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(act)
            
        for cat, items in categories.items():
            lines.append(f"### 📂 {cat}")
            lines.append("| 파일명 | Ticker | Evidence Type | 수정 일시 |")
            lines.append("|---|---|---|---|")
            for item in items:
                file_link = f"[{item['file_name']}](file:///{os.path.join(VAULT_DIR, item['rel_path']).replace('\\', '/')})"
                ticker_str = f"`{item['ticker']}`" if item['ticker'] else "-"
                ev_str = f"`{item['evidence_type']}`" if item['evidence_type'] else "-"
                # Highlight if priority high
                prefix = "🔥 " if item['priority_status'] == "HIGH" else ""
                lines.append(f"| {prefix}{file_link} | {ticker_str} | {ev_str} | {item['modified_time']} |")
            lines.append("")
            
    # Write dashboard
    os.makedirs(os.path.dirname(DASHBOARD_PATH), exist_ok=True)
    with open(DASHBOARD_PATH, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
        
    print(f"[OK] Metacognitive dashboard updated at: {DASHBOARD_PATH}")

def save_activity_json(activities, high_priority_items, scanned_count):
    summary = {
        "as_of": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "scanned_files_count": scanned_count,
        "recent_activity_count": len(activities),
        "high_priority_count": len(high_priority_items),
        "high_priority_items": [
            {
                "file_name": x["file_name"],
                "rel_path": x["rel_path"],
                "ticker": x["ticker"],
                "reason": x["reason"],
                "modified_time": x["modified_time"]
            } for x in high_priority_items
        ],
        "recent_activities": [
            {
                "file_name": x["file_name"],
                "category": x["category"],
                "ticker": x["ticker"],
                "modified_time": x["modified_time"]
            } for x in activities[:10] # Save top 10 for lightweight integration
        ]
    }
    
    os.makedirs(os.path.dirname(ACTIVITY_JSON_PATH), exist_ok=True)
    with open(ACTIVITY_JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
        
    print(f"[OK] Metacognitive activity JSON saved at: {ACTIVITY_JSON_PATH}")
    return summary

def main():
    import sys
    scan_all = '--all' in sys.argv
    
    # 1. Scan vault activities
    activities, high_priority_items, scanned_count = scan_activities(scan_all=scan_all)
    
    # 2. Update metacognitive_dashboard.md
    update_dashboard(activities, high_priority_items)
    
    # 3. Save JSON summary for integration
    summary = save_activity_json(activities, high_priority_items, scanned_count)
    
    # Print clean terminal summary
    print("\n==================================================")
    print("Obsidian Metacognitive Activity Monitoring Summary")
    print("==================================================")
    print(f"Scanned files count: {scanned_count}")
    print(f"Recent 24h activity count: {len(activities)}")
    print(f"High priority (action candidate) count: {len(high_priority_items)}")
    
    if high_priority_items:
        print("\nHigh Priority items detected:")
        for item in high_priority_items:
            print(f"  - [{item['ticker'] or 'No Ticker'}] {item['file_name']} (Mtime: {item['modified_time']})")
            print(f"    └ Reason: {item['reason']}")
            
    print("==================================================")

if __name__ == '__main__':
    main()
