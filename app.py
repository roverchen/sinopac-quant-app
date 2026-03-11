import streamlit as st
import os
import time
import base64
import json
import uuid
import hashlib
import random
from streamlit_javascript import st_javascript
from dotenv import load_dotenv

# 載入環境變數 (如 MAX API Keys)
# 使用絕對路徑確保無論從哪裡啟動都能讀到同目錄下的 .env
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)


# --- Mac SSL 憑證修正 (解決 [SSL: CERTIFICATE_VERIFY_FAILED]) ---
try:
    import certifi
    os.environ['SSL_CERT_FILE'] = certifi.where()
except ImportError:
    pass

import sinopac_api
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
import difflib
import requests
import yfinance as yf
import math
import pickle
import requests

# --- 🚀 Yahoo Finance 強化功能 (針對雲端環境優化) ---
# 建立帶有現代瀏覽器特徵的持久 Session，降低被 Yahoo 判定為爬蟲的機率
YF_SESSION = requests.Session()
YF_SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "en-US,en;q=0.9,zh-TW;q=0.8,zh;q=0.7",
    "Cache-Control": "no-cache"
})

def get_random_ua():
    """隨機切換 User-Agent 以降低被 Yahoo Finance 封鎖的機率"""
    ua_list = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15"
    ]
    return random.choice(ua_list)

# 導入外掛 API
try:
    import importlib
    import max_api
    importlib.reload(max_api) # 強制重新載入以套用 get_markets 改動
    from max_api import MaxExchangeAPI
except ImportError:
    MaxExchangeAPI = None

# --- 🎯 設備檢測與識別碼工具 ---
try:
    from streamlit.runtime.scriptrunner import get_script_run_ctx
except ImportError:
    get_script_run_ctx = None

def _creds_file_path(uid):
    """回傳特定使用者的憑證檔案路徑。"""
    return os.path.join(CACHE_DIR if os.path.isdir("cache") else "cache", f"creds_{uid}.json")

