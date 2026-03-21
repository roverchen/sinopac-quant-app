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

# Revenue analysis cache (24h)
revenue_cache = {}

def get_cached_pool(market_type: str):
    global results_cache
    if results_cache.get(market_type) is None:
        print(f"[Cache] Loading {market_type} data pool from storage...")
        pool = load_data_pool(market_type)
        if pool:
            results_cache[market_type] = pool
    return results_cache.get(market_type)

def extract_stock_code(raw_str, market_type=None):
    """Extract stock code and normalize (e.g., convert BTC-USD to btcusdt for CRYPTO)"""
    import re
    if not raw_str: return ""
    raw_str = str(raw_str).strip()
    match = re.search(r'\((.*?)\)', raw_str)
    code = match.group(1).upper() if match else raw_str.upper()
    
    # [v2.1.45] Normalize Crypto for consistency with MAX format
    # [v2.1.62] Default to TWD for Crypto to match MAX user balances
    if market_type == "CRYPTO":
        c = code.upper()
        if c.endswith("-USD") or c.endswith("-TWD"): 
            return f"{c[:-4].lower()}twd"
        if c.endswith("USDT") or c.endswith("TWD"): 
            return c.lower()
        return f"{c.lower()}twd"
    return code

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
    """Fetch major crypto symbols and MAX exchange pairs, prioritizing MAX naming (e.g., btcusdt)"""
    # [v2.1.44] Reinforced Fallback with MAX naming convention
    symbols = {
        "btcusdt": "Bitcoin (BTC/USDT)", "ethusdt": "Ethereum (ETH/USDT)", 
        "solusdt": "Solana (SOL/USDT)", "bnbusdt": "Binance Coin (BNB/USDT)", 
        "xrpusdt": "XRP (XRP/USDT)", "adausdt": "Cardano (ADA/USDT)", 
        "dogeusdt": "Dogecoin (DOGE/USDT)", "avaxusdt": "Avalanche (AVAX/USDT)", 
        "dotusdt": "Polkadot (DOT/USDT)", "trxusdt": "TRON (TRX/USDT)",
        "linkusdt": "Chainlink (LINK/USDT)", "polusdt": "Polygon (POL/USDT)", 
        "nearusdt": "NEAR Protocol (NEAR/USDT)", "ltcusdt": "Litecoin (LTC/USDT)", 
        "bchusdt": "Bitcoin Cash (BCH/USDT)", "shibusdt": "Shiba Inu (SHIB/USDT)", 
        "daiusdt": "Dai (DAI/USDT)", "uniusdt": "Uniswap (UNI/USDT)", 
        "leousdt": "UNUS SED LEO (LEO/USDT)", "aptusdt": "Aptos (APT/USDT)",
        "stxusdt": "Stacks (STX/USDT)", "okbusdt": "OKB (OKB/USDT)", 
        "atomusdt": "Cosmos (ATOM/USDT)", "imxusdt": "Immutable (IMX/USDT)", 
        "hbarusdt": "Hedera (HBAR/USDT)", "kasusdt": "Kaspa (KAS/USDT)", 
        "etcusdt": "Ethereum Classic (ETC/USDT)", "renderusdt": "Render (RENDER/USDT)", 
        "filusdt": "Filecoin (FIL/USDT)", "ldousdt": "Lido DAO (LDO/USDT)"
    }
    try:
        api = MaxExchangeAPI("", "")
        markets = api.get_markets()
        if not markets:
            print("[QuantService] MAX API returned empty market list, using MAX-formatted fallback.")
            return symbols
            
        # [v2.1.61] Deduplicate by base currency: Prioritize TWD over USDT for local users
        unique_live = {}
        for m in markets:
            market_id = m['id'].lower()
            if market_id.endswith('twd') or market_id.endswith('usdt'):
                base = m['base_unit'].lower()
                is_twd = market_id.endswith('twd')
                
                # Logic: If we haven't seen this coin, OR this is a TWD pair (overriding existing USDT)
                if base not in unique_live or is_twd:
                    unique_live[base] = (market_id, f"{m['name']} ({m['base_unit'].upper()}/{m['quote_unit'].upper()})")
        
        live_symbols = {v[0]: v[1] for v in unique_live.values()}

        # Merge live data into symbols (live data takes precedence)
        if live_symbols:
            return live_symbols
        
        # [v2.1.63] Deduplicate fallback list: Prioritize TWD
        unique_fallback = {}
        for k, v in symbols.items():
            base = k.replace('usdt', '').replace('twd', '')
            is_twd = k.endswith('twd')
            if base not in unique_fallback or is_twd:
                unique_fallback[base] = (k, v)
        return {v[0]: v[1] for v in unique_fallback.values()}
    except Exception as e:
        print(f"Error fetching Crypto symbols from MAX API: {e}. Using MAX-formatted fallback.")
        return symbols


