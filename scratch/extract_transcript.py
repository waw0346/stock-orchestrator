import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

log_path = r"C:\Users\kjw03\.gemini\antigravity\brain\be18f499-b2ea-4466-972a-1505f157e6ee\.system_generated\logs\transcript.jsonl"

try:
    print_flag = False
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            obj = json.loads(line)
            content = obj.get("content", "")
            tool_calls = obj.get("tool_calls", [])
            step_index = obj.get("step_index")
            source = obj.get("source")
            type_ = obj.get("type")
            
            # Start printing when scratch/calculate_samsung_biologics_vwap_regex.py is run
            if "calculate_samsung_biologics_vwap_regex" in str(tool_calls) or "calculate_samsung_biologics_vwap_regex" in content:
                print_flag = True
            
            if print_flag:
                print(f"=== STEP {step_index} | {source} | {type_} ({obj.get('created_at')}) ===")
                if tool_calls:
                    print(f"Tool calls: {json.dumps(tool_calls, ensure_ascii=False, indent=2)}")
                if content:
                    if len(content) > 1000:
                        print(content[:1000] + "... [TRUNCATED]")
                    else:
                        print(content)
                print()
                
            # Stop printing after the third user input
            if type_ == "USER_INPUT" and "후속작업" in content:
                # print_flag = False # keep printing a bit more to see if there is anything after it
                pass
except Exception as e:
    print("Error:", e)
