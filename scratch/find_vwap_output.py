import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

log_path = r"C:\Users\kjw03\.gemini\antigravity\brain\be18f499-b2ea-4466-972a-1505f157e6ee\.system_generated\logs\transcript.jsonl"

try:
    with open(log_path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            obj = json.loads(line)
            content = obj.get("content", "")
            tool_calls = obj.get("tool_calls", [])
            
            # Check if VWAP results or Samsung Biologics calculation output are in content
            if "1,292,779" in content or "1,292,779" in str(tool_calls) or "207940" in content:
                print(f"=== STEP {obj.get('step_index')} | {obj.get('source')} | {obj.get('type')} ===")
                if len(content) > 500:
                    print(content[:500] + "... [TRUNCATED]")
                else:
                    print(content)
                print()
except Exception as e:
    print("Error:", e)
