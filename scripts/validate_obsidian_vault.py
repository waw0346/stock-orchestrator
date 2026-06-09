import os
import re
import json
from datetime import datetime

VAULT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'obsidian', 'stock_log'))
REPORT_PATH = os.path.join(VAULT_DIR, '08_error_reviews', 'vault_hygiene_report.md')

EXCLUDE_DIRS = {'.makemd', '.obsidian', '.smart-env', '.space', '_templates', '.git'}
VALID_EVIDENCE_TYPES = {
    # Core Evidence Types
    'report', 'artifact', 'analysis', 'news', 'research_fact',
    # Operating & Log Types
    'daily-log', 'execution-log', 'execution_log', 'todo', 'candidate-board', 'commit-log', 'error-review', 'decision-journal',
    # Stock Hub & Index Types
    'stock-hub', 'stock-analysis', 'stock-analysis-archive', 'stock-analysis-index', 'investment-decision-ledger',
    # MOC & Meta Types
    'moc', 'design-doc', 'theme-map', 'ticker-trail', 'strategy-playbook', 'strategy_playbook', 'operating-charter',
    # Market & Screening Types
    'market-analysis', 'market-news', 'pullback-screen',
    # Calendar Types
    'stock-calendar-day', 'stock-calendar-month', 'stock-calendar-year', 'index', 'calendar-sync-history'
}

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
                # Clean quotes
                if val.startswith('[') and val.endswith(']'):
                    val = [x.strip().strip('"').strip("'") for x in val[1:-1].split(',')]
                elif val.startswith('"') and val.endswith('"'):
                    val = val[1:-1]
                elif val.startswith("'") and val.endswith("'"):
                    val = val[1:-1]
                properties[key] = val
        return properties, body
    return None, content

