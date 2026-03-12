from pydantic import BaseModel, Field
from typing import List, Optional

class StockAnalysisRequest(BaseModel):
    watchlist: List[str]
    defense_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    market_type: str = "TW"

class AnalysisResult(BaseModel):
    代碼: str
    名稱: str
    市場: Optional[str] = None
    最新價格: float
    操作建議: str
    一年位階: str
    年線乖離: str
    MA20乖離: str
    MACD狀態: str
    綜合評分: float
    _ma_base: Optional[float]
    _ma20: Optional[float]
    _atr: Optional[float]

class AnalysisResponse(BaseModel):
    results: List[AnalysisResult]
    timestamp: str

class AuthRequest(BaseModel):
    credential: str

class Token(BaseModel):
    access_token: str
    token_type: str

class UserCredentialsUpdate(BaseModel):
    creds: dict

class ScanRequest(BaseModel):
    market_type: str = "TW"
    defense_weight: float = 0.5

class ScanProgressResponse(BaseModel):
    status: str # "idle", "running", "completed", "error"
    progress: float
    message: str
    results_count: int = 0
    top_results: Optional[List[AnalysisResult]] = []
