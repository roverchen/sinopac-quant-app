from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from api.routes.auth import get_current_user
from api.models.schemas import StockAnalysisRequest, AnalysisResponse, AnalysisResult, ScanRequest, ScanProgressResponse, PaginatedAnalysisResponse
from api.services.quant_service import extract_stock_code, analyze_stock, fetch_tw_symbols, fetch_us_symbols, fetch_crypto_symbols
from api.services.data_fetcher import fetch_batch_data
from api.services.storage_service import save_data_pool, load_data_pool, get_user_watchlist, save_user_watchlist, get_all_user_watchlists
from datetime import datetime
import asyncio

router = APIRouter(prefix="/quant", tags=["quant"])

# 全域掃描狀態紀錄
scan_status = {
    "status": "idle",
    "progress": 0,
    "message": "系統就緒",
    "results_count": 0,
    "top_results": []
}

# 全域結果快取 (避免每次 reload 都從 GCS 重抓)
results_cache = {
    "TW": None,
    "US": None,
    "CRYPTO": None
}

def get_cached_pool(market_type: str):
    """取得快取的數據池，如不存在則從持久層讀取"""
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
        scan_status["message"] = f"正在獲取 {market_type} 代碼清單..."

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
        scan_status["message"] = f"開始併發抓取 {total} 檔數據..."

        # 分批抓取以免 API 超載 (Yahoo 比照辦理)
        chunk_size = 50
        results = []
        all_dfs = {}

        for i in range(0, total, chunk_size):
            chunk = symbols[i : i + chunk_size]
            data_map = fetch_batch_data(chunk, market_type)

            for s, df in data_map.items():
                name = symbols_map.get(s, "未知")
                analysis = analyze_stock(df, s, name, defense_weight, market_type)
                results.append(AnalysisResult(**analysis))
                all_dfs[s] = df

            # 更新進度
            progress = 10 + (i / total) * 85
            scan_status["progress"] = round(progress, 1)
            scan_status["message"] = f"已分析 {len(results)}/{total}..."
            scan_status["results_count"] = len(results)
            print(f"[Scan] Progress: {scan_status['progress']}% ({len(results)}/{total})")

            await asyncio.sleep(0.1) # 給予事件循環喘息空間

        # 保存結果至持久層 (依評分降序排列)
        results = sorted(results, key=lambda x: x.綜合評分, reverse=True)

        scan_status["message"] = "分析完成，正在保存數據池..."
        data_pool = {"results": results, "dfs": all_dfs, "timestamp": datetime.now().isoformat()}
        save_data_pool(market_type, data_pool)

        # 更新內存快取
        results_cache[market_type] = data_pool

        scan_status["top_results"] = results[:10]
        scan_status["status"] = "completed"
        scan_status["progress"] = 100
        scan_status["message"] = f"海選完成！成功分析 {len(results)} 檔標的。"

    except Exception as e:
        scan_status["status"] = "error"
        scan_status["message"] = f"掃描中斷: {str(e)}"
        print(f"Scan Error: {e}")

@router.post("/scan")
async def start_scan(request: ScanRequest, background_tasks: BackgroundTasks):
    """啟動全市場海選掃描。"""
    if scan_status["status"] == "running":
        raise HTTPException(status_code=400, detail="Scan already in progress")

    background_tasks.add_task(run_market_scan, request.market_type, request.defense_weight)
    return {"message": "Scan started"}

@router.get("/scan/progress", response_model=ScanProgressResponse)
async def get_scan_progress():
    """獲取當前掃描進度。"""
    return ScanProgressResponse(**scan_status)

