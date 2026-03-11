from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from api.routes.auth import get_current_user
from api.models.schemas import StockAnalysisRequest, AnalysisResponse, AnalysisResult, ScanRequest, ScanProgressResponse
from api.services.quant_service import extract_stock_code, analyze_stock, fetch_tw_symbols, fetch_us_symbols
from api.services.data_fetcher import fetch_batch_data
from api.services.storage_service import save_data_pool, get_user_watchlist, save_user_watchlist
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

async def run_market_scan(market_type: str, defense_weight: float):
    global scan_status
    try:
        scan_status["status"] = "running"
        scan_status["progress"] = 5
        scan_status["message"] = f"正在獲取 {market_type} 代碼清單..."
        
        symbols_map = fetch_tw_symbols() if market_type == "TW" else fetch_us_symbols()
        symbols = list(symbols_map.keys())
        total = len(symbols)
        
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
            
            await asyncio.sleep(0.1) # 給予事件循環喘息空間
            
        # 保存結果至持久層
        scan_status["message"] = "分析完成，正在保存數據池..."
        save_data_pool(market_type, {"results": results, "dfs": all_dfs, "timestamp": datetime.now().isoformat()})
        
        scan_status["top_results"] = sorted(results, key=lambda x: x.綜合評分, reverse=True)[:10]
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
    
    watchlist = request.watchlist
    # 如果傳入空清單，嘗試從儲存空間讀取
    if not watchlist:
        watchlist = get_user_watchlist(current_user, request.market_type)
    
    if not watchlist:
        return AnalysisResponse(results=[], timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    # 這裡未來可以優先從 data_pool 讀取以加速
    data_pool = fetch_batch_data(watchlist, request.market_type)
    
    # 取得名稱對照表
    tw_symbols = fetch_tw_symbols()
    us_symbols = fetch_us_symbols()
    
    for symbol in watchlist:
        code = extract_stock_code(symbol)
        df = data_pool.get(symbol)
        
        if df is not None:
            # 自動從對照表中補齊名稱
            name = tw_symbols.get(code)
            if not name:
                name = us_symbols.get(code)
            if not name:
                if "BTC" in code: name = "Bitcoin"
                elif "ETH" in code: name = "Ethereum"
                else: name = "未知"
                
            analysis = analyze_stock(df, code, name, request.defense_weight, request.market_type)
            results.append(AnalysisResult(**analysis))
        else:
            results.append(AnalysisResult(
                代碼=code, 名稱="無數據", 最新價格=0, 操作建議="❌ 無法取得數據",
                一年位階="-", 年線乖離="-", MA20乖離="-", MACD狀態="-", 綜合評分=-1,
                _ma_base=0, _ma20=0, _atr=0
            ))
            
    return AnalysisResponse(
        results=results,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

@router.get("/watchlist")
async def get_watchlist_api(market_type: str = "TW", current_user: str = Depends(get_current_user)):
    """取得使用者追蹤清單"""
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
