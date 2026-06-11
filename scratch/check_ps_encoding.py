with open("scripts/run_weekly_flow_momentum_update.ps1", "rb") as f:
    lines = f.readlines()

line_27 = lines[26] # 0-indexed line 27
print("Line 27:", line_27)
print("Bytes:", list(line_27))
