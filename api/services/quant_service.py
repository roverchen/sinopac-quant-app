import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import re
import requests
from max_api import MaxExchangeAPI

def extract_stock_code(raw_str):
    """提取股票代碼，處理 '名稱(代碼)', '代碼', 'ETH-USD' 等格式"""
    import re
    if not raw_str: return ""
    raw_str = str(raw_str).strip()
    match = re.search(r'\((.*?)\)', raw_str)
    if match: return match.group(1).upper()
    return raw_str.upper()

def fetch_tw_symbols():
    """從公開來源獲取所有台股代碼清單 (上市+上櫃+ETF+權證等全部類別)"""
    import requests
    import pandas as pd
    try:
        symbols = {}
        # 模式描述: 2=上市, 4=上櫃, 5=興櫃 (興櫃暫不抓取以維護穩健性)
        for mode in ["2", "4"]:
            url = f"https://isin.twse.com.tw/isin/C_public.jsp?strMode={mode}"
            response = requests.get(url, verify=False, timeout=15)
            response.encoding = 'big5'
            # 獲取表格
            dfs = pd.read_html(response.text)
            if not dfs: continue
            df = dfs[0]
            # 核心邏輯：第一欄包含 "代碼 名稱" 格式
            for val in df[0].dropna():
                # 匹配 '2330　台積電' 這種格式 (\u3000 是全形空格)
                parts = str(val).split('\u3000')
                if len(parts) >= 2:
                    code = parts[0].strip()
                    name = parts[1].strip()
                    # 過濾：純數字代碼基本為股票/ETF/存託憑證
                    if code.isalnum() and len(code) >= 4:
                        symbols[code] = name
        
        print(f"[QuantService] TW symbols scraped: {len(symbols)}")
        return symbols
    except Exception as e:
        print(f"Error fetching TW symbols: {e}")
        return {"2330": "台積電", "2317": "鴻海", "2303": "聯電", "2454": "聯發科", "2881": "富邦金"}

def fetch_us_symbols():
    """獲取 S&P 500 代碼清單"""
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
    """獲取主要加密貨幣與 MAX 有關的交易對"""
    symbols = {
        "BTC-USD": "Bitcoin",
        "ETH-USD": "Ethereum",
        "SOL-USD": "Solana",
        "BNB-USD": "Binance Coin",
        "DOGE-USD": "Dogecoin",
        "XRP-USD": "XRP",
        "ADA-USD": "Cardano",
        "MATIC-USD": "Polygon",
        "DOT-USD": "Polkadot",
        "LINK-USD": "Chainlink"
    }
    try:
        # 嘗試從 MAX API 增加交易對 (非同步獲取)
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
    """將代碼轉換為 Yahoo Finance 的 Ticker 格式"""
    if not code: return None
    if market_type == 'TW' and code.isdigit():
        return code + (".TW" if int(code) < 10000 else ".TWO")
    if market_type == 'CRYPTO':
        # 處理格式
        c = code.upper()
        if c.endswith('TWD'):
            return f"{c[:-3]}-TWD"
        if c.endswith('USDT'):
            return f"{c[:-4]}-USD"
        if "-" not in c:
            return f"{c}-USD"
        return c
    return code

def fetch_stock_data(code, ticker_str, period="1y"):
    """從 Yahoo Finance 抓取即時數據"""
    import yfinance as yf
    try:
        ticker = yf.Ticker(ticker_str)
        df = ticker.history(period=period, interval="1d")
        if df.empty and ".TW" in ticker_str:
            # 嘗試切換 .TW/.TWO
            ticker = yf.Ticker(ticker_str.replace(".TW", ".TWO"))
            df = ticker.history(period=period, interval="1d")
        return df
    except Exception as e:
        print(f"Error fetching {ticker_str}: {e}")
        return None

