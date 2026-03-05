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
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import difflib
import json
import requests
import yfinance as yf
import math

# --- 全域設定 ---
CACHE_DIR = "cache"
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

# --- 頁面設定 ---
st.set_page_config(page_title="量化選股戰情室", layout="wide")

# --- 手機版、表格優化與穩定連線 CSS ---
st.markdown("""
<style>
    /* 1. 穩定連線與捲動平衡：攔截瀏覽器導航手勢，但保留內部捲動自由 */
    html, body {
        overscroll-behavior: none !important; /* 核心：禁止瀏覽器級別的「下拉重整」與「左右翻頁」 */
    }
    
    [data-testid="stMain"] {
        overscroll-behavior: contain !important; /* 讓捲動事件停留在 App 容器內 */
        overflow-x: hidden !important;
    }
    
    /* 2. 側邊欄開關強化 (針對手機版明顯化，確保手勢被鎖定後依然能輕鬆開啟) */
    
    /* 2. 側邊欄開關強化 (針對手機版明顯化) */
    @media (max-width: 768px) {
        [data-testid="stSidebarCollapsedControl"] {
            background-color: #007bff !important;
            border-radius: 50% !important;
            padding: 5px !important;
            box-shadow: 0 0 15px rgba(0, 123, 255, 0.8) !important;
            left: 10px !important;
            top: 10px !important;
            width: 45px !important;
            height: 45px !important;
            z-index: 999999 !important;
        }
        [data-testid="stSidebarCollapsedControl"] svg {
            color: white !important;
            width: 30px !important;
            height: 30px !important;
        }
        /* 側邊欄頂部提示文字 */
        .mobile-hint {
            background: linear-gradient(90deg, #007bff, #00d4ff);
            color: white;
            padding: 10px;
            border-radius: 8px;
            text-align: center;
            font-weight: bold;
            margin-bottom: 15px;
            font-size: 0.9rem;
            box-shadow: 0 4px 6px rgba(0,0,0,0.2);
        }
    }
    /* 電腦版隱藏提示 */
    @media (min-width: 769px) {
        .mobile-hint { display: none !important; }
    }
    
    /* 2. 響應式佈局：預設隱藏手機版標籤 */
    .mobile-label { display: none; }

    @media (max-width: 768px) {
        /* 只隱藏 Header 的背景與其他雜項，保留側邊欄按鈕按鈕 */
        [data-testid="stHeader"] { 
            background: transparent !important;
        }
        .desktop-header { display: none !important; }
        
        /* 強制所有欄位垂直堆疊 (關鍵：針對 st.columns 內部容器) */
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
    }

    @media (min-width: 769px) {
        /* 電腦版限制最小寬度以防重疊 */
        div[data-testid="stHorizontalBlock"] {
            min-width: 850px !important;
            flex-wrap: nowrap !important;
        }
    }
</style>
""", unsafe_allow_html=True)

st.title("📈 台美股量化選股系統")

# --- 手機版側邊欄提示 ---
st.markdown('<div class="mobile-hint">💡 點擊左上角 ☰ 符號即可調整策略比重</div>', unsafe_allow_html=True)

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
            st.error("⚠️ **API 連線數已達上限 (Error 451)**")
            st.warning("這是永豐金證券伺服器的限制，通常是因為短時間內重複登入/清除快取導致。")
            st.info("💡 **請等待 3-5 分鐘後再重新整理頁面**，期間請避免點擊「重連 API」或「深度清除」。")
        else:
            st.error(f"API 登入失敗: {e}")
    return api

# 側邊欄：API 狀態
api = init_api()

# 確保合約在登入後只抓一次 (強制下載模式)
if not st.session_state.get('contracts_fetched', False):
    try:
        api.fetch_contracts()
        if not hasattr(api.Contracts, 'Stocks') or len(dir(api.Contracts.Stocks)) < 3:
            api.fetch_contracts(contract_download=True)
        st.session_state.contracts_fetched = True
    except:
        pass

