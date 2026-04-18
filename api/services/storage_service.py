import os
import json
import random
import pickle
import time
from datetime import datetime
from typing import Dict, List, Optional
from google.cloud import storage, firestore
from api.config import PROJECT_ID, CACHE_DIR, SYNC_DIR
from api.services.strategy_accounts import list_strategy_account_ids

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

def save_user_settings(user_id, settings):
    db = get_db()
    if db:
        try:
            db.collection("users").document(user_id).set({"settings": settings}, merge=True)
            return True
        except Exception as e:
            print(f"Firestore save settings error: {e}")
    return False

def get_user_settings(user_id):
    db = get_db()
    default_settings = {
        "email_notifications_enabled": True,
        "mirror_trading_confirmed": False,
        "total_allocation_pct": 10.0,
        "sip_amount_twd": 10000.0,
        "strategy_ratio": 0.5,
        "max_order_limit": 50000.0,
        "tp_pct": 20.0,
        "sl_pct": -5.0
    }
    if db:
        try:
            doc = db.collection("users").document(user_id).get()
            if doc.exists:
                data = doc.to_dict().get("settings", {})
                # Merge with defaults
                return {**default_settings, **data}
        except Exception as e:
            print(f"Firestore load settings error: {e}")
    return default_settings

def get_all_users_for_notifications():
    """Returns list of (email, user_id) for users with notifications enabled."""
    db = get_db()
    targets = []
    if db:
        try:
            docs = db.collection("users").stream()
            for doc in docs:
                data = doc.to_dict()
                settings = data.get("settings", {})
                # Default to True if not explicitly disabled
                if settings.get("email_notifications_enabled", True):
                    # For this system, user_id is the email
                    user_id = doc.id
                    if "@" in user_id:
                        targets.append((user_id, user_id))
        except Exception as e:
            print(f"Error fetching notification targets: {e}")
    return targets

