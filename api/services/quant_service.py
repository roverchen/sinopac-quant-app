import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import re
import requests
import asyncio
from max_api import MaxExchangeAPI
from api.services.storage_service import save_data_pool, load_data_pool
from api.models.schemas import AnalysisResult

# Scan status state
scan_status = {
    "status": "idle",
    "progress": 0,
    "message": "System Ready",
    "results_count": 0,
    "top_results": []
}

# Results cache for instant reload
results_cache = {
    "TW": None,
    "US": None,
    "CRYPTO": None
}

def get_cached_pool(market_type: str):
    global results_cache
    if results_cache.get(market_type) is None:
        print(f"[Cache] Loading {market_type} data pool from storage...")
        pool = load_data_pool(market_type)
        if pool:
            results_cache[market_type] = pool
    return results_cache.get(market_type)

def extract_stock_code(raw_str):
    """Extract stock code from format 'Name(Code)', 'Code', or 'ETH-USD'"""
    import re
    if not raw_str: return ""
    raw_str = str(raw_str).strip()
    match = re.search(r'\((.*?)\)', raw_str)
    if match: return match.group(1).upper()
    return raw_str.upper()

def fetch_tw_symbols():
    """Fetch all TW stock symbols (Listed, OTC, Emerging, ETFs)"""
    import requests
    import pandas as pd
    try:
        symbols = {}
        for mode in ["2", "4", "5"]:
            url = f"https://isin.twse.com.tw/isin/C_public.jsp?strMode={mode}"
            response = requests.get(url, verify=False, timeout=15)
            response.encoding = 'big5'
            dfs = pd.read_html(response.text)
            if not dfs: continue
            df = dfs[0]
            for val in df[0].dropna():
                parts = str(val).split('\u3000')
                if len(parts) >= 2:
                    code = parts[0].strip()
                    name = parts[1].strip()
                    if code.isdigit() and len(code) in [4, 5]:
                        # Typical TW stocks are 4 digits, ETFs are 5 digits.
                        # Exclude warrants which are usually 6 digits and contain names like "購/售/牛/熊"
                        if not any(x in name for x in ["購", "售", "牛", "熊"]):
                            symbols[code] = name
        print(f"[QuantService] TW symbols scraped: {len(symbols)}")
        return symbols
    except Exception as e:
        print(f"Error fetching TW symbols: {e}")
        return {"2330": "TSMC", "2317": "Hon Hai", "2303": "UMC", "2454": "MTK", "2881": "Fubon"}

def fetch_us_symbols():
    """Fetch S&P 500 symbols from Wikipedia"""
    import requests
    try:
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, verify=False, timeout=15)
        tables = pd.read_html(response.text)
        df = tables[0]
        return df.set_index('Symbol')['Security'].to_dict()
    except Exception as e:
        print(f"Error fetching US symbols: {e}")
        return {"AAPL": "Apple", "MSFT": "Microsoft", "NVDA": "Nvidia"}

def fetch_crypto_symbols():
    """Fetch major crypto symbols and MAX exchange pairs"""
    symbols = {
        "BTC-USD": "Bitcoin", "ETH-USD": "Ethereum", "SOL-USD": "Solana",
        "BNB-USD": "Binance Coin", "DOGE-USD": "Dogecoin", "XRP-USD": "XRP",
        "ADA-USD": "Cardano", "MATIC-USD": "Polygon", "DOT-USD": "Polkadot",
        "LINK-USD": "Chainlink"
    }
    try:
        api = MaxExchangeAPI("", "")
        markets = api.get_markets()
        for m in markets:
            if m['id'].endswith('twd') or m['id'].endswith('usdt'):
                key = m['id']
                if key.upper() not in symbols:
                    symbols[key] = f"{m['name']} ({m['base_unit'].upper()}/{m['quote_unit'].upper()})"
        return symbols
    except Exception as e:
        print(f"Error fetching Crypto symbols from MAX: {e}")
        return symbols

def get_yahoo_ticker(code, market_type='TW'):
    """Convert code to Yahoo Finance ticker format"""
    if not code: return None
    if market_type == 'TW' and code.isdigit():
        return code + (".TW" if int(code) < 10000 else ".TWO")
    if market_type == 'CRYPTO':
        c = code.upper()
        if c.endswith('TWD'): return f"{c[:-3]}-TWD"
        if c.endswith('USDT'): return f"{c[:-4]}-USD"
        if "-" not in c: return f"{c}-USD"
        return c
    return code

def fetch_stock_data(code, ticker_str, period="1y"):
    """Fetch daily OHLC data from Yahoo Finance"""
    import yfinance as yf
    try:
        ticker = yf.Ticker(ticker_str)
        df = ticker.history(period=period, interval="1d")
        if df.empty and ".TW" in ticker_str:
            ticker = yf.Ticker(ticker_str.replace(".TW", ".TWO"))
            df = ticker.history(period=period, interval="1d")
        return df
    except Exception as e:
        print(f"Error fetching {ticker_str}: {e}")
        return None

