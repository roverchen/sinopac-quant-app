import streamlit as st
import os
import time

# --- Mac SSL 憑證修正 (解決 [SSL: CERTIFICATE_VERIFY_FAILED]) ---
try:
    import certifi
    os.environ['SSL_CERT_FILE'] = certifi.where()
except ImportError:
    pass

import shioaji as sj
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
import plotly.graph_objects as go

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo('Asia/Taipei')
except Exception:
    try:
        import pytz
        TZ = pytz.timezone('Asia/Taipei')
    except Exception:
        # 最終備援：手動設定 UTC+8 偏移量 (對 K 線計算最穩定)
        from datetime import timezone
        TZ = timezone(timedelta(hours=8))

def get_now():
    return datetime.now(TZ).replace(tzinfo=None)

def get_file_time(path):
    ts = os.path.getmtime(path)
    # 讀取檔案時間並轉為目標時區，去除 tzinfo 以便與 naive datetime 比較
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(TZ).replace(tzinfo=None)
    except Exception:
        return datetime.fromtimestamp(ts)
from plotly.subplots import make_subplots
import os
import difflib
import json
import requests
import yfinance as yf
import math
import pickle

# --- 常數設定 ---
WATCHLIST_FILE = "watchlist.json"
CACHE_DIR = "cache"
RESULTS_CACHE_FILE = os.path.join(CACHE_DIR, "results_cache.pkl")
NAME_MAP_CACHE_FILE = os.path.join(CACHE_DIR, "name_map.pkl")

if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

# --- 頁面設定 ---
st.set_page_config(page_title="量化選股戰情室", layout="wide")

# --- 手機版、表格優化與穩定連線 CSS ---
st.markdown("""
<style>
        /* 穩定手勢：禁止瀏覽器級別的「下拉重整」與「左右翻頁」 */
        html, body {
            overscroll-behavior: none !important; 
            touch-action: pan-y !important;
        }
        
        [data-testid="stMain"] {
            overscroll-behavior: contain !important;
        }

        /* 移除所有不穩定的 :has 選擇器，改用單純的 class 控制 */
        .desktop-only { display: block; }
        .mobile-only { display: none; }

        @media (max-width: 768px) {
            .desktop-only { display: none !important; }
            .mobile-only { display: block !important; }
            
            /* 強制所有欄位垂直堆疊 */
            [data-testid="column"] {
                width: 100% !important;
                flex: 1 1 100% !important;
                min-width: 100% !important;
                margin-bottom: 2px !important;
            }
        
        /* 讓原生容器變成漂亮的卡片樣式 */
        [data-testid="stVerticalBlockBorderWrapper"] {
            border-left: 5px solid #00d4ff !important;
            background-color: #1e1e1e !important;
            border-radius: 12px !important;
            margin-bottom: 12px !important;
        }

        /* 顯示手機標籤 */
        .mobile-label { 
            display: inline-block; 
            color: #888;
            font-size: 0.8rem;
            margin-right: 6px;
            width: 70px;
        }

        /* 優化操作建議顯示 */
        code {
            display: block !important;
            width: 100% !important;
            padding: 10px !important;
            background: #2b2b2b !important;
            border-radius: 4px !important;
            margin: 5px 0 !important;
        }

        /* 讓按鈕在手機上更好點擊 */
        .stButton button {
            width: 100% !important;
            height: 40px !important;
            margin-top: 5px !important;
        }

        /* 列表中的股票按鈕優化 */
        [data-testid="column"] .stButton button {
            text-align: left !important;
            border: none !important;
            background: rgba(0, 212, 255, 0.1) !important;
            color: #00d4ff !important;
            font-size: 1rem !important;
            padding: 8px !important;
        }
        /* 側邊欄按鈕按鈕樣式 (手機版) */
        .stButton button {
            width: 100% !important;
            height: 40px !important;
            margin-top: 5px !important;
            background: rgba(0, 212, 255, 0.1) !important;
            color: #00d4ff !important;
            border: 1px solid rgba(0, 212, 255, 0.3) !important;
        }
        
        /* 隱藏不想在手機顯示的元素 */
        .desktop-only { display: none !important; }
        .mobile-only { display: block !important; }
        
        [data-testid="stSidebarCollapsedControl"] {
            z-index: 99999 !important;
        }
    }
</style>
""", unsafe_allow_html=True)

# 預設時區工具
st.title("📈 台美股量化選股系統")

# --- 手機版側邊欄提示 ---

# --- 初始化 API ---
@st.cache_resource
def init_api():
    api = sj.Shioaji()
    # 優先從 st.secrets 讀取，若無則使用預設硬編碼內容
    try:
        api_key = st.secrets.get("API_KEY", "BPHcXm1CfdU8jw626rRVx3MXB9aqJ3HKaaovHGHkzYTn")
        secret_key = st.secrets.get("SECRET_KEY", "AJvvVZqxQCaXDwPs5CE6jYhkU5pujBm7ujhFZNbfoM7a")
    except Exception:
        # 當找不到 secrets.toml 時，Streamlit 可能會拋出異常，此時回退到硬編碼
        api_key = "BPHcXm1CfdU8jw626rRVx3MXB9aqJ3HKaaovHGHkzYTn"
        secret_key = "AJvvVZqxQCaXDwPs5CE6jYhkU5pujBm7ujhFZNbfoM7a"
    
    try:
        # 避免重複連線，如果已經有 session 可以列出帳號代表已連線
        if len(api.list_accounts()) > 0:
            return api
        
        api.login(api_key=api_key, secret_key=secret_key)
    except Exception as e:
        error_msg = str(e)
        if "451" in error_msg or "Too Many Connections" in error_msg:
            st.sidebar.error("⚠️ **API 連線衝突**")
            st.sidebar.warning("目前有其他分頁正連線中，或剛才重啟過於頻繁。")
            st.sidebar.info("💡 系統已鎖定，5 分鐘內請勿頻繁重新整理。")
            # 在全連線衝突時，建立一個空的 mock api 對象避免後續程式當掉
            class MockApi:
                def list_accounts(self): return []
                def fetch_contracts(self, **kwargs): pass
            return MockApi()
        else:
            st.error(f"API 登入失敗: {e}")
    return api

# 側邊欄：API 狀態
api = init_api()

# 檢查連線健康度
is_mock = hasattr(api, 'list_accounts') and len(api.list_accounts()) == 0 and not hasattr(api, 'Contracts')
conn_status = "🔴 連線衝突 (唯讀模式)" if is_mock else "🟢 API 連線正常"

# --- 憑證交易與背景邏輯 ---

# 確保合約在登入後只抓一次 (強制下載模式)
if not st.session_state.get('contracts_fetched', False):
    try:
        api.fetch_contracts()
        if not hasattr(api.Contracts, 'Stocks') or len(dir(api.Contracts.Stocks)) < 3:
            api.fetch_contracts(contract_download=True)
        st.session_state.contracts_fetched = True
    except:
        pass

# --- 結果暫存 (Persistence) 邏輯 ---
# --- 結果暫存 (Persistence) 邏輯 ---
def save_results_cache(df, is_big_scan=False, market=None):
    """將掃描結果存入磁碟，防止手機重新整理後消失"""
    try:
        data = {
            "df": df,
            "timestamp": get_now().strftime("%Y-%m-%d %H:%M:%S"),
            "is_big_scan": is_big_scan,
            "scan_market": market
        }
        with open(RESULTS_CACHE_FILE, "wb") as f:
            pickle.dump(data, f)
    except Exception as e:
        print(f"快取存檔失敗: {e}")

