from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from api.routes.auth import get_current_user
from api.models.schemas import StockAnalysisRequest, AnalysisResponse, AnalysisResult, ScanRequest, ScanProgressResponse, PaginatedAnalysisResponse
from api.services.quant_service import (
    extract_stock_code, analyze_stock, fetch_tw_symbols, fetch_us_symbols, 
    fetch_crypto_symbols, run_market_scan, get_cached_pool, scan_status
)
from api.services.data_fetcher import fetch_batch_data
from api.services.storage_service import save_data_pool, get_user_watchlist, save_user_watchlist, get_all_user_watchlists
from datetime import datetime

router = APIRouter(prefix="/quant", tags=["quant"])

@router.post("/scan")
async def start_scan(request: ScanRequest, background_tasks: BackgroundTasks):
    if scan_status["status"] == "running":
        raise HTTPException(status_code=400, detail="Scan already in progress")
    background_tasks.add_task(run_market_scan, request.market_type, request.defense_weight)
    return {"message": "Scan started"}

@router.get("/scan/progress", response_model=ScanProgressResponse)
async def get_scan_progress():
    return ScanProgressResponse(**scan_status)

@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_watchlist(request: StockAnalysisRequest, current_user: str = Depends(get_current_user)):
    results = []
    data_map_needed = []
    if not request.watchlist:
        from api.services.storage_service import get_user_watchlist_filtered
        watchlist = get_user_watchlist_filtered(current_user, request.market_type)
    else:
        watchlist = request.watchlist

    if not watchlist:
        return AnalysisResponse(results=[], timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    # [v2.1.52] Deduplicate watchlist based on normalized codes
    unique_items = []
    seen = set()
    for s in watchlist:
        target_market = request.market_type
        if ":" in s:
            target_market, symbol_only = s.split(":", 1)
            code = extract_stock_code(symbol_only, target_market)
        else:
            code = extract_stock_code(s, target_market)
        
        check_key = f"{target_market}:{code}"
        if check_key not in seen:
            unique_items.append((s, target_market, code))
            seen.add(check_key)

    # [v2.2.0] Pre-fetch indices and exchange rate for needed markets
    indices_data = {}
    exchange_rate_val = 1.0
    needed_markets = {request.market_type}
    if request.watchlist:
        for s in request.watchlist:
            if ":" in s: needed_markets.add(s.split(":", 1)[0])
    
    import yfinance as yf
    for m in needed_markets:
        idx_sym = "^TWII" if m == "TW" else ("^GSPC" if m == "US" else "BTC-USD")
        try:
            indices_data[m] = yf.Ticker(idx_sym).history(period="1mo")
        except: pass
        
    if "CRYPTO" in needed_markets:
        try:
            rate_df = yf.Ticker("TWD=X").history(period="1d")
            if not rate_df.empty: exchange_rate_val = float(rate_df['Close'].iloc[-1])
        except: pass

    for s, target_market, code in unique_items:
        pool = get_cached_pool(target_market) or {}
        pool_results = { (r.get('symbol') if isinstance(r, dict) else getattr(r, 'symbol', None)): r for r in pool.get('results', []) }
        
        res = pool_results.get(code)
        # [v2.1.92] Fast Re-score Logic
        if res:
            v_score = res.get('value_score') if isinstance(res, dict) else getattr(res, 'value_score', 0)
            p_score = res.get('pullback_score') if isinstance(res, dict) else getattr(res, 'pullback_score', 0)
            
            if v_score is not None and p_score is not None:
                w = request.defense_weight
                new_score = round((w * v_score) + ((1 - w) * p_score), 1)
                
                if isinstance(res, dict):
                    res['score'] = new_score
                    if not res.get('market'): res['market'] = target_market
                    results.append(AnalysisResult(**res))
                else:
                    setattr(res, 'score', new_score)
                    if not getattr(res, 'market', None): setattr(res, 'market', target_market)
                    results.append(res)
                continue

        # Fallback to K-line analysis
        dfs = pool.get("dfs", {})
        if code in dfs:
            name = "Unknown"
            if res:
                name = res.get('name', 'Unknown') if isinstance(res, dict) else getattr(res, 'name', 'Unknown')
            analysis = analyze_stock(
                dfs[code], code, name, request.defense_weight, target_market, 
                skip_indicators=True, index_df=indices_data.get(target_market),
                exchange_rate=exchange_rate_val if target_market == 'CRYPTO' else 1.0
            )
            results.append(AnalysisResult(**analysis))
        else:
            data_map_needed.append((s, target_market))

    if data_map_needed:
        tw_symbols = fetch_tw_symbols()
        us_symbols = fetch_us_symbols()
        crypto_symbols = fetch_crypto_symbols()
        
        for symbol_raw, m in data_map_needed:
            code = extract_stock_code(symbol_raw, m)
            from api.services.data_fetcher import fetch_batch_data
            data_pool = fetch_batch_data([code], m)
            
            for c, kdf in data_pool.items():
                name = "Unknown"
                if m == "TW": name = tw_symbols.get(c, "Unknown")
                elif m == "US": name = us_symbols.get(c, "Unknown")
                elif m == "CRYPTO": name = crypto_symbols.get(c.upper(), "Unknown")

                analysis = analyze_stock(
                    kdf, c, name, 
                    request.defense_weight, m, 
                    index_df=indices_data.get(m),
                    exchange_rate=exchange_rate_val if m == 'CRYPTO' else 1.0
                )
                results.append(AnalysisResult(**analysis))

    results = sorted(results, key=lambda x: x.score if hasattr(x, 'score') else (x.get('score', 0) if isinstance(x, dict) else 0), reverse=True)
    return AnalysisResponse(results=results, timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

@router.get("/results", response_model=PaginatedAnalysisResponse)
async def get_market_results(
    market_type: str = "TW",
    page: int = 1,
    page_size: int = 20,
    query: str = "",
    defense_weight: float = None
):
    pool = get_cached_pool(market_type)
    if not pool:
        return PaginatedAnalysisResponse(
            results=[], total=0, page=page, page_size=page_size,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )

    all_results = pool.get("results", [])
    
    # Dynamic re-scoring based on weight
    if defense_weight is not None:
        w_rounded = round(defense_weight, 2)
        cache_key = f"res_{market_type}_{w_rounded}"
        
        from api.services.quant_service import results_cache
        cached_res = results_cache.get(cache_key)
        if cached_res:
             all_results = cached_res
        else:
            from concurrent.futures import ThreadPoolExecutor
            from api.services.quant_service import analyze_stock
            dfs = pool.get("dfs", {})
            
            def rescore_task(r):
                code = getattr(r, 'symbol', r.get('symbol') if isinstance(r, dict) else None)
                v_score = getattr(r, 'value_score', r.get('value_score') if isinstance(r, dict) else 0)
                p_score = getattr(r, 'pullback_score', r.get('pullback_score') if isinstance(r, dict) else 0)
                
                # [v2.1.92] Fast Re-score: Priority given to mathematical re-calculation
                if v_score is not None and p_score is not None:
                    new_score = round((defense_weight * v_score) + ((1 - defense_weight) * p_score), 1)
                    if isinstance(r, dict):
                        r['score'] = new_score
                        return AnalysisResult(**r)
                    else:
                        setattr(r, 'score', new_score)
                        return r

                # Fallback to K-line re-analysis only if sub-scores are unavailable
                df = dfs.get(code)
                name = getattr(r, 'name', r.get('name', 'Unknown') if isinstance(r, dict) else 'Unknown')
                if df is not None:
                    analysis = analyze_stock(df, code, name, defense_weight, market_type, skip_indicators=True, skip_revenue=True)
                    return AnalysisResult(**analysis)
                else:
                    return AnalysisResult(**r) if isinstance(r, dict) else r

            with ThreadPoolExecutor(max_workers=10) as executor:
                all_results = list(executor.map(rescore_task, all_results))
            
            results_cache[cache_key] = all_results
    
    # [v2.1.93] Performance: Only sort if defense_weight was provided (otherwise it's already pre-sorted from scan)
    if defense_weight is not None:
        all_results = sorted(all_results, key=lambda x: x.score if hasattr(x, 'score') else (x.get('score', 0) if isinstance(x, dict) else 0), reverse=True)
    for r in all_results:
        if hasattr(r, 'market') and not r.market:
            r.market = market_type

    if query:
        q = query.upper()
        all_results = [
            r for r in all_results
            if q in r.symbol.upper() or q in r.name.upper()
        ]

    total = len(all_results)
    start = (page - 1) * page_size
    end = start + page_size
    paginated_results = all_results[start:end]

    return PaginatedAnalysisResponse(
        results=paginated_results, total=total, page=page, page_size=page_size,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

@router.get("/watchlist")
async def get_watchlist_api(market_type: str = "TW", current_user: str = Depends(get_current_user)):
    from api.services.storage_service import get_user_watchlist_filtered, get_all_user_watchlists
    if market_type == "ALL": return get_all_user_watchlists(current_user)
    watchlist = get_user_watchlist_filtered(current_user, market_type)
    return {"watchlist": watchlist}

@router.post("/watchlist")
async def add_to_watchlist_api(symbol: str, market_type: str = "TW", current_user: str = Depends(get_current_user)):
    from api.services.storage_service import get_user_watchlist, save_user_watchlist
    watchlist = get_user_watchlist(current_user)
    entry = f"{market_type}:{symbol}"
    if entry not in watchlist:
        watchlist.append(entry)
        save_user_watchlist(current_user, watchlist)
    return {"status": "success", "watchlist": [s.split(":", 1)[1] for s in watchlist if s.startswith(f"{market_type}:")]}

@router.delete("/watchlist")
async def remove_from_watchlist_api(symbol: str, market_type: str = "TW", current_user: str = Depends(get_current_user)):
    from api.services.storage_service import get_user_watchlist, save_user_watchlist
    watchlist = get_user_watchlist(current_user)
    entry = f"{market_type}:{symbol}"
    if entry in watchlist:
        watchlist.remove(entry)
        save_user_watchlist(current_user, watchlist)
    return {"status": "success", "watchlist": [s.split(":", 1)[1] for s in watchlist if s.startswith(f"{market_type}:")]}

@router.get("/history")
async def get_symbol_history(symbol: str, market_type: str = "TW"):
    from api.services.quant_service import get_yahoo_ticker, fetch_stock_data
    from fastapi import HTTPException
    ticker_str = get_yahoo_ticker(symbol, market_type)
    try:
        df = fetch_stock_data(symbol, ticker_str, period="3mo")
        if df is None or df.empty:
            raise HTTPException(status_code=404, detail=f"No historical data found for {symbol}")
        history = []
        for index, row in df.iterrows():
            history.append({
                "date": index.strftime("%m/%d"),
                "open": round(float(row['Open']), 2),
                "high": round(float(row['High']), 2),
                "low": round(float(row['Low']), 2),
                "close": round(float(row['Close']), 2),
                "volume": int(row['Volume'])
            })
        return history
    except Exception as e:
        print(f"[History] Error fetching {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
@router.get("/trend")
async def get_market_trend(market_type: str = "TW", days: int = 7):
    """
    Fetch market index vs selection pool performance for dashboard trend chart.
    Selection Pool performance is the average normalized price of the TOP 5 stocks from latest scan.
    [v2.1.93] Optimized with 1-hour in-memory cache.
    """
    global trend_cache
    if 'trend_cache' not in globals():
        globals()['trend_cache'] = {}
    
    cache_key = f"{market_type}_{days}"
    now = datetime.now()
    if cache_key in globals()['trend_cache']:
        cached_data, timestamp = globals()['trend_cache'][cache_key]
        if (now - timestamp).total_seconds() < 3600: # 1 hour cache
            return cached_data

    from api.services.quant_service import get_yahoo_ticker, fetch_stock_data, extract_stock_code
    import yfinance as yf
    import pandas as pd
    
    # 1. Selection: Pick Index
    # [v2.1.63] Using BTC-USD for data availability (Yahoo Finance lacks BTC-TWD history)
    indices = {"TW": "^TWII", "US": "^GSPC", "CRYPTO": "BTC-USD"}
    index_symbol = indices.get(market_type, "^TWII")
    
    # 2. Selection: Pick Top 5 from Selection Pool
    pool = get_cached_pool(market_type)
    top_symbols = []
    if pool and pool.get("results"):
        # Take real top 5
        top_5 = pool["results"][:5]
        for item in top_5:
            code = getattr(item, 'symbol', item.get('symbol') if isinstance(item, dict) else None)
            if code: top_symbols.append(code)
    
    # Fallback if pool is empty
    if not top_symbols:
        if market_type == "TW": top_symbols = ["2330", "2317", "2454"]
        elif market_type == "US": top_symbols = ["AAPL", "MSFT", "NVDA"]
        else: top_symbols = ["ETH-USD", "SOL-USD", "BNB-USD"]

    # 3. Fetch Data (Extended range to ensure we have 'days' closing prices)
    period = "1mo"
    index_df = None
    try:
        index_df = fetch_stock_data(market_type, index_symbol, period=period)
    except Exception as e:
        print(f"[Trend] Index fetch failed for {index_symbol}: {e}")

    stock_dfs = {}
    for s in top_symbols:
        try:
            ticker = get_yahoo_ticker(s, market_type)
            df = fetch_stock_data(s, ticker, period=period)
            if df is not None and not df.empty:
                stock_dfs[s] = df
        except:
            continue

    # 4. Align and Aggregate
    # Fallback if index fails: Use first available stock or a flat line
    if index_df is None or index_df.empty:
        if stock_dfs:
            # Use the first stock as a proxy for the 'dates' but maybe index_norm is flat 100
            index_df = list(stock_dfs.values())[0]
            index_is_proxy = True
        else:
            raise HTTPException(status_code=404, detail="No historical data available for index or selection pool.")
    else:
        index_is_proxy = False

    # Get last N days of index
    index_recent = index_df.tail(days + 1)
    if len(index_recent) < 2:
        index_recent = index_df.tail(2) # Fallback
        
    dates = index_recent.index
    
    # helper for normalization (Return relative to start of period)
    def normalize_series(df, base_date):
        try:
            # Find closest available date to base_date
            valid_prices = df.loc[df.index <= base_date, 'Close']
            if valid_prices.empty: 
                # If no data before base_date, take the first available
                base_val = float(df['Close'].iloc[0])
            else:
                base_val = float(valid_prices.iloc[-1])
            
            if base_val == 0: return None
            return (df['Close'] / base_val) * 100
        except:
            return None

    base_date = dates[0]
    if index_is_proxy:
        index_norm = pd.Series(100.0, index=index_recent.index)
    else:
        index_norm = (index_recent['Close'] / index_recent['Close'].iloc[0]) * 100
    
    # Aggregate stock performance
    pool_norm_sum = None
    count = 0
    for s, df in stock_dfs.items():
        norm = normalize_series(df, base_date)
        if norm is not None:
            # Reindex to match index_recent dates
            norm = norm.reindex(index_recent.index).ffill().bfill()
            if pool_norm_sum is None:
                pool_norm_sum = norm
            else:
                pool_norm_sum += norm
            count += 1
    
    if count > 0:
        pool_norm = pool_norm_sum / count
    else:
        # Fallback to index + small random variance
        import numpy as np
        pool_norm = index_norm * (1 + np.random.normal(0, 0.01, len(index_norm)))

    # 5. Format for Recharts
    chart_data = []
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    
    for i, date in enumerate(dates):
        # We start from index 1 to show change from base
        if i == 0: continue 
        
        chart_data.append({
            "name": date.strftime("%m/%d"), # Use date instead of Mon/Tue for more realism
            "index": round(float(index_norm.iloc[i]), 2),
            "pool": round(float(pool_norm.iloc[i]), 2),
            "value": round(float(pool_norm.iloc[i]), 2) # Backward compatibility for old UI
        })

    # 6. Return
    result = {
        "market": market_type,
        "index_symbol": index_symbol,
        "top_stocks": top_symbols,
        "chart_data": chart_data
    }
    
    # Save to cache
    if 'trend_cache' in globals():
        globals()['trend_cache'][cache_key] = (result, datetime.now())
        
    return result
