import re
import pandas as pd
import numpy as np
import yfinance as yf
import requests
from datetime import datetime, timedelta

def extract_stock_code(raw_str):
    """提取股票代碼，處理 '名稱(代碼)', '代碼', 'ETH-USD' 等格式"""
    if not raw_str: return ""
    raw_str = str(raw_str).strip()
    match = re.search(r'\((.*?)\)', raw_str)
    if match: return match.group(1).upper()
    return raw_str.upper()

def fetch_tw_symbols():
    """從公開來源獲取台股代碼清單"""
    try:
        # 證交所 (上市)
        url = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2"
        response = requests.get(url, verify=False, timeout=15)
        response.encoding = 'big5'
        tables = pd.read_html(response.text)
        df = tables[0]
        symbols = {}
        for val in df[0].dropna():
            parts = str(val).split('\u3000')
            if len(parts) == 2 and parts[0].isdigit() and len(parts[0]) == 4:
                symbols[parts[0]] = parts[1]
        
        # OTC (上櫃)
        url_otc = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=4"
        response_otc = requests.get(url_otc, verify=False, timeout=15)
        response_otc.encoding = 'big5'
        tables_otc = pd.read_html(response_otc.text)
        df_otc = tables_otc[0]
        for val in df_otc[0].dropna():
            parts = str(val).split('\u3000')
            if len(parts) == 2 and parts[0].isdigit() and len(parts[0]) == 4:
                symbols[parts[0]] = parts[1]
        return symbols
    except Exception as e:
        print(f"Error fetching TW symbols: {e}")
        return {"2330": "台積電", "2317": "鴻海", "0050": "元大台灣50"}

def fetch_us_symbols():
    """獲取 S&P 500 代碼清單"""
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

def get_yahoo_ticker(code, market_type='TW'):
    """將代碼轉換為 Yahoo Finance 的 Ticker 格式"""
    if not code: return None
    if market_type == 'TW' and code.isdigit():
        return code + (".TW" if int(code) < 10000 else ".TWO")
    if market_type == 'CRYPTO' and "-USD" not in code:
        return code + "-USD"
    return code

def fetch_stock_data(code, ticker_str, period="1y"):
    """從 Yahoo Finance 抓取即時數據"""
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
    df['ma20'] = df['close'].rolling(window=20).mean()
    df['ma60'] = df['close'].rolling(window=60).mean()
    df['ma240'] = df['close'].rolling(window=240).mean()
    
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
    year_high = last_row['year_high']
    year_low = last_row['year_low']
    atr = last_row['atr']
    
    # 位階百分比
    level_percentile = (last_price - year_low) / (year_high - year_low) if year_high > year_low else 0.5
    
    # 乖離率
    defense_base = ma240_last if not np.isnan(ma240_last) else last_row['ma60']
    dist_to_defense = (last_price - defense_base) / defense_base if defense_base > 0 else 0
    dist_to_ma20 = (last_price - ma20_last) / ma20_last if ma20_last > 0 else 0
    
    # MACD 狀態
    macd = last_row['macd']
    signal = last_row['signal']
    is_gold_cross = macd > signal
    macd_status = "🔴 弱勢"
    if macd > 0 and is_gold_cross: macd_status = "🚀 強勢金叉"
    elif macd > 0 and not is_gold_cross: macd_status = "☁️ 高檔整理"
    elif macd < 0 and is_gold_cross: macd_status = "🌓 低檔金叉"
    
    # 分數計算 (Value Defense vs Growth)
    value_score = (1 - level_percentile) * 50
    if -0.05 < dist_to_defense < 0.05: value_score += 30
    
    pullback_score = (1 - min(abs(dist_to_ma20), 0.1)/0.1) * 50
    if is_gold_cross: pullback_score += 30
    
    final_score = (defense_weight * value_score) + ((1 - defense_weight) * pullback_score)
    
    # 建議建構 (簡化版)
    stop_loss = ma20_last if not np.isnan(ma20_last) else last_price * 0.95
    target = last_price * 1.2
    suggestion = f"🛡價值 | 買:{last_price:.1f} | 標:{target:.1f} | 損:{stop_loss:.1f}"
    
    return {
        "代碼": code,
        "名稱": name,
        "最新價格": round(last_price, 2),
        "操作建議": suggestion,
        "一年位階": f"{level_percentile*100:.1f}%",
        "年線乖離": f"{dist_to_defense*100:.1f}%",
        "MA20乖離": f"{dist_to_ma20*100:.1f}%",
        "MACD狀態": macd_status,
        "綜合評分": round(final_score, 1),
        "_ma_base": defense_base,
        "_ma20": ma20_last,
        "_atr": atr
    }
