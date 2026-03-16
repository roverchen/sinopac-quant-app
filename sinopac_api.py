import shioaji as sj
import streamlit as st
import os
import difflib
import pickle
from shioaji import Order
from shioaji.constant import Action, StockPriceType, OrderType

import pandas as pd
import numpy as np
import requests
# --- 模擬與初始化邏輯 ---

class MockApi:
    """模擬用的 API 類別，當連線數過多或連線失敗時使用。"""
    def list_accounts(self): return []
    def fetch_contracts(self, **kwargs): pass
    def login(self, **kwargs): pass
    def activate_ca(self, **kwargs): pass

def init_api(api_key, secret_key):
    """手動管理 API 實例於 session_state 中，避免及早載入合約導致 Segfault。"""
    if not api_key or not secret_key:
        return None
        
    # 檢查是否有已存在的且金鑰相同的實例
    if "api_instance" in st.session_state:
        if st.session_state.get("last_sj_key") == api_key and st.session_state.get("last_sj_secret") == secret_key:
            return st.session_state.api_instance
        else:
            # 金鑰更換，嘗試登出舊實例 (防止 native 層多重實例衝突)
            try:
                st.session_state.api_instance.logout()
            except: pass

    api = sj.Shioaji()
    try:
        api.login(api_key=api_key, secret_key=secret_key)
        st.session_state.api_instance = api
        st.session_state.last_sj_key = api_key
        st.session_state.last_sj_secret = secret_key
        st.session_state.sj_error = None
    except Exception as e:
        error_msg = str(e)
        st.session_state.sj_error = error_msg
        if "451" in error_msg or "Too Many Connections" in error_msg:
            return MockApi()
        else:
            return None
    return api

# --- 合約與搜尋邏輯 ---

@st.cache_data(ttl=86400, show_spinner=False)
def fetch_sp500_tickers():
    """從 Wikipedia 抓取 S&P 500 標的清單"""
    try:
        import ssl
        ssl_context = ssl._create_unverified_context()
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        # 使用 requests 配合 verify=False 或是直接讓 pandas 處理但帶入 ssl context
        # 由於 pandas 依賴 urllib/lxml，這裡最保險是用 requests
        import requests
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, verify=False, timeout=15)
        tables = pd.read_html(response.text)
        df = tables[0]
        # Wikipedia 格式：'Symbol', 'Security'
        tickers = df.set_index('Symbol')['Security'].to_dict()
        # [相容性修正] Wikipedia 符號中的 . 應轉為 - 供 Yahoo 使用 (例如 BRK.B -> BRK-B)
        processed = {k.replace('.', '-'): v for k, v in tickers.items()}
        return processed
    except Exception as e:
        print(f"⚠️ S&P 500 抓取失敗: {e}")
        return {}

@st.cache_data(ttl=86400, show_spinner=False)
def fetch_tw_tickers():
    """從公開來源 (TWSE) 獲取台股代碼清單 (備援方案)"""
    try:
        # 使用證交所公開資料 (僅示範，實際上可連接更多來源)
        url = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2"
        response = requests.get(url, verify=False, timeout=15)
        response.encoding = 'big5'
        tables = pd.read_html(response.text)
        df = tables[0]
        # 證交所格式：第一欄為 "有價證券代號及名稱"，格式為 "2330 台積電"
        mapping = {}
        for val in df[0].dropna():
            parts = str(val).split('\u3000') # 這是全型空格
            if len(parts) == 2 and parts[0].isdigit() and len(parts[0]) == 4:
                mapping[parts[0]] = parts[1]
        
        # OTC (上櫃)
        url_otc = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=4"
        response_otc = requests.get(url_otc, verify=False, timeout=15)
        response_otc.encoding = 'big5'
        tables_otc = pd.read_html(response_otc.text)
        df_otc = tables_otc[0]
        for val in df_otc[0].dropna():
            parts = str(val).split('\u3000')
            if len(parts) == 2 and parts[0].isdigit() and len(parts[0]) == 4:
                mapping[parts[0]] = parts[1]
                
        return mapping
    except Exception as e:
        print(f"⚠️ 台股清單抓取失敗: {e}")
        return {}

