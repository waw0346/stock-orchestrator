import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

log_path = r"C:\Users\kjw03\.gemini\antigravity\brain\be18f499-b2ea-4466-972a-1505f157e6ee\.system_generated\logs\transcript.jsonl"

try:
    steps = []
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            steps.append(json.loads(line))
            
    print("Let's look at steps 200 to 213:")
    for idx in range(200, min(214, len(steps))):
        s = steps[idx]
        print(f"=== STEP {s.get('step_index')} | {s.get('source')} | {s.get('type')} ===")
        print(s.get("content"))
        print()
except Exception as e:
    print("Error:", e)