@st.cache_data(show_spinner=False)
def get_stock_name_map(_api):
    """建立 代碼 -> 名稱 的映射表，包含台、美 (備用專案) 市場"""
    code_to_name = {}
    
    # --- 🇺🇸 美股備用清單 (針對函式庫版本限制的補全) ---
    # 這裡包含 S&P 500 與主要龍頭，確保搜尋 "nvida" 或 "NVDA" 必中
    US_STOCK_FALLBACK = {
        "NVDA": "NVIDIA Corp (US)", "AAPL": "Apple Inc (US)", "MSFT": "Microsoft Corp (US)",
        "GOOGL": "Alphabet Inc A (US)", "AMZN": "Amazon.com Inc (US)", "TSLA": "Tesla Inc (US)",
        "META": "Meta Platforms (US)", "AMD": "AMD (US)", "INTC": "Intel (US)",
        "NFLX": "Netflix (US)", "DIS": "Disney (US)", "NKE": "NIKE (US)",
        "MCD": "McDonald's (US)", "KO": "Coca-Cola (US)", "PEP": "PepsiCo (US)",
        "COST": "Costco (US)", "PYPL": "PayPal (US)", "BABA": "Alibaba (US)",
        "T": "AT&T (US)", "VZ": "Verizon (US)", "PFE": "Pfizer (US)",
        "JPM": "JPMorgan (US)", "V": "Visa (US)", "MA": "Mastercard (US)",
        "BRK.B": "Berkshire B (US)", "LLY": "Eli Lilly (US)", "XOM": "Exxon Mobil (US)"
    }
    # 預載備用清單
    code_to_name.update(US_STOCK_FALLBACK)

    # 如果有 API 合約資訊，則進行深度補完
    if hasattr(_api, "Contracts") and hasattr(_api.Contracts, "Stocks"):
        stocks = _api.Contracts.Stocks
        def recursive_scan(item, depth=0):
            if depth > 5: return
            for attr in dir(item):
                if attr.startswith('_') or attr in ['append', 'get', 'keys', 'post_init']: continue
                try:
                    val = getattr(item, attr)
                    if hasattr(val, '_code2contract'):
                        for c, contract in val._code2contract.items():
                            c_code = str(c).upper()
                            # 不要覆蓋已有的備用清單名稱 (保留 (US) 標記)
                            if c_code not in code_to_name:
                                code_to_name[c_code] = getattr(contract, 'name', 'Unknown')
                    elif hasattr(val, '__slots__') or hasattr(val, 'get'):
                        recursive_scan(val, depth + 1)
                except: continue
        recursive_scan(stocks)

    # 驗證機制 (台股預期萬檔以上，若不足則僅警告不崩潰)
    if len(code_to_name) < 1000:
        st.warning(f"⚠️ 股票清單載入不完全 (僅 {len(code_to_name)} 檔)，部分代碼可能暫時無法解析名稱。")
    return code_to_name

# --- 診斷與 UI 回饋 ---
try:
    current_map = get_stock_name_map(api)
    map_size = len(current_map)
    st.sidebar.caption(f"📊 已載入標的: {map_size} 檔")
    
    # 檢查函式庫是否受限於台股
    from shioaji.constant import Exchange
    if not hasattr(Exchange, "US"):
        st.sidebar.warning("⚠️ 偵測到函式庫版本受限 (僅支援台股)")
        st.sidebar.caption("💡 已啟用跨市場備用清單，NVDA 等美股仍可搜尋。")
except Exception as e:
    st.sidebar.caption(f"📊 標的載入中...")

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

@st.cache_data
def check_revenue_momentum(code):
    """檢查近三個月營收是否連續 YoY 年減 (僅限台股)"""
    if not code.isdigit(): return "N/A", True # 美股目前跳過營收檢查或回傳 OK
    try:
        # 使用 FinMind 開放 API
        url = "https://api.finmindtrade.com/api/v4/data"
        params = {
            "dataset": "TaiwanStockMonthRevenue",
            "data_id": code,
            "start_date": (datetime.now() - timedelta(days=150)).strftime("%Y-%m-%d")
        }
        res = requests.get(url, params=params, timeout=5)
        data = res.json().get('data', [])
        if len(data) >= 3:
            # 取得最近三筆資料
            recent_yoy = [d.get('revenue_month_year_comparison', 0) for d in data[-3:]]
            # 如果三個月都小於 0，則為營收衰退
            if all(y < 0 for y in recent_yoy):
                return "❌ 連續三月衰退", False
            return "✅ 營收動能正常", True
    except:
        pass
    return "💡 無法取得營收", True


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
        tickers = [c for c in code_to_name.keys() if not c.isdigit()]
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