def save_user_creds(uid, creds_dict):
    """將使用者憑證存到伺服器端 JSON 檔案。"""
    creds_dir = "cache"
    if not os.path.exists(creds_dir):
        os.makedirs(creds_dir)
    path = os.path.join(creds_dir, f"creds_{uid}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(creds_dict, f, ensure_ascii=False)

def load_user_creds(uid):
    """從伺服器端讀取使用者憑證。無檔案時回傳空 dict。"""
    path = os.path.join("cache", f"creds_{uid}.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def hash_password(password):
    """將密碼轉換為 SHA-256 hash 值。"""
    return hashlib.sha256(password.encode()).hexdigest()

def get_browser_state():
    """多人模式：透過暱稱與密碼登入，從伺服器端檔案讀取憑證。"""
    # 已經載入成功則直接回傳快取
    if st.session_state.get('browser_state_loaded'):
        return st.session_state.user_id, st.session_state.user_creds

    # 如果還沒登入，顯示登入畫面
    if 'user_id' not in st.session_state or not st.session_state.user_id:
        st.markdown("## 👋 歡迎使用報明牌系統")
        st.caption("請輸入您的暱稱與密碼。首次登入的使用者將自動以此密碼註冊環境。")
        nickname = st.text_input("您的暱稱（識別碼）", key="_login_nickname").strip().lower()
        password = st.text_input("登入密碼", type="password", key="_login_pwd")
        
        if st.button("🚀 進入系統", type="primary", use_container_width=True):
            if not nickname or not password:
                st.warning("請填寫暱稱與密碼！")
                st.stop()
            
            # 檢查密碼
            saved_creds = load_user_creds(nickname)
            provided_hash = hash_password(password)
            
            if saved_creds and "pwd_hash" in saved_creds:
                if saved_creds["pwd_hash"] != provided_hash:
                    st.error("❌ 密碼錯誤，請重新輸入！")
                    st.stop()
                # 密碼正確，登入成功
            else:
                # 新使用者註冊
                if not saved_creds: saved_creds = {}
                saved_creds["pwd_hash"] = provided_hash
                save_user_creds(nickname, saved_creds)
                st.success("✨ 偵測到新使用者，已為您建立個人環境！")
            
            st.session_state.user_id = nickname
            st.rerun()
        else:
            st.stop()

    uid = st.session_state.user_id

    # 初始化憑證 (若檔案不存在或為空)
    if 'user_creds' not in st.session_state:
        st.session_state.user_creds = {
            "sj_api_key": "", "sj_secret_key": "",
            "max_api_key": "", "max_api_secret": "",
            "person_id": "", "ca_passwd": ""
        }

    # 從伺服器端讀取憑證
    loaded = load_user_creds(uid)
    if loaded:
        st.session_state.user_creds.update(loaded)
        st.session_state.user_creds["_loaded"] = True

    st.session_state.browser_state_loaded = True
    return st.session_state.user_id, st.session_state.user_creds

def is_mobile_device():
    """透過 User-Agent 與 Query Parameter 判斷是否為行動裝置 (優化版)"""
    try:
        # 1. 優先檢查 Query Parameter (?mobile=1)
        if st.query_params.get("mobile") == "1":
            return True
        # 2. 檢查 User-Agent (擴展關鍵字)
        ua = st.context.headers.get("User-Agent", "").lower()
        mobile_keywords = ["mobile", "android", "iphone", "ipad", "phone", "ipod", "blackberry", "iemobile", "opera mini"]
        return any(m in ua for m in mobile_keywords)
    except:
        return False

def auto_close_sidebar():
    """在行動裝置上標記需要收合側邊欄，由主程式渲染時執行"""
    if is_mobile_device():
        st.session_state.should_close_sidebar = True

def render_sidebar_closer():
    if st.session_state.get('should_close_sidebar', False):
        import streamlit.components.v1 as components
        import time
        js_code = "<script>"
        js_code += "setTimeout(function() {"
        js_code += "var doc = window.parent.document;"
        js_code += "var sidebar = doc.querySelector('[data-testid=\"stSidebar\"]');"
        js_code += "if (sidebar) {"
        js_code += "    var btns = sidebar.querySelectorAll('button');"
        js_code += "    for (var i = 0; i < btns.length; i++) {"
        js_code += "        var btn = btns[i];"
        js_code += "        if (btn.getAttribute('aria-label') === 'Close' || (btn.querySelector('svg') && !btn.innerText)) {"
        js_code += "            btn.click();"
        js_code += "        }"
        js_code += "    }"
        js_code += "}"
        js_code += "var overlay = doc.querySelector('div[data-testid=\"stSidebarOverlay\"]');"
        js_code += "if (overlay) { overlay.click(); }"
        js_code += "doc.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', code: 'Escape', keyCode: 27, bubbles: true}));"
        js_code += "}, 500);"
        js_code += "// Execution ID: " + str(time.time())
        js_code += "</script>"
        components.html(js_code, height=0, width=0)
        st.session_state.should_close_sidebar = False

# --- 常數設定 ---
WATCHLIST_FILE = "watchlist.json"
CACHE_DIR = "cache"
# RESULTS_CACHE_FILE is now dynamic per user
NAME_MAP_CACHE_FILE = os.path.join(CACHE_DIR, "name_map.pkl")

if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

# --- yfinance 穩定性設定 (解決 Segfault 與時區問題) ---
if not os.path.exists(os.path.join(CACHE_DIR, "yf_cache")):
    os.makedirs(os.path.join(CACHE_DIR, "yf_cache"))
try:
    yf.set_tz_cache_location(os.path.join(CACHE_DIR, "yf_cache"))
except:
    pass

# --- 頁面設定 ---
st.set_page_config(page_title="金融商品市場報明牌系統", layout="wide")
user_id, user_creds = get_browser_state()
render_sidebar_closer() # 執行掛起的側邊欄收合請求

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

        /* 移除不穩定的 :has 選擇器，改用單純的 class 與物理空間隱藏 */
        .desktop-only { display: block; }
        .mobile-only { display: none; }
        .mobile-label { display: none; }
        
        /* 手機版原生按鈕優化 */
        @media (max-width: 768px) {
            .stButton > button {
                padding: 0.4rem 0.2rem !important;
                font-size: 0.82rem !important;
                min-height: 2.2rem !important;
            }
        }
        /* 電腦版按鈕優化 */
        @media (min-width: 769px) {
            .stButton > button {
                padding: 0.45rem 1rem !important;
                font-size: 0.9rem !important;
                min-height: 2.5rem !important;
                border-radius: 8px !important;
            }
        }

        @media (max-width: 768px) {
            .desktop-only { display: none !important; }
            .mobile-only { display: block !important; }
            .mobile-label { display: inline-block !important; color: #888; font-size: 0.8rem; margin-right: 6px; width: 70px; }

            /* --- 全自定義行動端元件 (Table-based for guaranteed horizontal layout) --- */
            .custom-table {
                width: 100% !important;
                border-collapse: collapse !important;
                border: none !important;
                margin: 10px 0 !important;
                table-layout: fixed !important;
            }
            .custom-table td {
                padding: 4px !important;
                border: none !important;
                vertical-align: middle !important;
                text-align: center !important;
            }
            
            .custom-btn {
                background: rgba(255,255,255,0.1) !important;
                border: 1px solid rgba(255,255,255,0.2) !important;
                border-radius: 10px !important;
                padding: 12px 2px !important;
                cursor: pointer !important;
                transition: background 0.2s !important;
                display: block !important;
                width: 100% !important;
                user-select: none !important;
                box-sizing: border-box !important;
            }
            .custom-btn:active {
                background: rgba(255,255,255,0.2) !important;
                transform: scale(0.98);
            }
            .custom-btn-icon { font-size: 1.4rem !important; margin-bottom: 2px !important; }
            .custom-btn-label { font-size: 0.7rem !important; color: #eee !important; display: block !important; font-weight: bold; }
            
            .custom-pg-num { font-size: 1.1rem !important; font-weight: bold !important; color: #fff !important; width: 100% !important; }
            
            /* 行動端專屬容器顯示 */
            .mobile-ui-container { display: block !important; width: 100% !important; }
            .desktop-ui-container { display: none !important; }
        }
        
        /* 非行動端預設隱藏 - 取消，全由 Python is_mob 控制 */
</style>
""", unsafe_allow_html=True)


# 預設時區工具
st.title("📈 金融商品市場報明牌系統")

# --- 行動端專屬：DOM 佈局強制修正 (不依賴 CSS Hacking) ---
import streamlit.components.v1 as components
components.html("""
<script>
    const parentWin = window.parent || window;
    function enforceHorizontal() {
        if (parentWin.innerWidth > 768) return;
        ['nav-marker', 'pg-marker'].forEach(id => {
            const marker = parentWin.document.getElementById(id);
            if (marker) {
                let container = marker.closest('.element-container');
                if (container && container.nextElementSibling) {
                    let block = container.nextElementSibling.querySelector('[data-testid="stHorizontalBlock"]');
                    if (block) {
                        block.style.setProperty('flex-wrap', 'nowrap', 'important');
                        block.style.setProperty('gap', '3px', 'important');
                        Array.from(block.children).forEach(col => {
                            col.style.setProperty('min-width', '0', 'important');
                            col.style.setProperty('flex', '1 1 0%', 'important');
                            col.style.setProperty('width', 'auto', 'important');
                        });
                    }
                }
            }
        });
    }
    const observer = new MutationObserver(enforceHorizontal);
    observer.observe(parentWin.document.body, { childList: true, subtree: true });
    enforceHorizontal();
</script>
""", height=0, width=0)

# --- 頂部快捷導覽列 ---
st.title("") # 佔位，微調頂部間距
st.markdown('<div id="nav-marker"></div>', unsafe_allow_html=True)
nav_cols = st.columns(5)
if nav_cols[0].button("📋 清單", use_container_width=True):
    st.session_state.active_page = "market"
    st.session_state.is_big_scan = False
    st.session_state.scan_market = None
    st.session_state.force_rescan = True
    st.rerun()
if nav_cols[1].button("📊 紀錄", use_container_width=True):
    st.session_state.active_page = "simulation"
    st.rerun()
if nav_cols[2].button("🇹🇼 台股", use_container_width=True):
    st.session_state.scan_market = "TW"
    st.session_state.is_big_scan = True
    st.session_state.trigger_daily_scan = True
    st.rerun()
if nav_cols[3].button("🇺🇸 美股", use_container_width=True):
    st.session_state.scan_market = "US"
    st.session_state.is_big_scan = True
    st.session_state.trigger_daily_scan = True
    st.rerun()
if nav_cols[4].button("🪙 加密", use_container_width=True):
    st.session_state.scan_market = "CRYPTO"
    st.session_state.is_big_scan = True
    st.session_state.trigger_daily_scan = True
    st.rerun()

# --- 手機版側邊欄提示 ---

# @st.cache_resource  <-- [REMOVED] 為了確保能套用最新的 max_api.py 修改，暫時關閉快取
def init_max_api_v5(key, secret):
    if MaxExchangeAPI:
        if key and secret and len(key) > 10:
            return MaxExchangeAPI(key, secret)
    return None

# --- 🔌 API 初始化 (Per-User Credentials from browser state) ---
# 永豐金 API：僅 LocalStorage
sj_key = user_creds.get("sj_api_key", "")
sj_secret = user_creds.get("sj_secret_key", "")
api = sinopac_api.init_api(sj_key, sj_secret)

# MAX API：LocalStorage → Secrets → .env → 空
max_key = user_creds.get("max_api_key") or st.secrets.get("MAX_API_KEY") or os.getenv("MAX_API_KEY")
max_secret = user_creds.get("max_api_secret") or st.secrets.get("MAX_API_SECRET") or os.getenv("MAX_API_SECRET")
max_api = init_max_api_v5(max_key, max_secret)


# 初始化 API 狀態文字
v_tag = f" v{max_api.VERSION}" if max_api else ""
m_api_status = f"已偵測{v_tag}" if max_key else "待設定"

# [REMOVED] 依要求移除 API 進階設定區塊

# 核心連線狀態檢查 (背景邏輯)
is_mock = isinstance(api, sinopac_api.MockApi) if api is not None else True

if max_api:
    bal = max_api.get_account_balance()
    st.session_state.max_balance = bal
    if 'error' in bal:
        if "404" in str(bal['error']):
            st.sidebar.caption(f"⚠️ MAX 連線無效 (404)。請檢查金鑰。")
        else:
            st.sidebar.caption(f"⚠️ MAX 連線錯誤: {bal.get('error', 'Unknown')}")


# --- 憑證交易與背景邏輯 ---

# 確保合約在登入後只抓一次 (強制下載模式)
if api is not None and not st.session_state.get('contracts_fetched', False):
    try:
        # 強制抓取全市場存量合約
        api.fetch_contracts()
        if hasattr(api, 'Contracts') and (not hasattr(api.Contracts, 'Stocks') or len(dir(api.Contracts.Stocks)) < 3):
            api.fetch_contracts(contract_download=True)
        
        # 額外確認數量是否達標 (台股約 1800+)
        code_map = sinopac_api.get_stock_name_map(api)
        if len(code_map) > 1500:
            st.session_state.contracts_fetched = True
    except:
        pass

# --- 結果暫存 (Persistence) 邏輯 ---
def validate_market_tickers(df, market):
    """驗證 DataFrame 內的代碼是否符合所屬市場 (嚴防 Crypto 混入美股)"""
    if df.empty or not market:
        return True
    
    tickers = df['代碼'].astype(str).tolist()
    if not tickers:
        return True
        
    if market == 'CRYPTO':
        # 加密貨幣代碼應包含 -USD
        crypto_count = sum(1 for t in tickers if "-USD" in t)
        return (crypto_count / len(tickers)) > 0.5
    elif market == 'TW':
        # 台股代碼通常為純數字
        tw_count = sum(1 for t in tickers if t[0].isdigit())
        return (tw_count / len(tickers)) > 0.5
    elif market == 'US':
        # 美股代碼通常為字母且不含 -USD
        us_count = sum(1 for t in tickers if t[0].isalpha() and "-USD" not in t)
        return (us_count / len(tickers)) > 0.5
    return True

def save_results_cache(df, is_big_scan=False, market=None, user_id="shared"):
    """將掃描結果存入磁碟，防止手機重新整理後消失"""
    try:
        # 0. 嚴格驗證市場一致性，防止資料污染
        if not validate_market_tickers(df, market):
            print(f"[Critical] Refusing to save cache: Market mismatch for {market}")
            return

        data = {
            "df": df,
            "timestamp": get_now().strftime("%Y-%m-%d %H:%M:%S"),
            "is_big_scan": is_big_scan,
            "scan_market": market
        }
        # 1. 儲存個人快取 (Session 恢復用)
        cache_file = os.path.join(CACHE_DIR, f"results_cache_{user_id}.pkl")
        with open(cache_file, "wb") as f:
            pickle.dump(data, f)
            
        # 2. 如果是全市場大選股，同步存入「每日全域共享快取」
        if is_big_scan and market:
            shared_file = os.path.join(CACHE_DIR, f"shared_results_{market}.pkl")
            with open(shared_file, "wb") as f:
                pickle.dump(data, f)
    except Exception as e:
        print(f"快取存檔失敗: {e}")

def load_results_cache(user_id="shared", market=None):
    """從磁碟載入上一次的掃描結果，支援市場級別的每日共享快取"""
    # 1. 優先檢查是否為「當日已掃過」的共享快取
    if market:
        shared_file = os.path.join(CACHE_DIR, f"shared_results_{market}.pkl")
        if os.path.exists(shared_file):
            try:
                with open(shared_file, "rb") as f:
                    data = pickle.load(f)
                    # 檢查快取日期是否為「今天」
                    cache_day = data.get('timestamp', '').split(' ')[0]
                    today_str = get_now().strftime("%Y-%m-%d")
                    if cache_day == today_str:
                        # 3. 額外驗證快取內容是否符合市場 (雙重防護)
                        cache_df = data.get('df', pd.DataFrame())
                        if validate_market_tickers(cache_df, market):
                            return data
                        else:
                            print(f"[Warning] Loading ignored: Cache content mismatch for {market}")
            except: pass

    # 2. 回退到個人專屬快取 (Session 恢復)
    return None

# --- 結果清單工具 ---

@st.cache_data(show_spinner=False)
def get_stock_name_map(_api):
    """橫向串接 sinopac_api 的映射表功能 (具備快取以加速 UI)"""
    return sinopac_api.get_stock_name_map(_api)



# --- 輔助函式 ---
WATCHLIST_FILE = "watchlist.json"

def get_watchlist_path(user_id):
    return os.path.join(CACHE_DIR, f"watchlist_{user_id}.json")

def load_watchlist(user_id):
    path = get_watchlist_path(user_id)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    
    # Priority 2: Legacy Server File (Transition phase for old users)
    if os.path.exists(WATCHLIST_FILE):
        try:
            with open(WATCHLIST_FILE, "r") as f:
                return json.load(f)
        except:
            pass

    # Priority 3: Defaults
    return ["2330", "2317", "0050"]

def save_watchlist(watchlist, user_id):
    """Save watchlist to backend JSON file tied to session ID"""
    st.session_state.watchlist = watchlist
    path = get_watchlist_path(user_id)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(watchlist, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Error saving watchlist: {e}")

# --- 🧪 模擬交易系統核心邏輯 (Paper Trading) ---

def get_trading_log_path(user_id):
    return os.path.join(CACHE_DIR, f"trading_log_{user_id}.json")

def load_trading_log(user_id):
    path = get_trading_log_path(user_id)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []

def save_trading_log(user_id, logs):
    path = get_trading_log_path(user_id)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving trading log: {e}")

def record_trade(user_id, category, symbol, name, price, reason, is_system=False, trade_type="Simulated", shares=1000):
    """記錄一筆新的模擬或實盤交易。is_system=True 會記入全域共享檔。"""
    log_id = "system" if is_system else user_id
    logs = load_trading_log(log_id)
    
    # 強制轉為 float 以支援加密貨幣的小數單位
    shares = float(shares)
    
    # 1. 系統自動規則：每日每市場僅限一筆
    if is_system:
        today_str = get_now().strftime("%Y-%m-%d")
        market_mark = reason.split(")")[0].split("(")[-1] if "(" in reason else ""
        for log in logs:
            if log['buy_time'].startswith(today_str) and market_mark in log['reason']:
                return False
                
    # 2. 檢查是否已持有該標的 (避免重複買入同一筆)
    for log in logs:
        if log['symbol'] == symbol and log['status'] == 'Open':
            return False
            
    new_trade = {
        "trade_id": str(uuid.uuid4())[:8],
        "category": "System" if is_system else "Manual",
        "trade_type": trade_type, # "Simulated" or "Real"
        "shares": int(shares),
        "symbol": symbol,
        "name": name,
        "buy_time": get_now().strftime("%Y-%m-%d %H:%M:%S"),
        "buy_price": float(price),
        "reason": reason,
        "status": "Open",
        "sell_time": None,
        "sell_price": None,
        "pnl": None,
        "pnl_percent": None
    }
    logs.append(new_trade)
    save_trading_log(log_id, logs)
    return True

def check_and_exit_trades(user_id, current_prices):
    """檢查個人與系統的未平倉位，若達標則進行結算或提醒。"""
    for log_id in ["system", user_id]:
        logs = load_trading_log(log_id)
        changed = False
        is_sys_log = (log_id == "system")
        
        for log in logs:
            if log['status'] == 'Open' and log['symbol'] in current_prices:
                curr_price = current_prices[log['symbol']]
                buy_price = log['buy_price']
                
                # 關鍵修正：防止除以零 (ZeroDivisionError)
                if buy_price <= 0:
                    continue
                    
                pnl_pct = (curr_price - buy_price) / buy_price
                
                # 策略：停損 -5%, 停利 +20%
                exit_triggered = False
                exit_reason = ""
                if pnl_pct <= -0.05:
                    exit_triggered = True
                    exit_reason = "Stop Loss (-5%)"
                elif pnl_pct >= 0.20:
                    exit_triggered = True
                    exit_reason = "Take Profit (+20%)"
                    
                if exit_triggered:
                    if is_sys_log:
                        # 系統紀錄：全自動平倉
                        log['status'] = 'Closed'
                        log['sell_time'] = get_now().strftime("%Y-%m-%d %H:%M:%S")
                        log['sell_price'] = float(curr_price)
                        log['pnl'] = float((curr_price - buy_price))
                        log['pnl_percent'] = float(pnl_pct * 100)
                        log['exit_reason'] = exit_reason
                        changed = True
                        st.toast(f"🤖 系統官方平倉：{log['symbol']} ({exit_reason})", icon="🏁")
                    else:
                        # 個人紀錄：僅通知，不自動平倉 (標記一個臨時狀態供 UI 顯示確認按鈕)
                        # 我們在 session_state 中暫存這個提醒，避免反覆彈出
                        toast_key = f"exit_toast_{log['trade_id']}"
                        if toast_key not in st.session_state:
                            st.toast(f"⚠️ 個人部位達標：{log['symbol']} {log['name']} ({exit_reason})。請至儀表板確認平倉。", icon="🔔")
                            st.session_state[toast_key] = True
                    
        if changed:
            save_trading_log(log_id, logs)

def display_simulation_dashboard(user_id):
    """在 UI 中顯示交易紀錄儀表板，區分『系統全域』與『個人手動』"""
    st.markdown("## 📈 交易紀錄儀表板 (Trading Record Dashboard)")
    
    tabs = st.tabs(["👤 我的手動執行 (個人隔離)", "🤖 系統自動執行 (全域共享)"])
    
    for i, (log_id, title) in enumerate([(user_id, "個人"), ("system", "系統")]):
        with tabs[i]:
            logs = load_trading_log(log_id)
            if not logs:
                st.info(f"📊 目前尚無{title}紀錄。")
                continue

            closed_trades = [l for l in logs if l['status'] == 'Closed']
            total_pnl = sum(l['pnl'] for l in closed_trades) if closed_trades else 0
            win_rate = (len([l for l in closed_trades if l['pnl'] > 0]) / len(closed_trades) * 100) if closed_trades else 0
            
            c1, c2, c3 = st.columns(3)
            c1.metric(f"{title}實現損益", f"{total_pnl:,.1f}")
            c2.metric(f"{title}勝率", f"{win_rate:.1f}%")
            c3.metric(f"{title}已結交易", len(closed_trades))
            
            st.markdown(f"#### 📥 {title}目前持倉")
            open_trades = [l for l in logs if l['status'] == 'Open']
            if open_trades:
                # 為了計算即時損益，嘗試從 session_state.results 拿價格 (如果有)
                curr_prices = {}
                if "results" in st.session_state:
                    curr_prices = dict(zip(st.session_state.results['代碼'], st.session_state.results['最新價格']))
                
                for trade in open_trades:
                    # 擴大理由欄位的顯示比例 (1:1.5:1.5:4:1)
                    cols = st.columns([1, 1.5, 1.5, 4, 1])
                    
                    # 顯示 模擬/實盤 (模擬不顯股數，實盤顯股數)
                    is_real = (trade.get("trade_type") == "Real")
                    t_type = "💰 實盤" if is_real else "🧪 模擬"
                    shares_text = f"**{trade.get('shares', 0):,.0f} 股**" if is_real else ""
                    cols[0].markdown(f"<span style='font-size:0.8rem'>{t_type}</span>\n\n{shares_text}", unsafe_allow_html=True)
                    
                    cols[1].write(f"**{trade['symbol']}**\n{trade['name']}")
                    cols[2].write(f"買入: {trade['buy_price']}\n{trade['buy_time'][:10]}")
                    
                    # 計算即時損益
                    if trade['symbol'] in curr_prices:
                        cp = curr_prices[trade['symbol']]
                        # 關鍵修正：防止除以零 (ZeroDivisionError)
                        if trade['buy_price'] > 0:
                            p_pct = (cp - trade['buy_price']) / trade['buy_price'] * 100
                        else:
                            p_pct = 0.0
                        color = "red" if p_pct >= 0 else "green"
                        cols[2].markdown(f"現價: {cp}\n<span style='color:{color}'>{p_pct:+.2f}%</span>", unsafe_allow_html=True)
                        
                        # 如果是個人手動，且達標，顯示確認按鈕
                        if log_id == user_id:
                            is_reached = (p_pct <= -5 or p_pct >= 20)
                            if is_reached:
                                if cols[4].button("🏁 確認平倉", key=f"exit_{trade['trade_id']}"):
                                    trade['status'] = 'Closed'
                                    trade['sell_time'] = get_now().strftime("%Y-%m-%d %H:%M:%S")
                                    trade['sell_price'] = float(cp)
                                    trade['pnl'] = float(cp - trade['buy_price'])
                                    trade['pnl_percent'] = float(p_pct)
                                    trade['exit_reason'] = "Manual Confirm (SL/TP Reached)"
                                    save_trading_log(log_id, logs)
                                    st.success(f"✅ {trade['symbol']} 已平倉紀錄！")
                                    st.rerun()
                            else:
                                if cols[4].button("提前平倉", key=f"exit_early_{trade['trade_id']}", help="手動提前結束此交易"):
                                    trade['status'] = 'Closed'
                                    trade['sell_time'] = get_now().strftime("%Y-%m-%d %H:%M:%S")
                                    trade['sell_price'] = float(cp)
                                    trade['pnl'] = float(cp - trade['buy_price'])
                                    trade['pnl_percent'] = float(p_pct)
                                    trade['exit_reason'] = "Manual Early Exit"
                                    save_trading_log(log_id, logs)
                                    st.rerun()
                    else:
                        cols[2].write("等待報價...")
                    
                    cols[3].caption(trade['reason'])
                    st.divider()
            else:
                st.write("目前無持倉。")
                
            st.markdown(f"#### 📜 {title}歷史成交紀錄")
            if closed_trades:
                df_closed = pd.DataFrame(closed_trades)[['symbol', 'name', 'buy_price', 'sell_price', 'pnl_percent', 'exit_reason', 'sell_time']]
                df_closed['pnl_percent'] = df_closed['pnl_percent'].apply(lambda x: f"{x:+.2f}%")
                st.dataframe(df_closed.sort_values('sell_time', ascending=False), use_container_width=True, hide_index=True)
    
    st.divider()

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
            return f"📉 轉機({latest_yoy:.1f}%)", True
        return f"📉 衰退({latest_yoy:.1f}%)", True
    except:
        return "無法取得", True

def resolve_stock_code(input_str, api):
    """橫向串接 sinopac_api 的代碼解析功能"""
    return sinopac_api.resolve_stock_code(input_str, api)

def build_buy_reason(row):
    """根據分析結果列生成詳細的買入理由描述"""
    w_def = int(row.get('_defense_weight', 0.5) * 100)
    w_gro = 100 - w_def
    
    # 計算主導策略
    v_w = row.get('_defense_weight', 0.5) * row.get('_v_score', 50)
    p_w = (1 - row.get('_defense_weight', 0.5)) * row.get('_p_score', 50)
    strategy = "強勢" if p_w >= v_w else "價值"
    
    level = row.get('_y_level_pct', 0.0) * 100
    y_bias = row.get('_defense_bias', 0) * 100
    ma20_bias = row.get('_ma20_bias', 0) * 100
    ma20_val = row.get('_ma20', 0)
    
    atr = row.get('_atr', 0)
    atr_mult = row.get('_atr_mult', 2.5)
    
    if strategy == "強勢":
        stop_val = row['最新價格'] - (atr * atr_mult)
    else:
        stop_val = row.get('_y_low', row['最新價格'] * 0.95) * 0.95
        
    return f"[{strategy}] (配置:{w_gro}%成長/{w_def}%防禦) 位階:{level:.1f}% | 年偏:{y_bias:+.1f}% | MA20偏:{ma20_bias:+.1f}% | MA20價:{ma20_val:.1f} | ATR損:{stop_val:.1f}"

def get_mass_scan_list(api, market='TW'):
    """橫向串接 sinopac_api 的海選清單過濾功能"""
    return sinopac_api.get_mass_scan_list(api, market)

# --- 🛠️ 核心隔離邏輯：Native Session ID 優先 (背景執行) ---
# user_id 已在上方初始化並啟動背景同步

# 1. 初始化 Watchlist (直接從後端 JSON 讀取，拋棄不穩定的 LocalStorage)
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = load_watchlist(user_id)

# 若網址上還殘留舊版的 w 參數，將其清除以保證網址純淨
if "w" in st.query_params:
    del st.query_params["w"]


if 'resolved_code' not in st.session_state:
    st.session_state.resolved_code = None
if 'suggestions' not in st.session_state:
    st.session_state.suggestions = []
if 'defense_weight' not in st.session_state:
    st.session_state.defense_weight = 0.5
if 'rows_per_page' not in st.session_state:
    # 根據裝置自動化預設值：電腦版 20, 手機版 3
    st.session_state.rows_per_page = 3 if is_mobile_device() else 20
if 'current_page' not in st.session_state:
    st.session_state.current_page = 0
if 'is_big_scan' not in st.session_state:
    st.session_state.is_big_scan = False
if 'scan_market' not in st.session_state:
    st.session_state.scan_market = None
if 'active_page' not in st.session_state:
    st.session_state.active_page = "market"


# --- 側邊欄：使用者資訊與登出 ---
with st.sidebar.container():
    c1, c2 = st.columns([2, 1])
    c1.markdown(f"👤 **{st.session_state.user_id.upper()}**")
    if c2.button("登出", key="logout_btn", use_container_width=True):
        st.session_state.user_id = None
        st.session_state.browser_state_loaded = False
        st.rerun()

st.sidebar.divider()

# --- 側邊欄：功能入口置頂 ---
# 1. 目前追蹤清單
st.sidebar.markdown('<div class="desktop-only">', unsafe_allow_html=True)
if st.sidebar.button("🚀 目前追蹤清單", use_container_width=True):
    auto_close_sidebar()
    st.session_state.active_page = "market"
    scan_btn = True # 模擬按鈕按下
else:
    scan_btn = False
st.markdown('</div>', unsafe_allow_html=True)

# 2. 交易紀錄儀表板
st.sidebar.markdown('<div class="desktop-only">', unsafe_allow_html=True)
if st.sidebar.button("📊 交易紀錄儀表板", use_container_width=True):
    auto_close_sidebar()
    st.session_state.active_page = "simulation"
    st.rerun()
st.markdown('</div>', unsafe_allow_html=True)

st.sidebar.markdown("###  全市場大選股")

# 2. 台灣/美國股票海選
with st.sidebar.container():
    st.markdown('<div class="desktop-only">', unsafe_allow_html=True)
    big_scan_tw_btn = st.sidebar.button("🇹🇼 台灣股票海選", use_container_width=True, 
                                        type="primary" if st.session_state.get("scan_market") == "TW" else "secondary",
                                        help="掃描台股全市場 (約 1800+ 檔) 並過濾出優質標的")
    big_scan_us_btn = st.sidebar.button("🇺🇸 美國股票海選", use_container_width=True,
                                        type="primary" if st.session_state.get("scan_market") == "US" else "secondary",
                                        help="掃描美股熱門標的並過濾出優質標的")
    big_scan_crypto_btn = st.sidebar.button("🪙 加密貨幣海選", use_container_width=True,
                                           type="primary" if st.session_state.get("scan_market") == "CRYPTO" else "secondary",
                                           help="掃描熱門加密貨幣並過濾出優質標的")
    st.markdown('</div>', unsafe_allow_html=True)

# 確保按下海選按鈕時切換回主頁
if big_scan_tw_btn:
    auto_close_sidebar()
    st.session_state.active_page = "market"
    st.session_state.scan_market = "TW"
    st.session_state.is_big_scan = True
    st.session_state.trigger_daily_scan = True
    st.rerun()
if big_scan_us_btn:
    auto_close_sidebar()
    st.session_state.active_page = "market"
    st.session_state.scan_market = "US"
    st.session_state.is_big_scan = True
    st.session_state.trigger_daily_scan = True
    st.rerun()
if big_scan_crypto_btn:
    auto_close_sidebar()
    st.session_state.active_page = "market"
    st.session_state.scan_market = "CRYPTO"
    st.session_state.is_big_scan = True
    st.session_state.trigger_daily_scan = True
    st.rerun()

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
        options=[3, 5, 10, 20, 50, 100],
        value=st.session_state.rows_per_page
    )
    st.markdown('</div>', unsafe_allow_html=True)
# 3. 新增股票 (始終顯示，方便使用者隨時加入追蹤)
st.sidebar.header("➕ 新增股票")
with st.sidebar.form("add_stock_form", clear_on_submit=True):
    new_input = st.text_input("輸入代碼或名稱 (例: 2330 或 台積電)")
    submitted = st.form_submit_button("新增到清單")
    if submitted and new_input:
        # 先進行代碼檢索，暫不觸發全域掃描
        resolved_code, suggestions = resolve_stock_code(new_input, api)
        if resolved_code:
            auto_close_sidebar()
            if resolved_code not in st.session_state.watchlist:
                st.session_state.watchlist.append(resolved_code)
                save_watchlist(st.session_state.watchlist, user_id)
                st.session_state.active_page = "market"
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
                auto_close_sidebar()
                if code not in st.session_state.watchlist:
                    st.session_state.watchlist.append(code)
                    save_watchlist(st.session_state.watchlist, user_id)
                    st.session_state.active_page = "market"
                    if "last_suggestions" in st.session_state:
                        del st.session_state.last_suggestions
                    st.rerun()

# 4. 🔒 交易憑證設定 (sidebar button → main area page)
st.sidebar.divider()
# 連線狀態摘要
sj_status = "✅" if (api and not is_mock) else ("⚠️" if sj_key else "⚪")
max_status = "✅" if max_api else ("⚠️" if max_key else "⚪")
if st.sidebar.button(f"🔒 交易憑證設定 ({sj_status}/{max_status})", use_container_width=True):
    st.session_state.active_page = "settings"
    st.rerun()

# --- 憑證啟動邏輯 ---
pfx_b64 = user_creds.get("ca_pfx_b64")
ca_path = os.path.join(os.path.dirname(__file__), "Sinopac.pfx")
ca_exists = os.path.exists(ca_path)

# 如果使用者有上傳過個人憑證且存在 LocalStorage，優先使用
if pfx_b64:
    try:
        import tempfile
        pfx_data = base64.b64decode(pfx_b64)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pfx") as tmp_cert:
            tmp_cert.write(pfx_data)
            ca_path = tmp_cert.name
            ca_exists = True
    except Exception as e:
        print(f"User PFX decode failed: {e}")

person_id = user_creds.get("person_id") or st.secrets.get("PERSON_ID", "")
ca_passwd = user_creds.get("ca_passwd") or st.secrets.get("CA_PASSWD", "")

ca_active = False
if person_id and ca_passwd and ca_exists and not is_mock:
    try:
        if api:
            api.activate_ca(ca_path=ca_path, ca_passwd=ca_passwd, person_id=person_id)
            ca_active = True
    except Exception as e:
        error_msg = str(e)
        if "token" in error_msg.lower():
            st.sidebar.caption("❌ 憑證密碼錯誤")
        elif "invalid password" in error_msg.lower():
            st.sidebar.caption("❌ 憑證密碼錯誤")
        elif "identity" in error_msg.lower():
            st.sidebar.caption("❌ 身分證字號不符")

if is_mock:
    st.sidebar.info("💡 目前處於「離線恢復模式」，名稱解析來自上次快取資料。")

# 顯示最後一筆模擬訂單 (如果有)
if "last_order" in st.session_state:
    st.sidebar.success(f"📌 **交易回報**\n\n{st.session_state.last_order}")


watchlist = st.session_state.watchlist

# --- 核心邏輯 ---
def fetch_and_analyze(watchlist, defense_weight=0.5, market_type=None):
    # --- [NEW] 嚴格過濾清單，確保代碼符合市場所屬，防止交叉污染 ---
    if market_type == 'CRYPTO':
        watchlist = [t for t in watchlist if "-USD" in str(t)]
    elif market_type == 'TW':
        watchlist = [t for t in watchlist if str(t)[0].isdigit()]
    elif market_type == 'US':
        watchlist = [t for t in watchlist if str(t)[0].isalpha() and "-USD" not in str(t)]
        
    data_list = []
    is_rate_limited = False # [修正] 初始化變數，避免小樣本名單時報錯

    
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
            if api is not None:
                api.fetch_contracts()
                code_to_name = get_stock_name_map(api)
            else:
                code_to_name = {}
        except:
            code_to_name = {}
    
    # 再次檢查合約狀態，若未完成則現場補抓 (增加至 60 秒 Timeout)
    if api is not None and not st.session_state.get('contracts_fetched', False):
        try:
            api.fetch_contracts(contracts_timeout=60000)
            st.session_state.contracts_fetched = True
        except Exception as e:
            # 如果已有足夠快取，則不打擾用戶；否則僅顯示輕量 Toast
            if len(code_to_name) > 1000:
                print(f"Background contract sync timeout. Fallback cache is healthy ({len(code_to_name)} items).")
            else:
                st.toast(f"⚠️ 合約即時同步超時，已切換至快取模式。")
    
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
            if c and c[1:2].isdigit() or c[0].isdigit():
                # 台股：預設嘗試 .TW (批次模式下僅嘗試一種以節省配額)
                t = f"{c}.TW" 
                tickers.append(t)
                ticker_to_code[t] = c
            else:
                # 美股處理
                t = c.replace('.', '-')
                tickers.append(t)
                ticker_to_code[t] = c
        
        # 2. 執行批次下載 (分段執行以提高成功率)
        try:
            all_dfs = {}
            chunk_size = 100 # 回歸高效批次下載
            
            for k in range(0, len(tickers), chunk_size):
                if is_rate_limited: break
                chunk = tickers[k:k+chunk_size]
                
                # 每個批次隨機更換 User-Agent
                YF_SESSION.headers.update({"User-Agent": get_random_ua()})
                
                status_placeholder.info(f"📥 正在批次下載 ({min(k + chunk_size, len(tickers))}/{len(tickers)})...")
                # 強制使用 auto_adjust=True 以獲獲取穩定的技術指標得分，並帶入專屬 Session 與增強逾時設定
                try:
                    batch_data = yf.download(
                        chunk, 
                        period="1y", # 改用 period="1y" 更穩定
                        group_by='ticker', 
                        threads=False, 
                        progress=False, 
                        timeout=20, 
                        auto_adjust=True,
                        session=YF_SESSION
                    )
                    
                    # 檢查下載結果是否異常 (Yahoo 有時會回傳字串或報錯)
                    if batch_data is None or (hasattr(batch_data, "empty") and batch_data.empty):
                        # 如果完全沒抓到且有報錯跡象，判定為頻率限制
                        print(f"[Warning] Batch returned empty. Possible rate limit at chunk starting {k}")
                        # 不直接跳出，嘗試等待更久
                    
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
                    
                    # [關鍵] 增加隨機延遲 (3 到 7 秒)，模仿人類瀏覽行為
                    wait_time = random.uniform(3.0, 7.0)
                    status_placeholder.warning(f"⏳ 正在冷卻以避免被封鎖... (等待 {wait_time:.1f}s)")
                    time.sleep(wait_time)
                except Exception as b_err:
                    err_str = str(b_err)
                    if "Too Many Requests" in err_str or "Rate limited" in err_str or "429" in err_str:
                        is_rate_limited = True
                        st.error("⚠️ 偵測到 Yahoo Finance 頻率限制 (Too Many Requests)，海選將自動暫停。")
                        break
                    print(f"[Error] Batch k={k} error: {b_err}")
                    time.sleep(10) # 發生錯誤時重裝更久
        except Exception as e:
            st.error(f"批次下載發生異常: {e}")

    for i, code in enumerate(watchlist):
        # 0. 代碼正規化 (確保大小寫一致，利於名稱比對與 API 調用)
        code = code.upper()
        
        progress_info = f"🕒 正在分析 ({i+1}/{len(watchlist)}): {code} ..."
        status_placeholder.info(progress_info)
        # 同步輸出到終端機供診斷
        print(f"[Analysis] {progress_info}")
        try:
            stock_name = code_to_name.get(code, "未知")
            # --- [NEW] 使用 _y 後綴來強制區隔與舊版(原始價)的緩存資料 ---
            cache_file = os.path.join(CACHE_DIR, f"{code}_y.csv")
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
                    df['ts'] = pd.to_datetime(df['ts'], utc=True, errors='coerce') # 讀取 CSV 後轉換時間格式
                    source = "💾 本地"
                    # --- [NEW] 安全檢查：若快取缺少必要的指標欄位，強制重算 ---
                    if 'signal' not in df.columns or 'macd' not in df.columns:
                        df = None # 強制進入下方的抓取與計算邏輯

            if df is None:
                if is_rate_limited:
                    data_list.append({
                        "代碼": code, "名稱": stock_name, "最新價格": 0, "操作建議": "⚠️ 頻率限制 (稍後再試)",
                        "一年位階": "-", "年線乖離": "-", "MA20乖離": "-", "MACD狀態": "-", "綜合評分": -1
                    })
                    continue

                # 1. 台股處理 (數字開頭)
                if code and code[0].isdigit():
                    for suffix in ['.TW', '.TWO']:
                        try:
                            # 隨機切換 UA 以降低封鎖
                            temp_session = requests.Session()
                            temp_session.headers.update({"User-Agent": get_random_ua()})
                            
                            t = yf.Ticker(code + suffix, session=temp_session)
                            # 增加 period=1y 備援，並放寬逾時
                            df_yf = t.history(period="1y", interval="1d", auto_adjust=True, timeout=15)
                            if not df_yf.empty:
                                df = df_yf.reset_index()
                                df.columns = [c.lower() for c in df.columns]
                                if 'date' in df.columns: df = df.rename(columns={'date': 'ts'})
                                df['ts'] = pd.to_datetime(df['ts'], utc=True, errors='coerce')
                                df = df[['ts', 'open', 'high', 'low', 'close', 'volume']]
                                source = f"🌐 Yahoo({suffix})"
                                break
                        except Exception as e:
                            # 偵測頻率限制
                            if "Too Many Requests" in str(e) or "Rate limited" in str(e):
                                is_rate_limited = True
                                break
                            continue
                    
                    if df is None and not is_rate_limited:
                        if not quiet_mode:
                            st.warning(f"無法取得台股 {code} 的 K 線資料")
                        data_list.append({
                            "代碼": code, "名稱": stock_name, "最新價格": 0, "操作建議": "❌ 無法取得數據",
                            "一年位階": "-", "年線乖離": "-", "MA20乖離": "-", "MACD狀態": "-", "綜合評分": -1
                        })
                        continue
                else:
                    # 2. 美股/加密貨幣處理
                    try:
                        query_code = code.replace('.', '-')
                        ticker = yf.Ticker(query_code, session=YF_SESSION)
                        # [相容性修正] 此環境 yfinance 1.2.0 不支援 history(threads=...) 參數
                        df_yf = ticker.history(start=start_date, interval="1d", auto_adjust=True)
                        
                        if df_yf.empty and market_type == 'CRYPTO':
                            df_yf = ticker.history(period="1y", interval="1d", auto_adjust=True)
                        
                        if not df_yf.empty:
                            df = df_yf.reset_index()
                            df.columns = [c.lower() for c in df.columns]
                            if 'date' in df.columns: df = df.rename(columns={'date': 'ts'})
                            df['ts'] = pd.to_datetime(df['ts'], utc=True, errors='coerce')
                            df = df[['ts', 'open', 'high', 'low', 'close', 'volume']]
                            source = "🌐 Yahoo"
                        else:
                            if not quiet_mode:
                                st.warning(f"Yahoo Finance 查無代碼 {code} 的歷史資料")
                            data_list.append({
                                "代碼": code, "名稱": stock_name, "最新價格": 0, "操作建議": "❌ 無有效數據",
                                "一年位階": "-", "年線乖離": "-", "MA20乖離": "-", "MACD狀態": "-", "綜合評分": -1
                            })
                    except Exception as yf_err:
                        if "Too Many Requests" in str(yf_err) or "Rate limited" in str(yf_err):
                            is_rate_limited = True
                            st.error("⚠️ Yahoo Finance 頻率限制 (Too Many Requests)，分析將自動停止。")
                        else:
                            if not quiet_mode:
                                st.error(f"資料抓取異常 ({code}): {yf_err}")
                
                # 抓取後的微小延遲
                time.sleep(0.3)
                
                # 確認資料有效性
                if df is None or df.empty:
                    continue

            # 如果成功取得資料且不是從本地快取讀取的，則儲存到本地快取 (此處僅存原始數據，指標會統一在下方計算)
            if df is not None and not df.empty and source != "💾 本地":
                df.to_csv(cache_file, index=False)
            
            # --- 統一技術指標計算入口 (不論來源為何都必須執行) ---
            if df is not None and not df.empty:
                # 確保欄位名稱正確
                df.columns = [c.lower() for c in df.columns]
                
                # 計算 MA 均線
                df['ma20'] = df['close'].rolling(window=20).mean()
                df['ma50'] = df['close'].rolling(window=50).mean()
                df['ma100'] = df['close'].rolling(window=100).mean()
                df['ma60'] = df['close'].rolling(window=60).mean()
                df['ma240'] = df['close'].rolling(window=240).mean()
                
                # 計算 MACD
                ema12 = df['close'].ewm(span=12).mean()
                ema26 = df['close'].ewm(span=26).mean()
                df['macd'] = ema12 - ema26
                df['signal'] = df['macd'].ewm(span=9).mean()
                df['hist'] = df['macd'] - df['signal']
                
                # 防禦性檢查：如果資料太短導致指標全是 NaN，補上預設值
                if len(df) < 5:
                    df['ma20'] = df['ma20'].fillna(df['close'])
                    df['ma60'] = df['ma60'].fillna(df['close'])
                    df['ma240'] = df['ma240'].fillna(df['close'])
            
            # --- 核心邏輯：雙策略評分 (新股彈性優化) ---
            if df is None or df.empty or 'ma20' not in df.columns:
                if not quiet_mode:
                    st.warning(f"⚠️ {code} 指標計算失敗，跳過分析")
                continue

            last_price = df['close'].iloc[-1]
            year_high = df['close'].max()
            year_low = df['close'].min()
            level_percentile = (last_price - year_low) / (year_high - year_low) if (year_high - year_low) != 0 else 0
            
            ma20_last = df['ma20'].iloc[-1]
            ma50_last = df['ma50'].iloc[-1]
            ma100_last = df['ma100'].iloc[-1]
            ma60_last = df['ma60'].iloc[-1]
            ma240_last = df['ma240'].iloc[-1]
            
            dist_to_ma20 = (last_price / ma20_last - 1) if not np.isnan(ma20_last) else 0
            
            # --- [修正] 市場彈性策略 ---
            if market_type == 'CRYPTO':
                has_defense_ma = not np.isnan(ma100_last)
                defense_base = ma100_last if has_defense_ma else ma50_last
                atr_multiplier = 3.0 # 加密貨幣抗震係數
            else:
                has_ma240 = not np.isnan(ma240_last)
                defense_base = ma240_last if has_ma240 else ma60_last
                atr_multiplier = 2.5 # 股市標準係數
            
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
            vol_momentum_ratio = 1.0
            if len(df) > 5:
                ma5 = df['close'].rolling(5).mean().iloc[-1]
                vol_ma5 = df['volume'].rolling(5).mean().iloc[-1]
                has_momentum = (last_price > ma5) and (df['volume'].iloc[-1] > vol_ma5 * 1.2)
                
                # 加密貨幣專屬：24小時成交量動能 (與 5 日均量比較)
                if market_type == 'CRYPTO':
                    vol_momentum_ratio = df['volume'].iloc[-1] / vol_ma5 if vol_ma5 > 0 else 1.0
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
            
            # --- [優化] 加密貨幣流動性懲罰：量縮則分數打折 (避免偽金叉) ---
            if market_type == 'CRYPTO' and vol_momentum_ratio < 0.8:
                final_score *= 0.7 # 量縮懲罰
            
            # 決定顯示在表格中的操作建議 (依據目前較高權重的策略得分)
            weighted_value_score = defense_weight * value_score
            weighted_pullback_score = (1 - defense_weight) * pullback_score
            
            if weighted_pullback_score >= weighted_value_score:
                # 強勢追蹤策略：使用 ATR 動態停損
                stop_loss = last_price - (atr_multiplier * atr) 
                # 動態風報比：極強動能(成交量爆發)給予 1:4 目標，否則 1:3
                rr_ratio = 4.0 if (market_type == 'CRYPTO' and vol_momentum_ratio > 2.0) else 3.0
                target = last_price + (last_price - stop_loss) * rr_ratio
                actionable_str = f"📈強勢 | 買:{growth_buy_zone:.1f} | 標:{target:.1f} | 損:{stop_loss:.1f} | 評分：{final_score:.1f}"
            else:
                # 價值防禦策略：採穩健 1:2 或固定 20% 目標
                target = defense_base * 1.2 if not np.isnan(defense_base) else value_buy_zone * 1.2
                stop_loss = year_low * 0.95
                m_tag = "⚡" if has_momentum else "" # 動能標記
                actionable_str = f"🛡價值{m_tag} | 買:{value_buy_zone:.1f} | 標:{target:.1f} | 損:{stop_loss:.1f} | 評分：{final_score:.1f}"

            # 如果營收衰退，則排到最下面 (分數砍半)
            if not is_rev_ok:
                final_score *= 0.1
            
            # 構建顯示用乖離標籤
            if market_type == 'CRYPTO':
                defense_label = f"{dist_to_defense*100:.1f}%(100日)"
            else:
                defense_label = f"{dist_to_defense*100:.1f}%" if has_ma240 else f"{dist_to_defense*100:.1f}%(季)"
            
            # 資料時間格式化 (僅顯示月-日)
            last_ts = df['ts'].iloc[-1].strftime('%m-%d')

            data_list.append({
                "代碼": code,
                "名稱": stock_name,
                "最新價格": last_price,
                "操作建議": actionable_str,
                "一年位階": f"{level_percentile*100:.1f}%",
                "年線乖離": defense_label,
                "MA20乖離": f"{dist_to_ma20*100:.1f}%",
                "MACD狀態": macd_status,
                "綜合評分": final_score,
                # 隱藏欄位：供即時重新計分使用 (不顯示在 UI)
                "_v_score": value_score,
                "_p_score": pullback_score,
                "_is_rev_ok": bool(is_rev_ok),
                "_v_buy": value_buy_zone,
                "_g_buy": growth_buy_zone,
                "_ma_base": defense_base,
                "_market_type": market_type,
                "_atr_mult": atr_multiplier,
                "_y_low": year_low,
                "_atr": atr,
                "_has_momentum": has_momentum,
                "_vol_ratio": vol_momentum_ratio,
                "_macd_status": macd_status,
                "_ma20": ma20_last,
                "_data_ts": last_ts,
                "_y_level_pct": level_percentile,
                "_defense_bias": dist_to_defense,
                "_ma20_bias": dist_to_ma20,
                "_defense_weight": defense_weight
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
    """Re-calculating scores without re-fetching data (using pre-analyzed data in DataFrame)."""
    if results_df.empty: return results_df
    
    # --- [修正] 結構檢查：防止快取版本不相容導致 KeyError ---
    required_cols = [
        '_v_score', '_p_score', '_is_rev_ok', '_g_buy', '_v_buy', '_ma_base', '_y_low',
        '_y_level_pct', '_defense_bias', '_ma20_bias', '_defense_weight'
    ]
    if not all(col in results_df.columns for col in required_cols):
        # 如果欄位不齊，可能是舊版快取。不報錯，直接回傳原始資料，並提示重新掃描。
        print("[Notice] Old cache detected in rescore_results, skipping vector update.")
        return results_df
    
    # 複製一份避免警告
    df = results_df.copy()
    
    # 使用向量運算重新計算綜合評分
    df['綜合評分'] = (defense_weight * df['_v_score']) + ((1 - defense_weight) * df['_p_score'])
    
    # 營收衰退懲罰 (確保使用比較運算而非位元反轉，以防 pandas 將布林自動轉為浮點數)
    df.loc[df['_is_rev_ok'] == False, '綜合評分'] *= 0.1
    
    # 重新產生操作建議文字
    def build_action(row):
        v_w = defense_weight * row['_v_score']
        p_w = (1 - defense_weight) * row['_p_score']
        score = row['綜合評分']
        
        # 取得指標
        atr = row.get('_atr', row['最新價格'] * 0.03)
        atr_mult = row.get('_atr_mult', 2.5) # 預設股市倍率
        has_momentum = row.get('_has_momentum', False)
        vol_ratio = row.get('_vol_ratio', 1.0)
        m_type = row.get('_market_type', 'TW')
        
        if p_w >= v_w:
            # 強勢追蹤逻辑 (ATR 停損)
            stop_loss = row['最新價格'] - (atr_mult * atr)
            # 動態風報比
            rr_ratio = 4.0 if (m_type == 'CRYPTO' and vol_ratio > 2.0) else 3.0
            target = row['最新價格'] + (row['最新價格'] - stop_loss) * rr_ratio
            return f"📈強勢 | 買:{row['_g_buy']:.1f} | 標:{target:.1f} | 損:{stop_loss:.1f} | 評分：{score:.1f}"
        else:
            # 價值防禦逻辑
            target = row['_ma_base'] * 1.2
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

# --- [NEW] 下單對話框 ---
@st.dialog("📝 下單確認 (模擬預覽)")
def show_order_dialog(row, user_id, api, max_api, ca_active):
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
        st.metric("建議買價", f"{buy_price:.2f}")
        
    # 判斷是否為虛擬貨幣或美股
    is_crypto = "-USD" in str(row['代碼'])
    is_us = ".TW" not in str(row['代碼']) and not is_crypto
    
    with col2:
        if is_crypto:
            qty = st.number_input("委託數量 (顆)", min_value=0.0001, value=0.1, step=0.01, format="%.4f")
        else:
            qty = st.number_input("委託股數", min_value=1, value=1000, step=100)
        
    # --- [NEW] MAX 市場智慧識別 ---
    max_market_id = None
    if max_api:
        # 取得 MAX 所有市場清單 (使用會話級快取避免頻繁請求)
        if "max_markets" not in st.session_state:
            try:
                # 如果是因為快取問題導致找不到屬性，這裡做最後一次嘗試
                if hasattr(max_api, "get_markets"):
                    st.session_state.max_markets = max_api.get_markets()
                else:
                    # 嘗試手動從模組獲取並注入 (極端手段)
                    from max_api import MaxExchangeAPI as SafeAPI
                    temp_api = SafeAPI(os.getenv("MAX_API_KEY"), os.getenv("MAX_API_SECRET"))
                    st.session_state.max_markets = temp_api.get_markets()
            except Exception as e:
                print(f"Error fetching MAX markets: {e}")
                st.session_state.max_markets = []
        
        # 轉換邏輯：MATIC -> POL, BTC-USD -> btctwd
        raw_symbol = str(row['代碼']).split('-')[0].lower()
        # 內建更名表
        rename_map = {"matic": "pol", "fb": "meta", "goog": "googl"}
        base_coin = rename_map.get(raw_symbol, raw_symbol)
        
        # 優先找 TWD 交易對，再找 USDT
        available_ids = [m['id'] for m in st.session_state.get('max_markets', [])]
        if f"{base_coin}twd" in available_ids:
            max_market_id = f"{base_coin}twd"
        elif f"{base_coin}usdt" in available_ids:
            max_market_id = f"{base_coin}usdt"
        
    total_amount = buy_price * qty
    st.success(f"💡 預估委託金額: **{total_amount:,.2f}** 元")
    
    # --- [NEW] 餘額檢查 ---
    insufficient_funds = False
    if max_api and is_crypto:
        max_bal = st.session_state.get('max_balance', {})
        twd_avail = float(max_bal.get('twd', {}).get('balance', 0))
        if total_amount > twd_avail:
            st.error(f"⚠️ 餘額不足！可用: **{twd_avail:,.2f}** TWD (缺: {total_amount - twd_avail:,.2f})")
            insufficient_funds = True
    
    st.divider()
    c1, c2 = st.columns(2)
    # 按鈕 1: 模擬下單 (永遠可用)
    if c1.button("🧪 執行模擬下單", use_container_width=True):
        # 使用詳細理由產生器
        reason = build_buy_reason(row)
        # 手動下單強制 is_system=False, 並記錄 股數 與 類型
        if record_trade(user_id, "Manual", row['代碼'], row['名稱'], buy_price, reason, is_system=False, trade_type="Simulated", shares=qty):
            st.toast(f"🚀 已錄入 {row['代碼']} 個人模擬委託 ({qty} 股)！", icon="✅")
            st.session_state.last_order = f"{get_now().strftime('%H:%M:%S')} - 已模擬買入 {row['代碼']}"
            st.rerun()
        else:
            st.warning(f"⚠️ 您已經持有 {row['代碼']} 的個人未平倉位。")
        
    # 按鈕 2: 實盤下單
    is_crypto = "-USD" in str(row['代碼'])
    
    if is_crypto:
        # 針對加密貨幣透過 MAX API 下單
        if max_api:
            btn_label = f"💰 MAX 實盤下單 ({max_market_id.upper()})" if max_market_id else "❌ MAX 不支援此幣"
            if c2.button(btn_label, use_container_width=True, type="primary", disabled=(not max_market_id or insufficient_funds)):
                try:
                    # 呼叫 MAX API 送出限價單
                    trade = max_api.place_order(
                        market=max_market_id,
                        side="buy",
                        volume=qty,
                        price=buy_price,
                        ord_type="limit"
                    )
                    
                    if 'error' in trade:
                        st.error(f"❌ MAX 下單失敗: {trade['error']}")
                    else:
                        # [NEW] 成功後也記錄在「個人紀錄」中作為持倉追蹤 (類型為 Real)
                        reason = f"MAX 實盤買入 ({trade.get('id', 'N/A')})"
                        record_trade(user_id, "Manual", row['代碼'], row['名稱'], buy_price, reason, is_system=False, trade_type="Real", shares=qty)
                        
                        st.session_state.last_order = f"{get_now().strftime('%H:%M:%S')} - MAX 已送出 {max_market_id.upper()} {qty}顆 (限價:{buy_price})"
                        st.toast(f"✅ MAX 委託已送出 ({max_market_id.upper()})！已加入持倉紀錄。", icon="🚀")
                        st.rerun()
                except Exception as e:
                    st.error(f"❌ MAX 系統異常: {e}")
        else:
            c2.info("🔴 MAX API 未設定")
    else:
        # 針對一般股票透過 Shioaji 永豐金 API 下單
        if ca_active:
            if c2.button("💰 API 實盤下單", use_container_width=True, type="primary"):
                try:
                    trade = sinopac_api.place_sinopac_order(api, row['代碼'], qty, buy_price)
                    
                    # [NEW] 成功後也記錄在「個人紀錄」中作為持倉追蹤 (類型為 Real)
                    reason = f"永豐金實盤買入 (委託號: {trade.order.id})"
                    record_trade(user_id, "Manual", row['代碼'], row['名稱'], buy_price, reason, is_system=False, trade_type="Real", shares=qty)
                    
                    st.session_state.last_order = f"{get_now().strftime('%H:%M:%S')} - 永豐金已送出 {row['代碼']} {qty}股 (限價:{buy_price})"
                    st.toast("✅ 永豐金委託已送出！已加入持倉紀錄。", icon="🚀")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ 下單失敗: {e}")
                    st.error(f"❌ API 下單失敗: {e}")
        else:
            c2.link_button("🌐 官網開啟下單", 
                         "https://www.sinotrade.com.tw/newweb/goOrder/?nav=0", 
                         use_container_width=True,
                         help="憑證未啟動，請手動至官網下單")

    # --- [NEW] 在對話框內顯示 K 線與 MACD 指標 ---
    st.divider()
    st.markdown(f"#### 📊 {row['代碼']} {row['名稱']} 技術圖表")
    cache_file = os.path.join(CACHE_DIR, f"{row['代碼']}_y.csv")
    if os.path.exists(cache_file):
        df_selected = pd.read_csv(cache_file)
        df_selected['ts'] = pd.to_datetime(df_selected['ts'], utc=True, errors='coerce')
        
        # --- 補齊圖表所需的技術指標 ---
        df_selected['ma20'] = df_selected['close'].rolling(window=20).mean()
        df_selected['ma60'] = df_selected['close'].rolling(window=60).mean()
        df_selected['ma240'] = df_selected['close'].rolling(window=240).mean()
        
        exp1 = df_selected['close'].ewm(span=12, adjust=False).mean()
        exp2 = df_selected['close'].ewm(span=26, adjust=False).mean()
        df_selected['macd'] = exp1 - exp2
        df_selected['signal'] = df_selected['macd'].ewm(span=9, adjust=False).mean()
        df_selected['hist'] = df_selected['macd'] - df_selected['signal']

        plot_financial_charts(df_selected, row['代碼'])
    else:
        st.warning(f"⚠️ 找不到 {row['代碼']} 的快取資料。")

# --- 自動化掃描與顯示 ---
# 如果正在顯示建議清單，可以選擇先不自動掃描，避免干擾使用者操作
current_watchlist_key = ",".join(watchlist)
should_sync = False

# --- 每日定時自動任務 (多市場互斥排程) ---
MARKET_SCHEDULE = {
    "US": (6, 0),      # 美股 06:00
    "CRYPTO": (23, 5), # 加密貨幣 23:05
    "TW": (14, 0)      # 台股 14:00
}

if st.session_state.active_page == "market":
    now_tp = get_now()
    sys_logs = load_trading_log("system")
    
    # 初始化自動執行追蹤器 (Session 層級)
    if "auto_last_run" not in st.session_state:
        st.session_state.auto_last_run = {}

    # 如果「手動」正在執行海選，暫停自動跳轉偵測
    if not st.session_state.get("is_big_scan"):
        for m_code, (h, m) in MARKET_SCHEDULE.items():
            if now_tp.hour >= h and (now_tp.hour > h or now_tp.minute >= m):
                # 1. 檢查今日「共享快取」是否已成功生成 (代表當日任務已圓滿達成)
                cached = load_results_cache(market=m_code)
                if cached is not None:
                    continue

                # 2. 檢查 Session 是否在 30 分鐘內已嘗試過 (防止頻率限制時無限循環跳轉)
                last_attempt_time = st.session_state.auto_last_run.get(f"{m_code}_time")
                if last_attempt_time:
                    delta = (now_tp - last_attempt_time).total_seconds()
                    if delta < 1800: # 30 分鐘冷卻時間
                        continue

                # 3. 檢查資料庫今日是否已執行成功 (雙重保險)
                has_executed = False
                today_prefix = now_tp.strftime("%Y-%m-%d")
                for l in sys_logs:
                    if l['buy_time'].startswith(today_prefix):
                        sym = l['symbol']
                        l_m = "TW"
                        if "-USD" in sym: l_m = "CRYPTO"
                        elif sym[0].isalpha() and "." not in sym: l_m = "US"
                        if l_m == m_code:
                            has_executed = True
                            break
                
                if not has_executed:
                    # 標記本次嘗試時間
                    st.session_state.auto_last_run[f"{m_code}_time"] = now_tp
                    
                    st.session_state.trigger_daily_scan = True
                    st.session_state.scan_market = m_code
                    st.session_state.is_big_scan = True
                    m_label = {"TW": "台股", "US": "美股", "CRYPTO": "加密貨幣"}.get(m_code, "未知")
                    st.info(f"⏰ 偵測到 {m_label} 開盤時間，正在為您自動執行本日官方海選...")
                    st.rerun()
                    break

# --- 啟動時優先從磁碟載入快取 (行動端穩定性關鍵) ---
# 使用具備回退機制的 user_id，確保隨時獲得隔離的快取
if "results" not in st.session_state:
    cache_data = load_results_cache(user_id=user_id)
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
            # 或者是有自動觸發標記
            if st.session_state.get("trigger_daily_scan"):
                should_sync = True
                # 注意：不要在這裡歸零旗標，保留給下方的掃描邏輯判斷市場使用

elif st.session_state.get("last_watchlist") != current_watchlist_key:
    # 只有當追蹤清單「內容改變」時，才自動觸發同步
    should_sync = True

# 移除原本位置的掃描按鈕 (已移至側邊欄最上方)
# scan_btn = st.sidebar.button("🚀 重新掃描目前清單", ...)
# big_scan_btn = st.button("🔍 執行「全市場」大選股", ...)

# --- 掃描執行邏輯 ---
is_trigger_daily = st.session_state.get("trigger_daily_scan", False)

if (big_scan_tw_btn or big_scan_us_btn or big_scan_crypto_btn or scan_btn or should_sync or 
    st.session_state.get("force_rescan") or is_trigger_daily):
    
    # 1. 決定市場與名單
    if big_scan_tw_btn or big_scan_us_btn or big_scan_crypto_btn or is_trigger_daily:
        # 決定市場類型：優先看按鈕，再看 Session State 紀錄
        m_type = st.session_state.get("scan_market") or "TW" 
        if big_scan_tw_btn: m_type = 'TW'
        elif big_scan_us_btn: m_type = 'US'
        elif big_scan_crypto_btn: m_type = 'CRYPTO'
        
        # 執行到此才正式歸零每日觸發旗標
        st.session_state.trigger_daily_scan = False
        
        m_label = {"TW": "台灣", "US": "美國", "CRYPTO": "加密貨幣"}.get(m_type, "未知")
        st.session_state.is_big_scan = True
        st.session_state.scan_market = m_type
        scan_list = get_mass_scan_list(api, market=m_type)
        toast_msg = f"🚀 開始 {m_label} 大平原掃描 (共 {len(scan_list)} 檔)..."
        # [重要] 開始新掃描前清除舊結果，防止 UI 顯示錯誤市場的數據
        st.session_state.results = pd.DataFrame()
    else:
        st.session_state.is_big_scan = False
        st.session_state.scan_market = None
        scan_list = watchlist
        toast_msg = "🔍 啟動市場掃描..."

    # 2. 執行分析
    st.toast(toast_msg, icon="🚀")
    with st.spinner('🔄 市場數據分析同步中...'):
        st.session_state.last_watchlist = current_watchlist_key
        
        # --- [NEW] 共享快取優先機制 ---
        results = pd.DataFrame()
        cached_data = None
        
        # 如果是全市場大選股，且不是強制刷新，先試著讀取今日共享快取
        if st.session_state.is_big_scan and not st.session_state.get("force_rescan"):
            cached_data = load_results_cache(user_id=user_id, market=st.session_state.scan_market)
            if cached_data:
                cache_day = cached_data['timestamp'].split(' ')[0]
                if cache_day == get_now().strftime("%Y-%m-%d"):
                    results = cached_data['df']
                    st.toast("💾 已偵測到今日海選紀錄，直接載入共享數據", icon="📥")

        # 若無快取或強制刷新，才執行 Yahoo Finance 分析
        if results.empty:
            st.session_state.force_rescan = False
            results = fetch_and_analyze(scan_list, defense_weight=st.session_state.defense_weight, market_type=st.session_state.scan_market)
        
        if not results.empty:
            st.session_state.results = results
            st.session_state.last_update = get_now().strftime("%H:%M:%S")
            st.session_state.current_page = 0 # 重設頁碼
            
            # --- [智慧快取保護] ---
            # 只有當掃描成功數量達到一定門檻 (例如 30%)，才更新共享快取
            # 這是為了避免「快取了失敗的掃描結果」導致整天所有人看到的都是空資料
            success_count = len(results)
            target_count = len(scan_list)
            success_rate = (success_count / target_count) if target_count > 0 else 0
            
            # 對於名單較少的掃描 (watchlist)，隨時存檔；對於「全市場大選股」，則需要 30% 門檻
            do_shared_save = True
            if st.session_state.is_big_scan and success_rate < 0.3:
                do_shared_save = False
                st.sidebar.warning(f"⚠️ 今日海選成功率過低 ({success_rate:.1%})，不更新共享快取以保護數據品質。")

            # 存入磁碟快取
            # 如果不符合共享門檻，我們傳入 is_big_scan=False 以防 save_results_cache 刷新共享檔
            save_results_cache(
                results, 
                is_big_scan=(st.session_state.is_big_scan and do_shared_save), 
                market=st.session_state.scan_market, 
                user_id=user_id
            )
            st.toast("✅ 數據同步完成！", icon="📉")
            
            # --- 🧪 模擬交易：自動跟單 (第一類：系統每日海選) ---
            # [優化] 只在系統定時觸發 (06:05) 時執行自動買入，手動大選股不跟進
            if is_trigger_daily:
                top_stock = results.iloc[0]
                m_type = st.session_state.scan_market or "TW"
                # 使用強化後的買入理由
                reason = build_buy_reason(top_stock)
                if record_trade("shared_sys", "Auto", top_stock['代碼'], top_stock['名稱'], top_stock['最新價格'], reason, is_system=True):
                    st.toast(f"🤖 系統本日官方推薦：{top_stock['代碼']}", icon="📥")
            
            # --- 🧪 模擬交易：檢查退場機制 (同時檢查系統與個人位階) ---
            current_prices = dict(zip(results['代碼'], results['最新價格']))
            check_and_exit_trades(user_id, current_prices)
        else:
            if st.session_state.is_big_scan:
                st.error("❌ 全市場掃描未成功取得數據。")
            else:
                st.warning("⚠️ 掃描完成，但在現有清單中找不到可分析的有效數據。")

# --- 頁面路由切換 ---
if st.session_state.active_page == "simulation":
    display_simulation_dashboard(user_id)
    st.stop()

if st.session_state.active_page == "settings":
    st.markdown("## 🔒 交易憑證設定")
    st.caption("每位使用者可獨立設定自己的 API 金鑰，資料以加密方式儲存於伺服器。未設定者僅能使用 Yahoo Finance 數據。")
    
    # --- 連線狀態 ---
    sc1, sc2 = st.columns(2)
    if api and not is_mock:
        sc1.success("🏦 永豐金：✅ 已連線")
    elif sj_key:
        err = st.session_state.get("sj_error", "原因未知")
        sc1.warning(f"🏦 永豐金：⚠️ 連線失敗 ({err})")
    else:
        sc1.info("🏦 永豐金：⚪ 待設定")
    
    if max_api:
        sc2.success(f"🪙 MAX：✅ 已連線{v_tag}")
    elif max_key:
        sc2.warning("🪙 MAX：⚠️ 金鑰已設定但連線失敗")
    else:
        sc2.info("🪙 MAX：⚪ 待設定")
    
    st.divider()
    
    # --- 永豐金 Sinopac API ---
    st.markdown("### 🏦 永豐金 Shioaji API")
    st.caption("前往 [Shioaji 官網](https://www.sinotrade.com.tw/openapi) 申請 API 金鑰")
    s_c1, s_c2 = st.columns(2)
    inp_sj_key = s_c1.text_input("API Key", value=user_creds.get("sj_api_key", ""), type="password", key="inp_sj_key")
    inp_sj_secret = s_c2.text_input("Secret Key", value=user_creds.get("sj_secret_key", ""), type="password", key="inp_sj_secret")
    
    s_c3, s_c4 = st.columns(2)
    inp_person_id = s_c3.text_input("身分證字號", value=user_creds.get("person_id", ""), key="inp_person_id",
                                     help="啟動憑證所需 (實盤下單)")
    inp_ca_passwd = s_c4.text_input("憑證密碼", value=user_creds.get("ca_passwd", ""), type="password", key="inp_ca_passwd",
                                     help="Sinopac.pfx 的保護密碼")
    uploaded_pfx = st.file_uploader("上傳憑證 (.pfx)", type=["pfx"], key="inp_pfx", help="實盤下單所需的電子憑證")
    if uploaded_pfx is not None:
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pfx") as tmp_file:
            tmp_file.write(uploaded_pfx.getbuffer())
        st.success("✅ 已上傳憑證檔案")
    
    st.divider()
    
    # --- MAX Exchange API ---
    st.markdown("### 🪙 MAX 交易所 API")
    st.caption("前往 [MAX 交易所](https://max.maicoin.com/) 申請 API 金鑰")
    m_c1, m_c2 = st.columns(2)
    inp_max_key = m_c1.text_input("API Key", value=user_creds.get("max_api_key", ""), type="password", key="inp_max_key")
    inp_max_secret = m_c2.text_input("API Secret", value=user_creds.get("max_api_secret", ""), type="password", key="inp_max_secret")
    
    st.divider()
    
    # --- 儲存按鈕 ---
    bc1, bc2 = st.columns(2)
    if bc1.button("💾 儲存設定", use_container_width=True, type="primary"):
        new_creds = {
            "sj_api_key": inp_sj_key.strip(),
            "sj_secret_key": inp_sj_secret.strip(),
            "max_api_key": inp_max_key.strip(),
            "max_api_secret": inp_max_secret.strip(),
            "person_id": inp_person_id.strip(),
            "ca_passwd": inp_ca_passwd.strip()
        }
        
        # 處理憑證檔案 (轉為 Base64 存入)
        if uploaded_pfx is not None:
            try:
                pfx_bytes = uploaded_pfx.getvalue()
                pfx_base64 = base64.b64encode(pfx_bytes).decode('utf-8')
                new_creds["ca_pfx_b64"] = pfx_base64
            except Exception as e:
                st.error(f"憑證處理失敗: {e}")
        elif user_creds.get("ca_pfx_b64"):
            new_creds["ca_pfx_b64"] = user_creds["ca_pfx_b64"]

        # [重要] 保持密碼 Hash 存在，避免下次登入被視為新使用者
        if "pwd_hash" in user_creds:
            new_creds["pwd_hash"] = user_creds["pwd_hash"]

        # 存到伺服器端 JSON 檔案
        save_user_creds(user_id, new_creds)
        
        # 更新 session_state
        st.session_state.user_creds = new_creds
        st.session_state.browser_state_loaded = True
        
        st.success("✅ 設定已儲存！系統自動更新中...")
        st.rerun()
    
    if bc2.button("🏠 返回", use_container_width=True):
        st.session_state.active_page = "market"
        st.rerun()

    # --- 🛠️ 診斷資訊 ---
    with st.expander("🛠️ 除錯與診斷資訊"):
        st.write(f"**目前識別碼 (UID):** `{user_id}`")
        creds_path = os.path.join("cache", f"creds_{user_id}.json")
        st.write(f"**伺服器端憑證檔案:** `{creds_path}` {'✅ 存在' if os.path.exists(creds_path) else '⚪ 尚未建立'}")
        st.write(f"**已載入金鑰數:** {sum(1 for k in ['sj_api_key','sj_secret_key','max_api_key','max_api_secret'] if user_creds.get(k))}")
        
        if st.button("🔄 強制重新讀取"):
            st.session_state.browser_state_loaded = False
            st.rerun()
            
        st.info("💡 設定資料儲存在伺服器端。UID 以 LocalStorage 持久化，若瀏覽器封鎖 LocalStorage，每次開新分頁會產生新 UID。")

    st.stop()

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

    # 2. 自動補完名稱 (增加 empty 檢查預防 KeyError)
    if not results.empty and (results['名稱'] == '未知').any():
        code_map = get_stock_name_map(api)
        if code_map:
            results['名稱'] = results.apply(
                lambda row: code_map.get(row['代碼'], row['名稱']) if row['名稱'] == '未知' else row['名稱'], 
                axis=1
            )
            st.session_state.results = results

    # 顯示首選
    if not results.empty:
        top_pick = results.iloc[0]
        st.success(f"🛡️ 今日最值得佈局：**{top_pick['代碼']} {top_pick['名稱']}** ({top_pick['操作建議']})")
    else:
        st.warning("⚠️ 目前清單中尚無有效的分析結果，請點擊「🚀 目前追蹤清單」。")
    

    # --- 自定義列表 ---
    is_big = st.session_state.get("is_big_scan", False)
    scan_market = st.session_state.get("scan_market", "TW")
    market_label = {"TW": "台灣", "US": "美國", "CRYPTO": "加密貨幣"}.get(scan_market, "未知")
    list_title = f"🏆 {market_label}全市場大選股排行榜" if is_big else "📊 目前追蹤清單"
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
    
    # 1. 顯示表頭 (僅在電腦版顯示)
    header_label = "100日乖離" if st.session_state.get("scan_market") == "CRYPTO" else "年線乖離"
    header_html = '<div class="desktop-only"><div style="display: flex; border: 1px solid #444; border-radius: 8px; padding: 10px; background: #262730; margin-bottom: 10px; font-weight: bold; align-items: center; font-size: 0.85rem;">'
    header_html += '<div style="flex: 1.5;">股票</div><div style="flex: 0.6;">時間</div><div style="flex: 0.8;">最新價</div><div style="flex: 0.8;">位階</div>'
    header_html += '<div style="flex: 0.8;">' + header_label + '</div><div style="flex: 0.8;">MA20乖離</div><div style="flex: 0.8;">MA20價</div>'
    header_html += '<div style="flex: 0.8;">ATR停損</div><div style="flex: 3.5;">操作建議</div><div style="flex: 0.5;"></div></div></div>'
    st.markdown(header_html, unsafe_allow_html=True)
    
    # 2. 顯示內容 (每一家股票一個穩定容器，手機自動轉卡片)
    is_mob = is_mobile_device()
    for index, row in paged_results.iterrows():
        with st.container(border=True):
            if is_mob:
                # --- [MOBILE VIEW] 卡片式佈局 ---
                icon = "🪙" if "-USD" in str(row['代碼']) else "🛒"
                
                # 頂部：股票名稱按鈕 (全寬)
                if st.button(f"{icon} {row['代碼']} {row['名稱']}", key=f"t_{row['代碼']}_{index}", use_container_width=True):
                    show_order_dialog(row, user_id, api, max_api, ca_active)
                
                # 中間：數據指標 (inline label：value)
                price_val = f"{row['最新價格']:.1f}" if row['最新價格'] != 0 else "-"
                ma20_raw = row.get('_ma20', 0)
                ma20_val = f"{ma20_raw:.1f}" if not pd.isna(ma20_raw) else "-"
                atr_mult_val = row.get('_atr_mult', 2.5)
                atr_stop_raw = row['最新價格'] - (atr_mult_val * row.get('_atr', 0))
                atr_stop = f"{atr_stop_raw:.1f}" if not pd.isna(atr_stop_raw) else "-"
                
                gc1, gc2, gc3 = st.columns(3)
                gc1.markdown(f'<span style="color:#888;font-size:0.75rem;">最新價：</span><b>{price_val}</b>', unsafe_allow_html=True)
                gc2.markdown(f'<span style="color:#888;font-size:0.75rem;">一年位階：</span>{row["一年位階"]}', unsafe_allow_html=True)
                gc3.markdown(f'<span style="color:#888;font-size:0.75rem;">{header_label}：</span>{row["年線乖離"]}', unsafe_allow_html=True)
                
                gc4, gc5, gc6 = st.columns(3)
                gc4.markdown(f'<span style="color:#888;font-size:0.75rem;">MA20乖離：</span>{row["MA20乖離"]}', unsafe_allow_html=True)
                gc5.markdown(f'<span style="color:#888;font-size:0.75rem;">MA20價：</span>{ma20_val}', unsafe_allow_html=True)
                gc6.markdown(f'<span style="color:#888;font-size:0.75rem;">ATR停損：</span>{atr_stop}', unsafe_allow_html=True)
                
                # 底部：操作建議 + 動作按鈕
                bc1, bc2 = st.columns([4, 1])
                bc1.markdown(f"**`{row['操作建議']}`**")
                
                is_big_scan = st.session_state.get("is_big_scan", False)
                current_watchlist = st.session_state.get("watchlist", [])
                action_icon = "➕" if is_big_scan else ("🗑️" if row['代碼'] in current_watchlist else "➕")
                
                if bc2.button(action_icon, key=f"btn_{row['代碼']}_{index}", use_container_width=True):
                    if is_big_scan:
                        if row['代碼'] not in st.session_state.watchlist:
                            st.session_state.watchlist.append(row['代碼'])
                            st.toast(f"✅ 已加入追蹤清單 {row['代碼']} {row['名稱']}")
                            save_watchlist(st.session_state.watchlist, user_id)
                        else:
                            st.toast(f"ℹ️ {row['代碼']} 已在清單中")
                    else:
                        if row['代碼'] in st.session_state.watchlist:
                            st.session_state.watchlist.remove(row['代碼'])
                            st.toast(f"🗑️ 已從清單移除 {row['代碼']}")
                            if "results" in st.session_state:
                                st.session_state.results = st.session_state.results[st.session_state.results['代碼'] != row['代碼']]
                                save_results_cache(st.session_state.results, is_big_scan=False, market=None, user_id=user_id)
                        else:
                            st.session_state.watchlist.append(row['代碼'])
                            st.toast(f"➕ 已加入追蹤清單 {row['代碼']}")
                            if "results" in st.session_state:
                                del st.session_state.results
                        save_watchlist(st.session_state.watchlist, user_id)
                        st.rerun()
            else:
                # --- [DESKTOP VIEW] 10欄標準佈局 ---
                cols = st.columns([1.5, 0.6, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 3.5, 0.5])
                
                # 欄位一：股票名稱 (轉為按鈕連結)
                icon = "🪙" if "-USD" in str(row['代碼']) else "🛒"
                if cols[0].button(f"{icon} {row['代碼']} {row['名稱']}", key=f"t_{row['代碼']}_{index}", use_container_width=True):
                    show_order_dialog(row, user_id, api, max_api, ca_active)
                
                # 欄位二：資料時間
                data_ts = row.get('_data_ts', '-')
                cols[1].markdown(f'<span class="mobile-label">資料時間:</span><span style="font-size:0.8rem; color:#888;">{data_ts}</span>', unsafe_allow_html=True)

                # 欄位三：最新價
                price_val = f"{row['最新價格']:.1f}" if row['最新價格'] != 0 else "-"
                cols[2].markdown(f'<span class="mobile-label">最新價:</span><b>{price_val}</b>', unsafe_allow_html=True)
                
                # 欄位四～六：指標
                cols[3].markdown(f'<span class="mobile-label">一年位階:</span>{row["一年位階"]}', unsafe_allow_html=True)
                cols[4].markdown(f'<span class="mobile-label">{header_label}:</span>{row["年線乖離"]}', unsafe_allow_html=True)
                cols[5].markdown(f'<span class="mobile-label">MA20乖離:</span>{row["MA20乖離"]}', unsafe_allow_html=True)
                
                # 欄位七～八：MA20 價 與 ATR 停損
                ma20_raw = row.get('_ma20', 0)
                ma20_val = f"{ma20_raw:.1f}" if not pd.isna(ma20_raw) else "-"
                atr_mult_curr = row.get('_atr_mult', 2.5)
                atr_stop_raw = row['最新價格'] - (atr_mult_curr * row.get('_atr', 0))
                atr_stop = f"{atr_stop_raw:.1f}" if not pd.isna(atr_stop_raw) else "-"
                cols[6].markdown(f'<span class="mobile-label">MA20價:</span>{ma20_val}', unsafe_allow_html=True)
                cols[7].markdown(f'<span class="mobile-label">ATR停損:</span>{atr_stop}', unsafe_allow_html=True)
                
                # 欄位九：操作建議
                cols[8].markdown(f"**`{row['操作建議']}`**")
                
                # 欄位十：動作按鈕
                is_big_scan = st.session_state.get("is_big_scan", False)
                action_icon = "➕" if is_big_scan else ("🗑️" if row['代碼'] in st.session_state.watchlist else "➕")

                if cols[9].button(action_icon, key=f"btn_{row['代碼']}_{index}", use_container_width=True):
                    if is_big_scan:
                        if row['代碼'] not in st.session_state.watchlist:
                            st.session_state.watchlist.append(row['代碼'])
                            st.toast(f"✅ 已加入追蹤清單 {row['代碼']} {row['名稱']}")
                            save_watchlist(st.session_state.watchlist, user_id)
                        else:
                            st.toast(f"ℹ️ {row['代碼']} 已在清單中")
                    else:
                        if row['代碼'] in st.session_state.watchlist:
                            st.session_state.watchlist.remove(row['代碼'])
                            st.toast(f"🗑️ 已從清單移除 {row['代碼']}")
                            if "results" in st.session_state:
                                st.session_state.results = st.session_state.results[st.session_state.results['代碼'] != row['代碼']]
                                save_results_cache(st.session_state.results, is_big_scan=False, market=None, user_id=user_id)
                        else:
                            st.session_state.watchlist.append(row['代碼'])
                            st.toast(f"➕ 已加入追蹤清單 {row['代碼']}")
                            if "results" in st.session_state:
                                del st.session_state.results
                        save_watchlist(st.session_state.watchlist, user_id)
                        st.rerun()

    # --- 分頁導航 ---
    if total_pages > 1:
        st.divider()
        # 使用 DOM 標記讓 JS 強制水平排列 (僅手機版生效)
        st.markdown('<div id="pg-marker"></div>', unsafe_allow_html=True)
        
        is_mob = is_mobile_device()
        p_cols = st.columns([1, 1, 1] if is_mob else [2, 6, 2])
        
        prev_label = "◀ 上一頁"
        next_label = "下一頁 ▶"
        
        if p_cols[0].button(prev_label, key="pg_prev", use_container_width=True):
            st.session_state.current_page -= 1
            st.rerun()
            
        p_cols[1].markdown(f"<div style='text-align:center; padding-top:10px;'>{st.session_state.current_page + 1} / {total_pages}</div>", unsafe_allow_html=True)
        
        if p_cols[2].button(next_label, key="pg_next", use_container_width=True):
            st.session_state.current_page += 1
            st.rerun()
    
    st.divider()
    
    # 互動式圖表已移至「下單確認」對話框內，此處保持簡潔
    pass
else:
    st.info("🔄 正在初始化市場數據，或請點擊左側「🚀 目前追蹤清單」。")