def load_results_cache():
    """從磁碟載入上一次的掃描結果"""
    if os.path.exists(RESULTS_CACHE_FILE):
        try:
            with open(RESULTS_CACHE_FILE, "rb") as f:
                return pickle.load(f)
        except:
            pass
    return None

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
        "PEP": "PepsiCo", "LIN": "Linde", "BAC": "BofA",
        "ABT": "Abbott", "TMUS": "T-Mobile", "WMT": "Walmart",
        "TXN": "Texas Inst", "DHR": "Danaher", "NEE": "NextEra",
        "RTX": "Raytheon", "LOW": "Lowe's", "UNP": "Union Pacific",
        "AMAT": "Applied Mat", "HON": "Honeywell", "SPGI": "S&P Global",
        "PGR": "Progressive", "GS": "Goldman Sachs", "CAT": "Caterpillar",
        "INTU": "Intuit", "QCOM": "Qualcomm", "IBM": "IBM",
        "SBUX": "Starbucks", "GE": "GE", "TJX": "TJX Cos",
        "MDLZ": "Mondelez", "BLK": "BlackRock", "NOW": "ServiceNow",
        "ISRG": "Intuitive Surg", "PLTR": "Palantir", "SMCI": "SMCI",
        "COIN": "Coinbase", "U": "Unity", "SE": "Sea Ltd",
        "SQ": "Square", "PYPL": "PayPal", "SHOP": "Shopify",
        "SNOW": "Snowflake", "MSTR": "MicroStrategy", "MARA": "Marathon",
        "RIOT": "Riot", "MU": "Micron", "ARM": "ARM", "ASML": "ASML",
        "TSM": "TSMC ADR", "PANW": "Palo Alto", "FTNT": "Fortinet",
        "CRWD": "CrowdStrike", "DDOG": "Datadog"
    }
    code_to_name.update(US_STOCK_FALLBACK)

    # 檢查是否為 MockApi (連線衝突模式)
    is_mock = hasattr(_api, 'list_accounts') and len(_api.list_accounts()) == 0 and not hasattr(_api, 'Contracts')

    if not is_mock and hasattr(_api, "Contracts") and hasattr(_api.Contracts, "Stocks"):
        stocks = _api.Contracts.Stocks
        def recursive_scan(item, depth=0):
            if depth > 6: return # 增加深度以確保抓到標的
            # 優先處理已知為合約集合的節點
            if hasattr(item, '_code2contract'):
                for c, contract in item._code2contract.items():
                    c_code = str(c).upper()
                    if c_code not in code_to_name:
                        code_to_name[c_code] = getattr(contract, 'name', 'Unknown')
                return

            # 如果不是，則繼續往下遞迴
            for attr in dir(item):
                if attr.startswith('_') or attr in ['append', 'get', 'keys', 'post_init']: continue
                try:
                    val = getattr(item, attr)
                    if val and (hasattr(val, '_code2contract') or hasattr(val, '__dict__') or hasattr(val, 'get')):
                        recursive_scan(val, depth + 1)
                except: continue

        # 針對台股常見市場節點進行優先顯性掃描
        for mk in ['TSE', 'OTC', 'OES']:
            if hasattr(stocks, mk):
                recursive_scan(getattr(stocks, mk))
        
        # 剩餘的進行全域遞迴 (捕捉美股或其他特殊節點)
        recursive_scan(stocks)
        
        # 成功抓取後，存入磁碟快取供離線使用 (僅在總量顯著增加時更新)
        if len(code_to_name) > 1000:
            try:
                # 如果目前的 US 列表比快取新，則強制更新
                with open(NAME_MAP_CACHE_FILE, "wb") as f:
                    pickle.dump(code_to_name, f)
            except: pass
    else:
        # 如果是 MockApi 或抓取失敗，嘗試從磁碟載入
        if os.path.exists(NAME_MAP_CACHE_FILE):
            try:
                with open(NAME_MAP_CACHE_FILE, "rb") as f:
                    cached_map = pickle.load(f)
                    code_to_name.update(cached_map)
            except: pass

    # 驗證機制
    if is_mock:
        st.sidebar.info("💡 目前處於「離線恢復模式」，名稱解析來自上次快取資料。")
    elif len(code_to_name) < 1000:
        # 只在側邊欄顯示一次輕量警告，不打斷主畫面
        st.sidebar.caption(f"ℹ️ 載入 {len(code_to_name)} 檔清單...")

    return code_to_name


# --- 輔助函式 ---
WATCHLIST_FILE = "watchlist.json"