def get_symbol_name(symbol, market_type='TW'):
    """Lookup symbol name from results cache or return symbol as fallback"""
    global results_cache
    pool = results_cache.get(market_type)
    if pool is None:
        # Try loading if cache is empty
        pool = load_data_pool(market_type)
        if pool:
            results_cache[market_type] = pool
    
    if pool and 'summary' in pool:
        # Search in summary dataframe
        df = pool['summary']
        
        # [v2.1.43] Handle MATIC <-> POL fallback
        query_symbols = [symbol]
        if symbol == "MATIC-USD": query_symbols.append("POL-USD")
        if symbol == "POL-USD": query_symbols.append("MATIC-USD")
        
        match = df[df['symbol'].isin(query_symbols)]
        if not match.empty:
            return match.iloc[0]['name']
            
    return symbol

def get_yahoo_ticker(code, market_type='TW'):
    """Convert code to Yahoo Finance ticker format (supporting MAX symbols)"""
    if not code: return None
    code_upper = code.upper()
    
    if market_type == 'TW' and code.isdigit():
        return f"{code}.TW"
        
    if market_type == 'CRYPTO':
        # 1. Handle special migrations
        if code_upper in ["MATIC-USD", "MATICUSDT", "MATIC"]: return "POL-USD"
        if code_upper in ["POL-USD", "POLUSDT", "POL"]: return "POL-USD"
        
        # [v2.1.63] Reverting to -USD for Yahoo Finance because -TWD pairs are not available
        if code_upper.endswith('USDT') or code_upper.endswith('TWD'):
            suffix = code_upper[-4:] if code_upper.endswith('USDT') else code_upper[-3:]
            clean_code = code_upper[:-len(suffix)].rstrip('-')
            return f"{clean_code}-USD"
            
        # 3. YF direct or fallback
        if "-" not in code_upper:
            return f"{code_upper}-USD"
        return code_upper
        
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
    df['vol_ma20'] = df['volume'].rolling(window=20).mean()

    ema12 = df['close'].ewm(span=12).mean()
    ema26 = df['close'].ewm(span=26).mean()
    df['macd'] = ema12 - ema26
    df['signal'] = df['macd'].ewm(span=9).mean()
    df['hist'] = df['macd'] - df['signal']
    df['hist_slope'] = df['hist'].diff() # [v2.2.0] MACD Histogram Slope

    high_low = df['high'] - df['low']
    high_cp = (df['high'] - df['close'].shift()).abs()
    low_cp = (df['low'] - df['close'].shift()).abs()
    tr = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
    df['atr'] = tr.rolling(window=14).mean()
    df['atr5'] = tr.rolling(window=5).mean() # [v2.2.0] Short-term ATR for spike detection

    df['year_high'] = df['close'].rolling(window=240, min_periods=30).max()
    df['year_low'] = df['close'].rolling(window=240, min_periods=30).min()
    return df

