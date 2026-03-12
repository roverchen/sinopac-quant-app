import os
import json
import pickle
from google.cloud import storage, firestore
from api.config import PROJECT_ID, CACHE_DIR, SYNC_DIR

# Ensure directories exist
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(SYNC_DIR, exist_ok=True)

# 延遲初始化 Firestore 用戶端
_db = None
def get_db():
    global _db
    if _db is None:
        try:
            from google.cloud import firestore
            _db = firestore.Client(project=PROJECT_ID)
        except Exception as e:
            print(f"[Storage] Firestore client failed: {e}")
    return _db

# 延遲初始化 GCS 用戶端
_gcs = None
def get_gcs():
    global _gcs
    if _gcs is None:
        try:
            from google.cloud import storage
            _gcs = storage.Client(project=PROJECT_ID)
        except Exception as e:
            print(f"[Storage] GCS client failed: {e}")
    return _gcs

def update_user_credentials(user_id, creds):
    """保存憑證：優先使用 Firestore，失敗則存入本地 JSON"""
    db = get_db()
    if db:
        try:
            db.collection("users").document(user_id).set({"credentials": creds}, merge=True)
            return True
        except Exception as e:
            print(f"Firestore save error: {e}")
    
    # 本地備援
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        path = os.path.join(CACHE_DIR, f"creds_{user_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(creds, f, ensure_ascii=False)
    except Exception as e:
        print(f"[Storage] Local credentials save failed: {e}")
    return True

def get_user_credentials(user_id):
    """加載憑證：優先從 Firestore 讀取。增加強健性檢查避免 TypeError。"""
    db = get_db()
    creds = {}
    if db:
        try:
            doc = db.collection("users").document(user_id).get()
            if doc.exists:
                creds = doc.to_dict().get("credentials", {})
        except Exception as e:
            print(f"Firestore load error: {e}")
            
    # 如果 Firestore 沒抓到，嘗試本地
    if not isinstance(creds, dict):
        creds = {}
        
    if not creds:
        path = os.path.join(CACHE_DIR, f"creds_{user_id}.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                try:
                    creds = json.load(f)
                except:
                    creds = {}
    
    return creds if isinstance(creds, dict) else {}

#保留舊名稱別名以相容舊路由
load_credentials = get_user_credentials
save_credentials = update_user_credentials

def save_user_watchlist(user_id, market, watchlist):
    """保存使用者追蹤清單"""
    db = get_db()
    if db:
        try:
            db.collection("users").document(user_id).set({f"watchlist_{market}": watchlist}, merge=True)
            return True
        except Exception as e:
            print(f"Firestore save watchlist error: {e}")
            
    # 本地備援
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        path = os.path.join(CACHE_DIR, f"watchlist_{market}_{user_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(watchlist, f, ensure_ascii=False)
    except Exception as e:
        print(f"[Storage] Local watchlist save failed: {e}")
    return True

def get_user_watchlist(user_id, market):
    """取得使用者追蹤清單"""
    db = get_db()
    if db:
        try:
            doc = db.collection("users").document(user_id).get()
            if doc.exists:
                return doc.to_dict().get(f"watchlist_{market}", [])
        except Exception as e:
            print(f"Firestore load watchlist error: {e}")
    # 本地備援
    path = os.path.join(CACHE_DIR, f"watchlist_{market}_{user_id}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    # Defaults
    if market == "TW":
        return ["2330", "2317", "0050"]
    if market == "CRYPTO":
        return ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "DOGE-USD"]
    return ["AAPL", "MSFT", "NVDA"]

def get_all_user_watchlists(user_id):
    """取得所有市場的追蹤清單"""
    return {
        "TW": get_user_watchlist(user_id, "TW"),
        "US": get_user_watchlist(user_id, "US"),
        "CRYPTO": get_user_watchlist(user_id, "CRYPTO")
    }

def save_user_mock_positions(user_id, positions):
    """保存使用者模擬持倉"""
    db = get_db()
    if db:
        try:
            db.collection("users").document(user_id).set({"mock_positions": positions}, merge=True)
            return True
        except Exception as e:
            print(f"Firestore save mock_positions error: {e}")
            
    # 本地備援
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        path = os.path.join(CACHE_DIR, f"mock_positions_{user_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(positions, f, ensure_ascii=False)
    except Exception as e:
        print(f"[Storage] Local mock_positions save failed: {e}")
    return True

def get_user_mock_positions(user_id):
    """取得使用者模擬持倉"""
    db = get_db()
    if db:
        try:
            doc = db.collection("users").document(user_id).get()
            if doc.exists:
                return doc.to_dict().get("mock_positions", [])
        except Exception as e:
            print(f"Firestore load mock_positions error: {e}")
    # 本地備援
    path = os.path.join(CACHE_DIR, f"mock_positions_{user_id}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except:
                return []
    
    # 預設範例持倉 (首次使用者)
    return [
        {
            "symbol": "2330",
            "qty": 1000,
            "buy_price": 1025.0,
            "market": "TW",
            "is_simulation": True
        }
    ]

def save_data_pool(market, data):
    """將海選數據池保存到 GCS (或本地 .pkl)"""
    # 這裡的 data 通常是包含 'dfs' 的大型 dict
    gcs = get_gcs()
    if gcs:
        try:
            bucket = gcs.bucket(f"{PROJECT_ID}-data")
            blob = bucket.blob(f"shared_results_{market}.pkl")
            content = pickle.dumps(data)
            blob.upload_from_string(content)
            return True
        except Exception as e:
            print(f"GCS save error: {e}")
            
    # 本地備援
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        path = os.path.join(CACHE_DIR, f"shared_results_{market}.pkl")
        with open(path, "wb") as f:
            pickle.dump(data, f)
    except Exception as e:
        print(f"[Storage] Local data pool save failed: {e}")
    return True

def load_data_pool(market):
    """從 GCS 加載海選數據池"""
    gcs = get_gcs()
    if gcs:
        try:
            bucket = gcs.bucket(f"{PROJECT_ID}-data")
            blob = bucket.blob(f"shared_results_{market}.pkl")
            if blob.exists():
                content = blob.download_as_string()
                return pickle.loads(content)
        except Exception as e:
            print(f"GCS load error: {e}")
            
    # 本地備援
    path = os.path.join(CACHE_DIR, f"shared_results_{market}.pkl")
    if os.path.exists(path):
        with open(path, "rb") as f:
            return pickle.load(f)
    return None