def get_mass_scan_list(api):
    """從 4.6 萬檔合約中過濾出真正的股票 (台股 4 碼, 美股字母代碼)"""
    all_map = get_stock_name_map(api)
    filtered = []
    for code in all_map.keys():
        # 台股：4 碼數字 (排除 6 碼權證)
        if code.isdigit() and len(code) == 4:
            filtered.append(code)
        # 美股：純字母 (排除含有點號或數字的衍生標的)
        elif code.isalpha():
            filtered.append(code)
    return filtered

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
    st.session_state.rows_per_page = 10
if 'current_page' not in st.session_state:
    st.session_state.current_page = 0

# --- 側邊欄設定 ---
st.sidebar.markdown("### ⚙️ 策略與顯示設定")
# 動態權重滑桿
st.session_state.defense_weight = st.sidebar.slider(
    "⚖️ 策略偏好 (成長 vs 防禦)",
    min_value=0.0, max_value=1.0, value=st.session_state.defense_weight, step=0.05,
    help="0%: 強勢成長回測 | 100%: 價值防禦守護"
)
st.sidebar.caption(f"目前權重: {100-st.session_state.defense_weight*100:.0f}% 成長 / {st.session_state.defense_weight*100:.0f}% 防禦")

# 每頁顯示數量 (預設 10 檔以減輕手機負載)
st.session_state.rows_per_page = st.sidebar.select_slider(
    "📄 每頁顯示數量 (手機建議 10)",
    options=[10, 20, 50, 100],
    value=st.session_state.rows_per_page
)
st.sidebar.divider()
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

# 2. 顯示建議清單 (如果有的話)
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

watchlist = st.session_state.watchlist

