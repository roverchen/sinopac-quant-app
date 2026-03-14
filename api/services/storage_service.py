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

def save_user_watchlist(user_id, watchlist):
    """
    Save unified watchlist. 
    Format: list of strings "MARKET:SYMBOL" (e.g., "TW:2330")
    """
    db = get_db()
    if db:
        try:
            db.collection("users").document(user_id).set({"watchlist": watchlist}, merge=True)
            return True
        except Exception as e:
            print(f"Firestore save watchlist error: {e}")

    try:
        path = os.path.join(CACHE_DIR, f"watchlist_{user_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(watchlist, f, ensure_ascii=False)
    except Exception as e:
        print(f"[Storage] Local watchlist save failed: {e}")
    return True

def get_user_watchlist(user_id):
    """
    Retrieve unified watchlist. Performs lazy migration if needed.
    """
    db = get_db()
    watchlist = None
    
    if db:
        try:
            doc = db.collection("users").document(user_id).get()
            if doc.exists:
                data = doc.to_dict()
                watchlist = data.get("watchlist")
                
                # Lazy migration from old fields
                if watchlist is None:
                    tw = data.get("watchlist_TW", [])
                    us = data.get("watchlist_US", [])
                    crypto = data.get("watchlist_CRYPTO", [])
                    if tw or us or crypto:
                        watchlist = []
                        for s in tw: watchlist.append(f"TW:{s}")
                        for s in us: watchlist.append(f"US:{s}")
                        for s in crypto: watchlist.append(f"CRYPTO:{s}")
                        # Save back the migrated version
                        save_user_watchlist(user_id, watchlist)
        except Exception as e:
            print(f"Firestore load watchlist error: {e}")
    
    if watchlist is not None:
        return watchlist

    # Local fallback
    path = os.path.join(CACHE_DIR, f"watchlist_{user_id}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
            
    # Default initial list
    return ["TW:2330", "TW:2317", "US:AAPL", "US:NVDA", "CRYPTO:BTC-USD"]

def get_user_watchlist_filtered(user_id, market):
    """Helper to get only symbols for a specific market from unified list"""
    full = get_user_watchlist(user_id)
    if market == "ALL":
        return [s.split(":", 1)[1] for s in full if ":" in s]
    return [s.split(":", 1)[1] for s in full if s.startswith(f"{market}:")]

def get_all_user_watchlists(user_id):
    full = get_user_watchlist(user_id)
    return {
        "TW": [s.split(":", 1)[1] for s in full if s.startswith("TW:")],
        "US": [s.split(":", 1)[1] for s in full if s.startswith("US:")],
        "CRYPTO": [s.split(":", 1)[1] for s in full if s.startswith("CRYPTO:")]
    }

def save_user_trade_logs(user_id, logs):
    """Save unified trade logs (positions, pending, history)"""
    db = get_db()
    if db:
        try:
            db.collection("users").document(user_id).set({"trade_logs": json.loads(json.dumps(logs))}, merge=True)
        except Exception as e:
            print(f"Firestore save trade_logs error: {e}")
    
    try:
        path = os.path.join(CACHE_DIR, f"trade_logs_{user_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Storage] Local trade_logs save failed: {e}")
    return True

def get_user_trade_logs(user_id):
    """Retrieve unified trade logs. Performs lazy migration if needed."""
    db = get_db()
    logs = None
    if db:
        try:
            doc = db.collection("users").document(user_id).get()
            if doc.exists:
                data = doc.to_dict()
                logs = data.get("trade_logs")
                
                # Lazy migration from old fields
                if logs is None:
                    print(f"[Storage] Migrating legacy data for {user_id}...")
                    logs = []
                    # 1. Positions
                    for pos in data.get("mock_positions", []):
                        logs.append({**pos, "entry_type": "POSITION", "status": "OPEN", "trade_id": pos.get("trade_id", f"POS-{int(time.time())}")})
                    # 2. Pending
                    for order in data.get("pending_orders", []):
                        logs.append({**order, "entry_type": "PENDING", "status": "OPEN"})
                    # 3. History
                    for hist in data.get("trade_history", []):
                        logs.append({**hist, "entry_type": "HISTORY", "status": "FILLED"})
                    
                    if logs:
                        save_user_trade_logs(user_id, logs)
                
                # Cleanup legacy fields if logs were successfully retrieved/migrated
                if logs is not None and any(k in data for k in ["mock_positions", "pending_orders", "trade_history"]):
                    print(f"[Storage] Cleaning up legacy fields for {user_id}...")
                    from google.cloud import firestore
                    db.collection("users").document(user_id).update({
                        "mock_positions": firestore.DELETE_FIELD,
                        "pending_orders": firestore.DELETE_FIELD,
                        "trade_history": firestore.DELETE_FIELD
                    })
        except Exception as e:
            print(f"Firestore load trade_logs error: {e}")
    
    if logs is not None:
        return logs

    # Local fallback
    path = os.path.join(CACHE_DIR, f"trade_logs_{user_id}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try: return json.load(f)
            except: return []
    return []

# Wrapper functions to maintain compatibility while shifting to trade_logs
def save_user_mock_positions(user_id, positions):
    logs = get_user_trade_logs(user_id)
    # Remove old positions, add new ones
    logs = [L for L in logs if L.get("entry_type") != "POSITION"]
    for p in positions:
        logs.append({**p, "entry_type": "POSITION", "status": "OPEN"})
    return save_user_trade_logs(user_id, logs)

def get_user_mock_positions(user_id):
    logs = get_user_trade_logs(user_id)
    return [L for L in logs if L.get("entry_type") == "POSITION"]

def save_user_pending_orders(user_id, orders):
    logs = get_user_trade_logs(user_id)
    logs = [L for L in logs if L.get("entry_type") != "PENDING"]
    for o in orders:
        logs.append({**o, "entry_type": "PENDING", "status": "OPEN"})
    return save_user_trade_logs(user_id, logs)

def get_user_pending_orders(user_id):
    logs = get_user_trade_logs(user_id)
    return [L for L in logs if L.get("entry_type") == "PENDING"]

def save_user_trade_history(user_id, history):
    logs = get_user_trade_logs(user_id)
    logs = [L for L in logs if L.get("entry_type") != "HISTORY"]
    for h in history:
        logs.append({**h, "entry_type": "HISTORY", "status": "FILLED"})
    return save_user_trade_logs(user_id, logs)

def get_user_trade_history(user_id):
    logs = get_user_trade_logs(user_id)
    return [L for L in logs if L.get("entry_type") == "HISTORY"]
            
    path = os.path.join(CACHE_DIR, f"trade_history_{user_id}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try: return json.load(f)
            except: return []
    return []

def save_data_pool(market, data):
    # GCS persist (Primary for multi-instance)
    gcs = get_gcs()
    if gcs:
        try:
            bucket_name = f"{PROJECT_ID}-data"
            bucket = gcs.bucket(bucket_name)
            if not bucket.exists():
                bucket = gcs.create_bucket(bucket_name, location="asia-east1")
            blob = bucket.blob(f"shared_results_{market}.pkl")
            blob.upload_from_string(pickle.dumps(data))
        except Exception as e:
            print(f"GCS save error: {e}")

    # Firestore persist (Alternative for results list only - lightweight)
    db = get_db()
    if db:
        try:
            # We only store the 'results' part in Firestore as it's JSON serializable
            # and what the frontend mostly needs.
            results = data.get("results", [])
            db.collection("scans").document(market).set({
                "results": json.loads(json.dumps(results)),
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            print(f"Firestore scan result save error: {e}")

    try:
        path = os.path.join(CACHE_DIR, f"shared_results_{market}.pkl")
        with open(path, "wb") as f:
            pickle.dump(data, f)
    except Exception as e:
        print(f"[Storage] Local data pool save failed: {e}")
    return True

def load_data_pool(market):
    # Try GCS
    gcs = get_gcs()
    if gcs:
        try:
            bucket = gcs.bucket(f"{PROJECT_ID}-data")
            blob = bucket.blob(f"shared_results_{market}.pkl")
            if blob.exists():
                return pickle.loads(blob.download_as_string())
        except Exception as e:
            print(f"GCS load error: {e}")

    # Try Firestore
    db = get_db()
    if db:
        try:
            doc = db.collection("scans").document(market).get()
            if doc.exists:
                scan_data = doc.to_dict()
                return {"results": scan_data.get("results", []), "metadata": {"source": "firestore"}}
        except Exception as e:
            print(f"Firestore scan result load error: {e}")

    path = os.path.join(CACHE_DIR, f"shared_results_{market}.pkl")
    if os.path.exists(path):
        with open(path, "rb") as f:
            return pickle.load(f)
    return None