def calculate_technical_indicators(df):
    """計算常用技術指標 (MA, MACD, ATR, Year High/Low)"""
    if df is None or df.empty:
        return None
        
    df = df.copy()
    df.columns = [c.lower() for c in df.columns]
    
    # 計算 MA
    df['ma5'] = df['close'].rolling(window=5).mean()
    df['ma20'] = df['close'].rolling(window=20).mean()
    df['ma60'] = df['close'].rolling(window=60).mean()
    df['ma100'] = df['close'].rolling(window=100).mean()
    df['ma240'] = df['close'].rolling(window=240).mean()
    
    # 計算成交量 MA
    df['vol_ma5'] = df['volume'].rolling(window=5).mean()
    
    # 計算 MACD
    ema12 = df['close'].ewm(span=12).mean()
    ema26 = df['close'].ewm(span=26).mean()
    df['macd'] = ema12 - ema26
    df['signal'] = df['macd'].ewm(span=9).mean()
    df['hist'] = df['macd'] - df['signal']
    
    # 計算 ATR
    high_low = df['high'] - df['low']
    high_cp = (df['high'] - df['close'].shift()).abs()
    low_cp = (df['low'] - df['close'].shift()).abs()
    tr = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
    df['atr'] = tr.rolling(window=14).mean()
    
    # 一年高低點 (240交易日)
    df['year_high'] = df['close'].rolling(window=240, min_periods=30).max()
    df['year_low'] = df['close'].rolling(window=240, min_periods=30).min()
    
    return df

def check_revenue_momentum(code):
    """
    營收檢查：近三個月 YoY 趨勢。
    """
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
        if len(data) < 3: return "數據不足", True
        
        yoy_list = []
        for d in data[-3:]:
            yoy = d.get('revenue_month_year_comparison') or d.get('revenue_percentage_change_year') or 0
            yoy_list.append(yoy)
            
        latest_yoy = yoy_list[-1]
        is_declining = all(yoy_list[i] > yoy_list[i+1] for i in range(len(yoy_list)-1))
        
        # 衰退判定：連續三個月 YoY 遞減且最新一月為負
        if is_declining and latest_yoy < 0:
            return f"📉 衰退({latest_yoy:.1f}%)", False
            
        return f"✅ 正常({latest_yoy:.1f}%)", True
    except:
        return "無法取得", True