@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_watchlist(request: StockAnalysisRequest, current_user: str = Depends(get_current_user)):
    """分析追蹤清單並返回結果。使用併發抓取優化。"""
    results = []

    if not request.watchlist:
        from api.services.storage_service import get_user_watchlist
        watchlist = get_user_watchlist(current_user, request.market_type)
    else:
        watchlist = request.watchlist

    if not watchlist:
        return AnalysisResponse(results=[], timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    # 這裡優先從 data_pool 讀取以加速 (如有最近掃描)
    pool = get_cached_pool(request.market_type) or {}
    pool_results = {r.代碼: r for r in pool.get("results", [])}
    dfs = pool.get("dfs", {})

    results = []
    data_map_needed = []

    for s in watchlist:
        code = extract_stock_code(s)
        if code in pool_results and request.defense_weight == 0.5: # 預設權重直接用快取
            results.append(pool_results[code])
        elif code in dfs: # 有數據但權重不同，重刷
            name = pool_results[code].名稱 if code in pool_results else "未知"
            analysis = analyze_stock(dfs[code], code, name, request.defense_weight, request.market_type)
            results.append(AnalysisResult(**analysis))
        else:
            data_map_needed.append(s)

    if data_map_needed:
        data_pool = fetch_batch_data(data_map_needed, request.market_type)
        # 取得名稱對照表
        tw_symbols = fetch_tw_symbols() if request.market_type == "TW" else {}
        us_symbols = fetch_us_symbols() if request.market_type == "US" else {}
        crypto_symbols = fetch_crypto_symbols() if request.market_type == "CRYPTO" else {}

        for symbol in data_map_needed:
            code = extract_stock_code(symbol)
            df = data_pool.get(symbol)
            if df is not None:
                # 命名稱邏輯
                name = "未知"
                if request.market_type == "TW": name = tw_symbols.get(code, "未知")
                elif request.market_type == "US": name = us_symbols.get(code, "未知")
                elif request.market_type == "CRYPTO": name = crypto_symbols.get(code.lower(), "未知")

                analysis = analyze_stock(df, code, name, request.defense_weight, request.market_type)
                results.append(AnalysisResult(**analysis))
            else:
                results.append(AnalysisResult(
                    代碼=code, 名稱="無數據", 最新價格=0, 操作建議="❌ 無法取得數據",
                    一年位階="-", 年線乖離="-", MA20乖離="-", MACD狀態="-", 綜合評分=-1,
                    ma_base=0, ma20=0, atr=0
                ))

    # 確保依評分排序
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
    """獲取全市場海選結果 (從快取或持久層讀取並分頁)。支援動態權重重算。"""
    pool = get_cached_pool(market_type)
    if not pool:
        return PaginatedAnalysisResponse(
            results=[], total=0, page=page, page_size=page_size,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )

    all_results = pool.get("results", [])

    # 如果提供權重，則根據快取中的數據重新計算分數
    if defense_weight is not None:
        dfs = pool.get("dfs", {})
        new_results = []
        for r in all_results:
            # r 是 AnalysisResult 物件
            code = getattr(r, '代碼', None)
            df = dfs.get(code)
            if df is not None:
                # 重新分析以獲取新分數
                # 這裡需要名稱，我們從現有結果抓
                name = getattr(r, '名稱', '未知')
                analysis = analyze_stock(df, code, name, defense_weight, market_type)
                new_results.append(AnalysisResult(**analysis))
            else:
                new_results.append(r)
        all_results = new_results

    # 確保依評分排序 (Fix slider ranking bug)
    all_results = sorted(all_results, key=lambda x: getattr(x, '綜合評分', -1), reverse=True)

    # 確保每個結果都有市場欄位
    for r in all_results:
        if hasattr(r, '市場') and not r.市場:
            r.市場 = market_type

    # 全部結果按評分降序排列 (防禦性再次排序)
    all_results = sorted(all_results, key=lambda x: getattr(x, '綜合評分', -1), reverse=True)

    # 全局搜尋過濾
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
    """取得使用者追蹤清單"""
    if market_type == "ALL":
        return get_all_user_watchlists(current_user)
    watchlist = get_user_watchlist(current_user, market_type)
    return {"watchlist": watchlist}

@router.post("/watchlist")
async def add_to_watchlist_api(symbol: str, market_type: str = "TW", current_user: str = Depends(get_current_user)):
    """新增標的至追蹤清單"""
    watchlist = get_user_watchlist(current_user, market_type)
    if symbol not in watchlist:
        watchlist.append(symbol)
        save_user_watchlist(current_user, market_type, watchlist)
    return {"status": "success", "watchlist": watchlist}

@router.delete("/watchlist")
async def remove_from_watchlist_api(symbol: str, market_type: str = "TW", current_user: str = Depends(get_current_user)):
    """從追蹤清單移除標的"""
    watchlist = get_user_watchlist(current_user, market_type)
    if symbol in watchlist:
        watchlist.remove(symbol)
        save_user_watchlist(current_user, market_type, watchlist)
    return {"status": "success", "watchlist": watchlist}

@router.get("/history")
async def get_symbol_history(symbol: str, market_type: str = "TW"):
    """獲取歷史 K 線數據 (OHLC)"""
    from api.services.quant_service import get_yahoo_ticker, fetch_stock_data
    from fastapi import HTTPException

    ticker_str = get_yahoo_ticker(symbol, market_type)
    print(f"[History] Fetching {symbol} ({market_type}) using ticker {ticker_str}")

    try:
        df = fetch_stock_data(symbol, ticker_str, period="3mo")
        if df is None or df.empty:
            print(f"[History] No data returned for {ticker_str}")
            raise HTTPException(status_code=404, detail=f"No historical data found for {symbol}")

        # 格式化為 Recharts 友善格式
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
        print(f"[History] Returning {len(history)} data points for {symbol}")
        return history
    except Exception as e:
        print(f"[History] Error fetching {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
