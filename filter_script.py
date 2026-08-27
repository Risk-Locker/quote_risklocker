import re
import sys

with open('fix/company/GLOBAL_BENEFITS_CATALOG.md', encoding='utf-8') as f:
    valid_keys = set(re.findall(r'`([a-z0-9-]+)`', f.read()))

with open('commands/seed-demo.py', encoding='utf-8') as f:
    lines = f.readlines()

out_lines = []
in_dict = False
dict_lines = []
dict_key = None
brace_level = 0

for line in lines:
    if '{' in line and not in_dict:
        # maybe start
        brace_level += line.count('{')
        brace_level -= line.count('}')
        if brace_level > 0:
            in_dict = True
            dict_lines = [line]
            dict_key = None
            continue
    elif in_dict:
        dict_lines.append(line)
        brace_level += line.count('{')
        brace_level -= line.count('}')
        
        m = re.search(r'\"concept_key\"\s*:\s*\"([a-z0-9-]+)\"', line)
        if m:
            dict_key = m.group(1)
        m2 = re.search(r'\'concept_key\'\s*:\s*\'([a-z0-9-]+)\'', line)
        if m2:
            dict_key = m2.group(1)
            
        if brace_level == 0:
            in_dict = False
            if dict_key and dict_key not in valid_keys:
                pass # skip
            else:
                out_lines.extend(dict_lines)
            continue
    
    if not in_dict:
        out_lines.append(line)

# Handle potential trailing commas left by removed items
final_lines = []
for i, line in enumerate(out_lines):
    if line.strip() == '],':
        # if the previous line ended with a comma, it's fine, Python allows trailing commas in lists
        pass
    final_lines.append(line)

with open('commands/seed-demo.py', 'w', encoding='utf-8') as f:
    f.writelines(final_lines)

print('Done filtering')