def calculate_technical_indicators(df):
    """Calculate MA, MACD, ATR, Year High/Low"""
    if df is None or df.empty: return None
    df = df.copy()
    df.columns = [c.lower() for c in df.columns]

    df['ma5'] = df['close'].rolling(window=5).mean()
    df['ma20'] = df['close'].rolling(window=20).mean()
    df['ma60'] = df['close'].rolling(window=60).mean()
    df['ma100'] = df['close'].rolling(window=100).mean()
    df['ma240'] = df['close'].rolling(window=240).mean()
    df['vol_ma5'] = df['volume'].rolling(window=5).mean()

    ema12 = df['close'].ewm(span=12).mean()
    ema26 = df['close'].ewm(span=26).mean()
    df['macd'] = ema12 - ema26
    df['signal'] = df['macd'].ewm(span=9).mean()
    df['hist'] = df['macd'] - df['signal']

    high_low = df['high'] - df['low']
    high_cp = (df['high'] - df['close'].shift()).abs()
    low_cp = (df['low'] - df['close'].shift()).abs()
    tr = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
    df['atr'] = tr.rolling(window=14).mean()

    df['year_high'] = df['close'].rolling(window=240, min_periods=30).max()
    df['year_low'] = df['close'].rolling(window=240, min_periods=30).min()
    return df

def check_revenue_momentum(code):
    """Check revenue momentum: last 3 months YoY trend"""
    if not code.isdigit(): return "N/A", True
    try:
        url = "https://api.finmindtrade.com/api/v4/data"
        params = {
            "dataset": "TaiwanStockMonthRevenue",
            "data_id": code,
            "start_date": (datetime.now() - timedelta(days=200)).strftime("%Y-%m-%d")
        }
        res = requests.get(url, params=params, timeout=5)
        data = res.json().get('data', [])
        if len(data) < 3: return "Incomplete", True

        yoy_list = []
        for d in data[-3:]:
            yoy = d.get('revenue_month_year_comparison') or d.get('revenue_percentage_change_year') or 0
            yoy_list.append(yoy)

        latest_yoy = yoy_list[-1]
        is_declining = all(yoy_list[i] > yoy_list[i+1] for i in range(len(yoy_list)-1))

        if is_declining and latest_yoy < 0:
            return f"Declining({latest_yoy:.1f}%)", False
        return f"Normal({latest_yoy:.1f}%)", True
    except:
        return "Unavailable", True

def analyze_stock(df, code, name, defense_weight=0.5, market_type='TW'):
    """Analyze single stock and return AnalysisResult compatible dict"""
    if df is None or len(df) < 10:
        return {
            "symbol": code, "name": name, "price": 0, "suggestion": "Invalid Data",
            "level": "-", "ma240_diff": "-", "ma20_diff": "-", "macd_status": "-", "score": -1
        }

    df = calculate_technical_indicators(df)
    last_row = df.iloc[-1]
    last_price = last_row['close']
    ma20_last = last_row['ma20']
    ma240_last = last_row['ma240']
    ma100_last = last_row['ma100']
    year_high = last_row['year_high']
    year_low = last_row['year_low']
    atr = last_row['atr']

    level_percentile = (last_price - year_low) / (year_high - year_low) if year_high > year_low else 0.5
    if market_type == 'CRYPTO':
        defense_base = ma100_last if not np.isnan(ma100_last) else last_row['ma60']
    else:
        defense_base = ma240_last if not np.isnan(ma240_last) else last_row['ma60']

    dist_to_defense = (last_price - defense_base) / defense_base if defense_base > 0 else 0
    dist_to_ma20 = (last_price - ma20_last) / ma20_last if ma20_last > 0 else 0

    macd = last_row['macd']
    signal = last_row['signal']
    hist = last_row['hist']
    is_gold_cross = (df['hist'].iloc[-2] <= 0 if len(df) > 1 else False) and hist > 0
    is_above_zero = macd > 0 and signal > 0

    macd_status = "Bearish"
    if is_above_zero:
        macd_status = "Bullish Cross" if is_gold_cross else "Bullish Consolidation"
    else:
        macd_status = "Low Cross" if is_gold_cross else "Weak Consolidation"

    ma5 = last_row['ma5']
    vol_ma5 = last_row['vol_ma5']
    has_vol_momentum = (last_price > ma5) and (last_row['volume'] > vol_ma5 * 1.2)

    value_score = (1 - level_percentile) * 50
    if -0.05 < dist_to_defense < 0.05: value_score += 30
    if has_vol_momentum: value_score += 20

    pullback_score = (1 - min(abs(dist_to_ma20), 0.1)/0.1) * 50
    if is_gold_cross:
        pullback_score += 50 if is_above_zero else 30

    final_score = (defense_weight * value_score) + ((1 - defense_weight) * pullback_score)
    is_rev_ok = True
    if market_type == 'TW' and code.isdigit():
        rev_msg, is_rev_ok = check_revenue_momentum(code)
        if not is_rev_ok: final_score *= 0.1

    def sanitize(val):
        if val is None or (isinstance(val, (float, np.floating)) and np.isnan(val)): return 0.0
        if isinstance(val, (float, np.floating)) and np.isinf(val): return 999.9 if val > 0 else -999.9
        return float(val) if isinstance(val, (int, float, np.integer, np.floating)) else val

    last_price = sanitize(last_price)
    final_score = sanitize(final_score)
    defense_base = sanitize(defense_base)
    ma20_last = sanitize(ma20_last)
    atr = sanitize(atr)

    weighted_value = defense_weight * value_score
    weighted_growth = (1 - defense_weight) * pullback_score

    if weighted_growth >= weighted_value:
        type_prefix = "Growth"
        entry_price = ma20_last
        atr_mult = 3.0 if market_type == 'CRYPTO' else 2.5
        stop_loss = last_price - (atr_mult * atr)
        rr_ratio = 4.0 if (market_type == 'CRYPTO' and last_row['volume'] > vol_ma5 * 2.0) else 3.0
        target_price = last_price + (last_price - stop_loss) * rr_ratio
    else:
        type_prefix = "Value"
        entry_price = min(last_price, defense_base)
        target_price = max(defense_base, entry_price * 1.2)
        stop_loss = year_low * 0.95
        if has_vol_momentum: type_prefix += "+"

    suggestion = f"{type_prefix} | Buy:{entry_price:.1f} | TP:{target_price:.1f} | SL:{sanitize(stop_loss):.1f}"
    if not is_rev_ok: suggestion = "REVENUE_WARNING | " + suggestion

    return {
        "symbol": code, "name": name, "price": round(last_price, 2), "suggestion": suggestion,
        "level": f"{sanitize(level_percentile)*100:.1f}%", "ma240_diff": f"{sanitize(dist_to_defense)*100:.1f}%",
        "ma20_diff": f"{sanitize(dist_to_ma20)*100:.1f}%", "macd_status": macd_status,
        "score": round(final_score, 1), "market": market_type, "ma_base": defense_base,
        "ma20": ma20_last, "atr": atr, "entry_price": round(sanitize(entry_price), 2),
        "stop_loss": round(sanitize(stop_loss), 2), "target_price": round(sanitize(target_price), 2)
    }

