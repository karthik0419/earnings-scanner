import sys
sys.path.insert(0, '.')
from data.nse_universe import fetch_sector_universe, fetch_nse_eq_list

df = fetch_sector_universe()
print(f"\nWeekly universe : {len(df)} stocks")

eq = fetch_nse_eq_list()
print(f"NSE EQ full list: {len(eq)} stocks")

base_syms = set(df["symbol"].str.upper())
eq_syms   = set(eq["symbol"].str.upper()) if not eq.empty else set()

harsha_weekly = "HARSHA" in base_syms
harsha_eq     = "HARSHA" in eq_syms
extra = len(eq_syms - base_syms)

print(f"\nHARSHA in weekly universe : {harsha_weekly}")
print(f"HARSHA in NSE EQ list     : {harsha_eq}")
print(f"Extra below-index stocks  : {extra}")
print(f"\nWith discovery mode, total reachable = {len(df) + extra} stocks")
