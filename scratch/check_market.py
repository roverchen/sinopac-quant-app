import sys
import os
import yfinance as yf
from datetime import datetime

def check_benchmarks():
    start_date = "2026-04-28"
    end_date = "2026-05-21"
    
    indices = {
        "^TWII": "Taiwan Weighted Index (台股大盤)",
        "^GSPC": "S&P 500 Index (美股大盤)",
        "BTC-USD": "Bitcoin (比特幣)"
    }
    
    print(f"Benchmark Performance from {start_date} to {end_date}:")
    print(f"{'Index/Asset':<35} | {'Start Price':<12} | {'End Price':<12} | {'Return %':<10}")
    print("-" * 75)
    for sym, name in indices.items():
        try:
            ticker = yf.Ticker(sym)
            df = ticker.history(start=start_date, end=end_date)
            if not df.empty:
                start_price = df['Close'].iloc[0]
                end_price = df['Close'].iloc[-1]
                ret_pct = ((end_price - start_price) / start_price) * 100
                print(f"{name:<35} | {start_price:<12.2f} | {end_price:<12.2f} | {ret_pct:<8.2f}%")
            else:
                print(f"{name:<35} | No data found")
        except Exception as e:
            print(f"{name:<35} | Error: {e}")

if __name__ == "__main__":
    check_benchmarks()
