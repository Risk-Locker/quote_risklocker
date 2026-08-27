import re
import json
import glob
import os
from difflib import get_close_matches

# 1. Load Global Benefits
with open("fix/company/GLOBAL_BENEFITS_CATALOG.md", encoding="utf-8") as f:
    global_md = f.read()

concepts = {}
for line in global_md.split('\n'):
    m = re.match(r'\|\s*\d+\s*\|\s*`([a-z0-9-]+)`\s*\|\s*([^\|]+)\s*\|', line)
    if m:
        key, name = m.group(1).strip(), m.group(2).strip()
        concepts[key] = name

# Flatten for fuzzy matching
concept_names = {v.lower(): k for k, v in concepts.items()}

def map_concept(title):
    title = title.lower().strip()
    title = re.sub(r'\[cite:.*?\]', '', title).strip()
    title = re.sub(r'\(.*?\)', '', title).strip()
    
    # Exact match
    for k, v in concepts.items():
        if k.replace('-', ' ') in title or title in v.lower():
            return k
            
    # Fuzzy match
    matches = get_close_matches(title, concept_names.keys(), n=1, cutoff=0.3)
    if matches:
        return concept_names[matches[0]]
        
    # Manual overrides
    if "own damage" in title: return "own-damage"
    if "tp injury" in title: return "third-party-bi"
    if "tp property" in title: return "third-party-property"
    if "tow" in title: return "towing"
    if "legal defense" in title: return "legal-costs-defense"
    if "betterment" in title: return "betterment-protection"
    if "windscreen" in title or "glass" in title: return "windscreen"
    if "special peril" in title or "flood" in title: return "special-perils"
    if "strike" in title or "riot" in title: return "strike-riot-civil-commotion"
    if "passenger" in title and "liability" in title:
        if "of passenger" in title: return "legal-liability-of-passengers"
        return "legal-liability-to-passengers"
    if "cart" in title or "repair allowance" in title: return "repair-allowance"
    
    return "unknown"

configs = []
for file in glob.glob("fix/company/**/UPDATED*.md", recursive=True):
    with open(file, encoding="utf-8") as f:
        content = f.read()
        
    # Identify company
    company_name = "Unknown"
    company_slug = "unknown"
    if "AmAssurance" in file or "amgen" in file.lower():
        company_name = "AmAssurance"
        company_slug = "amassurance"
    elif "Berjaya" in file:
        company_name = "Berjaya Sompo"
        company_slug = "berjayasompo"
    elif "Etiqa" in file:
        company_name = "Etiqa"
        company_slug = "etiqa"
    elif "Lonpac" in file:
        company_name = "Lonpac"
        company_slug = "lonpac"
    elif "QBE" in file:
        company_name = "QBE"
        company_slug = "qbe"
    elif "STMB" in file:
        company_name = "STMB"
        company_slug = "stmb"
    elif "tune" in file.lower():
        company_name = "Tune Protect"
        company_slug = "tune-protect"
        
    config = {
        "company_slug": company_slug,
        "company_name": company_name,
        "products": []
    }
    
    # Simple regex to find sections that look like products/tiers
    # E.g. ### 3.1 Tier 1: Auto365 Comprehensive Lite
    blocks = re.split(r'###\s+[\d\.]+\s+([^<]+)', content)
    
    # Also find add-ons block
    addons_block = ""
    for i in range(1, len(blocks), 2):
        title = blocks[i].strip()
        body = blocks[i+1]
        
        if "Add-on" in title or "Optional" in title:
            addons_block += body
            continue
            
        product = {
            "product_key": f"{company_slug}-{title.lower().replace(' ', '-').replace(':', '')[:20]}",
            "product_name": title,
            "segment_key": "private",
            "vehicle_key": "car",
            "coverage_key": "comprehensive",
            "default_benefits": [],
            "addons": [] # we'll populate this later from the addons block
        }
        
        # Parse table
        lines = body.split('\n')
        for line in lines:
            if line.startswith('|') and not '---' in line and not 'Benefit Title' in line:
                parts = [p.strip() for p in line.split('|')[1:-1]]
                if len(parts) >= 3:
                    ben_title = re.sub(r'\[cite:.*?\]', '', parts[0]).replace('**', '').strip()
                    ben_desc = re.sub(r'\[cite:.*?\]', '', parts[1]).strip()
                    c_key = map_concept(ben_title)
                    product["default_benefits"].append({
                        "concept_key": c_key,
                        "display_value": ben_desc,
                        "price": 0
                    })
        
        if product["default_benefits"]:
            config["products"].append(product)
            
    # Parse addons
    global_addons = []
    if addons_block:
        for line in addons_block.split('\n'):
            if line.startswith('|') and not '---' in line and not 'Benefit Title' in line:
                parts = [p.strip() for p in line.split('|')[1:-1]]
                if len(parts) >= 3:
                    ben_title = re.sub(r'\[cite:.*?\]', '', parts[0]).replace('**', '').strip()
                    ben_desc = re.sub(r'\[cite:.*?\]', '', parts[1]).strip()
                    c_key = map_concept(ben_title)
                    global_addons.append({
                        "concept_key": c_key,
                        "display_value": ben_desc,
                        "price": 0 # Default price for addon
                    })
                    
    # Attach addons to all products
    for p in config["products"]:
        p["addons"] = global_addons
        
    if config["products"]:
        configs.append(config)

with open('generated_configs.json', 'w') as f:
    json.dump(configs, f, indent=2)

print("Generated generated_configs.json")
