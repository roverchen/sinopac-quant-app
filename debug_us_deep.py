import shioaji as sj

api = sj.Shioaji()
api.login(api_key="BPHcXm1CfdU8jw626rRVx3MXB9aqJ3HKaaovHGHkzYTn", secret_key="AJvvVZqxQCaXDwPs5CE6jYhkU5pujBm7ujhFZNbfoM7a")

print("--- Comprehensive Search for US Stocks ---")
# Try to specifically fetch US contracts
try:
    print("Trying api.fetch_contracts(exchange='US')...")
    api.fetch_contracts(exchange='US')
    print("Fetch US ok.")
except Exception as e:
    print(f"Fetch US failed: {e}")

# Search for NVDA in all accessible contracts
found = False
for category in ['Stocks', 'Futures', 'Options', 'Indexs']:
    if hasattr(api.Contracts, category):
        cat_obj = getattr(api.Contracts, category)
        print(f"Searching in {category}...")
        # Check if we can find NVDA or AAPL in any exchange
        for exc in dir(cat_obj):
            if exc.isupper() and len(exc) <= 4:
                exc_obj = getattr(cat_obj, exc)
                if hasattr(exc_obj, 'get'):
                    # Try some common US symbols
                    for sym in ['NVDA', 'AAPL', 'TSLA']:
                        contract = exc_obj.get(sym)
                        if contract:
                            print(f"FOUND {sym} in {category}.{exc}!")
                            found = True
                        
if not found:
    print("Could not find any US stock symbols in standard contract categories.")

# Check for US-specific attributes one last time
print(f"Contracts keys: {api.Contracts.__dict__.keys()}")

api.logout()
