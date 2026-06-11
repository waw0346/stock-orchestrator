import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

log_path = r"C:\Users\kjw03\.gemini\antigravity\brain\be18f499-b2ea-4466-972a-1505f157e6ee\.system_generated\logs\transcript.jsonl"

try:
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            obj = json.loads(line)
            step_idx = obj.get("step_index")
            if step_idx in [208, 209, 210]:
                print(f"=== STEP {step_idx} | {obj.get('source')} | {obj.get('type')} ===")
                print(obj.get("content"))
                print()
except Exception as e:
    print("Error:", e)