def get_all_users_with_auto_trade():
    """Returns list of user IDs for users with auto_trade_enabled."""
    db = get_db()
    targets = []
    if db:
        try:
            docs = db.collection("users").stream()
            for doc in docs:
                data = doc.to_dict()
                creds = data.get("credentials", {})
                if creds.get("auto_trade_enabled", False):
                    targets.append(doc.id)
        except Exception as e:
            print(f"Error fetching auto-trade users: {e}")
    return targets

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
        # [v2.1.53] Ensure all entries are normalized with MARKET: prefix
        normalized = []
        changed = False
        for s in watchlist:
            if ":" in s:
                normalized.append(s)
            else:
                # Deduce market
                from api.services.quant_service import extract_stock_code
                if s.isdigit(): m = "TW"
                elif "-" in s or "USDT" in s.upper() or "TWD" in s.upper(): m = "CRYPTO"
                else: m = "US"
                # Standardize
                normalized.append(f"{m}:{s}")
                changed = True
        
        if changed:
            # Deduplicate while preserving order (using dict as an ordered set)
            unique_normalized = list(dict.fromkeys(normalized))
            save_user_watchlist(user_id, unique_normalized)
            return unique_normalized
        return normalized

    # Local fallback
    path = os.path.join(CACHE_DIR, f"watchlist_{user_id}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
            
    # Default initial list
    return ["TW:2330", "TW:2317", "US:AAPL", "US:NVDA", "CRYPTO:BTC-USD"]

def get_user_watchlist_filtered(user_id, market):
    """Helper to get only symbols for a specific market from unified list with legacy fallback"""
    full = get_user_watchlist(user_id)
    if market == "ALL":
        return full
        
    results = []
    for s in full:
        if ":" in s:
            m, sym = s.split(":", 1)
            if m == market:
                results.append(sym)
        else:
            # [v2.1.52] Fallback for entries without ":" prefix
            if market == "TW" and s.isdigit():
                results.append(s)
            elif market == "CRYPTO" and ("-" in s or "USDT" in s.upper() or "TWD" in s.upper()):
                results.append(s)
            elif market == "US" and not s.isdigit() and "-" not in s:
                results.append(s)
    return results

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
            def to_dict(obj):
                if hasattr(obj, 'model_dump'): return obj.model_dump()
                if hasattr(obj, 'dict'): return obj.dict()
                return obj
            plain_logs = [to_dict(L) if not isinstance(L, dict) else L for L in logs]
            db.collection("users").document(user_id).set({"trade_logs": plain_logs}, merge=True)
        except Exception as e:
            print(f"Firestore save trade_logs error for {user_id}: {e}")
    
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
                        logs.append({**order, "entry_type": "PENDING", "status": "OPEN", "trade_id": order.get("trade_id") or order.get("order_id") or f"ORDR-{int(time.time())}-{random.randint(100,999)}"})
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
    
    if logs:
        # Repair Loop: Ensure every entry has a trade_id
        repaired = False
        for L in logs:
            if not L.get("trade_id"):
                L["trade_id"] = L.get("order_id") or f"FIX-{int(time.time())}-{random.randint(100,999)}"
                repaired = True
        if repaired:
            print(f"[Storage] Repaired {user_id} logs with missing trade_ids.")
            save_user_trade_logs(user_id, logs)
        return logs

    # Local fallback: Only if Firestore returned nothing or empty list
    path = os.path.join(CACHE_DIR, f"trade_logs_{user_id}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try:
                local_logs = json.load(f)
                if local_logs:
                    print(f"[Storage] Using local fallback for {user_id} (count: {len(local_logs)})")
                    return local_logs
            except:
                pass
    return []

def get_all_users_with_pending() -> List[str]:
    """Retrieve all user IDs that have PENDING orders in their trade logs."""
    db = get_db()
    users_with_pending = []
    if db:
        try:
            docs = db.collection("users").stream()
            for doc in docs:
                data = doc.to_dict()
                logs = data.get("trade_logs", [])
                if any(L.get("entry_type") == "PENDING" for L in logs):
                    users_with_pending.append(doc.id)
        except Exception as e:
            print(f"[Storage] Error discovering pending users: {e}")
    # Always include strategy accounts if they have pending orders
    for system_user in list_strategy_account_ids():
        if system_user not in users_with_pending:
            logs = get_user_trade_logs(system_user)
            if any(L.get("entry_type") == "PENDING" for L in logs):
                users_with_pending.append(system_user)
    return list(set(users_with_pending))

def save_robot_status(status_dict):
    """Persist AutoRobot state for UI visibility."""
    db = get_db()
    if db:
        try:
            db.collection("users").document("system_auto").set({
                "robot_status": {
                    **status_dict,
                    "last_updated": datetime.now().isoformat()
                }
            }, merge=True)
        except Exception as e:
            print(f"[Storage] Failed to save robot status: {e}")

def get_robot_status():
    """Retrieve AutoRobot state."""
    db = get_db()
    if db:
        try:
            doc = db.collection("users").document("system_auto").get()
            if doc.exists:
                return doc.to_dict().get("robot_status", {})
        except:
            pass
    return {}

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
            # Relocate scans to system_auto/market_scans/[MARKET]
            results = data.get("results", [])
            # Convert results to dict safely (handles Pydantic models)
            def to_dict(obj):
                if hasattr(obj, 'model_dump'): return obj.model_dump()
                if hasattr(obj, 'dict'): return obj.dict()
                return obj

            plain_results = [to_dict(r) for r in results]
            
            db.collection("users").document("system_auto").collection("market_scans").document(market).set({
                "results": plain_results,
                "timestamp": datetime.now().isoformat(),
                "market": market
            })
            print(f"[Storage] Successfully saved {len(plain_results)} scan results to Firestore for {market}")
        except Exception as e:
            print(f"[Storage] Firestore scan result save error for {market}: {e}")
            import traceback
            traceback.print_exc()

    try:
        path = os.path.join(CACHE_DIR, f"shared_results_{market}.pkl")
        with open(path, "wb") as f:
            pickle.dump(data, f)
    except Exception as e:
        print(f"[Storage] Local data pool save failed: {e}")
    return True

def load_data_pool(market):
    """
    Load data pool with a layered approach:
    1. Try GCS (Full Pickle - results + dfs)
    2. Try Local CACHE_DIR (Full Pickle)
    3. Try Firestore (Results Summary only)
    """
    final_pool = None
    
    # Layer 1: GCS (Full)
    gcs = get_gcs()
    if gcs:
        try:
            bucket = gcs.bucket(f"{PROJECT_ID}-data")
            blob = bucket.blob(f"shared_results_{market}.pkl")
            if blob.exists():
                final_pool = pickle.loads(blob.download_as_string())
                final_pool["metadata"] = {"source": "gcs", "timestamp": final_pool.get("timestamp")}
        except Exception as e:
            print(f"[Storage] GCS load fallback: {e}")

    # Layer 2: Local Pickle (Full) - If GCS failed or not used
    if not final_pool:
        path = os.path.join(CACHE_DIR, f"shared_results_{market}.pkl")
        if os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    final_pool = pickle.load(f)
                    final_pool["metadata"] = {"source": "local", "timestamp": final_pool.get("timestamp")}
            except Exception as e:
                print(f"[Storage] Local pickle corrupt: {e}")

    # Layer 3: Firestore (Results Only) - High availability
    # We always check Firestore to see if results are NEWER than the pickle
    db = get_db()
    if db:
        try:
            # Try new system_auto path first
            doc = db.collection("users").document("system_auto").collection("market_scans").document(market).get()
            if not doc.exists:
                # Fallback to legacy
                doc = db.collection("scans").document(market).get()
            
            if doc.exists:
                fs_data = doc.to_dict()
                fs_results = fs_data.get("results", [])
                fs_ts = fs_data.get("timestamp")
                
                if not final_pool:
                    final_pool = {"results": fs_results, "dfs": {}, "timestamp": fs_ts, "metadata": {"source": "firestore"}}
                else:
                    # Merge logic: if Firestore is newer than pickle, use Firestore results but KEEP pickle dfs
                    pickle_ts = final_pool.get("timestamp", "0")
                    if fs_ts and fs_ts > pickle_ts:
                        print(f"[Storage] {market} Firestore results are newer than local pickle. Merging.")
                        final_pool["results"] = fs_results
                        final_pool["timestamp"] = fs_ts
                        final_pool["metadata"]["merged_from"] = "firestore"
        except Exception as e:
            print(f"[Storage] Firestore summary check failed: {e}")

    return final_pool

def acquire_daily_trade_lock(market: str, current_time: datetime, user_id: str = "system_auto") -> bool:
    """
    Attempts to acquire an atomic distributed lock for the daily auto-trade.
    Prevents multiple Cloud Run instances from executing the trade concurrently.
    """
    db = get_db()
    if not db:
        return True # Fallback for local simulation
        
    date_str = current_time.strftime("%Y-%m-%d")
    lock_id = f"{market}_{date_str}"
    
    try:
        from google.cloud import exceptions
        doc_ref = db.collection("users").document(user_id).collection("locks").document(lock_id)
        # create() atomically throws an Exception if the document already exists.
        doc_ref.create({
            "locked_at": current_time.isoformat(),
            "market": market,
            "date": date_str,
            "user_id": user_id,
        })
        print(f"[Storage] Successfully acquired distributed lock for {user_id}:{lock_id}")
        return True
    except exceptions.Conflict:
        print(f"[Storage] Lock for {user_id}:{lock_id} is currently held by another instance. Skipping duplicate execution.")
        return False
    except Exception as e:
        print(f"[Storage] Distributed lock acquisition error (allowing fallback execution): {e}")
        return True