def check_revenue_momentum(code):
    """Check revenue momentum: last 3 months YoY trend"""
    if not code.isdigit(): return "N/A", True
    
    # Check cache first
    now = datetime.now()
    if code in revenue_cache:
        msg, status, ts = revenue_cache[code]
        if now - ts < timedelta(hours=24):
            return msg, status

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
            res = (f"Declining({latest_yoy:.1f}%)", False)
        else:
            res = (f"Normal({latest_yoy:.1f}%)", True)
        
        revenue_cache[code] = (*res, now)
        return res
    except:
        return "Unavailable", True

def analyze_stock(df, code, name, defense_weight=0.5, market_type='TW', skip_indicators=False, skip_revenue=False, exchange_rate: float = 1.0, index_df=None):
    """Analyze single stock and return AnalysisResult compatible dict [v2.2.0]"""
    if df is None or len(df) < 20: 
        return {
            "symbol": code, "name": name, "price": 0, "suggestion": "Invalid Data",
            "level": "-", "ma240_diff": "-", "ma20_diff": "-", "macd_status": "-", "score": -1
        }

    df = df.copy()
    df.columns = [c.lower() for c in df.columns]

    # Defensive: if skip_indicators is True but columns are missing, force calculate
    required_cols = ['ma20', 'ma240', 'ma100', 'ma60', 'macd', 'signal', 'hist', 'atr', 'atr5', 'hist_slope', 'year_high', 'year_low', 'ma5', 'vol_ma5', 'vol_ma20']
    missing = [c for c in required_cols if c not in df.columns]
    
    if not skip_indicators or missing:
        df = calculate_technical_indicators(df)
    
    last_row = df.iloc[-1]
    prev_row = df.iloc[-2] if len(df) > 1 else last_row
    
    last_price = last_row['close']
    ma20_last = last_row['ma20']
    ma240_last = last_row['ma240']
    ma100_last = last_row['ma100']
    year_high = last_row['year_high']
    year_low = last_row['year_low']
    atr = last_row['atr']
    atr5 = last_row['atr5']
    vol_ma20 = last_row['vol_ma20']
    hist = last_row['hist']
    hist_slope = last_row['hist_slope']

    # 1. Price Space & Level
    level_percentile = (last_price - year_low) / (year_high - year_low) if year_high > year_low else 0.5
    if market_type == 'CRYPTO':
        defense_base = ma100_last if not np.isnan(ma100_last) else last_row['ma60']
    else:
        defense_base = ma240_last if not np.isnan(ma240_last) else last_row['ma60']

    dist_to_defense = (last_price - defense_base) / defense_base if defense_base > 0 else 0
    dist_to_ma20 = (last_price - ma20_last) / ma20_last if ma20_last > 0 else 0

    # 2. Market Relative Strength (RS) [v2.2.0]
    rs_score = 50 # Neutral
    if index_df is not None and len(index_df) >= 10:
        try:
            # 10-day return comparison
            stock_ret = (last_price - df['close'].iloc[-10]) / df['close'].iloc[-10]
            idx_ret = (index_df['Close'].iloc[-1] - index_df['Close'].iloc[-10]) / index_df['Close'].iloc[-10]
            # RS is the outperformance
            rs = stock_ret - idx_ret
            rs_score = min(100, max(0, 50 + rs * 500)) # 2% outperf = +10 pts
        except: pass

    # 3. Volume & Pattern Detection [v2.2.0]
    vol_last = last_row['volume']
    body = abs(last_price - last_row['open'])
    lower_shadow = min(last_row['open'], last_price) - last_row['low']
    
    # Choking Volume: Low level + extremely low volume
    is_choking = (level_percentile < 0.2) and (vol_last < vol_ma20 * 0.5)
    
    # Bottoming Volume: Long lower shadow + some volume pick up
    is_bottoming = (level_percentile < 0.3) and (lower_shadow > body * 1.5) and (vol_last > vol_ma20 * 0.8)
    
    # Washout (Pullback + Low Vol)
    is_washout = (-0.03 < dist_to_ma20 < 0.02) and (vol_last < vol_ma20)
    
    # 4. Momentum & MACD Convergence
    macd = last_row['macd']
    signal = last_row['signal']
    is_gold_cross = (df['hist'].iloc[-2] <= 0 if len(df) > 1 else False) and hist > 0
    is_above_zero = macd > 0 and signal > 0
    
    has_vol_momentum = (last_price > last_row['ma5']) and (vol_last > last_row['vol_ma5'] * 1.2)
    
    # [v2.3.0] Opening Strength & Early Momentum Chase
    open_price = last_row['open']
    prev_close = prev_row['close'] if len(df) > 1 else open_price
    opening_strength = (open_price / prev_close) - 1 if prev_close > 0 else 0
    
    momentum_chase_bonus = 0
    is_momentum_chase = False
    if opening_strength > 0.07:
        is_momentum_chase = True
        momentum_chase_bonus = 30
        if level_percentile < 0.3: # Low level attack
            momentum_chase_bonus += 20
        elif level_percentile > 0.8: # High level exhaustion
            momentum_chase_bonus -= 40

    # MACD Convergence Score (Bonus if histogram is improving)
    momentum_bonus = 20 if hist_slope > 0 else 0
    if is_gold_cross: momentum_bonus += 30

    # 5. [v2.2.0] New Weight Table Logic
    # Value Calculation (Defense)
    # Price(50%), Momentum(10%), Volume(20%), RS(20%)
    v_price = (1 - level_percentile) * 100
    v_moment = 60 if is_above_zero else 30 # Simple proxy for momentum in Value score
    v_vol = 50 + (30 if is_choking else 0) + (20 if is_bottoming else 0)
    v_rs = rs_score
    value_score = (v_price * 0.5) + (v_moment * 0.1) + (v_vol * 0.2) + (v_rs * 0.2)

    # Pullback Calculation (Growth)
    # Momentum(50%), Price(10%), Volume(20%), RS(20%)
    g_moment = (1 - min(abs(dist_to_ma20), 0.1)/0.1) * 50 + momentum_bonus + momentum_chase_bonus
    g_price = (1 - level_percentile) * 100
    g_vol = 50 + (30 if is_washout else 0) + (20 if has_vol_momentum else 0)
    g_rs = rs_score
    pullback_score = (g_moment * 0.5) + (g_price * 0.1) + (g_vol * 0.2) + (g_rs * 0.2)

    # 6. Filters & Penalties
    final_score = (defense_weight * value_score) + ((1 - defense_weight) * pullback_score)
    
    # Volatility Filter: Penalty for sudden spikes (Fake breakouts)
    # [v2.3.0] Skip penalty if it's a valid momentum chase gap
    if atr5 > 1.5 * atr and not is_momentum_chase: final_score *= 0.8
    
    # Hard Stop-Loss Penalty: Break MA20-3% or MACD Histogram drops significantly
    if last_price < ma20_last * 0.97 or (hist < 0 and hist_slope < 0):
        final_score *= 0.5

    # [v2.2.0] Restore revenue check
    is_rev_ok = True
    if market_type == 'TW' and code.isdigit() and not skip_revenue:
        rev_msg, is_rev_ok = check_revenue_momentum(code)
        if not is_rev_ok: final_score *= 0.1
    
    macd_status = "Bearish"
    if is_above_zero:
        macd_status = "Bullish Cross" if is_gold_cross else "Bullish Consolidation"
    else:
        macd_status = "Low Cross" if is_gold_cross else "Weak Consolidation"
    
    # [v2.2.0] Enhanced MACD Status with convergence info
    if hist_slope > 0 and hist < 0:
        macd_status += " (Converging)"

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
        type_prefix = "Momentum Chase" if is_momentum_chase else "Growth"
        entry_price = ma20_last
        atr_mult = 3.0 if market_type == 'CRYPTO' else 2.5
        stop_loss = last_price - (atr_mult * atr)
        rr_ratio = 4.0 if (market_type == 'CRYPTO' and vol_last > vol_ma20 * 2.0) else 3.0
        target_price = last_price + (last_price - stop_loss) * rr_ratio
    else:
        type_prefix = "Value"
        entry_price = min(last_price, defense_base)
        target_price = max(defense_base, entry_price * 1.2)
        stop_loss = year_low * 0.95
        if is_choking: type_prefix += "(Choke)"
        if is_bottoming: type_prefix += "(Bottom)"

    # [v2.1.64] Convert prices to TWD if exchange_rate provided
    if market_type == 'CRYPTO' and exchange_rate > 1.0:
        last_price *= exchange_rate
        entry_price *= exchange_rate
        target_price *= exchange_rate
        stop_loss *= exchange_rate
        ma20_last *= exchange_rate
        defense_base *= exchange_rate
        atr *= exchange_rate

    suggestion = f"{type_prefix} | Buy:{entry_price:.1f} | TP:{target_price:.1f} | SL:{sanitize(stop_loss):.1f}"
    if not is_rev_ok: suggestion = "REVENUE_WARNING | " + suggestion
    return {
        "symbol": code, "name": name, "price": round(last_price, 2), "suggestion": suggestion,
        "level": f"{sanitize(level_percentile)*100:.1f}%", "ma240_diff": f"{sanitize(dist_to_defense)*100:.1f}%",
        "ma20_diff": f"{sanitize(dist_to_ma20)*100:.1f}%", "macd_status": macd_status,
        "score": round(final_score, 1), "market": market_type, "ma_base": defense_base,
        "ma20": ma20_last, "atr": atr, "entry_price": round(sanitize(entry_price), 2),
        "stop_loss": round(sanitize(stop_loss), 2), "target_price": round(sanitize(target_price), 2),
        "value_score": round(sanitize(value_score), 1), "pullback_score": round(sanitize(pullback_score), 1),
        "rs_score": round(sanitize(rs_score), 1), "opening_strength": round(sanitize(opening_strength), 4)
    }

