import requests, pandas as pd
from io import StringIO
HEADERS = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.niftyindices.com/'}
BASE = 'https://www.niftyindices.com/IndexConstituent/'

indices = {
    'Nifty 500':            'ind_nifty500list.csv',
    'Nifty Smallcap 250':   'ind_niftysmallcap250list.csv',
    'Nifty Largemidcap 250':'ind_niftylargemidcap250list.csv',
}
for name, fname in indices.items():
    r = requests.get(BASE + fname, headers=HEADERS, timeout=10)
    df = pd.read_csv(StringIO(r.text))
    df.columns = [c.strip() for c in df.columns]
    sym_col = next((c for c in df.columns if c.strip().lower() == 'symbol'), None)
    symbols = df[sym_col].dropna().str.strip().tolist() if sym_col else []
    found = [s for s in symbols if 'HARSHA' in s.upper()]
    status = str(found) if found else 'NOT FOUND'
    print(f"{name}: {len(symbols)} stocks | HARSHA: {status}")
