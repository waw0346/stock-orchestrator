import codecs

file_path = "scripts/run_weekly_flow_momentum_update.ps1"

# Read file contents as UTF-8
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Write file contents with UTF-8 BOM
with open(file_path, "w", encoding="utf-8-sig") as f:
    f.write(content)

print("File successfully rewritten with UTF-8 BOM.")