@st.cache_data(show_spinner=False)
def get_stock_name_map(_api):
    """建立 代碼 -> 名稱 的映射表，包含台、美 (備用專案) 市場"""
    code_to_name = {}
    
    # --- 🇺🇸 美股備用清單 (針對函式庫版本限制的補全) ---
    US_STOCK_FALLBACK = {
        "NVDA": "NVIDIA", "AAPL": "Apple", "MSFT": "Microsoft",
        "GOOGL": "Alphabet", "AMZN": "Amazon", "TSLA": "Tesla",
        "META": "Meta", "AMD": "AMD", "INTC": "Intel",
        "NFLX": "Netflix", "DIS": "Disney", "NKE": "NIKE",
        "MCD": "McDonald's", "KO": "Coca-Cola", "PEP": "PepsiCo",
        "COST": "Costco", "PYPL": "PayPal", "BABA": "Alibaba",
        "T": "AT&T", "VZ": "Verizon", "PFE": "Pfizer",
        "JPM": "JPMorgan", "V": "Visa", "MA": "Mastercard",
        "BRK.B": "Berkshire", "LLY": "Eli Lilly", "XOM": "Exxon",
        "AVGO": "Broadcom", "ORCL": "Oracle", "CRM": "Salesforce",
        "ADBE": "Adobe", "CSCO": "Cisco", "CVX": "Chevron",
        "MRK": "Merck", "ABBV": "AbbVie", "ACN": "Accenture",
        "BAC": "BofA", "ABT": "Abbott", "TMUS": "T-Mobile", "WMT": "Walmart",
        "TXN": "Texas Inst", "DHR": "Danaher", "NEE": "NextEra",
        "RTX": "Raytheon", "LOW": "Lowe's", "UNP": "Union Pacific",
        "AMAT": "Applied Mat", "HON": "Honeywell", "SPGI": "S&P Global",
        "PGR": "Progressive", "GS": "Goldman Sachs", "CAT": "Caterpillar",
        "INTU": "Intuit", "QCOM": "Qualcomm", "IBM": "IBM",
        "SBUX": "Starbucks", "GE": "GE", "TJX": "TJX Cos",
        "MDLZ": "Mondelez", "BLK": "BlackRock", "NOW": "ServiceNow",
        "ISRG": "Intuitive Surg", "PLTR": "Palantir", "SMCI": "SMCI",
        "COIN": "Coinbase", "U": "Unity", "SE": "Sea Ltd",
        "SQ": "Square", "SHOP": "Shopify", "SNOW": "Snowflake",
        "MSTR": "MicroStrategy", "MARA": "Marathon", "RIOT": "Riot",
        "MU": "Micron", "ARM": "ARM", "ASML": "ASML", "TSM": "TSMC ADR",
        "PANW": "Palo Alto", "FTNT": "Fortinet", "CRWD": "CrowdStrike", "DDOG": "Datadog",
        "ABNB": "Airbnb", "LRCX": "Lam Research", "ADI": "Analog Devices",
        "KLAC": "KLA Corp", "MELI": "MercadoLibre", "REGN": "Regeneron", "VRTX": "Vertex",
        "ADSK": "Autodesk", "NXPI": "NXP", "PYPL": "Block", "DOCU": "DocuSign", 
        "RBLX": "Roblox", "SNAP": "Snapchat", "PINS": "Pinterest", "TWLO": "Twilio", 
        "OKTA": "Okta", "ZS": "Zscaler", "NET": "Cloudflare", "MRVL": "Marvell", 
        "WDAY": "Workday", "TEAM": "Atlassian", "MDB": "MongoDB", "FSLY": "Fastly", 
        "SPOT": "Spotify", "AFRM": "Affirm", "SOFI": "SoFi", "HOOD": "Robinhood", 
        "DKNG": "DraftKings", "PATH": "UiPath", "AI": "C3.ai", "WFC": "Wells Fargo", 
        "C": "Citigroup", "MS": "Morgan Stanley", "SHEL": "Shell", "TTE": "TotalEnergies", 
        "BP": "BP", "COP": "ConocoPhillips", "SLB": "Schlumberger", "HAL": "Halliburton",
        "CMG": "Chipotle"
    }
    code_to_name.update(US_STOCK_FALLBACK)
    
    # --- 🇺🇸 S&P 500 動態補全 (嘗試獲取 500+ 標的) ---
    sp500 = fetch_sp500_tickers()
    if sp500:
        code_to_name.update(sp500)

    # 嘗試從 Shioaji 抓取最新合約 (台股)
    is_mock = isinstance(_api, MockApi) or _api is None
    if not is_mock and hasattr(_api, "Contracts") and hasattr(_api.Contracts, "Stocks"):
        stocks = _api.Contracts.Stocks
        for market_attr in ["TSE", "OTC"]:
            try:
                market_stocks = getattr(stocks, market_attr)
                for stock in market_stocks:
                    code_to_name[stock.code] = stock.name
            except:
                pass
                
    else:
        # 如果沒有 API 登入，則嘗試從公開來源補完 (本地掃描需求)
        tw_fallback = fetch_tw_tickers()
        if tw_fallback:
            code_to_name.update(tw_fallback)
                
    return code_to_name