async def run_market_scan(market_type: str, defense_weight: float = 0.5):
    """Background task to scan market and save results pool"""
    global scan_status, results_cache
    from api.services.data_fetcher import fetch_batch_data

    try:
        print(f"[QuantService] Starting {market_type} market scan (Defense Weight: {defense_weight})...")
        scan_status["status"] = "running"
        scan_status["progress"] = 5
        scan_status["message"] = f"Fetching {market_type} symbols..."

        if market_type == "TW": symbols_map = fetch_tw_symbols()
        elif market_type == "US": symbols_map = fetch_us_symbols()
        else: symbols_map = fetch_crypto_symbols()

        symbols = list(symbols_map.keys())
        total = len(symbols)
        if total == 0: raise ValueError(f"No symbols found for {market_type}")

        print(f"[QuantService] Starting {market_type} market scan (Defense Weight: {defense_weight}). Filtered Symbols: {total}")
        
        chunk_size = 30 # Smaller batches for more frequent updates
        results = []
        all_dfs = {}

        for i in range(0, total, chunk_size):
            chunk = symbols[i : i + chunk_size]
            print(f"[QuantService] Fetching {market_type} chunk {i//chunk_size + 1}: {chunk[:3]}...")
            data_map = fetch_batch_data(chunk, market_type)

            for s, df in data_map.items():
                name = symbols_map.get(s, "Unknown")
                analysis = analyze_stock(df, s, name, defense_weight, market_type)
                results.append(AnalysisResult(**analysis))
                all_dfs[s] = df

            scan_status["progress"] = round(10 + (i / total) * 85, 1)
            scan_status["message"] = f"Analyzed {len(results)}/{total} items..."
            print(f"[QuantService] {market_type} Progress: {len(results)}/{total}")
            scan_status["results_count"] = len(results)
            
            # Partial save to GCS every 500 stocks for better responsiveness
            if len(results) % 500 == 0 or i + chunk_size >= total:
                print(f"[QuantService] Syncing results to GCS ({len(results)} stocks)...")
                # Ensure results are sorted by score before partial save
                sorted_partial = sorted(results, key=lambda x: x.score, reverse=True)
                partial_pool = {"results": sorted_partial, "dfs": all_dfs, "timestamp": datetime.now().isoformat(), "is_partial": True}
                save_data_pool(market_type, partial_pool)
                results_cache[market_type] = partial_pool
                
            await asyncio.sleep(0.02)

        results = sorted(results, key=lambda x: x.score, reverse=True)
        data_pool = {"results": results, "dfs": all_dfs, "timestamp": datetime.now().isoformat()}
        save_data_pool(market_type, data_pool)
        results_cache[market_type] = data_pool

        scan_status["top_results"] = results[:10]
        scan_status["status"] = "completed"
        scan_status["progress"] = 100
        msg = f"Scan complete. Analyzed {len(results)} stocks."
        scan_status["message"] = msg
        print(f"[QuantService] {market_type} {msg}")
    except Exception as e:
        scan_status["status"] = "error"
        scan_status["message"] = f"Scan failed: {str(e)}"
        print(f"Scan Error: {e}")
