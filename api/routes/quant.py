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
    if not request.watchlist:
        from api.services.storage_service import get_user_watchlist_filtered
        watchlist = get_user_watchlist_filtered(current_user, request.market_type)
    else:
        watchlist = request.watchlist

    if not watchlist:
        return AnalysisResponse(results=[], timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    pool = get_cached_pool(request.market_type) or {}
    pool_results = {r.symbol: r for r in pool.get("results", [])}
    dfs = pool.get("dfs", {})

    results = []
    data_map_needed = []

    for s in watchlist:
        code = extract_stock_code(s)
        if code in pool_results and request.defense_weight == 0.5:
            results.append(pool_results[code])
        elif code in dfs:
            name = pool_results[code].name if code in pool_results else "Unknown"
            analysis = analyze_stock(dfs[code], code, name, request.defense_weight, request.market_type)
            results.append(AnalysisResult(**analysis))
        else:
            data_map_needed.append(s)

    if data_map_needed:
        data_pool = fetch_batch_data(data_map_needed, request.market_type)
        tw_symbols = fetch_tw_symbols() if request.market_type == "TW" else {}
        us_symbols = fetch_us_symbols() if request.market_type == "US" else {}
        crypto_symbols = fetch_crypto_symbols() if request.market_type == "CRYPTO" else {}

        for symbol in data_map_needed:
            code = extract_stock_code(symbol)
            df = data_pool.get(symbol)
            if df is not None:
                name = "Unknown"
                if request.market_type == "TW": name = tw_symbols.get(code, "Unknown")
                elif request.market_type == "US": name = us_symbols.get(code, "Unknown")
                elif request.market_type == "CRYPTO": name = crypto_symbols.get(code.lower(), "Unknown")

                analysis = analyze_stock(df, code, name, request.defense_weight, request.market_type)
                results.append(AnalysisResult(**analysis))
            else:
                results.append(AnalysisResult(
                    symbol=code, name="No Data", price=0, suggestion="Failed to fetch data",
                    level="-", ma240_diff="-", ma20_diff="-", macd_status="-", score=-1,
                    ma_base=0, ma20=0, atr=0
                ))

    results = sorted(results, key=lambda x: x.score, reverse=True)
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
    
    # Optimization: Only re-score if weight is actually different from default (0.5) 
    # Or if we want to support dynamic rescanning without full re-calculation.
    if defense_weight is not None and abs(defense_weight - 0.5) > 0.001:
        # Check if we already have this weight in cache to avoid CPU spike
        cache_key = f"res_{market_type}_{defense_weight}"
        from api.services.quant_service import results_cache
        if results_cache.get(cache_key):
             all_results = results_cache[cache_key]
        else:
            from api.services.quant_service import analyze_stock
            dfs = pool.get("dfs", {})
            new_results = []
            for r in all_results:
                code = getattr(r, 'symbol', r.get('symbol') if isinstance(r, dict) else None)
                df = dfs.get(code)
                if df is not None:
                    name = getattr(r, 'name', r.get('name', 'Unknown') if isinstance(r, dict) else 'Unknown')
                    analysis = analyze_stock(df, code, name, defense_weight, market_type)
                    new_results.append(AnalysisResult(**analysis))
                else:
                    new_results.append(r)
            all_results = new_results
            # Cache for a short while or until next scan
            results_cache[cache_key] = all_results
    
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