def resolve_stock_code(input_str, api):
    """
    將使用者輸入（代碼或名稱）解析為代碼。
    如果無法精確解析，則傳回建議清單。
    """
    input_str = input_str.strip().upper()
    if not input_str:
        return None, []
    
    code_to_name = get_stock_name_map(api)
    if not code_to_name:
        return None, []

    # 1. 精確比對 (代碼優先)
    if input_str in code_to_name:
        return input_str, []
    
    # 2. 精確比對 (名稱優先)
    for code, name in code_to_name.items():
        if name.upper() == input_str:
            return code, []

    # 3. 如果輸入是純英文 (可能為美股 Ticker) - 針對 Ticker 做優先處理
    if input_str.isalpha():
        # A. 前綴比對 (例如 NV -> NVDA)
        prefix_matches = []
        for code, name in code_to_name.items():
            if code.upper().startswith(input_str):
                prefix_matches.append((name, code))
        if prefix_matches:
            return None, sorted(prefix_matches, key=lambda x: len(x[1]))[:8]

        # B. 針對 Ticker 的拼寫糾錯
        tickers = [c for c in code_to_name.keys() if not (c and c[0].isdigit())]
        close_tickers = difflib.get_close_matches(input_str, tickers, n=5, cutoff=0.5)
        if close_tickers:
            results = [(code_to_name[c], c) for c in close_tickers]
            return None, results

    # 4. 處理台股同音/錯別字變體
    var_set = {input_str}
    for char in ["來", "萊", "錸"]:
        if char in input_str:
            for target in ["來", "萊", "錸"]:
                var_set.add(input_str.replace(char, target))
    for char in ["德", "得"]:
        if char in input_str:
            for target in ["德", "得"]:
                var_set.add(input_str.replace(char, target))
    variants = list(var_set)

    # 5. 模糊建議
    suggestions = []
    for code, name in code_to_name.items():
        if any(v in name.upper() for v in variants):
            suggestions.append((name, code))
    
    if len(suggestions) < 5:
        all_names = list(code_to_name.values())
        close_names = difflib.get_close_matches(input_str, all_names, n=5, cutoff=0.5)
        name_to_code = {v: k for k, v in code_to_name.items()}
        for n in close_names:
            c = name_to_code.get(n)
            if c and not any(s[1] == c for s in suggestions):
                suggestions.append((n, c))

    if suggestions:
        return None, suggestions[:8]
    return None, []

def get_mass_scan_list(api, market='TW'):
    """從數萬檔合約中過濾出真正的股票、ETF、美股。"""
    if market == 'CRYPTO':
        return [
            "btcusdt", "ethusdt", "solusdt", "bnbusdt", "xrpusdt", 
            "adausdt", "dogeusdt", "avaxusdt", "dotusdt", "trxusdt",
            "linkusdt", "polusdt", "nearusdt", "ltcusdt", "bchusdt",
            "shibusdt", "daiusdt", "uniusdt", "leousdt", "aptusdt",
            "stxusdt", "okbusdt", "atomusdt", "imxusdt", "hbarusdt",
            "kasusdt", "etcusdt", "renderusdt", "filusdt", "ldousdt"
        ]

    all_map = get_stock_name_map(api)
    filtered = []
    for code, name in all_map.items():
        if market == 'TW':
            if code and code[0].isdigit():
                if any(k in name for k in ['購', '售', '牛', '熊', '認', '特', '債', '定']):
                    continue
                if len(code) == 4:
                    filtered.append(code)
                elif len(code) == 6 and code.startswith(('00', '01')):
                    filtered.append(code)
        elif market == 'US':
            if code and code[0].isalpha() and not (code.endswith('.TW') or code.endswith('.TWO') or '-USD' in str(code)):
                filtered.append(code)
    
    return sorted(filtered)

# --- 下單封裝邏輯 ---

def place_sinopac_order(api, symbol, qty, price):
    """將 Shioaji 下單邏輯封裝，簡化主程式 UI 代碼。"""
    if not api or isinstance(api, MockApi):
        raise Exception("目前處於模擬或未連線模式，無法執行實盤下單。")
        
    contract = None
    for mk in ["TSE", "OTC"]:
        try:
            contract = getattr(api.Contracts.Stocks, mk)[symbol]
            if contract: break
        except: continue
        
    if not contract:
        raise Exception(f"❌ 找不到該標的 {symbol} 的合約。")
        
    order = Order(
        price=price,
        quantity=qty,
        action=Action.Buy,
        price_type=StockPriceType.LMT,
        order_type=OrderType.ROD,
        account=api.list_accounts()[0]
    )
    
    trade = api.place_order(contract, order)
    return trade
