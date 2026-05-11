import requests
HEADERS = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.niftyindices.com/'}

# Check Microcap raw format
r = requests.get('https://www.niftyindices.com/IndexConstituent/ind_niftymicrocap250list.csv', headers=HEADERS, timeout=10)
lines = r.text.strip().split('\n')
print(f"Total lines: {len(lines)}")
print("First 8 lines:")
for i, l in enumerate(lines[:8]):
    print(f"  [{i}] {repr(l[:120])}")
print("Last 3 lines:")
for l in lines[-3:]:
    print(f"  {repr(l[:120])}")

# Try to find the real header row
import pandas as pd
from io import StringIO
for skip in range(0, 6):
    try:
        df = pd.read_csv(StringIO(r.text), skiprows=skip)
        df.columns = [c.strip() for c in df.columns]
        sym_col = next((c for c in df.columns if c.strip().lower() == 'symbol'), None)
        if sym_col:
            syms = df[sym_col].dropna().str.strip().tolist()
            syms = [s for s in syms if s and not s.upper().startswith('DUMMY') and len(s) <= 20]
            print(f"\nskiprows={skip} -> {len(syms)} symbols, sym_col='{sym_col}'")
            print(f"Sample: {syms[:5]}")
            # Check HARSHA
            found = [s for s in syms if 'HARSHA' in s.upper()]
            print(f"HARSHA in list: {found if found else 'NOT FOUND'}")
            break
    except Exception as e:
        print(f"skiprows={skip} -> error: {e}")
