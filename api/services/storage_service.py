import os
import json
import pickle
import time
from typing import Dict, List, Optional
from google.cloud import storage, firestore
from api.config import PROJECT_ID, CACHE_DIR, SYNC_DIR

# Ensure directories exist
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(SYNC_DIR, exist_ok=True)

# Delayed initialization of Firestore client
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

# Delayed initialization of GCS client
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
    # Save credentials: Prioritize Firestore, fallback to local JSON
    db = get_db()
    if db:
        try:
            db.collection("users").document(user_id).set({"credentials": creds}, merge=True)
            return True
        except Exception as e:
            print(f"Firestore save error: {e}")

    # Local fallback
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        path = os.path.join(CACHE_DIR, f"creds_{user_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(creds, f, ensure_ascii=False)
    except Exception as e:
        print(f"[Storage] Local credentials save failed: {e}")
    return True

def get_user_credentials(user_id):
    # Load credentials: Prioritize Firestore
    db = get_db()
    creds = {}
    if db:
        try:
            doc = db.collection("users").document(user_id).get()
            if doc.exists:
                creds = doc.to_dict().get("credentials", {})
        except Exception as e:
            print(f"Firestore load error: {e}")

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

load_credentials = get_user_credentials
save_credentials = update_user_credentials

def save_user_watchlist(user_id, market, watchlist):
    # Save user watchlist
    db = get_db()
    if db:
        try:
            db.collection("users").document(user_id).set({f"watchlist_{market}": watchlist}, merge=True)
            return True
        except Exception as e:
            print(f"Firestore save watchlist error: {e}")

    try:
        path = os.path.join(CACHE_DIR, f"watchlist_{market}_{user_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(watchlist, f, ensure_ascii=False)
    except Exception as e:
        print(f"[Storage] Local watchlist save failed: {e}")
    return True

def get_user_watchlist(user_id, market):
    # Retrieve user watchlist
    db = get_db()
    if db:
        try:
            doc = db.collection("users").document(user_id).get()
            if doc.exists:
                return doc.to_dict().get(f"watchlist_{market}", [])
        except Exception as e:
            print(f"Firestore load watchlist error: {e}")
    
    path = os.path.join(CACHE_DIR, f"watchlist_{market}_{user_id}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    if market == "TW": return ["2330", "2317", "0050"]
    if market == "CRYPTO": return ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "DOGE-USD"]
    return ["AAPL", "MSFT", "NVDA"]

def get_all_user_watchlists(user_id):
    return {
        "TW": get_user_watchlist(user_id, "TW"),
        "US": get_user_watchlist(user_id, "US"),
        "CRYPTO": get_user_watchlist(user_id, "CRYPTO")
    }

def save_user_mock_positions(user_id, positions):
    # Save user mock positions
    db = get_db()
    success = False
    if db:
        try:
            db.collection("users").document(user_id).set({"mock_positions": json.loads(json.dumps(positions))}, merge=True)
            success = True
        except Exception as e:
            print(f"Firestore save mock_positions error: {e}")

    # Fallback/Mirror to local
    try:
        path = os.path.join(CACHE_DIR, f"mock_positions_{user_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(positions, f, ensure_ascii=False)
    except Exception as e:
        print(f"[Storage] Local mock_positions save failed: {e}")
    return True

def get_user_mock_positions(user_id):
    db = get_db()
    if db:
        try:
            doc = db.collection("users").document(user_id).get()
            if doc.exists:
                return doc.to_dict().get("mock_positions", [])
        except Exception as e:
            print(f"Firestore load mock_positions error: {e}")
    
    path = os.path.join(CACHE_DIR, f"mock_positions_{user_id}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try: return json.load(f)
            except: return []
    return [{"symbol": "2330", "qty": 1000, "buy_price": 1025.0, "market": "TW", "is_simulation": True}]

def get_all_users_with_pending() -> List[str]:
    # Retrieve a list of all user IDs that have pending orders
    users = []
    # Local scan
    if os.path.exists(CACHE_DIR):
        for filename in os.listdir(CACHE_DIR):
            if filename.startswith("pending_orders_") and filename.endswith(".json"):
                user_id = filename.replace("pending_orders_", "").replace(".json", "")
                if user_id:
                    users.append(user_id)
    # Firestore scan
    db = get_db()
    if db:
        try:
            docs = db.collection("users").stream()
            for doc in docs:
                if doc.to_dict().get("pending_orders"):
                    users.append(doc.id)
        except: pass
    return list(set(users))

def save_user_pending_orders(user_id, orders):
    db = get_db()
    if db:
        try:
            db.collection("users").document(user_id).set({"pending_orders": orders}, merge=True)
            return True
        except Exception as e:
            print(f"Firestore save pending_orders error: {e}")

    try:
        path = os.path.join(CACHE_DIR, f"pending_orders_{user_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(orders, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Storage] Local pending_orders save failed: {e}")
    return True

def get_user_pending_orders(user_id):
    db = get_db()
    if db:
        try:
            doc = db.collection("users").document(user_id).get()
            if doc.exists:
                return doc.to_dict().get("pending_orders", [])
        except Exception as e:
            print(f"Firestore load pending_orders error: {e}")
    
    path = os.path.join(CACHE_DIR, f"pending_orders_{user_id}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try: return json.load(f)
            except: return []
    return []

def save_user_trade_history(user_id, history):
    # Save user trade history
    db = get_db()
    if db:
        try:
            # Firestore has a 1MB limit per document. If history is HUGE, we might need a sub-collection.
            # But for simple trading, 1MB is enough for ~2000-5000 records.
            db.collection("users").document(user_id).set({"trade_history": json.loads(json.dumps(history))}, merge=True)
        except Exception as e:
            print(f"Firestore save trade_history error: {e}")

    # Fallback/Mirror
    try:
        path = os.path.join(CACHE_DIR, f"trade_history_{user_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Storage] Local trade_history save failed: {e}")
    return True

def get_user_trade_history(user_id):
    db = get_db()
    if db:
        try:
            doc = db.collection("users").document(user_id).get()
            if doc.exists:
                return doc.to_dict().get("trade_history", [])
        except Exception as e:
            print(f"Firestore load trade_history error: {e}")
            
    path = os.path.join(CACHE_DIR, f"trade_history_{user_id}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try: return json.load(f)
            except: return []
    return []

def save_data_pool(market, data):
    gcs = get_gcs()
    if gcs:
        try:
            bucket_name = f"{PROJECT_ID}-data"
            bucket = gcs.bucket(bucket_name)
            if not bucket.exists():
                print(f"[Storage] Creating missing bucket: {bucket_name}")
                bucket = gcs.create_bucket(bucket_name, location="asia-east1")
            
            blob = bucket.blob(f"shared_results_{market}.pkl")
            content = pickle.dumps(data)
            blob.upload_from_string(content)
            return True
        except Exception as e:
            print(f"GCS save error: {e}")

    try:
        path = os.path.join(CACHE_DIR, f"shared_results_{market}.pkl")
        with open(path, "wb") as f:
            pickle.dump(data, f)
    except Exception as e:
        print(f"[Storage] Local data pool save failed: {e}")
    return True

def load_data_pool(market):
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

    path = os.path.join(CACHE_DIR, f"shared_results_{market}.pkl")
    if os.path.exists(path):
        with open(path, "rb") as f:
            return pickle.load(f)
    return None
