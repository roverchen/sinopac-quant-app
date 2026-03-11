from concurrent.futures import ThreadPoolExecutor, as_completed
from api.services.quant_service import get_yahoo_ticker

def fetch_batch_data(symbols, market_type='TW', period="1y"):
    """
    使用 ThreadPoolExecutor 併發抓取多檔股票數據。
    比單一循環抓取快得多。
    """
    import yfinance as yf
    import pandas as pd
    results = {}
    tickers_map = {s: get_yahoo_ticker(s, market_type) for s in symbols}
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_symbol = {
            executor.submit(yf.Ticker(t).history, period=period): s 
            for s, t in tickers_map.items() if t
        }
        
        for future in as_completed(future_to_symbol):
            symbol = future_to_symbol[future]
            try:
                df = future.result()
                if not df.empty:
                    results[symbol] = df
            except Exception as e:
                print(f"Error fetching {symbol}: {e}")
                
    return results

def download_and_pool(symbols, market_type='TW'):
    """
    批次下載並回傳一個包含 DataFrames 的池子。
    可以用於全市場掃描後的數據持久化。
    """
    # 這裡可以加入分批 logic 以免被 Yahoo 封鎖
    return fetch_batch_data(symbols, market_type)
