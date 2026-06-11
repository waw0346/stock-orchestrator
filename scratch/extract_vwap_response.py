import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

log_path = r"C:\Users\kjw03\.gemini\antigravity\brain\be18f499-b2ea-4466-972a-1505f157e6ee\.system_generated\logs\transcript.jsonl"

try:
    steps = []
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            steps.append(json.loads(line))
            
    for idx in range(145, min(160, len(steps))):
        step = steps[idx]
        print(f"=== STEP {step.get('step_index')} | {step.get('source')} | {step.get('type')} ===")
        content = step.get('content', '')
        tool_calls = step.get('tool_calls', [])
        if tool_calls:
            print("Tool calls:", json.dumps(tool_calls, ensure_ascii=False, indent=2))
        if content:
            print(content)
        print()
except Exception as e:
    print("Error:", e)
