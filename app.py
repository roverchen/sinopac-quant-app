import streamlit as st
import os
import time
import base64
import json
from dotenv import load_dotenv

# 載入環境變數 (如 MAX API Keys)
load_dotenv()


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

# 導入外掛 API
try:
    from max_api import MaxExchangeAPI
except ImportError:
    MaxExchangeAPI = None

# --- 🎯 設備檢測與識別碼工具 ---
import uuid
try:
    from streamlit.runtime.scriptrunner import get_script_run_ctx
except ImportError:
    get_script_run_ctx = None

def get_session_uid():
    """取得當前 Session 的識別碼，優先選用穩定且唯一的 session_id"""
    try:
        if get_script_run_ctx:
            ctx = get_script_run_ctx()
            if ctx:
                return f"s_{ctx.session_id[:8]}"
    except:
        pass
    
    # 回退到網址參數 (如果有的話)
    u = st.query_params.get("u")
    if u:
        return u
    return "shared"

def is_mobile_device():
    """透過 User-Agent 簡易判斷是否為行動裝置"""
    try:
        # 使用最新的 st.context.headers (取代已棄用的 _get_websocket_headers)
        ua = st.context.headers.get("User-Agent", "").lower()
        return any(m in ua for m in ["mobile", "android", "iphone", "ipad"])
    except:
        return False

# --- 常數設定 ---
WATCHLIST_FILE = "watchlist.json"
CACHE_DIR = "cache"
# RESULTS_CACHE_FILE is now dynamic per user
NAME_MAP_CACHE_FILE = os.path.join(CACHE_DIR, "name_map.pkl")

if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

