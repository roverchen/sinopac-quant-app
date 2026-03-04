
import shioaji as sj
import pandas as pd
from datetime import datetime, timedelta

api = sj.Shioaji()
api.login(api_key="BPHcXm1CfdU8jw626rRVx3MXB9aqJ3HKaaovHGHkzYTn", secret_key="AJvvVZqxQCaXDwPs5CE6jYhkU5pujBm7ujhFZNbfoM7a")

print("--- Checking 2330 kbars (100 days) ---")
try:
    contract = api.Contracts.Stocks["2330"]
    # Testing 100 days to match app.py
    start_date = (datetime.now() - timedelta(days=100)).strftime("%Y-%m-%d")
    print(f"Requesting from {start_date}")
    kbars = api.kbars(contract, start=start_date)
    print(f"kbars type: {type(kbars)}")
    
    if isinstance(kbars, sj.data.Kbars):
        df = pd.DataFrame({**kbars})
        df.columns = [c.lower() for c in df.columns]
        print("Success! Head of DataFrame:")
        print(df.head())
    else:
        print(f"kbars is not the expected type: {type(kbars)}")
        print(f"kbars string: {kbars}")

except Exception as e:
    print(f"Error checking kbars: {type(e).__name__}: {e}")

api.logout()