def load_watchlist():
    if os.path.exists(WATCHLIST_FILE):
        try:
            with open(WATCHLIST_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return ["2330", "2317"]

def save_watchlist(watchlist):
    with open(WATCHLIST_FILE, "w") as f:
        json.dump(watchlist, f)

@st.cache_data(ttl=86400)
def check_revenue_momentum(code):
    """
    優化後的營收檢查：改採「近三個月 YoY 趨勢」邏輯。
    如果連續三個月 YoY 遞減且最新一月年減 > 10%，則視為真衰退。
    若最新一月已轉正或止跌，則給予轉機空間。
    """
    if not code.isdigit(): return "N/A", True
    try:
        # 使用 FinMind 開放 API
        url = "https://api.finmindtrade.com/api/v4/data"
        params = {
            "dataset": "TaiwanStockMonthRevenue",
            "data_id": code,
            "start_date": (get_now() - timedelta(days=200)).strftime("%Y-%m-%d")
        }
        res = requests.get(url, params=params, timeout=5)
        data = res.json().get('data', [])
        if len(data) < 3: return "數據不足", True
        
        # 取得近三個月的 YoY
        # 不同版本 API 欄位可能不同，嘗試常見名稱
        yoy_list = []
        for d in data[-3:]:
            yoy = d.get('revenue_month_year_comparison') or d.get('revenue_percentage_change_year') or 0
            yoy_list.append(yoy)
            
        latest_yoy = yoy_list[-1]
        prev_yoy = yoy_list[-2]
        is_trending_down = all(yoy_list[i] > yoy_list[i+1] for i in range(len(yoy_list)-1))
        
        if latest_yoy > 0:
            return f"📈 成長({latest_yoy:.1f}%)", True
        if latest_yoy > prev_yoy:
            return f"🔄 轉機({latest_yoy:.1f}%)", True
        if is_trending_down and latest_yoy < -10:
            return f"⚠️ 衰退({latest_yoy:.1f}%)", False
            
        return f"偏弱({latest_yoy:.1f}%)", True
    except:
        return "無法取得", True


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

        # B. 針對 Ticker 的拼寫糾錯 (更寬鬆的門檻以捕捉 nvida -> NVDA)
        tickers = [c for c in code_to_name.keys() if not (c and c[0].isdigit())]
        close_tickers = difflib.get_close_matches(input_str, tickers, n=5, cutoff=0.5)
        if close_tickers:
            results = [(code_to_name[c], c) for c in close_tickers]
            return None, results

    # 4. 處理台股同音/錯別字變體 (錸德/萊德等)
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

    # 5. 模糊建議 (包含子字串與名稱相似度)
    suggestions = []
    
    # A. 名稱包含子字串 (包含變體)
    for code, name in code_to_name.items():
        if any(v in name.upper() for v in variants):
            suggestions.append((name, code))
    
    # B. 如果建議太少，才使用慢速的 difflib 比對全市場名稱
    if len(suggestions) < 5:
        all_names = list(code_to_name.values())
        # 限制比對深度與提高門檻，避免找太久與出現亂湊的結果
        close_names = difflib.get_close_matches(input_str, all_names, n=5, cutoff=0.5)
        name_to_code = {v: k for k, v in code_to_name.items()}
        for n in close_names:
            c = name_to_code.get(n)
            if c and not any(s[1] == c for s in suggestions):
                suggestions.append((n, c))

    if suggestions:
        # 排序：長度越接近輸入的排越前面
        suggestions.sort(key=lambda x: abs(len(x[0]) - len(input_str)))
        return None, suggestions[:8]
            
    return None, []

def get_mass_scan_list(api, market='TW'):
    """從 4.6 萬檔合約中過濾出真正的股票
    market='TW': 台股 4 碼數字
    market='US': 美股純字母代碼
    """
    all_map = get_stock_name_map(api)
    filtered = []
    for code in all_map.keys():
        if market == 'TW':
            # 台股：數字開頭 (包含 4 碼股票與 6 碼/字母型 ETF，排除純字母權證或其他)
            if code and code[0].isdigit():
                filtered.append(code)
        elif market == 'US':
            # 美股：字母開頭 (排除純數字台股及帶點號的特殊標的)
            if code and code[0].isalpha() and not (code.endswith('.TW') or code.endswith('.TWO')):
                filtered.append(code)
    
    # 排序：台股按數字、美股按字母
    return sorted(filtered)

# --- 側邊欄設定 ---
# 1. 優先處理搜尋與新增邏輯
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = load_watchlist()
if 'resolved_code' not in st.session_state:
    st.session_state.resolved_code = None
if 'suggestions' not in st.session_state:
    st.session_state.suggestions = []
if 'defense_weight' not in st.session_state:
    st.session_state.defense_weight = 0.5
if 'rows_per_page' not in st.session_state:
    st.session_state.rows_per_page = 5
if 'current_page' not in st.session_state:
    st.session_state.current_page = 0
if 'is_big_scan' not in st.session_state:
    st.session_state.is_big_scan = False
if 'scan_market' not in st.session_state:
    st.session_state.scan_market = None

# --- [NEW] 側邊欄：功能入口置頂 ---
st.sidebar.markdown("### 🚀 快速功能")

# 1. 台灣股票海選 (使用 .desktop-only 包裹，在手機版隱藏)
with st.sidebar.container():
    st.markdown('<div class="desktop-only">', unsafe_allow_html=True)
    big_scan_tw_btn = st.sidebar.button("🔍 台灣股票海選", use_container_width=True, 
                                        type="primary" if st.session_state.get("scan_market") == "TW" else "secondary")
    big_scan_us_btn = st.sidebar.button("🔎 美國股票海選", use_container_width=True,
                                        type="primary" if st.session_state.get("scan_market") == "US" else "secondary")
    st.markdown('</div>', unsafe_allow_html=True)

# 2. 重新掃描目前清單 (僅在非大選股模式且非手機版顯示)
scan_btn = False
if not st.session_state.get("is_big_scan", False):
    with st.sidebar.container():
        st.markdown('<div class="desktop-only">', unsafe_allow_html=True)
        scan_btn = st.sidebar.button("🔄 重新掃描目前清單", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

st.sidebar.divider()
st.sidebar.markdown("### ⚙️ 策略與顯示設定")
# 動態權重滑桿
st.session_state.defense_weight = st.sidebar.slider(
    "⚖️ 策略偏好 (成長 vs 防禦)",
    min_value=0.0, max_value=1.0, value=st.session_state.defense_weight, step=0.05,
    help="0%: 強勢成長回測 | 100%: 價值防禦守護"
)
st.sidebar.caption(f"目前權重: {100-st.session_state.defense_weight*100:.0f}% 成長 / {st.session_state.defense_weight*100:.0f}% 防禦")

# 每頁顯示數量 (使用 .desktop-only 包裹，在手機版隱藏)
with st.sidebar.container():
    st.markdown('<div class="desktop-only">', unsafe_allow_html=True)
    st.session_state.rows_per_page = st.sidebar.select_slider(
        "📄 每頁顯示數量",
        options=[5, 10, 20, 50, 100],
        value=st.session_state.rows_per_page
    )
    st.markdown('</div>', unsafe_allow_html=True)
# 3. 新增股票 (僅在「目前追蹤清單」模式下顯示)
if not st.session_state.get("is_big_scan", False):
    st.sidebar.header("➕ 新增股票")
    with st.sidebar.form("add_stock_form", clear_on_submit=True):
        new_input = st.text_input("輸入代碼或名稱 (例: 2330 或 台積電)")
        submitted = st.form_submit_button("新增到清單")
        if submitted and new_input:
            # 先進行代碼檢索，暫不觸發全域掃描
            resolved_code, suggestions = resolve_stock_code(new_input, api)
            if resolved_code:
                if resolved_code not in st.session_state.watchlist:
                    st.session_state.watchlist.append(resolved_code)
                    save_watchlist(st.session_state.watchlist)
                    # 成功找到代碼，清除建議並準備同步
                    if "last_suggestions" in st.session_state:
                        del st.session_state.last_suggestions
                    st.rerun()
                else:
                    st.sidebar.warning(f"⚠️ {resolved_code} 已在清單中")
            elif suggestions:
                # 沒找到精確代碼，存下建議
                st.session_state.last_suggestions = (new_input, suggestions)
            else:
                st.sidebar.error(f"❌ 找不到與「{new_input}」相符的股票")
                if "last_suggestions" in st.session_state:
                    del st.session_state.last_suggestions

    # 顯示建議清單 (如果有的話)
    if "last_suggestions" in st.session_state:
        orig_input, suggestions = st.session_state.last_suggestions
        st.sidebar.info(f"🤔 找不到「{orig_input}」，您指的可能是：")
        for name, code in suggestions:
            if st.sidebar.button(f"{name} ({code})", key=f"suggest_{code}"):
                if code not in st.session_state.watchlist:
                    st.session_state.watchlist.append(code)
                    save_watchlist(st.session_state.watchlist)
                    del st.session_state.last_suggestions
                    st.rerun()

# 4. 交易憑證設定 (移至側邊欄最下方)
st.sidebar.divider()
st.sidebar.subheader("🔒 交易憑證設定")
person_id = st.sidebar.text_input("身分證字號", value=st.secrets.get("PERSON_ID", ""), type="default", help="啟動憑證所需")
ca_passwd = st.sidebar.text_input("憑證密碼", value=st.secrets.get("CA_PASSWD", ""), type="password", help="Sinopac.pfx 的保護密碼")
ca_path = os.path.join(os.getcwd(), "Sinopac.pfx")

ca_active = False
if person_id and ca_passwd and os.path.exists(ca_path):
    try:
        if not is_mock:
            api.activate_ca(ca_path=ca_path, ca_passwd=ca_passwd, person_id=person_id)
            st.sidebar.success("🔑 憑證已啟動 (可執行實盤)")
            ca_active = True
        else:
            st.sidebar.warning("⚠️ 唯讀模式下無法啟動憑證")
    except Exception as e:
        st.sidebar.error(f"❌ 憑證啟動失敗: {str(e)[:50]}...")

# 顯示最後一筆模擬訂單 (如果有)
if "last_order" in st.session_state:
    st.sidebar.success(f"📌 **交易回報**\n\n{st.session_state.last_order}")

watchlist = st.session_state.watchlist

# --- 核心邏輯 ---
def fetch_and_analyze(watchlist, defense_weight=0.5):
    data_list = []
    
    # 每次新掃描前，重置自動重連標記，以便未來再次觸發時能重連
    if 'auto_reconnected' in st.session_state:
        st.session_state.auto_reconnected = False
        
    # 擴大歷史長度至 365 天 (以計算年線 MA240 與一年高低位階)
    start_date = (get_now() - timedelta(days=365)).strftime("%Y-%m-%d")
    
    # 預先建立 代碼 -> 名稱 映射
    try:
        code_to_name = get_stock_name_map(api)
    except:
        # 如果對應表還沒好，嘗試現場補抓合約 (這在 API 被重置後很有用)
        try:
            api.fetch_contracts()
            code_to_name = get_stock_name_map(api)
        except:
            code_to_name = {}
    
    # 再次檢查合約狀態，若未完成則現場補抓
    if not st.session_state.get('contracts_fetched', False):
        api.fetch_contracts()
        st.session_state.contracts_fetched = True
    
    # 紀錄是否已經在迴圈中嘗試過重抓合約，避免每檔都重抓
    has_retried_contracts = False
    
    # 決定是否開啟靜音模式 (當目標數量大於 10 時自動開啟，避免 UI 警告塞車)
    quiet_mode = len(watchlist) > 10
    
    # 用於顯示進度的佔位符
    status_placeholder = st.empty()
    
    # --- [NEW] 混合模式：如果是海選（名單較多），採用 Yahoo 批次下載以達閃電速度 ---
    use_batch = len(watchlist) > 5
    if use_batch:
        status_placeholder.info(f"⚡ 啟動閃電海選模式 (批次下載 {len(watchlist)} 檔)...")
        # 1. 將 4 碼轉為 Yahoo 格式 (上市 .TW, 上櫃 .TWO)
        # 為了效率，先全部嘗試 .TW，後續分析時若沒資料再補抓 .TWO
        ticker_to_code = {} # 紀錄 Ticker -> 原代碼 的映射
        tickers = []
        for c in watchlist:
            if c and c[0].isdigit():
                t1 = f"{c}.TW"
                t2 = f"{c}.TWO"
                tickers.append(t1)
                tickers.append(t2)
                ticker_to_code[t1] = c
                ticker_to_code[t2] = c
            else:
                tickers.append(c)
                ticker_to_code[c] = c
        
        # 2. 執行批次下載 (分段執行以提高成功率)
        try:
            all_dfs = {}
            chunk_size = 100 # 加大 chunk 以提升速度，但也增加單次失敗風險
            for k in range(0, len(tickers), chunk_size):
                chunk = tickers[k:k+chunk_size]
                status_placeholder.info(f"📥 正在批次下載市場數據 ({min(k + chunk_size, len(tickers))}/{len(tickers)})...")
                batch_data = yf.download(chunk, start=start_date, group_by='ticker', threads=True, progress=False, timeout=10)
                
                # 處理下載回來的數據
                for t in chunk:
                    try:
                        if t in batch_data:
                            d = batch_data[t].dropna()
                            if not d.empty:
                                code_key = ticker_to_code[t]
                                # 如果已經有資料 (可能是 .TW 抓到了)，則不覆蓋
                                if code_key not in all_dfs:
                                    all_dfs[code_key] = d
                    except: continue
                # 稍微休息避免被封鎖
                if len(tickers) > 500: time.sleep(0.5)
        except Exception as e:
            st.error(f"批次下載發生異常: {e}")

    for i, code in enumerate(watchlist):
        progress_info = f"🕒 正在分析 ({i+1}/{len(watchlist)}): {code} ..."
        status_placeholder.info(progress_info)
        # 同步輸出到終端機供診斷
        print(f"[Analysis] {progress_info}")
        try:
            stock_name = code_to_name.get(code, "未知")
            cache_file = os.path.join(CACHE_DIR, f"{code}.csv")
            df = None
            source = "☁️ 雲端"

            # 混合模式：優先檢查剛才批次抓取的結果
            if use_batch and code in all_dfs:
                df = all_dfs[code].reset_index()
                df.columns = [c.lower() for c in df.columns]
                if 'date' in df.columns: df = df.rename(columns={'date': 'ts'})
                source = "⚡ 閃電"

            # 檢查快取是否存在且為「今日」更新
            if os.path.exists(cache_file):
                file_time = get_file_time(cache_file)
                if file_time.date() == get_now().date():
                    df = pd.read_csv(cache_file)
                    df['ts'] = pd.to_datetime(df['ts']) # 讀取 CSV 後轉換時間格式
                    source = "💾 本地"
                    # --- [NEW] 安全檢查：若快取缺少必要的指標欄位，強制重算 ---
                    if 'signal' not in df.columns or 'macd' not in df.columns:
                        df = None # 強制進入下方的抓取與計算邏輯

            if df is None:
                # 取得合約物件 (支援台股與美股備用機制)
                contract = None
                
                # 1. 優先嘗試標準路徑 (台股：數字開頭)
                if code and code[0].isdigit():
                    for mk in ['TSE', 'OTC', 'OES']:
                        if hasattr(api.Contracts.Stocks, mk):
                            try:
                                contract = getattr(api.Contracts.Stocks, mk)[code]
                                if contract: break
                            except: continue
                    
                    # 2. 如果標準路徑找不到，嘗試全域掃描 (防止節點名稱變更)
                    if not contract:
                        def find_in_obj(obj, depth=0):
                            if depth > 3: return None # 限制搜尋深度以防卡死
                            for a in dir(obj):
                                if (a.startswith('_') or 
                                    a.startswith('model_') or 
                                    a in ['append', 'get', 'keys', 'post_init']): 
                                    continue
                                try:
                                    sub = getattr(obj, a)
                                    if hasattr(sub, '__getitem__'):
                                        try:
                                            res = sub[code]
                                            if res: return res
                                        except: pass
                                    # 繼續往下一層找 (深度限制)
                                    if hasattr(sub, '__dict__'):
                                        res = find_in_obj(sub, depth + 1)
                                        if res: return res
                                except: pass
                            return None
                        contract = find_in_obj(api.Contracts.Stocks)

                    if not contract:
                        status_msg = "❌ 找不到合約"
                        if not st.session_state.get('last_chance_tried', False):
                            st.toast(f"🔍 正在刷新系統合約以尋找 {code}...", icon="🔄")
                            try:
                                # 加入超時限制 (如果有支援的話)
                                api.fetch_contracts(contract_download=True)
                                # 刷新後立刻再找一次
                                contract = find_in_obj(api.Contracts.Stocks)
                            except Exception as e:
                                st.warning(f"合約同步發生異常: {e}")
                            st.session_state.last_chance_tried = True
                            
                    if not contract:
                        if not quiet_mode:
                            st.warning(f"找不到代碼 {code} 的合約，請確認代碼是否正確。")
                        print(f"[Warning] Contract not found for {code}")
                        data_list.append({
                            "代碼": code, "名稱": stock_name, "最新價格": 0, "操作建議": status_msg,
                            "一年位階": "-", "年線乖離": "-", "MA20乖離": "-", "MACD狀態": "-", "綜合評分": -1
                        })
                        continue
                    
                    # 取得台股 KBar
                    try:
                        kbars = api.kbars(contract, start=start_date)
                        df = pd.DataFrame({**kbars})
                        source = "☁️ 雲端"
                        
                        # --- [修正] 如果 Shioaji 回傳空資料 (常見於新股 7717)，嘗試切換到 yfinance 備援 ---
                        if df.empty:
                            print(f"[Fallback] Shioaji no data for {code}, trying yfinance...")
                            for suffix in ['.TW', '.TWO']:
                                try:
                                    t = yf.Ticker(code + suffix)
                                    df_yf = t.history(period="1y", interval="1d")
                                    if not df_yf.empty:
                                        df = df_yf.reset_index()
                                        df.columns = [c.lower() for c in df.columns]
                                        if 'date' in df.columns:
                                            df = df.rename(columns={'date': 'ts'})
                                        df['ts'] = pd.to_datetime(df['ts'])
                                        df = df[['ts', 'open', 'high', 'low', 'close', 'volume']]
                                        source = f"🌐 Yahoo({suffix})"
                                        break
                                except: continue
                    except Exception as e:
                        error_msg = str(e)
                        # --- [Auto-Reconnect] 捕捉 Token 過期或連線中斷引發的 Timeout ---
                        if "api/v1/data/kbars" in error_msg:
                            if not st.session_state.get('auto_reconnected', False):
                                st.warning("⚠️ API 連線逾時或 Token 已過期，系統正在自動重新連線...")
                                st.session_state.auto_reconnected = True
                                st.cache_resource.clear()
                                time.sleep(1) # 讓舊連線稍微冷卻釋放
                                st.rerun()
                            else:
                                if not quiet_mode:
                                    st.error("❌ 自動重連後仍無法取得資料，請手動點擊「🔄 重連 API」。")
                        
                        if not quiet_mode:
                            st.warning(f"無法取得台股 {code} 的 K 線資料: {e}")
                        print(f"[Error] Failed to fetch kbars for {code}: {e}")
                        data_list.append({
                            "代碼": code, "名稱": stock_name, "最新價格": 0, "操作建議": "❌ 無法取得K線",
                            "一年位階": "-", "年線乖離": "-", "MA20乖離": "-", "MACD狀態": "-", "綜合評分": -1
                        })
                        continue
                else:
                    # 3. 處理美股 (透過 yfinance 補完計畫)
                    try:
                        ticker = yf.Ticker(code)
                        df_yf = ticker.history(period="1y", interval="1d")
                        if not df_yf.empty:
                            df = df_yf.reset_index()
                            df.columns = [c.lower() for c in df.columns]
                            if 'date' in df.columns:
                                df = df.rename(columns={'date': 'ts'})
                            df['ts'] = pd.to_datetime(df['ts'])
                            df = df[['ts', 'open', 'high', 'low', 'close', 'volume']]
                            source = "🌐 Yahoo"
                        else:
                            if not quiet_mode:
                                st.warning(f"Yahoo Finance 查無代碼 {code} 的歷史資料")
                            print(f"[Warning] No yfinance data for {code}")
                            data_list.append({
                                "代碼": code, "名稱": stock_name, "最新價格": 0, "操作建議": "❌ 無美股數據",
                                "一年位階": "-", "年線乖離": "-", "MA20乖離": "-", "MACD狀態": "-", "綜合評分": -1
                            })
                            continue
                    except Exception as yf_err:
                        st.error(f"美股數據抓取失敗 ({code}): {yf_err}")
                        data_list.append({
                            "代碼": code, "名稱": stock_name, "最新價格": 0, "操作建議": "❌ 抓取失敗",
                            "一年位階": "-", "年線乖離": "-", "MA20乖離": "-", "MACD狀態": "-", "綜合評分": -1
                        })
                        continue
                
                # 確認資料有效性
                if df is None or df.empty:
                    if not quiet_mode:
                        st.warning(f"代碼 {code} 無法獲取有效資料")
                    continue

                df.columns = [c.lower() for c in df.columns]
                df['ts'] = pd.to_datetime(df['ts'])

                # 計算指標並存檔
                df['ma20'] = df['close'].rolling(window=20).mean()
                df['ma60'] = df['close'].rolling(window=60).mean()
                df['ma240'] = df['close'].rolling(window=240).mean()
                ema12 = df['close'].ewm(span=12).mean()
                ema26 = df['close'].ewm(span=26).mean()
                df['macd'] = ema12 - ema26
                df['signal'] = df['macd'].ewm(span=9).mean()
                df['hist'] = df['macd'] - df['signal']
                
                # 儲存到本地快取
                df.to_csv(cache_file, index=False)
            
            # --- 核心邏輯：雙策略評分 (新股彈性優化) ---
            last_price = df['close'].iloc[-1]
            year_high = df['close'].max()
            year_low = df['close'].min()
            level_percentile = (last_price - year_low) / (year_high - year_low) if (year_high - year_low) != 0 else 0
            
            ma20_last = df['ma20'].iloc[-1]
            ma60_last = df['ma60'].iloc[-1]
            ma240_last = df['ma240'].iloc[-1]
            
            dist_to_ma20 = (last_price / ma20_last - 1) if not np.isnan(ma20_last) else 100
            
            # --- [修正] IPO 彈性防護：若無年線 (MA240)，改用季線 (MA60) 作為防禦基準 ---
            has_ma240 = not np.isnan(ma240_last)
            defense_base = ma240_last if has_ma240 else ma60_last
            dist_to_defense = (last_price / defense_base - 1) if not np.isnan(defense_base) else 0
            
            # MACD 狀態優化：加入 0 軸偏向過濾器
            is_gold_cross = False
            if len(df) >= 30:
                # 0軸過濾器：快線與慢線都在 0 以上為「強勢區」，以下為「弱勢區」
                is_above_zero = df['macd'].iloc[-1] > 0 and df['signal'].iloc[-1] > 0
                zone_prefix = "🎯強勢" if is_above_zero else "🩹弱勢"
                
                last_hist = df['hist'].iloc[-1]
                prev_hist = df['hist'].iloc[-2]
                if prev_hist <= 0 and last_hist > 0:
                    macd_status = f"{zone_prefix}金叉"
                    is_gold_cross = True
                elif prev_hist >= 0 and last_hist < 0:
                    macd_status = f"{zone_prefix}死叉"
                else:
                    macd_status = f"{zone_prefix}整理" if is_above_zero else "低檔盤整"
            else:
                macd_status = "資料不足"
            
            # --- [NEW] 計算 ATR (真實波幅) 用於動態停損 ---
            if len(df) > 20:
                high_low = df['high'] - df['low']
                high_cp = np.abs(df['high'] - df['close'].shift())
                low_cp = np.abs(df['low'] - df['close'].shift())
                tr = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
                atr = tr.rolling(14).mean().iloc[-1]
            else:
                atr = last_price * 0.03
            
            # --- [NEW] 價值防禦「動能觸發」 (Volume and MA5) ---
            if len(df) > 5:
                ma5 = df['close'].rolling(5).mean().iloc[-1]
                vol_ma5 = df['volume'].rolling(5).mean().iloc[-1]
                has_momentum = (last_price > ma5) and (df['volume'].iloc[-1] > vol_ma5 * 1.2)
            else:
                has_momentum = False
            
            # 盈餘動能檢查 (海選模式下跳過以節省時間)
            if use_batch or len(watchlist) > 100:
                rev_status, is_rev_ok = "跳過(海選)", True
            else:
                rev_status, is_rev_ok = check_revenue_momentum(code)
            
            # A. 價值防禦分數 (Value Defense)
            value_buy_zone = min(last_price, defense_base) if not np.isnan(defense_base) else last_price
            value_score = (1 - level_percentile) * 50
            if -0.05 < dist_to_defense < 0.05:
                value_score += 30 # 貼近年線基礎分
            if has_momentum:
                value_score += 20 # 動能加成 (避免資金卡死)
            
            # B. 強勢股回測分數 (Growth Pullback)
            growth_buy_zone = ma20_last if not np.isnan(ma20_last) else last_price
            pullback_score = (1 - min(abs(dist_to_ma20), 0.1)/0.1) * 50
            if is_gold_cross: 
                # 加上 0 軸濾鏡加成
                bonus = 50 if "強勢" in macd_status else 30
                pullback_score += bonus
            
            # 根據滑桿權重結合分數
            final_score = (defense_weight * value_score) + ((1 - defense_weight) * pullback_score)
            
            # 決定顯示在表格中的操作建議 (依據目前較高權重的策略得分)
            weighted_value_score = defense_weight * value_score
            weighted_pullback_score = (1 - defense_weight) * pullback_score
            
            if weighted_pullback_score >= weighted_value_score:
                # 強勢追蹤策略：使用 ATR 動態停損 (預設 2.5 倍 ATR，美股高波自動拉開)
                stop_loss = last_price - (2.5 * atr) 
                target = last_price + (last_price - stop_loss) * 3 # 1:3 風報比
                actionable_str = f"📈強勢 | 買:{growth_buy_zone:.1f} | 標:{target:.1f} | 損:{stop_loss:.1f} | 評分：{final_score:.1f}"
            else:
                target = ma240_last * 1.2 if not np.isnan(ma240_last) else value_buy_zone * 1.2
                stop_loss = year_low * 0.95
                m_tag = "⚡" if has_momentum else "" # 動能標記
                actionable_str = f"🛡價值{m_tag} | 買:{value_buy_zone:.1f} | 標:{target:.1f} | 損:{stop_loss:.1f} | 評分：{final_score:.1f}"

            # 如果營收衰退，則排到最下面 (分數砍半)
            if not is_rev_ok:
                final_score *= 0.1
            
            data_list.append({
                "代碼": code,
                "名稱": stock_name,
                "最新價格": last_price,
                "操作建議": actionable_str,
                "一年位階": f"{level_percentile*100:.1f}%",
                "年線乖離": f"{dist_to_defense*100:.1f}%" if has_ma240 else f"{dist_to_defense*100:.1f}%(季)",
                "MA20乖離": f"{dist_to_ma20*100:.1f}%",
                "MACD狀態": macd_status,
                "綜合評分": final_score,
                # 隱藏欄位：供即時重新計分使用 (不顯示在 UI)
                "_v_score": value_score,
                "_p_score": pullback_score,
                "_is_rev_ok": is_rev_ok,
                "_v_buy": value_buy_zone,
                "_g_buy": growth_buy_zone,
                "_ma_base": defense_base,
                "_has_ma240": has_ma240,
                "_y_low": year_low,
                "_atr": atr,
                "_has_momentum": has_momentum,
                "_macd_status": macd_status,
                "_ma20": ma20_last
            })
            
            # --- 頻率保護：如果是大選股，加入微小延遲防止被封鎖 ---
            if quiet_mode:
                time.sleep(0.01)
            
        except Exception as e:
            if not quiet_mode:
                st.warning(f"無法取得 {code} 的資料: {str(e)}")
            print(f"[Critical Error] {code}: {str(e)}")
            
    if not data_list:
        return pd.DataFrame(columns=["代碼", "名稱", "最新價格", "操作建議", "一年位階", "年線乖離", "MA20乖離", "MACD狀態", "綜合評分"])
        
    # 清除進度顯示
    status_placeholder.empty()
    
    results_df = pd.DataFrame(data_list).sort_values("綜合評分", ascending=False)
    return results_df

def rescore_results(results_df, defense_weight):
    """僅重新計算分數，不重新抓取資料 (直接使用 DataFrame 內的預分析資料，極速回應)"""
    if results_df.empty: return results_df
    
    # --- [修正] 結構檢查：防止快取版本不相容導致 KeyError ---
    required_cols = ['_v_score', '_p_score', '_is_rev_ok', '_g_buy', '_v_buy', '_ma_base', '_has_ma240', '_y_low']
    if not all(col in results_df.columns for col in required_cols):
        # 如果欄位不齊，可能是舊版快取。不報錯，直接回傳原始資料，並提示重新掃描。
        print("[Notice] Old cache detected in rescore_results, skipping vector update.")
        return results_df
    
    # 複製一份避免警告
    df = results_df.copy()
    
    # 使用向量運算重新計算綜合評分
    df['綜合評分'] = (defense_weight * df['_v_score']) + ((1 - defense_weight) * df['_p_score'])
    
    # 營收衰退懲罰
    df.loc[~df['_is_rev_ok'], '綜合評分'] *= 0.1
    
    # 重新產生操作建議文字
    def build_action(row):
        v_w = defense_weight * row['_v_score']
        p_w = (1 - defense_weight) * row['_p_score']
        score = row['綜合評分']
        
        # 取得指標
        atr = row.get('_atr', row['最新價格'] * 0.03)
        has_momentum = row.get('_has_momentum', False)
        
        if p_w >= v_w:
            # 強勢追蹤逻辑 (ATR 停損)
            stop_loss = row['最新價格'] - (2.5 * atr)
            target = row['最新價格'] + (row['最新價格'] - stop_loss) * 3
            return f"📈強勢 | 買:{row['_g_buy']:.1f} | 標:{target:.1f} | 損:{stop_loss:.1f} | 評分：{score:.1f}"
        else:
            # 價值防禦逻辑 (動能標記)
            target = row['_ma_base'] * 1.2 if row['_has_ma240'] else row['_v_buy'] * 1.2
            stop_loss = row['_y_low'] * 0.95
            m_tag = "⚡" if has_momentum else ""
            return f"🛡價值{m_tag} | 買:{row['_v_buy']:.1f} | 標:{target:.1f} | 損:{stop_loss:.1f} | 評分：{score:.1f}"

    df['操作建議'] = df.apply(build_action, axis=1)
    
    # 重新排序
    return df.sort_values("綜合評分", ascending=False)

def plot_financial_charts(df, title):
    # 建立具有兩行子圖的圖表
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.05, 
                        subplot_titles=(f'{title} K線圖', 'MACD 指標'),
                        row_width=[0.3, 0.7])

    # 1. K線圖
    fig.add_trace(go.Candlestick(
        x=df['ts'], open=df['open'], high=df['high'], 
        low=df['low'], close=df['close'], name='K線'
    ), row=1, col=1)

    # 加入均線
    fig.add_trace(go.Scatter(x=df['ts'], y=df['ma20'], name='MA20', line=dict(color='yellow', width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df['ts'], y=df['ma60'], name='MA60', line=dict(color='cyan', width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df['ts'], y=df['ma240'], name='MA240 (年線)', line=dict(color='red', width=2)), row=1, col=1)

    # 2. MACD 指標
    fig.add_trace(go.Scatter(x=df['ts'], y=df['macd'], name='MACD', line=dict(color='blue', width=1.5)), row=2, col=1)
    fig.add_trace(go.Scatter(x=df['ts'], y=df['signal'], name='Signal', line=dict(color='orange', width=1.5)), row=2, col=1)
    
    # MACD 柱狀圖 (Histogram)
    colors = ['red' if val >= 0 else 'green' for val in df['hist']]
    fig.add_trace(go.Bar(x=df['ts'], y=df['hist'], name='Histogram', marker_color=colors), row=2, col=1)

    # 佈局設定
    fig.update_layout(
        height=600,
        showlegend=True,
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        margin=dict(l=50, r=50, t=50, b=50)
    )
    
    st.plotly_chart(fig, width="stretch")

# --- 自動化掃描與顯示 ---
# 如果正在顯示建議清單，可以選擇先不自動掃描，避免干擾使用者操作
current_watchlist_key = ",".join(watchlist)
should_sync = False

# --- 啟動時優先從磁碟載入快取 (行動端穩定性關鍵) ---
if "results" not in st.session_state:
    cache_data = load_results_cache()
    if cache_data:
        # 檢查快取資料結構是否相容 (版本遷移檢查)
        cache_df = cache_data.get("df", pd.DataFrame())
        if "_ma_base" in cache_df.columns:
            st.session_state.results = cache_df
            st.session_state.last_update = cache_data["timestamp"]
            st.session_state.is_big_scan = cache_data.get("is_big_scan", False)
            st.session_state.scan_market = cache_data.get("scan_market")
            st.session_state.last_watchlist = current_watchlist_key
            st.toast("💾 已從快取恢復上次數據", icon="📥")
        else:
            # 如果快取太舊，則不載入，強制觸發新掃描
            print("[Incompatibility] Old cache version detected, ignoring file.")
            st.sidebar.warning("⚠️ 發現舊版快取資料，將自動進行全新掃描以套用新功能。")
            should_sync = True
    else:
        # 完全沒快取時，才考慮是否自動啟動 (謹慎觸發)
        if "last_suggestions" not in st.session_state:
            # 只有在 watchlist 不為空時才執行
            if watchlist:
                should_sync = True

elif st.session_state.get("last_watchlist") != current_watchlist_key:
    # 只有當追蹤清單「內容改變」時，才自動觸發同步
    should_sync = True

# 移除原本位置的掃描按鈕 (已移至側邊欄最上方)
# scan_btn = st.sidebar.button("🚀 重新掃描目前清單", ...)
# big_scan_btn = st.button("🔍 執行「全市場」大選股", ...)

# --- 掃描執行邏輯 ---
if big_scan_tw_btn or big_scan_us_btn or scan_btn or should_sync or st.session_state.get("force_rescan"):
    # 1. 決定市場與名單
    if big_scan_tw_btn or big_scan_us_btn:
        m_type = 'TW' if big_scan_tw_btn else 'US'
        m_label = "台灣" if m_type == 'TW' else "美國"
        st.session_state.is_big_scan = True
        st.session_state.scan_market = m_type
        scan_list = get_mass_scan_list(api, market=m_type)
        toast_msg = f"🚀 開始 {m_label} 股票大平原掃描 (共 {len(scan_list)} 檔)..."
    else:
        st.session_state.is_big_scan = False
        st.session_state.scan_market = None
        scan_list = watchlist
        toast_msg = "🔍 啟動市場掃描..."

    # 2. 執行分析
    st.toast(toast_msg, icon="🚀")
    with st.spinner('🔄 市場數據分析同步中...'):
        st.session_state.last_watchlist = current_watchlist_key
        st.session_state.force_rescan = False
        
        results = fetch_and_analyze(scan_list, defense_weight=st.session_state.defense_weight)
        
        if not results.empty:
            st.session_state.results = results
            st.session_state.last_update = get_now().strftime("%H:%M:%S")
            st.session_state.current_page = 0 # 重設頁碼
            
            # 存入磁碟快取
            save_results_cache(results, is_big_scan=st.session_state.is_big_scan, market=st.session_state.scan_market)
            st.toast("✅ 數據同步完成！", icon="📉")
        else:
            if st.session_state.is_big_scan:
                st.error("❌ 全市場掃描未成功取得數據。")
            else:
                st.warning("⚠️ 掃描完成，但在現有清單中找不到可分析的有效數據。")

# 顯示最後更新時間與結果
if "results" in st.session_state:
    results = st.session_state.results
    
    if "last_update" in st.session_state:
        st.sidebar.caption(f"最後更新時間: {st.session_state.last_update}")
            
    # --- 自動名稱修復與即時重新計分 ---
    # 1. 檢查是否需要根據滑桿重新計分 (極速向量運算)
    if "last_weight" not in st.session_state:
        st.session_state.last_weight = st.session_state.defense_weight
        
    if st.session_state.last_weight != st.session_state.defense_weight:
        results = rescore_results(results, st.session_state.defense_weight)
        st.session_state.results = results
        st.session_state.last_weight = st.session_state.defense_weight

    # 2. 自動補完名稱
    if (results['名稱'] == '未知').any():
        code_map = get_stock_name_map(api)
        if code_map:
            results['名稱'] = results['代碼'].apply(lambda c: code_map.get(c, '未知'))
            st.session_state.results = results

    # 顯示首選
    if not results.empty:
        top_pick = results.iloc[0]
        st.success(f"🛡️ 今日最值得佈局：**{top_pick['代碼']} {top_pick['名稱']}** ({top_pick['操作建議']})")
    else:
        st.warning("⚠️ 目前清單中尚無有效的分析結果，請點擊「🚀 重新掃描」。")
    
    # --- 指標說明 ---
    w_def = int(st.session_state.defense_weight * 100)
    w_gro = 100 - w_def
    with st.expander(f"💡 投資策略與操作建議 ({w_def}% 價值防禦 + {w_gro}% 強勢回測)"):
        st.markdown(f"""
        本系統目前採用 **「{w_def}/{w_gro} 權重動態配置」** 策略，並透過「營收趨勢」與「波動率 (ATR)」計算精確點位：
        - **🛡️ 價值防禦 ({w_def}% 資金權重)**：
            - **適用**：長線有撐的穩健股。標註 `⚡` 代表具備 **「量增 + 站回5日線」** 的動能觸發訊號。
            - **操作**：建議在**靠近年線**且具備動能時買進，目標看年線之上 20%，停損設於前波低點 (-5%)。
        - **📈 強勢回測 ({w_gro}% 資金權重)**：
            - **適用**：多頭趨勢成長股。採用 **ATR 動態停損**，自動適應市場波動，降低被掃出場的機率。
            - **操作**：回測支撐時買進，停損設為 **2.5倍 ATR**，停利採 **1:3 風報比** 鎖定利潤。
        - **MACD 狀態**：`🎯強勢金叉` (0軸上) 代表噴發力較強；`🩹弱勢金叉` (0軸下) 視為低檔技術性反彈。
        """)

    # --- 自定義列表 ---
    is_big = st.session_state.get("is_big_scan", False)
    list_title = "🏆 全市場大選股排行榜" if is_big else "📊 目前追蹤清單"
    st.markdown(f"### {list_title}")
    
    # 分頁計算
    total_rows = len(results)
    rows_per_page = st.session_state.rows_per_page
    total_pages = math.ceil(total_rows / rows_per_page) if total_rows > 0 else 1
    
    # 確保頁碼在有效範圍內
    if st.session_state.current_page >= total_pages:
        st.session_state.current_page = max(0, total_pages - 1)
        
    start_idx = st.session_state.current_page * rows_per_page
    end_idx = min(start_idx + rows_per_page, total_rows)
    paged_results = results.iloc[start_idx:end_idx]

    # --- 渲染邏輯：單一路徑原生容器 (最穩定方案) ---
    
    # 1. 顯示表頭 (直接使用 HTML 以確保 .desktop-only 隱藏完全生效)
    st.markdown("""
    <div class="desktop-only">
        <div style="display: flex; border: 1px solid #444; border-radius: 8px; padding: 10px; background: #262730; margin-bottom: 10px; font-weight: bold; align-items: center;">
            <div style="flex: 1.5;">股票</div>
            <div style="flex: 0.8;">最新價</div>
            <div style="flex: 0.8;">位階</div>
            <div style="flex: 0.8;">年線乖離</div>
            <div style="flex: 0.8;">MA20乖離</div>
            <div style="flex: 0.8;">MA20價</div>
            <div style="flex: 0.8;">ATR停損</div>
            <div style="flex: 3.5;">操作建議</div>
            <div style="flex: 0.5;"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # --- [NEW] 下單對話框 ---
    @st.dialog("📝 下單確認 (模擬預覽)")
    def show_order_dialog(row):
        st.markdown(f"### 🎯 準備委託: **{row['代碼']} {row['名稱']}**")
        
        # 提取建議買價
        try:
            # 解析建議字串: "📈強勢 | 買:1255.0 | 標:1443.2 | 損:1192.2"
            action_parts = row['操作建議'].split('|')
            buy_price = float(action_parts[1].split(':')[1].strip())
        except:
            buy_price = row['最新價格']
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("建議買價", f"{buy_price:.1f}")
        with col2:
            qty = st.number_input("委託股數", min_value=1, value=1000, step=100)
            
        st.success(f"💡 預估委託金額: **{buy_price * qty:,.0f}** 元")
        
        st.divider()
        c1, c2 = st.columns(2)
        # 按鈕 1: 模擬下單 (永遠可用)
        if c1.button("🧪 執行模擬下單", use_container_width=True):
            st.toast(f"🚀 已錄入 {row['代碼']} 模擬委託！", icon="✅")
            st.session_state.last_order = f"{get_now().strftime('%H:%M:%S')} - 已模擬買入 {row['代碼']} {qty}股"
            st.rerun()
            
        # 按鈕 2: 實盤下單 (需憑證啟動)
        if ca_active:
            if c2.button("💰 API 實盤下單", use_container_width=True, type="primary"):
                try:
                    # 1. 取得合約
                    contract = None
                    for mk in ["TSE", "OTC"]:
                        try:
                            contract = getattr(api.Contracts.Stocks, mk)[row['代碼']]
                            if contract: break
                        except: continue
                    
                    if not contract:
                        st.error("❌ 找不到該標的合約，無法下單。")
                    else:
                        # 2. 建立訂單 (預設為市價或最接近建議價)
                        # 注意：此處僅為展示架構，實際下單需處理 Order 對象
                        from shioaji import Order
                        from shioaji.constant import Action, PriceType, OrderType
                        
                        order = Order(
                            price=buy_price,
                            quantity=qty,
                            action=Action.Buy,
                            price_type=PriceType.LMT, # 限價
                            order_type=OrderType.ROD, # 當日有效
                            account=api.list_accounts()[0] # 預設取第一個帳號
                        )
                        
                        trade = api.place_order(contract, order)
                        st.session_state.last_order = f"{get_now().strftime('%H:%M:%S')} - API 已送出 {row['代碼']} {qty}股 (限價:{buy_price})"
                        st.toast("✅ API 委託已送出！", icon="🚀")
                        st.rerun()
                except Exception as e:
                    st.error(f"❌ API 下單失敗: {e}")
        else:
            c2.link_button("🌐 官網開啟下單", 
                         "https://www.sinotrade.com.tw/newweb/goOrder/?nav=0", 
                         use_container_width=True,
                         help="憑證未啟動，請手動至官網下單")

        # --- [NEW] 在對話框內顯示 K 線與 MACD 指標 ---
        st.divider()
        st.markdown(f"#### 📊 {row['代碼']} {row['名稱']} 技術圖表")
        cache_file = os.path.join(CACHE_DIR, f"{row['代碼']}.csv")
        if os.path.exists(cache_file):
            df_selected = pd.read_csv(cache_file)
            df_selected['ts'] = pd.to_datetime(df_selected['ts'])
            plot_financial_charts(df_selected, row['代碼'])
        else:
            st.warning(f"⚠️ 找不到 {row['代碼']} 的快取資料。")

    # 2. 顯示內容 (每一家股票一個穩定容器，手機自動轉卡片)
    for index, row in paged_results.iterrows():
        with st.container(border=True):
            cols = st.columns([1.5, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 3.5, 0.5])
            
            # 欄位一：股票名稱 (轉為按鈕連結)
            if cols[0].button(f"🛒 {row['代碼']} {row['名稱']}", key=f"t_{row['代碼']}_{index}", use_container_width=True):
                show_order_dialog(row)
            
            # 欄位二：最新價 (手機版會標註標籤)
            price_val = f"{row['最新價格']:.1f}" if row['最新價格'] != 0 else "-"
            cols[1].markdown(f'<span class="mobile-label">最新價:</span><b>{price_val}</b>', unsafe_allow_html=True)
            
            # 欄位三～五：指標
            cols[2].markdown(f'<span class="mobile-label">一年位階:</span>{row["一年位階"]}', unsafe_allow_html=True)
            cols[3].markdown(f'<span class="mobile-label">年線乖離:</span>{row["年線乖離"]}', unsafe_allow_html=True)
            cols[4].markdown(f'<span class="mobile-label">MA20乖離:</span>{row["MA20乖離"]}', unsafe_allow_html=True)
            
            # 欄位六～七：新增的 MA20 價 與 ATR 停損
            ma20_val = f"{row.get('_ma20', 0):.1f}"
            atr_stop = f"{row['最新價格'] - (2.5 * row.get('_atr', 0)):.1f}"
            cols[5].markdown(f'<span class="mobile-label">MA20價:</span>{ma20_val}', unsafe_allow_html=True)
            cols[6].markdown(f'<span class="mobile-label">ATR停損:</span>{atr_stop}', unsafe_allow_html=True)
            
            # 欄位八：操作建議
            cols[7].markdown(f"**`{row['操作建議']}`**")
            
            # 欄位九：動作按鈕 (唯一 Key)
            action_icon = "🗑️" if row['代碼'] in st.session_state.watchlist else "➕"
            if cols[8].button(action_icon, key=f"btn_{row['代碼']}_{index}", use_container_width=True):
                if row['代碼'] in st.session_state.watchlist:
                    st.session_state.watchlist.remove(row['代碼'])
                    st.toast(f"已從清單移除 {row['代碼']}")
                else:
                    st.session_state.watchlist.append(row['代碼'])
                    st.toast(f"已加入追蹤清單 {row['代碼']}")
                save_watchlist(st.session_state.watchlist)
                if not st.session_state.get("is_big_scan") and "results" in st.session_state:
                    del st.session_state.results
                st.rerun()

    # --- 分頁導航 ---
    if total_pages > 1:
        st.divider()
        nav_cols = st.columns([2, 1, 1, 1, 2])
        if nav_cols[1].button("◀️ 上一頁", disabled=(st.session_state.current_page == 0)):
            st.session_state.current_page -= 1
            st.rerun()
        
        nav_cols[2].write(f"第 {st.session_state.current_page + 1} / {total_pages} 頁")
        
        if nav_cols[3].button("下一頁 ▶️", disabled=(st.session_state.current_page == total_pages - 1)):
            st.session_state.current_page += 1
            st.rerun()
    
    st.divider()
    
    # 互動式圖表已移至「下單確認」對話框內，此處保持簡潔
    pass
else:
    st.info("🔄 正在初始化市場數據，或請點擊左側「🚀 手動重新掃描數據」。")