# --- 核心邏輯 ---
def fetch_and_analyze(watchlist, defense_weight=0.5):
    data_list = []
    # 儲存所有個股的歷史資料供視覺化使用
    history_data = {}
    
    # 擴大歷史長度至 365 天 (以計算年線 MA240 與一年高低位階)
    start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
    
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

            # 檢查快取是否存在且為「今日」更新
            if os.path.exists(cache_file):
                file_time = datetime.fromtimestamp(os.path.getmtime(cache_file))
                if file_time.date() == datetime.now().date():
                    df = pd.read_csv(cache_file)
                    df['ts'] = pd.to_datetime(df['ts']) # 讀取 CSV 後轉換時間格式
                    source = "💾 本地"

            if df is None:
                # 取得合約物件 (支援台股與美股備用機制)
                contract = None
                
                # 1. 優先嘗試標準路徑 (台股)
                if code.isdigit():
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
                    except Exception as e:
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
            
            # --- 核心邏輯：雙策略評分 ---
            last_price = df['close'].iloc[-1]
            year_high = df['close'].max()
            year_low = df['close'].min()
            level_percentile = (last_price - year_low) / (year_high - year_low) if (year_high - year_low) != 0 else 0
            
            ma20_last = df['ma20'].iloc[-1]
            ma240_last = df['ma240'].iloc[-1]
            dist_to_ma20 = (last_price / ma20_last - 1) if not np.isnan(ma20_last) else 100
            dist_to_ma240 = (last_price / ma240_last - 1) if not np.isnan(ma240_last) else 0
            
            # MACD 狀態
            is_gold_cross = False
            if len(df) >= 2:
                last_hist = df['hist'].iloc[-1]
                prev_hist = df['hist'].iloc[-2]
                is_gold_cross = prev_hist <= 0 and last_hist > 0
                macd_status = "🚀 金叉發動" if is_gold_cross else "趨勢中"
            else:
                macd_status = "資料不足"
            
            # 盈餘動能檢查
            rev_status, is_rev_ok = check_revenue_momentum(code)
            
            # A. 價值防禦分數 (Value Defense)
            value_buy_zone = min(last_price, ma240_last) if not np.isnan(ma240_last) else last_price
            value_score = (1 - level_percentile) * 50
            if -0.05 < dist_to_ma240 < 0.05:
                value_score += 50
            
            # B. 強勢股回測分數 (Growth Pullback)
            growth_buy_zone = ma20_last if not np.isnan(ma20_last) else last_price
            pullback_score = (1 - min(abs(dist_to_ma20), 0.1)/0.1) * 50
            if is_gold_cross: pullback_score += 50
            
            # 根據滑桿權重結合分數
            final_score = (defense_weight * value_score) + ((1 - defense_weight) * pullback_score)
            
            # 決定顯示在表格中的操作建議 (依據目前較高權重的策略得分)
            weighted_value_score = defense_weight * value_score
            weighted_pullback_score = (1 - defense_weight) * pullback_score
            
            if weighted_pullback_score >= weighted_value_score:
                target = growth_buy_zone * 1.15
                stop_loss = growth_buy_zone * 0.95
                actionable_str = f"📈強勢 | 買:{growth_buy_zone:.1f} | 標:{target:.1f} | 損:{stop_loss:.1f} | 評分：{final_score:.1f}"
            else:
                target = ma240_last * 1.2 if not np.isnan(ma240_last) else value_buy_zone * 1.2
                stop_loss = year_low * 0.95
                actionable_str = f"🛡價值 | 買:{value_buy_zone:.1f} | 標:{target:.1f} | 損:{stop_loss:.1f} | 評分：{final_score:.1f}"

            # 如果營收衰退，則排到最下面 (分數砍半)
            if not is_rev_ok:
                final_score *= 0.1
            
            data_list.append({
                "代碼": code,
                "名稱": stock_name,
                "最新價格": last_price,
                "操作建議": actionable_str,
                "一年位階": f"{level_percentile*100:.1f}%",
                "年線乖離": f"{dist_to_ma240*100:.1f}%",
                "MA20乖離": f"{dist_to_ma20*100:.1f}%",
                "MACD狀態": macd_status,
                "綜合評分": final_score,
                # 隱藏欄位：供即時重新計分使用 (不顯示在 UI)
                "_v_score": value_score,
                "_p_score": pullback_score,
                "_is_rev_ok": is_rev_ok,
                "_v_buy": value_buy_zone,
                "_g_buy": growth_buy_zone,
                "_ma240": ma240_last,
                "_y_low": year_low
            })
            
            history_data[code] = df
            
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
        
        if p_w >= v_w:
            g_buy = row['_g_buy']
            target = g_buy * 1.15
            stop = g_buy * 0.95
            return f"📈強勢 | 買:{g_buy:.1f} | 標:{target:.1f} | 損:{stop:.1f} | 評分：{score:.1f}"
        else:
            v_buy = row['_v_buy']
            ma240 = row['_ma240']
            target = ma240 * 1.2 if not np.isnan(ma240) else v_buy * 1.2
            stop = row['_y_low'] * 0.95
            return f"🛡價值 | 買:{v_buy:.1f} | 標:{target:.1f} | 損:{stop:.1f} | 評分：{score:.1f}"

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

if "results" not in st.session_state:
    # 第一次啟動時，若沒有建議清單正在顯示，則自動啟動
    if "last_suggestions" not in st.session_state:
        should_sync = True
elif st.session_state.get("last_watchlist") != current_watchlist_key:
    # 清單有變動，必定同步
    should_sync = True

# 執行同步
scan_btn = st.sidebar.button("🚀 重新掃描目前清單", use_container_width=True, type="primary")
big_scan_btn = st.sidebar.button("🔍 執行「全市場」大選股", use_container_width=True)

if should_sync or scan_btn:
    st.toast("🔍 啟動市場掃描...", icon="🚀")
    with st.spinner('🔄 市場數據分析同步中...'):
        st.session_state.last_watchlist = current_watchlist_key
        results = fetch_and_analyze(watchlist, defense_weight=st.session_state.defense_weight)
        st.session_state.results = results
        st.session_state.last_update = datetime.now().strftime("%H:%M:%S")
        st.session_state.is_big_scan = False # 標記為一般掃描
        
        if results.empty:
            st.warning("⚠️ 掃描完成，但在現有清單中找不到可分析的有效數據。")
        else:
            st.toast("✅ 數據同步完成！", icon="📉")

