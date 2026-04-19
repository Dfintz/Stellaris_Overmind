"""Examine raw Clausewitz text structure of a Stellaris save."""
from __future__ import annotations

import io
import zipfile
from pathlib import Path


def main() -> None:
    save_path = Path(
        r"C:\Users\Fintz\OneDrive\Documents\Paradox Interactive\Stellaris"
        r"\save games\techarancoalition_-1265884157\ironman.sav"
    )
    
    with zipfile.ZipFile(save_path, "r") as zf:
        with zf.open("gamestate") as f:
            text = io.TextIOWrapper(f, encoding="utf-8").read()
    
    print(f"Gamestate: {len(text)} chars ({len(text)/1024/1024:.1f} MB)")
    
    # Show first 2000 chars to see top-level structure
    print("\n=== FIRST 2000 CHARS ===")
    print(text[:2000])
    
    # Find top-level blocks by tracking brace depth
    print("\n=== TOP-LEVEL KEY=VALUE/BLOCK entries (first 40) ===")
    depth = 0
    i = 0
    n = len(text)
    entries = []
    while i < n and len(entries) < 40:
        c = text[i]
        if c == '{':
            depth += 1
            i += 1
        elif c == '}':
            depth -= 1
            i += 1
        elif c == '#':
            # Skip comment
            end = text.find('\n', i)
            i = end + 1 if end != -1 else n
        elif c == '"':
            end = text.find('"', i + 1)
            i = end + 1 if end != -1 else n
        elif depth == 0 and c.isalpha():
            # Read the key
            j = i
            while j < n and text[j] not in ' \t\r\n={}<>':
                j += 1
            key = text[i:j]
            # Skip whitespace
            while j < n and text[j] in ' \t\r\n':
                j += 1
            # Check what follows
            if j < n and text[j] == '=':
                j += 1
                while j < n and text[j] in ' \t\r\n':
                    j += 1
                if j < n and text[j] == '{':
                    # Block value — find size roughly
                    block_start = j
                    local_depth = 0
                    k = j
                    while k < n:
                        if text[k] == '{':
                            local_depth += 1
                        elif text[k] == '}':
                            local_depth -= 1
                            if local_depth == 0:
                                break
                        elif text[k] == '"':
                            end = text.find('"', k + 1)
                            k = end if end != -1 else n - 1
                        k += 1
                    block_size = k - block_start
                    entries.append(f"{key} = {{ ... }} ({block_size} chars)")
                    i = k + 1
                else:
                    # Scalar value
                    val_start = j
                    while j < n and text[j] not in ' \t\r\n':
                        j += 1
                    val = text[val_start:j]
                    entries.append(f"{key} = {val}")
                    i = j
            else:
                i = j
        else:
            i += 1
    
    for e in entries:
        print(f"  {e}")
    
    # Find where 'country' block starts and show its structure
    print("\n=== COUNTRY BLOCK STRUCTURE ===")
    country_pos = text.find('\ncountry=')
    if country_pos == -1:
        country_pos = text.find('\ncountry =')
    if country_pos == -1:
        country_pos = text.find('country={')
    
    if country_pos != -1:
        print(f"'country' found at offset {country_pos}")
        # Show 500 chars around it
        start = max(0, country_pos - 50)
        print(text[start:country_pos + 500])
    else:
        print("'country' key not found!")
    
    # Find tech_status
    print("\n=== TECH_STATUS STRUCTURE ===")
    tech_pos = text.find('tech_status=')
    if tech_pos == -1:
        tech_pos = text.find('tech_status =')
    if tech_pos != -1:
        print(f"First 'tech_status' at offset {tech_pos}")
        print(text[tech_pos:tech_pos+500])
    
    # Find traditions
    print("\n=== TRADITIONS STRUCTURE ===")
    trad_pos = text.find('\n\ttraditions=')
    if trad_pos == -1:
        trad_pos = text.find('traditions={')
    if trad_pos != -1:
        print(f"First 'traditions' at offset {trad_pos}")
        print(text[trad_pos:trad_pos+300])
    
    # Find active_policies
    print("\n=== ACTIVE_POLICIES STRUCTURE ===")
    pol_pos = text.find('active_policies=')
    if pol_pos == -1:
        pol_pos = text.find('active_policies =')
    if pol_pos != -1:
        print(f"First 'active_policies' at offset {pol_pos}")
        print(text[pol_pos:pol_pos+500])


if __name__ == "__main__":
    main()