def run_validation():
    print(f"Scanning Vault: {VAULT_DIR}")
    
    # 1. Map all existing files in the vault (case-insensitive keys)
    # We map template files so links to them work, but exclude transient dot-folders
    existing_files = {}
    total_files_scanned = 0
    map_exclude = {'.makemd', '.obsidian', '.smart-env', '.space', '.git'}
    
    for root, dirs, files in os.walk(VAULT_DIR):
        dirs[:] = [d for d in dirs if d not in map_exclude]
        for file in files:
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, VAULT_DIR).replace('\\', '/')
            name_without_ext = os.path.splitext(file)[0]
            
            existing_files[name_without_ext.lower()] = rel_path
            existing_files[rel_path.lower()] = rel_path
            total_files_scanned += 1


    # 2. Inspect individual files
    issues = []
    dead_links_count = 0
    invalid_properties_count = 0
    
    link_pattern = re.compile(r'\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]')
    ticker_pattern = re.compile(r'^\d{6}$')
    date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}') # Match starting with YYYY-MM-DD

    for root, dirs, files in os.walk(VAULT_DIR):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for file in files:
            if not file.endswith('.md'):
                continue
                
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, VAULT_DIR).replace('\\', '/')
            
            # Skip reading the hygiene report itself to prevent recursion loop
            if os.path.abspath(file_path) == os.path.abspath(REPORT_PATH):
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception as e:
                issues.append({
                    "file": rel_path,
                    "type": "read_error",
                    "severity": "CRITICAL",
                    "message": f"Failed to read file: {str(e)}"
                })
                continue
                
            properties, body = parse_frontmatter(content)
            
            # Check Properties/Frontmatter
            if properties:
                # Validate ticker
                if 'ticker' in properties:
                    tickers = properties['ticker']
                    # Handle both list and string
                    if not isinstance(tickers, list):
                        tickers = [tickers] if tickers is not None else []
                    
                    for tk in tickers:
                        tk_str = str(tk).strip()
                        if tk_str and tk_str != "SYSTEM" and not ticker_pattern.match(tk_str):
                            issues.append({
                                "file": rel_path,
                                "type": "invalid_property",
                                "severity": "WARN",
                                "message": f"Invalid ticker code: '{tk_str}' (must be 6 digits or 'SYSTEM')"
                            })
                            invalid_properties_count += 1
                
                # Validate date / as_of
                for date_key in ['date', 'as_of']:
                    if date_key in properties:
                        date_val = str(properties[date_key]).strip()
                        # Handle yearly or monthly formats
                        if len(date_val) == 4 or len(date_val) == 7: # YYYY or YYYY-MM
                            continue
                        if not date_pattern.match(date_val):
                            issues.append({
                                "file": rel_path,
                                "type": "invalid_property",
                                "severity": "WARN",
                                "message": f"Invalid format for '{date_key}': '{date_val}' (must start with YYYY-MM-DD)"
                            })
                            invalid_properties_count += 1

                
                # Validate type / evidence_type
                for type_key in ['type', 'evidence_type']:
                    if type_key in properties:
                        t_val = str(properties[type_key])
                        if t_val not in VALID_EVIDENCE_TYPES:
                            issues.append({
                                "file": rel_path,
                                "type": "invalid_property",
                                "severity": "WARN",
                                "message": f"Unknown {type_key}: '{t_val}'"
                            })
                            invalid_properties_count += 1
            
            # Check internal links
            links = link_pattern.findall(body)
            # Also check links in frontmatter text if any, but regex body is sufficient
            for link in links:
                link_clean = link.strip().replace('\\', '/')
                # Allow referencing files with folders or just names
                link_lower = link_clean.lower()
                
                # Strip leading/trailing slashes or dots
                link_lower_clean = link_lower.strip('/')
                
                # Check match
                matched = False
                if link_lower_clean in existing_files:
                    matched = True
                elif link_lower_clean.split('/')[-1] in existing_files:
                    matched = True
                
                if not matched:
                    # Ignore links to future/uncaptured daily logs or calendar days
                    # that are intentionally created ahead as references.
                    # We only warn for general files that are broken.
                    is_future_daily = 'daily_logs' in link_lower or 'calendar' in link_lower or re.match(r'^\d{4}-\d{2}-\d{2}', link_clean)
                    severity = "INFO" if is_future_daily else "WARN"
                    
                    issues.append({
                        "file": rel_path,
                        "type": "dead_link",
                        "severity": severity,
                        "message": f"Internal link target not found: [[{link}]]"
                    })
                    if severity == "WARN":
                        dead_links_count += 1

    # 3. Generate Report
    report_lines = [
        "---",
        "title: Vault Hygiene Report",
        "date: " + datetime.now().strftime("%Y-%m-%d"),
        "type: error-review",
        "status: active",
        "tags:",
        "  - stock-orchestrator",
        "  - hygiene-report",
        "---",
        "",
        "# 🧹 Vault Hygiene & Metacognitive Report",
        f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 📊 Summary",
        f"- **Total Files Scanned**: {total_files_scanned}",
        f"- **Invalid Properties Found**: {invalid_properties_count}",
        f"- **Dead Links Found (Warnings)**: {dead_links_count}",
        f"- **Status**: " + ("🔴 Action Required" if (invalid_properties_count + dead_links_count) > 0 else "🟢 Healthy"),
        "",
        "## 🔍 Detailed Issues List",
        ""
    ]
    
    if not issues:
        report_lines.append("🟢 No structural issues found in the Obsidian Vault.")
    else:
        # Group by file
        file_groups = {}
        for issue in issues:
            f = issue["file"]
            if f not in file_groups:
                file_groups[f] = []
            file_groups[f].append(issue)
            
        for f, f_issues in file_groups.items():
            report_lines.append(f"### 📄 [{f}](file:///{os.path.join(VAULT_DIR, f).replace('\\', '/')})")
            for iss in f_issues:
                prefix = "⚠️" if iss["severity"] == "WARN" else "🔴" if iss["severity"] == "CRITICAL" else "ℹ️"
                report_lines.append(f"- {prefix} **[{iss['type']}]** ({iss['severity']}): {iss['message']}")
            report_lines.append("")
            
    # Ensure directory exists
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    
    with open(REPORT_PATH, 'w', encoding='utf-8') as rf:
        rf.write('\n'.join(report_lines))
        
    print(f"Hygiene report successfully generated at: {REPORT_PATH}")
    
    # Return JSON for agent parse
    summary = {
        "total_files": total_files_scanned,
        "invalid_properties": invalid_properties_count,
        "dead_links": dead_links_count,
        "status": "WARN" if (invalid_properties_count + dead_links_count) > 0 else "HEALTHY",
        "issues_summary": issues[:10] # Output first 10 issues
    }
    return json.dumps(summary, indent=2)

if __name__ == '__main__':
    result_json = run_validation()
    print("--- JSON SUMMARY ---")
    print(result_json)