elif big_scan_btn:
    mass_list = get_mass_scan_list(api)
    st.toast(f"🐘 啟動全市場掃描 ({len(mass_list)} 檔)...", icon="🔍")
    with st.spinner(f'🔄 全市場數據同步中 (共 {len(mass_list)} 檔)...'):
        # 執行全市場分析
        results = fetch_and_analyze(mass_list, defense_weight=st.session_state.defense_weight)
        
        if not results.empty:
            st.session_state.results = results
            st.session_state.last_update = datetime.now().strftime("%H:%M:%S")
            st.session_state.is_big_scan = True # 標記為大選股模式
            st.session_state.current_page = 0   # 重設頁碼
            st.toast("✅ 全市場大選股完成！", icon="🏆")
        else:
            st.error("❌ 全市場掃描未成功取得數據。")

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
        本系統目前採用 **「{w_def}/{w_gro} 權重配置」** 策略，並自動剔除營收衰退標的，計算出最具勝算的行動點位：
        - **🛡️ 價值防禦 ({w_def}% 資金權重)**：
            - **適用**：長線有撐的穩健股 (股價低位階或具年線保護)。
            - **操作**：建議在**靠近年線或前低**時買進，不破底就續抱，中長線目標看**年線之上 20%**。
        - **📈 強勢回測 ({w_gro}% 資金權重)**：
            - **適用**：多頭趨勢中、回測支撐的成長股 (如台積電、美股巨頭，股價在年線之上)。
            - **操作**：建議在**靠近 20 日線 (MA20)** 動能轉強時買進，跌破 MA20 停損 (-5%)，短波段停利抓 **+15%**。
        - **MACD 狀態**：`🚀 金叉發動` 代表短線動能剛由空轉多。
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
    
    # 1. 顯示表頭 (電腦版會顯示，手機版透過 CSS 隱藏)
    st.markdown('<div class="desktop-header">', unsafe_allow_html=True)
    h_cols = st.columns([1.5, 1, 1, 1, 1, 3.5, 0.5])
    headers = ["股票", "最新價", "位階", "年線乖離", "MA20乖離", "操作建議 (買點/目標/停損)", ""]
    for col, header in zip(h_cols, headers):
        col.write(f"**{header}**")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # 2. 顯示內容 (每一家股票一個穩定容器，手機自動轉卡片)
    for index, row in paged_results.iterrows():
        with st.container(border=True):
            cols = st.columns([1.5, 1, 1, 1, 1, 3.5, 0.5])
            
            # 欄位一：股票名稱
            cols[0].write(f"**{row['代碼']}** {row['名稱']}")
            
            # 欄位二：最新價 (手機版會標註標籤)
            price_val = f"{row['最新價格']:.1f}" if row['最新價格'] != 0 else "-"
            cols[1].markdown(f'<span class="mobile-label">最新價:</span><b>{price_val}</b>', unsafe_allow_html=True)
            
            # 欄位三～五：指標
            cols[2].markdown(f'<span class="mobile-label">一年位階:</span>{row["一年位階"]}', unsafe_allow_html=True)
            cols[3].markdown(f'<span class="mobile-label">年線乖離:</span>{row["年線乖離"]}', unsafe_allow_html=True)
            cols[4].markdown(f'<span class="mobile-label">MA20乖離:</span>{row["MA20乖離"]}', unsafe_allow_html=True)
            
            # 欄位六：操作建議
            cols[5].markdown(f"**`{row['操作建議']}`**")
            
            # 欄位七：動作按鈕 (唯一 Key，手機電腦版通用同一個元件)
            action_icon = "🗑️" if row['代碼'] in st.session_state.watchlist else "➕"
            if cols[6].button(action_icon, key=f"btn_{row['代碼']}_{index}", use_container_width=True):
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
    
    # 互動式圖表選擇 (按需讀取快取，極速流暢)
    selected_code = st.selectbox("選擇要查看詳情的股票", results['代碼'].tolist())
    
    if selected_code:
        cache_file = os.path.join(CACHE_DIR, f"{selected_code}.csv")
        if os.path.exists(cache_file):
            df_selected = pd.read_csv(cache_file)
            df_selected['ts'] = pd.to_datetime(df_selected['ts'])
            plot_financial_charts(df_selected, selected_code)
        else:
            st.warning(f"⚠️ 找不到 {selected_code} 的快取資料，請重新掃描。")
else:
    st.info("🔄 正在初始化市場數據，或請點擊左側「🚀 手動重新掃描數據」。")