# --- 頁面設定 ---
st.set_page_config(page_title="金融商品市場報明牌系統", layout="wide")

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
        .mobile-label { display: none; }

        @media (max-width: 768px) {
            .desktop-only { display: none !important; }
            .mobile-only { display: block !important; }
            .mobile-label { display: inline-block !important; color: #888; font-size: 0.8rem; margin-right: 6px; width: 70px; }

            /* --- 恢復股票卡片專屬的垂直堆疊 (防止被誤傷) --- */
            [data-testid="stVerticalBlockBorderWrapper"] [data-testid="column"] {
                width: 100% !important;
                flex: 1 1 100% !important;
                min-width: 100% !important;
                margin-bottom: 2px !important;
            }
            [data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stHorizontalBlock"] {
                flex-direction: column !important;
            }

            /* --- 移除所有不穩定的 st-emotion-cache 依賴，改用穩定選擇器 --- */
            .pagination-container {
                display: flex !important;
                flex-direction: row !important;
                flex-wrap: nowrap !important;
                align-items: center !important;
                justify-content: center !important;
                gap: 10px !important;
                width: 100% !important;
                margin: 10px 0 !important;
                padding: 5px !important;
            }
            
            /* 強制讓分頁內的按鈕容器保持水平 */
            .pagination-container > div {
                flex: 1 !important;
                display: flex !important;
                justify-content: center !important;
            }

            /* 恢復卡片樣式 */
            [data-testid="stVerticalBlockBorderWrapper"] {
                border-left: 5px solid #00d4ff !important;
                background-color: #1e1e1e !important;
                border-radius: 12px !important;
                margin-bottom: 12px !important;
                padding: 10px !important;
            }
            
            .stButton button {
                font-size: 0.85rem !important;
            }
        }
</style>
""", unsafe_allow_html=True)


# 預設時區工具
st.title("📈 金融商品市場報明牌系統")

# --- 手機版側邊欄提示 ---

# --- 初始化 API ---
@st.cache_resource
def init_max_api():
    if MaxExchangeAPI:
        key = os.getenv("MAX_API_KEY")
        secret = os.getenv("MAX_API_SECRET")
        if key and secret:
            return MaxExchangeAPI(key, secret)
    return None

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
        
        # [NEW] 登入後立即抓取合約，設定較長的 Timeout (60秒) 確保穩定
        # fetch_contracts 是使用多數功能的先決條件
        try:
            api.fetch_contracts(contracts_timeout=60000)
        except Exception as ce:
            print(f"Initial contract fetch timeout/error: {ce}")
            # 即使失敗也先返回 api，後續邏輯會再嘗試
            
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
max_api = init_max_api()

# 核心連線狀態檢查 (背景邏輯)
is_mock = hasattr(api, 'list_accounts') and len(api.list_accounts()) == 0 and not hasattr(api, 'Contracts')

# 顯示 MAX 餘額
if max_api:
    bal = max_api.get_account_balance()
    if 'error' not in bal:
        twd = bal.get('twd', {}).get('balance', 0)
        btc = bal.get('btc', {}).get('balance', 0)
        eth = bal.get('eth', {}).get('balance', 0)
        st.sidebar.caption(f"💰 餘額: {twd:,.0f} TWD | {btc:.4f} BTC | {eth:.4f} ETH")
    else:
        st.sidebar.caption(f"⚠️ MAX 連線錯誤: {bal.get('error', 'Unknown')}")

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
def save_results_cache(df, is_big_scan=False, market=None, user_id="shared"):
    """將掃描結果存入磁碟，防止手機重新整理後消失"""
    try:
        data = {
            "df": df,
            "timestamp": get_now().strftime("%Y-%m-%d %H:%M:%S"),
            "is_big_scan": is_big_scan,
            "scan_market": market
        }
        cache_file = os.path.join(CACHE_DIR, f"results_cache_{user_id}.pkl")
        with open(cache_file, "wb") as f:
            pickle.dump(data, f)
    except Exception as e:
        print(f"快取存檔失敗: {e}")

def load_results_cache(user_id="shared"):
    """從磁碟載入上一次的掃描結果"""
    cache_file = os.path.join(CACHE_DIR, f"results_cache_{user_id}.pkl")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "rb") as f:
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
        "SNOW": "Snowflake", "MSTR": "MicroStrategy", "COIN": "Coinbase", "PLTR": "Palantir",
        "ABNB": "Airbnb", "LRCX": "Lam Research", "MU": "Micron", "ADI": "Analog Devices",
        "KLAC": "KLA Corp", "MELI": "MercadoLibre", "REGN": "Regeneron", "VRTX": "Vertex",
        "ADSK": "Autodesk", "NXPI": "NXP"}
    # 追加更多常用美股
    US_STOCK_ADDITIONAL = {
        "PYPL": "PayPal", "SQ": "Block", "U": "Unity", "SE": "Sea Ltd",
        "DOCU": "DocuSign", "RBLX": "Roblox", "SNAP": "Snapchat", "PINS": "Pinterest",
        "TWLO": "Twilio", "OKTA": "Okta", "ZS": "Zscaler", "NET": "Cloudflare",
        "MRVL": "Marvell", "WDAY": "Workday", "TEAM": "Atlassian", "MDB": "MongoDB",
        "FSLY": "Fastly", "NET": "Cloudflare", "SHOP": "Shopify", "SPOT": "Spotify",
        "AFRM": "Affirm", "SOFI": "SoFi", "HOOD": "Robinhood", "COIN": "Coinbase",
        "DKNG": "DraftKings", "PATH": "UiPath", "AI": "C3.ai", "SMCI": "Super Micro",
        "ARM": "Arm Holdings", "LLY": "Eli Lilly", "V": "Visa", "MA": "Mastercard",
        "JPM": "JPMorgan", "BAC": "Bank of America", "WFC": "Wells Fargo", "C": "Citigroup",
        "GS": "Goldman Sachs", "MS": "Morgan Stanley", "BRK.B": "Berkshire B", "BLK": "BlackRock",
        "XOM": "Exxon", "CVX": "Chevron", "SHEL": "Shell", "TTE": "TotalEnergies",
        "BP": "BP", "COP": "ConocoPhillips", "SLB": "Schlumberger", "HAL": "Halliburton",
        "NKE": "Nike", "SBUX": "Starbucks", "MCD": "McDonald's", "CMG": "Chipotle",
        "TJX": "TJX Companies", "LULU": "Lululemon", "TGT": "Target", "LOW": "Lowe's",
        "HD": "Home Depot", "COST": "Costco", "WMT": "Walmart", "PG": "P&G",
        "KO": "Coca-Cola", "PEP": "PepsiCo", "MDLZ": "Mondelez", "PM": "Philip Morris",
        "MO": "Altria", "CL": "Colgate", "KMB": "Kimberly-Clark", "EL": "Estee Lauder",
        "PFE": "Pfizer", "MRK": "Merck", "JNJ": "Johnson & Johnson", "ABT": "Abbott",
        "MDT": "Medtronic", "TMO": "Thermo Fisher", "DHR": "Danaher", "ISRG": "Intuitive",
        "AMT": "American Tower", "PLD": "Prologis", "CCI": "Crown Castle", "PSA": "Public Storage",
        "EQIX": "Equinix", "DLR": "Digital Realty", "SPG": "Simon Property", "WY": "Weyerhaeuser",
        "T": "AT&T", "VZ": "Verizon", "TMUS": "T-Mobile", "META": "Meta", "GOOGL": "Alphabet",
        "NFLX": "Netflix", "DIS": "Disney", "CMCSA": "Comcast", "CHTR": "Charter",
        "WBD": "Warner Bros", "PARA": "Paramount", "LYV": "Live Nation", "TTWO": "Take-Two",
        "EA": "Electronic Arts", "ZM": "Zoom", "DASH": "DoorDash", "UBER": "Uber",
        "LYFT": "Lyft", "ABNB": "Airbnb", "BKNG": "Booking", "EXPE": "Expedia",
        "TSLA": "Tesla", "F": "Ford", "GM": "GM", "RIVN": "Rivian", "LCID": "Lucid",
        "DAL": "Delta Air", "UAL": "United Air", "AAL": "American Air", "LUV": "Southwest",
        "CAT": "Caterpillar", "DE": "John Deere", "HON": "Honeywell", "GE": "GE Aerospace",
        "RTX": "Raytheon", "LMT": "Lockheed", "BA": "Boeing", "UPS": "UPS",
        "FDX": "FedEx", "UNP": "Union Pacific", "CSX": "CSX", "NSC": "Norfolk Southern",
        "A": "Agilent", "ACN": "Accenture", "ADBE": "Adobe", "ADI": "Analog Devices",
        "ADP": "Automatic Data", "ADSK": "Autodesk", "AEE": "Ameren", "AEP": "Am Electric",
        "AES": "AES Corp", "AFL": "Aflac", "AIG": "Am International", "AIZ": "Assurant",
        "AJG": "Arthur J. Gallagher", "AKAM": "Akamai", "ALB": "Albemarle", "ALGN": "Align",
        "ALL": "Allstate", "ALLE": "Allegion", "AMAT": "Applied Materials", "AMCR": "Amcor",
        "AMD": "AMD", "AME": "AMETEK", "AMGN": "Amgen", "AMP": "Ameriprise",
        "AMT": "American Tower", "AMZN": "Amazon", "ANET": "Arista", "ANSS": "ANSYS",
        "AON": "Aon", "AOS": "A.O. Smith", "APD": "Air Products", "APH": "Amphenol",
        "APTV": "Aptiv", "ARE": "Alexandria", "ATO": "Atmos Energy", "AVB": "AvalonBay",
        "AVGO": "Broadcom", "AVY": "Avery Dennison", "AWK": "Am Water Works", "AXP": "Am Express",
        "AZO": "AutoZone", "BA": "Boeing", "BAC": "BofA", "BALL": "Ball Corp",
        "BAX": "Baxter", "BBWI": "Bath & Body Works", "BBY": "Best Buy", "BDX": "Becton Dickinson",
        "BEN": "Franklin Resources", "BF.B": "Brown-Forman", "BIIB": "Biogen", "BIO": "Bio-Rad",
        "BK": "BNY Mellon", "BKNG": "Booking", "BKR": "Baker Hughes", "BLK": "BlackRock",
        "BMY": "Bristol-Myers", "BR": "Broadridge", "BRK.B": "Berkshire B", "BRO": "Brown & Brown",
        "BSX": "Boston Scientific", "BWA": "BorgWarner", "BXP": "Boston Properties", "C": "Citigroup",
        "CAG": "Conagra", "CAH": "Cardinal Health", "CARR": "Carrier", "CAT": "Caterpillar",
        "CB": "Chubb", "CBOE": "Cboe", "CBRE": "CBRE Group", "CCI": "Crown Castle",
        "CCL": "Carnival", "CDNS": "Cadence", "CDW": "CDW", "CE": "Celanese",
        "CEG": "Constellation Energy", "CF": "CF Industries", "CFG": "Citizens Financial", "CHD": "Church & Dwight",
        "CHRW": "C.H. Robinson", "CHTR": "Charter", "CI": "Cigna", "CINF": "Cincinnati Financial",
        "CL": "Colgate", "CLX": "Clorox", "CMA": "Comerica", "CMCSA": "Comcast",
        "CME": "CME Group", "CMG": "Chipotle", "CMI": "Cummins", "CMS": "CMS Energy",
        "CNC": "Centene", "CNP": "CenterPoint", "COF": "Capital One", "COO": "CooperCos",
        "COP": "ConocoPhillips", "COST": "Costco", "CPB": "Campbell Soup", "CPRT": "Copart",
        "CPT": "Camden Property", "CRL": "Charles River", "CRM": "Salesforce", "CSGP": "CoStar",
        "CSX": "CSX", "CTAS": "Cintas", "CTLT": "Catalent", "CTRA": "Coterra",
        "CTSH": "Cognizant", "CTVA": "Corteva", "CVS": "CVS Health", "CVX": "Chevron",
        "CZR": "Caesars", "D": "Dominion Energy", "DAL": "Delta", "DD": "DuPont",
        "DE": "John Deere", "DFS": "Discover", "DG": "Dollar General", "DGX": "Quest",
        "DHI": "D.R. Horton", "DHR": "Danaher", "DIS": "Disney", "DLR": "Digital Realty",
        "DLTR": "Dollar Tree", "DOV": "Dover", "DOW": "Dow", "DPZ": "Domino's",
        "DRI": "Darden", "DTE": "DTE Energy", "DUK": "Duke Energy", "DVA": "DaVita",
        "DVN": "Devon", "DXC": "DXC Technology", "DXCM": "Dexcom", "EA": "Electronic Arts",
        "EBAY": "eBay", "ECL": "Ecolab", "ED": "Consol Edison", "EFX": "Equifax",
        "EIX": "Edison International", "EL": "Estee Lauder", "ELV": "Elevance", "EMN": "Eastman",
        "EMR": "Emerson", "ENPH": "Enphase", "EOG": "EOG Resources", "EPAM": "EPAM",
        "EQIX": "Equinix", "EQT": "EQT", "ES": "Eversource", "ESS": "Essex Property",
        "ETN": "Eaton", "ETR": "Entergy", "ETSY": "Etsy", "EVRG": "Evergy",
        "EW": "Edwards Lifesciences", "EXC": "Exelon", "EXPD": "Expeditors", "EXPE": "Expedia",
        "EXR": "Extra Space", "F": "Ford", "FANG": "Diamondback", "FAST": "Fastenal",
        "FCX": "Freeport-McMoRan", "FDS": "FactSet", "FDX": "FedEx", "FE": "FirstEnergy",
        "FFIV": "F5", "FIS": "FIS", "FISV": "Fiserv", "FITB": "Fifth Third",
        "FLT": "Fleetcor", "FMC": "FMC", "FOX": "Fox Corp B", "FOXA": "Fox Corp A",
        "FRT": "Federal Realty", "FSLR": "First Solar", "FTNT": "Fortinet", "FTV": "Fortive",
        "GD": "General Dynamics", "GE": "GE", "GEHC": "GE HealthCare", "GEN": "Gen Digital",
        "GILD": "Gilead", "GIS": "General Mills", "GL": "Globe Life", "GLW": "Corning",
        "GM": "GM", "GNRC": "Generac", "GOOG": "Alphabet C", "GOOGL": "Alphabet A",
        "GPC": "Genuine Parts", "GPN": "Global Payments", "GRMN": "Garmin", "GS": "Goldman Sachs",
        "GWW": "Grainger", "HAL": "Halliburton", "HAS": "Hasbro", "HBAN": "Huntington",
        "HCA": "HCA Healthcare", "HD": "Home Depot", "HES": "Hess", "HIG": "Hartford",
        "HII": "Huntington Ingalls", "HLT": "Hilton", "HOLX": "Hologic", "HON": "Honeywell",
        "HPE": "HP Ent", "HPQ": "HP Inc", "HRL": "Hormel", "HSIC": "Henry Schein",
        "HST": "Host Hotels", "HSY": "Hershey", "HUM": "Humana", "HWM": "Howmet Aerospace",
        "IBM": "IBM", "ICE": "ICE", "IDXX": "IDEXX", "IEX": "IDEX", "IFF": "IFF",
        "ILMN": "Illumina", "INCY": "Incyte", "INTC": "Intel", "INTU": "Intuit",
        "IP": "Intl Paper", "IPG": "Interpublic Group", "IQV": "IQVIA", "IRM": "Iron Mountain",
        "ISRG": "Intuitive", "IT": "Gartner", "ITW": "Illinois Tool", "IVZ": "Invesco",
        "J": "Jacobs", "JBHT": "J.B. Hunt", "JCI": "Johnson Controls", "JKHY": "Jack Henry",
        "JNJ": "J&J", "JNPR": "Juniper", "JPM": "JPMorgan", "K": "Kellogg",
        "KDP": "Keurig Dr Pepper", "KEY": "KeyCorp", "KEYS": "Keysight", "KHC": "Kraft Heinz",
        "KIM": "Kimco", "KMB": "Kimberly-Clark", "KMI": "Kinder Morgan", "KMX": "CarMax",
        "KO": "Coca-Cola", "KR": "Kroger", "L": "Loews", "LRCX": "Lam Research",
        "LULU": "Lululemon", "LUV": "Southwest", "LYB": "LyondellBasell", "MA": "Mastercard",
        "MAR": "Marriott", "MAS": "Masco", "MCD": "McDonald's", "MCHP": "Microchip",
        "MCK": "McKesson", "MCO": "Moody's", "MDLZ": "Mondelez", "MDT": "Medtronic",
        "MET": "MetLife", "META": "Meta", "MGM": "MGM Resorts", "MHK": "Mohawk",
        "MKC": "McCormick", "MKTX": "MarketAxess", "MLM": "Martin Marietta", "MMC": "Marsh McLennan",
        "MMM": "3M", "MNST": "Monster", "MO": "Altria", "MOH": "Molina",
        "MOS": "Mosaic", "MPC": "Marathon Petroleum", "MPWR": "Monolithic Power", "MRK": "Merck",
        "MRNA": "Moderna", "MRO": "Marathon Oil", "MS": "Morgan Stanley", "MSCI": "MSCI",
        "MSFT": "Microsoft", "MSI": "Motorola", "MTB": "M&T Bank", "MTCH": "Match Group",
        "MTD": "Mettler Toledo", "MU": "Micron", "NCLH": "Norwegian Cruise", "NDAQ": "Nasdaq",
        "NDSN": "Nordson", "NEE": "NextEra", "NEM": "Newmont", "NFLX": "Netflix",
        "NI": "NiSource", "NKE": "Nike", "NOC": "Northrop Grumman", "NOW": "ServiceNow",
        "NRG": "NRG Energy", "NSC": "Norfolk Southern", "NTAP": "NetApp", "NTRS": "Northern Trust",
        "NUE": "Nucor", "NVDA": "NVIDIA", "NVR": "NVR", "NWL": "Newell Brands",
        "NWS": "News Corp B", "NWSA": "News Corp A", "O": "Realty Income", "ODFL": "Old Dominion",
        "OKE": "ONEOK", "OMC": "Omnicom", "ON": "ON Semiconductor", "ORCL": "Oracle",
        "ORLY": "O'Reilly", "OTIS": "Otis", "OXY": "Occidental", "PANW": "Palo Alto",
        "PARA": "Paramount", "PAYC": "Paycom", "PAYX": "Paychex", "PCAR": "PACCAR",
        "PCG": "PG&E", "PEG": "Public Service", "PEP": "PepsiCo", "PFE": "Pfizer",
        "PFG": "Principal Financial", "PG": "P&G", "PGR": "Progressive", "PH": "Parker-Hannifin",
        "PHM": "PulteGroup", "PKG": "Packaging Corp", "PKI": "PerkinElmer", "PLD": "Prologis",
        "PM": "Philip Morris", "PNC": "PNC", "PNR": "Pentair", "PNW": "Pinnacle West",
        "POOL": "Pool Corp", "PPG": "PPG", "PPL": "PPL Corp", "PRU": "Prudential",
        "PSA": "Public Storage", "PSX": "Phillips 66", "PTC": "PTC", "PYPL": "PayPal",
        "QCOM": "Qualcomm", "QRVO": "Qorvo", "RCL": "Royal Caribbean", "RE": "Everest Re",
        "REG": "Regency Centers", "REGN": "Regeneron", "RF": "Regions Financial", "RHI": "Robert Half",
        "RJF": "Raymond James", "RL": "Ralph Lauren", "RMD": "ResMed", "ROK": "Rockwell",
        "ROL": "Rollins", "ROP": "Roper", "ROST": "Ross Stores", "RSG": "Republic Services",
        "RTX": "Raytheon", "RVTY": "Revvity", "SBAC": "SBA Comm", "SBUX": "Starbucks",
        "SCHW": "Schwab", "SEDG": "SolarEdge", "SEE": "Sealed Air", "SHW": "Sherwin-Williams",
        "SJM": "J.M. Smucker", "SLB": "Schlumberger", "SNA": "Snap-on", "SNPS": "Synopsys",
        "SO": "Southern Co", "SPG": "Simon Property", "SPGI": "S&P Global", "SRE": "Sempra",
        "STE": "STERIS", "STT": "State Street", "STX": "Seagate", "STZ": "Constellation Brands",
        "SWK": "Stanley Black & Decker", "SWKS": "Skyworks", "SYF": "Synchrony", "SYK": "Stryker",
        "SYY": "Sysco", "T": "AT&T", "TAP": "Molson Coors", "TDG": "TransDigm",
        "TDY": "Teledyne", "TECH": "Bio-Techne", "TEL": "TE Connectivity", "TER": "Teradyne",
        "TFC": "Truist", "TFX": "Teleflex", "TGT": "Target", "TJX": "TJX Companies",
        "TMO": "Thermo Fisher", "TMUS": "T-Mobile", "TPR": "Tapestry", "TRMB": "Trimble",
        "TROW": "T. Rowe Price", "TRV": "Travelers", "TSCO": "Tractor Supply", "TSLA": "Tesla",
        "TSN": "Tyson Foods", "TT": "Trane", "TTWO": "Take-Two", "TXN": "Texas Instruments",
        "TXT": "Textron", "TYL": "Tyler Technologies", "UAL": "United Airlines", "UDR": "UDR",
        "UHS": "Universal Health", "ULTA": "Ulta Beauty", "UNH": "UnitedHealth", "UNP": "Union Pacific",
        "UPS": "UPS", "URI": "United Rentals", "USB": "U.S. Bancorp", "V": "Visa",
        "VFC": "VF Corp", "VICI": "VICI Properties", "VLO": "Valero", "VMC": "Vulcan",
        "VNO": "Vornado", "VRSK": "Verisk", "VRSN": "Verisign", "VRTX": "Vertex",
        "VTR": "Ventas", "VTRS": "Viatris", "VZ": "Verizon", "WAB": "Wabtec",
        "WAT": "Waters", "WBA": "Walgreens", "WBD": "Warner Bros", "WDC": "Western Digital",
        "WEC": "WEC Energy", "WELL": "Welltower", "WFC": "Wells Fargo", "WHR": "Whirlpool",
        "WM": "Waste Management", "WMB": "Williams Cos", "WMT": "Walmart", "WRB": "W.R. Berkley",
        "WRK": "WestRock", "WST": "West Pharmaceutical", "WTW": "Willis Towers Watson", "WY": "Weyerhaeuser"
    }
    
    # --- 🇹🇼 台股重點備用清單 (防止 API 同步延遲導致的名稱缺失) ---
    TW_STOCK_FALLBACK = {
        "2330": "台積電", "2317": "鴻海", "2454": "聯發科", "2382": "廣達",
        "2330.TW": "台積電", "2317.TW": "鴻海", "2454.TW": "聯發科", "2382.TW": "廣達",
        "2308": "台達電", "2881": "富邦金", "2882": "國泰金", "2303": "聯電",
        "0050": "元大台灣50", "0056": "元大高股息", "00878": "國泰永續高股息", "00919": "群益台灣精選高息"
    }
    
    # --- 🪙 加密貨幣名稱補全 (針對 Yahoo Finance 代碼) ---
    CRYPTO_FALLBACK = {
        "BTC-USD": "比特幣", "ETH-USD": "以太幣", "SOL-USD": "Solana",
        "BNB-USD": "幣安幣", "XRP-USD": "瑞波幣", "ADA-USD": "卡爾達諾",
        "DOGE-USD": "狗狗幣", "AVAX-USD": "雪崩幣", "DOT-USD": "波卡幣",
        "TRX-USD": "波場幣", "LINK-USD": "Chainlink", "POL28321-USD": "Polygon (POL)",
        "NEAR-USD": "NEAR", "LTC-USD": "萊特幣", "BCH-USD": "比特現金",
        "SHIB-USD": "柴犬幣", "DAI-USD": "DAI", "UNI7083-USD": "Uniswap",
        "LEO-USD": "LEO", "APT21794-USD": "Aptos", "STX4847-USD": "Stacks",
        "OKB-USD": "OKB", "ATOM-USD": "Cosmos", "IMX10603-USD": "Immutable",
        "HBAR-USD": "HBAR", "KAS-USD": "Kaspa", "ETC-USD": "以太經典",
        "RENDER-USD": "Render", "FIL-USD": "Filecoin", "LDO-USD": "Lido"
    }
    
    code_to_name.update(US_STOCK_FALLBACK)
    if 'US_STOCK_ADDITIONAL' in locals():
        code_to_name.update(US_STOCK_ADDITIONAL)
    code_to_name.update(TW_STOCK_FALLBACK)
    code_to_name.update(CRYPTO_FALLBACK)

    # 檢查是否為 MockApi (連線衝突模式)
    is_mock = hasattr(_api, 'list_accounts') and len(_api.list_accounts()) == 0 and not hasattr(_api, 'Contracts')

    # --- 強化合約同步 (關鍵修復：解決 82 檔問題) ---
    if not is_mock and hasattr(_api, "Contracts") and hasattr(_api.Contracts, "Stocks"):
        # 如果當前合約庫太小，強制啟動深度下載
        if len(code_to_name) < 1000:
            with st.spinner("📦 正在深度同步市場數據 (預計 15 秒)..."):
                try:
                    _api.fetch_contracts(contract_download=True)
                except:
                    _api.fetch_contracts()
    
    if not is_mock and hasattr(_api, "Contracts") and hasattr(_api.Contracts, "Stocks"):
        stocks = _api.Contracts.Stocks
        
        def recursive_scan(item, depth=0):
            if depth > 5: return # 防止過深
            
            # [優先級 1] 合約直接映射節點
            if hasattr(item, '_code2contract'):
                c2c = item._code2contract
                for c, contract in c2c.items():
                    c_code = str(c).upper()
                    if c_code not in code_to_name:
                        code_to_name[c_code] = getattr(contract, 'name', 'Unknown')
                return

            # [優先級 2] 屬性遞迴
            for attr in dir(item):
                if attr.startswith('_') or attr in ['append', 'get', 'keys', 'post_init']: continue
                try:
                    val = getattr(item, attr)
                    # 只有具備子節點特徵的才進去
                    if val and (hasattr(val, '_code2contract') or hasattr(val, '__dict__')):
                        recursive_scan(val, depth + 1)
                except: continue

        # 針對常見市場節點進行優先顯性掃描
        for mk in ['TSE', 'OTC', 'OES', 'US', 'USA']:
            if hasattr(stocks, mk):
                recursive_scan(getattr(stocks, mk))
        
        # 成功抓取後，存入磁碟快取
        if len(code_to_name) > 1000:
            try:
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
    # Priority 1: URL Parameters (passed from LocalStorage by JS Bridge)
    if "w" in st.query_params:
        try:
            encoded_w = st.query_params["w"]
            decoded_w = base64.b64decode(encoded_w).decode('utf-8')
            return json.loads(decoded_w)
        except:
            pass

    # Priority 2: Legacy Server File (Transition phase)
    if os.path.exists(WATCHLIST_FILE):
        try:
            with open(WATCHLIST_FILE, "r") as f:
                return json.load(f)
        except:
            pass

    # Priority 3: Defaults
    return ["2330", "2317", "0050"]

def save_watchlist(watchlist):
    """Now purely session-based. Persistence is handled by the JS Bridge in the UI."""
    st.session_state.watchlist = watchlist

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
                    cols = st.columns([1, 2, 2, 2, 2])
                    
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
                        p_pct = (cp - trade['buy_price']) / trade['buy_price'] * 100
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
    if market == 'CRYPTO':
        # 加密貨幣：自定義主流幣清單 (Yahoo Finance 格式)
            return [
                "BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD", 
                "ADA-USD", "DOGE-USD", "AVAX-USD", "DOT-USD", "TRX-USD",
                "LINK-USD", "POL28321-USD", "NEAR-USD", "LTC-USD", "BCH-USD",
                "SHIB-USD", "DAI-USD", "UNI7083-USD", "LEO-USD", "APT21794-USD",
                "STX4847-USD", "OKB-USD", "ATOM-USD", "IMX10603-USD", "HBAR-USD",
                "KAS-USD", "ETC-USD", "RENDER-USD", "FIL-USD", "LDO-USD"
            ]

    all_map = get_stock_name_map(api)
    filtered = []
    for code, name in all_map.items():
        if market == 'TW':
            # 台股規則優化：
            # 1. 只有 4 碼數字 (普通股) 或 00/01 開頭的 6 碼 (ETF/REITs) 才納入
            # 2. 排除權證與特殊標的 (名稱含 購/售/牛/熊/認/特/債/定)
            if code and code[0].isdigit():
                if any(k in name for k in ['購', '售', '牛', '熊', '認', '特', '債', '定']):
                    continue
                # 嚴格限制普通股 (4碼) 與主流 ETF (6碼且00或01開頭)
                if len(code) == 4:
                    filtered.append(code)
                elif len(code) == 6 and code.startswith(('00', '01')):
                    filtered.append(code)
        elif market == 'US':
            # 美股：字母開頭且排除加密貨幣代碼
            if code and code[0].isalpha() and not (code.endswith('.TW') or code.endswith('.TWO') or '-USD' in str(code)):
                filtered.append(code)
    
    # 排序：台股按數字、美股按字母
    return sorted(filtered)

# --- 🛠️ 核心隔離邏輯：Native Session ID 優先 ---
# 使用 Streamlit 內置的 session_id 作為隔離主鍵，不再需要跳轉等待
user_id = get_session_uid()

# 1. Watchlist 初始化：優先取網址參數 (由 JS Bridge 懶加載提供)，其次取 LocalStorage
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = load_watchlist()

# 2. LocalStorage / URL Bridge (非阻塞式背景處理)
# 這裡僅負責把 python 的 watchlist 同步給 JS 儲存，不再強制跳轉 UID
if ("w" not in st.query_params) and "ls_init_attempted" not in st.session_state:
    st.session_state.ls_init_attempted = True
    st.components.v1.html("""
        <script>
            const stored = localStorage.getItem('sinopac_watchlist');
            const url = new URL(window.parent.location.href);
            if (!url.searchParams.has('w') && stored && stored !== '[]' && stored !== 'null') {
                url.searchParams.set('w', btoa(stored));
                window.parent.location.href = url.toString();
            }
        </script>
    """, height=0)

# 3. Persistence: Only write back to localStorage if the watchlist has actually changed
# This prevents the JS iframe from stealing focus on every re-run (Character typed, etc.)
if 'watchlist' in st.session_state:
    current_wl_json = json.dumps(st.session_state.watchlist)
    if st.session_state.get('last_synced_wl') != current_wl_json:
        st.session_state.last_synced_wl = current_wl_json
        st.components.v1.html(f"""
            <script>
                localStorage.setItem('sinopac_watchlist', '{current_wl_json}');
            </script>
        """, height=0)

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


if st.sidebar.button("📊 交易紀錄儀表板", use_container_width=True):
    st.session_state.active_page = "simulation"
    st.rerun()

# --- [NEW] 側邊欄：功能入口置頂 ---
# 1. 掃描目前追蹤清單 (置頂且不隱藏)
if st.sidebar.button("🚀 目前追蹤清單", use_container_width=True):
    st.session_state.active_page = "market"
    scan_btn = True # 模擬按鈕按下
else:
    scan_btn = False

st.sidebar.markdown("###  大數據海選")

# 2. 台灣/美國股票海選
with st.sidebar.container():
    st.markdown('<div class="desktop-only">', unsafe_allow_html=True)
    big_scan_tw_btn = st.sidebar.button("🇹🇼 台灣股票海選", use_container_width=True, 
                                        type="primary" if st.session_state.get("scan_market") == "TW" else "secondary")
    big_scan_us_btn = st.sidebar.button("🇺🇸 美國股票海選", use_container_width=True,
                                        type="primary" if st.session_state.get("scan_market") == "US" else "secondary")
    big_scan_crypto_btn = st.sidebar.button("🪙 加密貨幣海選", use_container_width=True,
                                           type="primary" if st.session_state.get("scan_market") == "CRYPTO" else "secondary")
    st.markdown('</div>', unsafe_allow_html=True)

# 確保按下海選按鈕時切換回主頁
if big_scan_tw_btn or big_scan_us_btn or big_scan_crypto_btn:
    st.session_state.active_page = "market"

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
            if resolved_code not in st.session_state.watchlist:
                st.session_state.watchlist.append(resolved_code)
                save_watchlist(st.session_state.watchlist)
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
def fetch_and_analyze(watchlist, defense_weight=0.5, market_type=None):
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
    
    # 再次檢查合約狀態，若未完成則現場補抓 (增加至 60 秒 Timeout)
    if not st.session_state.get('contracts_fetched', False):
        try:
            api.fetch_contracts(contracts_timeout=60000)
            st.session_state.contracts_fetched = True
        except Exception as e:
            st.warning(f"⚠️ 合約資料抓取超時，系統將嘗試使用快取或局部數據：{str(e)[:50]}")
    
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
                # 美股處理：將 BRK.B 轉為 BRK-B 以利 Yahoo 識別
                t = c.replace('.', '-')
                tickers.append(t)
                ticker_to_code[t] = c
        
        # 2. 執行批次下載 (分段執行以提高成功率)
        try:
            all_dfs = {}
            chunk_size = 100 # 加大 chunk 以提升速度，但也增加單次失敗風險
            for k in range(0, len(tickers), chunk_size):
                chunk = tickers[k:k+chunk_size]
                status_placeholder.info(f"📥 正在批次下載市場數據 ({min(k + chunk_size, len(tickers))}/{len(tickers)})...")
                # 強制使用 auto_adjust=True 以獲取穩定的技術指標得分
                batch_data = yf.download(chunk, start=start_date, group_by='ticker', threads=True, progress=False, timeout=10, auto_adjust=True)
                
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
                    # 2. 獲取台股歷史數據 (統一改用 Yahoo Finance 模式)
                    status_msg = "❌ 抓取失敗"
                    for suffix in ['.TW', '.TWO']:
                        try:
                            t = yf.Ticker(code + suffix)
                            # 使用 auto_adjust=True 確保指標一致性
                            df_yf = t.history(start=start_date, interval="1d", auto_adjust=True)
                            if not df_yf.empty:
                                df = df_yf.reset_index()
                                df.columns = [c.lower() for c in df.columns]
                                if 'date' in df.columns:
                                    df = df.rename(columns={'date': 'ts'})
                                df['ts'] = pd.to_datetime(df['ts'])
                                # 統一欄位
                                df = df[['ts', 'open', 'high', 'low', 'close', 'volume']]
                                source = f"🌐 Yahoo({suffix})"
                                break
                        except: continue
                    
                    if df is None:
                        if not quiet_mode:
                            st.warning(f"無法取得台股 {code} 的 K 線資料")
                        data_list.append({
                            "代碼": code, "名稱": stock_name, "最新價格": 0, "操作建議": "❌ 無法取得數據",
                            "一年位階": "-", "年線乖離": "-", "MA20乖離": "-", "MACD狀態": "-", "綜合評分": -1
                        })
                        continue
                else:
                    # 3. 處理美股 (透過 yfinance 補完計畫)
                    try:
                        # 確保代碼符號對 Yahoo 友善 (如 BRK.B -> BRK-B)
                        query_code = code.replace('.', '-')
                        ticker = yf.Ticker(query_code)
                        try:
                            # 優先嘗試 start_date
                            df_yf = ticker.history(start=start_date, interval="1d", auto_adjust=True)
                            if df_yf.empty and market_type == 'CRYPTO':
                                # 幣圈備援：若 start_date 抓不到，嘗試 period='1y' (解決時區與開始日期偏移問題)
                                df_yf = ticker.history(period="1y", interval="1d", auto_adjust=True)
                            
                            if not df_yf.empty:
                                df = df_yf.reset_index()
                                df.columns = [c.lower() for c in df.columns]
                                if 'date' in df.columns: df = df.rename(columns={'date': 'ts'})
                                df['ts'] = pd.to_datetime(df['ts'])
                                df = df[['ts', 'open', 'high', 'low', 'close', 'volume']]
                                source = "🌐 Yahoo"
                            else:
                                if not quiet_mode:
                                    st.warning(f"Yahoo Finance 查無代碼 {code} 的歷史資料")
                                data_list.append({
                                    "代碼": code, "名稱": stock_name, "最新價格": 0, "操作建議": "❌ 無有效數據",
                                    "一年位階": "-", "年線乖離": "-", "MA20乖離": "-", "MACD狀態": "-", "綜合評分": -1
                                })
                                continue
                        except Exception as inner_err:
                            st.error(f"單一數據抓取異常 ({code}): {inner_err}")
                            continue
                    except Exception as yf_err:
                        st.error(f"資料抓取過程中發生未預期錯誤 ({code}): {yf_err}")
                        continue
                
                # 確認資料有效性
                if df is None or df.empty:
                    if not quiet_mode:
                        st.warning(f"代碼 {code} 無法獲取有效資料")
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
                "_data_ts": last_ts
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
    required_cols = ['_v_score', '_p_score', '_is_rev_ok', '_g_buy', '_v_buy', '_ma_base', '_y_low']
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

# --- 自動化掃描與顯示 ---
# 如果正在顯示建議清單，可以選擇先不自動掃描，避免干擾使用者操作
current_watchlist_key = ",".join(watchlist)
should_sync = False

# --- 每日定時自動任務 (Taipei 09:05) ---
now_tp = get_now()
if now_tp.hour >= 9 and now_tp.minute >= 5:
    today_str = now_tp.strftime("%Y-%m-%d")
    # 檢查今日系統紀錄是否已存在
    sys_logs = load_trading_log("system")
    has_today = any(l['buy_time'].startswith(today_str) for l in sys_logs)
    
    if not has_today and st.session_state.active_page == "market":
        # 觸發自動海選
        st.session_state.trigger_daily_scan = True
        st.info("⏰ 偵測到開盤時間，正在為您自動執行本日官方海選...")

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
                st.session_state.trigger_daily_scan = False

elif st.session_state.get("last_watchlist") != current_watchlist_key:
    # 只有當追蹤清單「內容改變」時，才自動觸發同步
    should_sync = True

# 移除原本位置的掃描按鈕 (已移至側邊欄最上方)
# scan_btn = st.sidebar.button("🚀 重新掃描目前清單", ...)
# big_scan_btn = st.button("🔍 執行「全市場」大選股", ...)

# --- 掃描執行邏輯 ---
if (big_scan_tw_btn or big_scan_us_btn or big_scan_crypto_btn or scan_btn or should_sync or st.session_state.get("force_rescan")):
    # 1. 決定市場與名單
    if big_scan_tw_btn or big_scan_us_btn or big_scan_crypto_btn or st.session_state.get("trigger_daily_scan"):
        if big_scan_tw_btn: m_type = 'TW'
        elif big_scan_us_btn: m_type = 'US'
        elif big_scan_crypto_btn: m_type = 'CRYPTO'
        else: m_type = 'TW' # 預設自動掃描為台股
        
        m_label = {"TW": "台灣", "US": "美國", "CRYPTO": "加密貨幣"}[m_type]
        st.session_state.is_big_scan = True
        st.session_state.scan_market = m_type
        scan_list = get_mass_scan_list(api, market=m_type)
        toast_msg = f"🚀 開始 {m_label} 大平原掃描 (共 {len(scan_list)} 檔)..."
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
        
        results = fetch_and_analyze(scan_list, defense_weight=st.session_state.defense_weight, market_type=st.session_state.scan_market)
        
        if not results.empty:
            st.session_state.results = results
            st.session_state.last_update = get_now().strftime("%H:%M:%S")
            st.session_state.current_page = 0 # 重設頁碼
            
            # 存入磁碟快取
            save_results_cache(results, is_big_scan=st.session_state.is_big_scan, market=st.session_state.scan_market, user_id=user_id)
            st.toast("✅ 數據同步完成！", icon="📉")
            
            # --- 🧪 模擬交易：自動跟單 (第一類：系統每日海選) ---
            if st.session_state.is_big_scan:
                top_stock = results.iloc[0]
                m_type = st.session_state.scan_market or "TW"
                reason = f"系統自動海選第一名 ({m_type}) (評分: {top_stock['綜合評分']:.1f})"
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
    if st.button("🏠 返回行情掃描 (Market)"):
        st.session_state.active_page = "market"
        st.rerun()
    display_simulation_dashboard(user_id)
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

    # 2. 自動補完名稱
    if (results['名稱'] == '未知').any():
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
    
    # --- 指標說明 (動態調整) ---
    w_def = int(st.session_state.defense_weight * 100)
    w_gro = 100 - w_def
    is_crypto = st.session_state.get("scan_market") == "CRYPTO"
    
    # 策略文字變數
    def_ma = "100日線" if is_crypto else "年線"
    atr_mult = "3.0倍" if is_crypto else "2.5倍"
    pullback_target = "MA20/MA50" if is_crypto else "MA20"
    
    with st.expander(f"💡 策略心法與操作建議 ({w_def}% 價值防禦 + {w_gro}% 強勢平回)"):
        st.markdown(f"""
        本系統採用 **({w_def}/{w_gro} 權重動態配置)** 策略，透過營收趨勢與成交量能計算精確點位：
        - **🛡️ 價值防禦 ({w_def}%)**:
            - **標的**: 基本面優質、具備長期支撐。 (M) 標示為 (量能激增 + 重回 5 日線) 動能觸發。
            - **進場**: 參考 **{def_ma}** 支撐。設定 **1:2 盈虧比** 或預期 +20%。停損位設於近期低點 (-5%)。
        - **📈 強勢平回 ({w_gro}%)**:
            - **標的**: 強勢趨勢股/加密貨幣。 { "!! 流動性過濾: 若 24h 成交量大幅萎縮，則評分遞減。" if is_crypto else "" }
            - **進場**: 參考 **{pullback_target}** 支撐進場。停損位設於 **{atr_mult} 倍 ATR**。
            - **目標**: 預期 **1:3 盈虧比**。若帶量突破，目標上看 **1:4**。
        - **MACD 狀態**: (🎯強勢) (大於 0) = 高爆發力階段；(🩹弱勢) (小於 0) = 超跌反彈階段。
        """)

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
    st.markdown(f"""
    <div class="desktop-only">
        <div style="display: flex; border: 1px solid #444; border-radius: 8px; padding: 10px; background: #262730; margin-bottom: 10px; font-weight: bold; align-items: center; font-size: 0.85rem;">
            <div style="flex: 1.5;">股票</div>
            <div style="flex: 0.6;">時間</div>
            <div style="flex: 0.8;">最新價</div>
            <div style="flex: 0.8;">位階</div>
            <div style="flex: 0.8;">{header_label}</div>
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
            
        # --- [NEW] MAX 市場智慧識別 ---
        max_market_id = None
        if max_api:
            # 取得 MAX 所有市場清單 (使用會話級快取避免頻繁請求)
            if "max_markets" not in st.session_state:
                st.session_state.max_markets = max_api.get_markets()
            
            # 轉換邏輯：MATIC -> POL, BTC-USD -> btctwd
            raw_symbol = str(row['代碼']).split('-')[0].lower()
            # 內建更名表
            rename_map = {"matic": "pol", "fb": "meta", "goog": "googl"}
            base_coin = rename_map.get(raw_symbol, raw_symbol)
            
            # 優先找 TWD 交易對，再找 USDT
            available_ids = [m['id'] for m in st.session_state.max_markets]
            if f"{base_coin}twd" in available_ids:
                max_market_id = f"{base_coin}twd"
            elif f"{base_coin}usdt" in available_ids:
                max_market_id = f"{base_coin}usdt"
            
        st.success(f"💡 預估委託金額: **{buy_price * qty:,.0f}** 元")
        
        st.divider()
        c1, c2 = st.columns(2)
        # 按鈕 1: 模擬下單 (永遠可用)
        if c1.button("🧪 執行模擬下單", use_container_width=True):
            reason = f"用戶手動選擇 ({row['操作建議']})"
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
                if c2.button(btn_label, use_container_width=True, type="primary", disabled=(not max_market_id)):
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
                            # Shioaji place_order returns a Trade object, not a dict with 'error'.
                            # Error handling is typically done via exceptions or checking trade status.
                            # Assuming a successful placement if no exception is raised.
                            # [NEW] 成功後也記錄在「個人紀錄」中作為持倉追蹤 (類型為 Real)
                            reason = f"永豐金實盤買入 (委託號: {trade.order.id})" # Use trade.order.id for order ID
                            record_trade(user_id, "Manual", row['代碼'], row['名稱'], buy_price, reason, is_system=False, trade_type="Real", shares=qty)
                            
                            st.session_state.last_order = f"{get_now().strftime('%H:%M:%S')} - 永豐金已送出 {row['代碼']} {qty}股 (限價:{buy_price})"
                            st.toast("✅ 永豐金委託已送出！已加入持倉紀錄。", icon="🚀")
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
        cache_file = os.path.join(CACHE_DIR, f"{row['代碼']}_y.csv")
        if os.path.exists(cache_file):
            df_selected = pd.read_csv(cache_file)
            df_selected['ts'] = pd.to_datetime(df_selected['ts'])
            
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

    # 2. 顯示內容 (每一家股票一個穩定容器，手機自動轉卡片)
    for index, row in paged_results.iterrows():
        with st.container(border=True):
            cols = st.columns([1.5, 0.6, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 3.5, 0.5])
            
            # 欄位一：股票名稱 (轉為按鈕連結)
            icon = "🪙" if "-USD" in str(row['代碼']) else "🛒"
            if cols[0].button(f"{icon} {row['代碼']} {row['名稱']}", key=f"t_{row['代碼']}_{index}", use_container_width=True):
                show_order_dialog(row)
            
            # 欄位二：資料時間
            data_ts = row.get('_data_ts', '-')
            cols[1].markdown(f'<span class="mobile-label">資料時間:</span><span style="font-size:0.8rem; color:#888;">{data_ts}</span>', unsafe_allow_html=True)

            # 欄位三：最新價 (手機版會標註標籤)
            price_val = f"{row['最新價格']:.1f}" if row['最新價格'] != 0 else "-"
            cols[2].markdown(f'<span class="mobile-label">最新價:</span><b>{price_val}</b>', unsafe_allow_html=True)
            
            # 欄位四～六：指標
            cols[3].markdown(f'<span class="mobile-label">一年位階:</span>{row["一年位階"]}', unsafe_allow_html=True)
            cols[4].markdown(f'<span class="mobile-label">{header_label}:</span>{row["年線乖離"]}', unsafe_allow_html=True)
            cols[5].markdown(f'<span class="mobile-label">MA20乖離:</span>{row["MA20乖離"]}', unsafe_allow_html=True)
            
            # 欄位七～八：新增的 MA20 價 與 ATR 停損
            ma20_raw = row.get('_ma20', 0)
            ma20_val = f"{ma20_raw:.1f}" if not pd.isna(ma20_raw) else "-"
            atr_mult = row.get('_atr_mult', 2.5)
            atr_stop_raw = row['最新價格'] - (atr_mult * row.get('_atr', 0))
            atr_stop = f"{atr_stop_raw:.1f}" if not pd.isna(atr_stop_raw) else "-"
            cols[6].markdown(f'<span class="mobile-label">MA20價:</span>{ma20_val}', unsafe_allow_html=True)
            cols[7].markdown(f'<span class="mobile-label">ATR停損:</span>{atr_stop}', unsafe_allow_html=True)
            
            # 欄位九：操作建議
            cols[8].markdown(f"**`{row['操作建議']}`**")
            
            # 欄位十：動作按鈕 (唯一 Key)
            is_big_scan = st.session_state.get("is_big_scan", False)
            if is_big_scan:
                action_icon = "➕"
            else:
                action_icon = "🗑️" if row['代碼'] in st.session_state.watchlist else "➕"

            if cols[9].button(action_icon, key=f"btn_{row['代碼']}_{index}", use_container_width=True):
                if is_big_scan:
                    if row['代碼'] not in st.session_state.watchlist:
                        st.session_state.watchlist.append(row['代碼'])
                        st.toast(f"✅ 已加入追蹤清單 {row['代碼']} {row['名稱']}")
                        save_watchlist(st.session_state.watchlist)
                    else:
                        st.toast(f"ℹ️ {row['代碼']} 已在清單中")
                else:
                    if row['代碼'] in st.session_state.watchlist:
                        st.session_state.watchlist.remove(row['代碼'])
                        st.toast(f"🗑️ 已從清單移除 {row['代碼']}")
                        # --- [優化] 即時從目前顯示的分析結果中移除該列，避免整頁重新掃描 ---
                        if "results" in st.session_state:
                            st.session_state.results = st.session_state.results[st.session_state.results['代碼'] != row['代碼']]
                            # 更新快取，確保重新整理後依然保持現狀
                            save_results_cache(st.session_state.results, is_big_scan=False, market=None, user_id=user_id)
                    else:
                        st.session_state.watchlist.append(row['代碼'])
                        st.toast(f"➕ 已加入追蹤清單 {row['代碼']}")
                        # 如果是新加入，則還是需要重新掃描來獲取分析數據
                        if "results" in st.session_state:
                            del st.session_state.results
                    
                    save_watchlist(st.session_state.watchlist)
                    st.rerun()

    # --- 分頁導航 ---
    if total_pages > 1:
        st.divider()
        # --- 🚀 [FINAL FIX] 不再依賴 st.columns，直接使用 HTML 並排 ---
        st.markdown('<div class="pagination-container">', unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 1, 1])
        
        is_mob = is_mobile_device()
        prev_label = "◀️" if is_mob else "◀️ 上一頁"
        next_label = "▶️" if is_mob else "下一頁 ▶️"
        
        with col1:
            if st.button(prev_label, key="prev_pg", disabled=(st.session_state.current_page == 0), use_container_width=True):
                st.session_state.current_page -= 1
                st.rerun()
        
        with col2:
            st.markdown(f"<div style='text-align:center; padding-top:8px; font-weight:bold;'>{st.session_state.current_page + 1}/{total_pages}</div>", unsafe_allow_html=True)
        
        with col3:
            if st.button(next_label, key="next_pg", disabled=(st.session_state.current_page == total_pages - 1), use_container_width=True):
                st.session_state.current_page += 1
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.divider()
    
    # 互動式圖表已移至「下單確認」對話框內，此處保持簡潔
    pass
else:
    st.info("🔄 正在初始化市場數據，或請點擊左側「🚀 目前追蹤清單」。")