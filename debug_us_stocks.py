import shioaji as sj

api = sj.Shioaji()
api.login(api_key="BPHcXm1CfdU8jw626rRVx3MXB9aqJ3HKaaovHGHkzYTn", secret_key="AJvvVZqxQCaXDwPs5CE6jYhkU5pujBm7ujhFZNbfoM7a")

print("--- API Contracts Inspection ---")
# Check if US stocks are under a different attribute or exchange
try:
    print(f"Contracts: {dir(api.Contracts)}")
    if hasattr(api.Contracts, 'USStocks'):
        print("Found USStocks attribute!")
    else:
        print("USStocks attribute NOT found in api.Contracts")
    
    # Check if they are in Stocks but require a specific exchange
    if hasattr(api.Contracts, 'Stocks'):
        print(f"Stocks exchanges: {dir(api.Contracts.Stocks)}")
        # Check if US is an exchange in Stocks
        if 'US' in dir(api.Contracts.Stocks):
            print("Found US exchange in api.Contracts.Stocks")
        else:
            print("US exchange NOT found in api.Contracts.Stocks")
            
    # List all attributes of api.Contracts that might be US-related
    for attr in dir(api.Contracts):
        if "US" in attr:
            print(f"Possible US attribute: {attr}")

    # Try searching for a known US stock symbol (AAPL)
    print("\n--- Searching for AAPL ---")
    try:
        # Some versions use api.Contracts.Stocks.US["AAPL"] or similar
        # Let's try to find it by iteration if possible (be careful with large sets)
        print("Attempting to find AAPL by various means...")
        # Check if api.Contracts has any exchange named 'US' or 'NAS' or 'NYS'
        for exc in ['TSE', 'OTC', 'US', 'NAS', 'NYS', 'NASDAQ', 'NYSE']:
            if hasattr(api.Contracts.Stocks, exc):
                print(f"Stocks has exchange: {exc}")
    except Exception as e:
        print(f"Search error: {e}")

except Exception as e:
    print(f"General error: {e}")

api.logout()