def analyze_stock(df, code, name, defense_weight=0.5, market_type='TW'):
    """分析單一標的並返回結果 dict"""
    if df is None or len(df) < 10:
        return {
            "代碼": code, "名稱": name, "最新價格": 0, "操作建議": "❌ 無效數據",
            "一年位階": "-", "年線乖離": "-", "MA20乖離": "-", "MACD狀態": "-", "綜合評分": -1
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
    
    # 位階百分比
    level_percentile = (last_price - year_low) / (year_high - year_low) if year_high > year_low else 0.5
    
    # 乖離率 (README: 台股 240/60, Crypto 100)
    if market_type == 'CRYPTO':
        defense_base = ma100_last if not np.isnan(ma100_last) else last_row['ma60']
    else:
        defense_base = ma240_last if not np.isnan(ma240_last) else last_row['ma60']
    
    dist_to_defense = (last_price - defense_base) / defense_base if defense_base > 0 else 0
    dist_to_ma20 = (last_price - ma20_last) / ma20_last if ma20_last > 0 else 0
    
    # MACD 狀態 (加入 0 軸濾鏡)
    macd = last_row['macd']
    signal = last_row['signal']
    hist = last_row['hist']
    prev_hist = df['hist'].iloc[-2] if len(df) > 1 else hist
    
    is_gold_cross = prev_hist <= 0 and hist > 0
    is_above_zero = macd > 0 and signal > 0
    
    macd_status = "🔴 弱勢"
    if is_above_zero:
        macd_status = "🚀 強勢金叉" if is_gold_cross else "☁️ 強勢整理"
    else:
        macd_status = "🌓 低檔金叉" if is_gold_cross else "🔴 弱勢盤整"
    
    # 成交量動能 (README: 站在 5 日均線上 且 成交量 > 5 日均量 1.2 倍)
    ma5 = last_row['ma5']
    vol_ma5 = last_row['vol_ma5']
    has_vol_momentum = (last_price > ma5) and (last_row['volume'] > vol_ma5 * 1.2)
    
    # 分數計算 (README 規則)
    # A. 價值防禦
    value_score = (1 - level_percentile) * 50
    if -0.05 < dist_to_defense < 0.05: value_score += 30
    if has_vol_momentum: value_score += 20
    
    # B. 強勢拉回
    pullback_score = (1 - min(abs(dist_to_ma20), 0.1)/0.1) * 50
    if is_gold_cross:
        bonus = 50 if is_above_zero else 30
        pullback_score += bonus
    
    final_score = (defense_weight * value_score) + ((1 - defense_weight) * pullback_score)

    # 營收檢查 (僅台股且非海選模式 - 這裡我們簡化為如果是台股就查)
    is_rev_ok = True
    rev_msg = ""
    if market_type == 'TW' and code.isdigit():
        rev_msg, is_rev_ok = check_revenue_momentum(code)
        if not is_rev_ok:
            final_score *= 0.1 # 營收衰退打一折

    # --- 魯棒性修正: 處理 NaN / Inf ---
    def sanitize(val):
        if val is None or (isinstance(val, (float, np.floating)) and np.isnan(val)):
            return 0.0
        if isinstance(val, (float, np.floating)) and np.isinf(val):
            return 999.9 if val > 0 else -999.9
        return float(val) if isinstance(val, (int, float, np.integer, np.floating)) else val

    last_price = sanitize(last_price)
    final_score = sanitize(final_score)
    defense_base = sanitize(defense_base)
    ma20_last = sanitize(ma20_last)
    atr = sanitize(atr)
    
    # 進出場建議 (README 規則)
    weighted_value = defense_weight * value_score
    weighted_growth = (1 - defense_weight) * pullback_score
    
    if weighted_growth >= weighted_value:
        # 強勢回測劇本
        suggestion_type = "📈強勢"
        entry_price = ma20_last
        atr_mult = 3.0 if market_type == 'CRYPTO' else 2.5
        stop_loss = last_price - (atr_mult * atr)
        rr_ratio = 4.0 if (market_type == 'CRYPTO' and last_row['volume'] > vol_ma5 * 2.0) else 3.0
        target_price = last_price + (last_price - stop_loss) * rr_ratio
    else:
        # 價值防禦劇本
        suggestion_type = "🛡價值"
        entry_price = min(last_price, defense_base)
        # README: 目標價 (停利)：防禦均線 或 買價的 +20%
        target_price = max(defense_base, entry_price * 1.2)
        stop_loss = year_low * 0.95
        if has_vol_momentum: suggestion_type += "⚡"

    suggestion = f"{suggestion_type} | 買:{entry_price:.1f} | 標:{target_price:.1f} | 損:{sanitize(stop_loss):.1f}"
    if not is_rev_ok: suggestion = "⚠️營收衰退 | " + suggestion
    
    return {
        "代碼": code,
        "名稱": name,
        "最新價格": round(last_price, 2),
        "操作建議": suggestion,
        "一年位階": f"{sanitize(level_percentile)*100:.1f}%",
        "年線乖離": f"{sanitize(dist_to_defense)*100:.1f}%",
        "MA20乖離": f"{sanitize(dist_to_ma20)*100:.1f}%",
        "MACD狀態": macd_status,
        "綜合評分": round(final_score, 1),
        "ma_base": defense_base,
        "ma20": ma20_last,
        "atr": atr,
        "entry_price": round(sanitize(entry_price), 2),
        "stop_loss": round(sanitize(stop_loss), 2),
        "target_price": round(sanitize(target_price), 2)
    }
