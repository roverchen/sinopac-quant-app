import os
import json
import pickle
from google.cloud import storage, firestore
from api.config import PROJECT_ID, CACHE_DIR

# 初始化 Firestore 用戶端
try:
    db = firestore.Client(project=PROJECT_ID)
except Exception as e:
    print(f"[Storage] Firestore client failed: {e}. Falling back to local.")
    db = None

# 初始化 GCS 用戶端
try:
    gcs = storage.Client(project=PROJECT_ID)
except Exception as e:
    print(f"[Storage] GCS client failed: {e}. Falling back to local.")
    gcs = None

def update_user_credentials(user_id, creds):
    """保存憑證：優先使用 Firestore，失敗則存入本地 JSON"""
    if db:
        try:
            db.collection("users").document(user_id).set({"credentials": creds}, merge=True)
            return True
        except Exception as e:
            print(f"Firestore save error: {e}")
    
    # 本地備援
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, f"creds_{user_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(creds, f, ensure_ascii=False)
    return True

def get_user_credentials(user_id):
    """加載憑證：優先從 Firestore 讀取"""
    if db:
        try:
            doc = db.collection("users").document(user_id).get()
            if doc.exists:
                return doc.to_dict().get("credentials", {})
        except Exception as e:
            print(f"Firestore load error: {e}")
            
    # 本地備援
    path = os.path.join(CACHE_DIR, f"creds_{user_id}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

#保留舊名稱別名以相容舊路由
load_credentials = get_user_credentials
save_credentials = update_user_credentials

def save_user_watchlist(user_id, market, watchlist):
    """保存使用者追蹤清單"""
    if db:
        try:
            db.collection("users").document(user_id).set({f"watchlist_{market}": watchlist}, merge=True)
            return True
        except Exception as e:
            print(f"Firestore save watchlist error: {e}")
            
    # 本地備援
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, f"watchlist_{market}_{user_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(watchlist, f, ensure_ascii=False)
    return True

def get_user_watchlist(user_id, market):
    """取得使用者追蹤清單"""
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
    return ["2330", "2317", "0050"] if market == "TW" else ["AAPL", "MSFT", "NVDA"]

def save_data_pool(market, data):
    """將海選數據池保存到 GCS (或本地 .pkl)"""
    # 這裡的 data 通常是包含 'dfs' 的大型 dict
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
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, f"shared_results_{market}.pkl")
    with open(path, "wb") as f:
        pickle.dump(data, f)
    return True

def load_data_pool(market):
    """從 GCS 加載海選數據池"""
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
