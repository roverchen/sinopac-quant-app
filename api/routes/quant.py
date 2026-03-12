from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from api.routes.auth import get_current_user
from api.models.schemas import StockAnalysisRequest, AnalysisResponse, AnalysisResult, ScanRequest, ScanProgressResponse, PaginatedAnalysisResponse
from api.services.quant_service import extract_stock_code, analyze_stock, fetch_tw_symbols, fetch_us_symbols, fetch_crypto_symbols
from api.services.data_fetcher import fetch_batch_data
from api.services.storage_service import save_data_pool, load_data_pool, get_user_watchlist, save_user_watchlist, get_all_user_watchlists
from datetime import datetime
import asyncio

router = APIRouter(prefix="/quant", tags=["quant"])

# Global scan status
scan_status = {
    "status": "idle",
    "progress": 0,
    "message": "System Ready",
    "results_count": 0,
    "top_results": []
}

# Global results cache
results_cache = {
    "TW": None,
    "US": None,
    "CRYPTO": None
}

def get_cached_pool(market_type: str):
    global results_cache
    if results_cache.get(market_type) is None:
        print(f"[Cache] Loading {market_type} data pool from storage...")
        pool = load_data_pool(market_type)
        if pool:
            results_cache[market_type] = pool
    return results_cache.get(market_type)

async def run_market_scan(market_type: str, defense_weight: float):
    global scan_status, results_cache
    try:
        scan_status["status"] = "running"
        scan_status["progress"] = 5
        scan_status["message"] = f"Fetching {market_type} symbols..."

        if market_type == "TW":
            symbols_map = fetch_tw_symbols()
        elif market_type == "US":
            symbols_map = fetch_us_symbols()
        else:
            symbols_map = fetch_crypto_symbols()

        symbols = list(symbols_map.keys())
        total = len(symbols)
        print(f"[Scan] {market_type} symbols found: {total}")

        if total == 0:
            raise ValueError(f"No symbols found for {market_type}")

        scan_status["progress"] = 10
        scan_status["message"] = f"Scanning {total} stocks..."

        chunk_size = 50
        results = []
        all_dfs = {}

        for i in range(0, total, chunk_size):
            chunk = symbols[i : i + chunk_size]
            data_map = fetch_batch_data(chunk, market_type)

            for s, df in data_map.items():
                name = symbols_map.get(s, "Unknown")
                analysis = analyze_stock(df, s, name, defense_weight, market_type)
                results.append(AnalysisResult(**analysis))
                all_dfs[s] = df

            progress = 10 + (i / total) * 85
            scan_status["progress"] = round(progress, 1)
            scan_status["message"] = f"Analyzed {len(results)}/{total}..."
            scan_status["results_count"] = len(results)
            print(f"[Scan] Progress: {scan_status['progress']}% ({len(results)}/{total})")

            await asyncio.sleep(0.1)

        results = sorted(results, key=lambda x: x.綜合評分, reverse=True)

        scan_status["message"] = "Saving results pool..."
        data_pool = {"results": results, "dfs": all_dfs, "timestamp": datetime.now().isoformat()}
        save_data_pool(market_type, data_pool)

        results_cache[market_type] = data_pool

        scan_status["top_results"] = results[:10]
        scan_status["status"] = "completed"
        scan_status["progress"] = 100
        scan_status["message"] = f"Scan complete. Analyzed {len(results)} stocks."

    except Exception as e:
        scan_status["status"] = "error"
        scan_status["message"] = f"Scan failed: {str(e)}"
        print(f"Scan Error: {e}")

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
        from api.services.storage_service import get_user_watchlist
        watchlist = get_user_watchlist(current_user, request.market_type)
    else:
        watchlist = request.watchlist

    if not watchlist:
        return AnalysisResponse(results=[], timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    pool = get_cached_pool(request.market_type) or {}
    pool_results = {r.代碼: r for r in pool.get("results", [])}
    dfs = pool.get("dfs", {})

    results = []
    data_map_needed = []

    for s in watchlist:
        code = extract_stock_code(s)
        if code in pool_results and request.defense_weight == 0.5:
            results.append(pool_results[code])
        elif code in dfs:
            name = pool_results[code].名稱 if code in pool_results else "Unknown"
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
                    代碼=code, 名稱="No Data", 最新價格=0, 操作建議="❌ Failed to fetch data",
                    一年位階="-", 年線乖離="-", MA20乖離="-", MACD狀態="-", 綜合評分=-1,
                    ma_base=0, ma20=0, atr=0
                ))

    results = sorted(results, key=lambda x: x.綜合評分, reverse=True)

    return AnalysisResponse(
        results=results,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

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

    if defense_weight is not None:
        dfs = pool.get("dfs", {})
        new_results = []
        for r in all_results:
            code = getattr(r, '代碼', None)
            df = dfs.get(code)
            if df is not None:
                name = getattr(r, '名稱', 'Unknown')
                analysis = analyze_stock(df, code, name, defense_weight, market_type)
                new_results.append(AnalysisResult(**analysis))
            else:
                new_results.append(r)
        all_results = new_results

    all_results = sorted(all_results, key=lambda x: getattr(x, '綜合評分', -1), reverse=True)

    for r in all_results:
        if hasattr(r, '市場') and not r.市場:
            r.市場 = market_type

    all_results = sorted(all_results, key=lambda x: getattr(x, '綜合評分', -1), reverse=True)

    if query:
        q = query.upper()
        all_results = [
            r for r in all_results
            if q in getattr(r, '代碼', '').upper() or q in getattr(r, '名稱', '').upper()
        ]

    total = len(all_results)
    start = (page - 1) * page_size
    end = start + page_size

    paginated_results = all_results[start:end]

    return PaginatedAnalysisResponse(
        results=paginated_results,
        total=total,
        page=page,
        page_size=page_size,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

@router.get("/watchlist")
async def get_watchlist_api(market_type: str = "TW", current_user: str = Depends(get_current_user)):
    if market_type == "ALL":
        return get_all_user_watchlists(current_user)
    watchlist = get_user_watchlist(current_user, market_type)
    return {"watchlist": watchlist}

@router.post("/watchlist")
async def add_to_watchlist_api(symbol: str, market_type: str = "TW", current_user: str = Depends(get_current_user)):
    watchlist = get_user_watchlist(current_user, market_type)
    if symbol not in watchlist:
        watchlist.append(symbol)
        save_user_watchlist(current_user, market_type, watchlist)
    return {"status": "success", "watchlist": watchlist}

@router.delete("/watchlist")
async def remove_from_watchlist_api(symbol: str, market_type: str = "TW", current_user: str = Depends(get_current_user)):
    watchlist = get_user_watchlist(current_user, market_type)
    if symbol in watchlist:
        watchlist.remove(symbol)
        save_user_watchlist(current_user, market_type, watchlist)
    return {"status": "success", "watchlist": watchlist}

@router.get("/history")
async def get_symbol_history(symbol: str, market_type: str = "TW"):
    from api.services.quant_service import get_yahoo_ticker, fetch_stock_data
    from fastapi import HTTPException

    ticker_str = get_yahoo_ticker(symbol, market_type)
    print(f"[History] Fetching {symbol} ({market_type}) using ticker {ticker_str}")

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