async def run_market_scan(market_type: str, defense_weight: float = 0.5):
    """Background task to scan market and save results pool"""

    try:
        from api.services.data_fetcher import fetch_batch_data
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

        # [v2.2.0] Fetch Index Data for RS calculation
        index_symbol = "^TWII" if market_type == "TW" else ("^GSPC" if market_type == "US" else "BTC-USD")
        index_df = None
        try:
            import yfinance as yf
            index_df = yf.Ticker(index_symbol).history(period="1mo")
            print(f"[QuantService] Fetched index {index_symbol} for RS calculation.")
        except Exception as e:
            print(f"[QuantService] Failed to fetch index {index_symbol}: {e}")

        # [v2.1.64] Fetch USD/TWD rate if Crypto
        exchange_rate = 1.0
        if market_type == "CRYPTO":
            try:
                rate_df = yf.Ticker("TWD=X").history(period="1d")
                if not rate_df.empty:
                    exchange_rate = float(rate_df['Close'].iloc[-1])
                    print(f"[QuantService] Using USD/TWD rate: {exchange_rate}")
            except Exception as e:
                print(f"[QuantService] Failed to fetch TWD rate: {e}")

        chunk_size = 30 # Smaller batches for more frequent updates
        results = []
        all_dfs = {}

        for i in range(0, total, chunk_size):
            chunk = symbols[i : i + chunk_size]
            print(f"[QuantService] Processing {market_type} chunk {i//chunk_size + 1}/{(total+chunk_size-1)//chunk_size} ({len(chunk)} symbols)")
            
            chunk_dfs = fetch_batch_data(chunk, market_type)
            all_dfs.update(chunk_dfs)

            for sym in chunk:
                if sym in chunk_dfs:
                    res = analyze_stock(
                        chunk_dfs[sym], sym, symbols_map.get(sym, "Unknown"), 
                        defense_weight=defense_weight, market_type=market_type, 
                        exchange_rate=exchange_rate, index_df=index_df
                    )
                    results.append(AnalysisResult(**res))
                    all_dfs[sym] = chunk_dfs[sym]

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
