from pydantic import BaseModel, Field
from typing import List, Optional

class StockAnalysisRequest(BaseModel):
    watchlist: List[str]
    defense_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    market_type: str = "TW"

class AnalysisResult(BaseModel):
    symbol: str
    name: str
    market: Optional[str] = None
    price: float
    suggestion: str
    level: str
    ma240_diff: str
    ma20_diff: str
    macd_status: str
    score: float
    ma_base: Optional[float] = None
    ma20: Optional[float] = None
    atr: Optional[float] = None
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    target_price: Optional[float] = None

class AnalysisResponse(BaseModel):
    results: List[AnalysisResult]
    timestamp: str

class PaginatedAnalysisResponse(BaseModel):
    results: List[AnalysisResult]
    total: int
    page: int
    page_size: int
    timestamp: str

class AuthRequest(BaseModel):
    credential: str

class Token(BaseModel):
    access_token: str
    token_type: str

class UserCredentialsUpdate(BaseModel):
    creds: dict

class UserSettings(BaseModel):
    email_notifications_enabled: bool = True

class UserSettingsUpdate(BaseModel):
    settings: UserSettings

class ScanRequest(BaseModel):
    market_type: str = "TW"
    defense_weight: float = 0.5

class ScanProgressResponse(BaseModel):
    status: str # "idle", "running", "completed", "error"
    progress: float
    message: str
    results_count: int = 0
    top_results: Optional[List[AnalysisResult]] = []
