from fastapi import APIRouter, HTTPException, Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from api.models.schemas import AuthRequest, Token, UserCredentialsUpdate
from api.services.auth_service import verify_password, create_access_token, decode_access_token, get_password_hash
from api.services.storage_service import load_credentials, save_credentials
from api.config import JWT_SECRET

router = APIRouter(prefix="/auth", tags=["auth"])
security = HTTPBearer()

async def get_current_user(auth: HTTPAuthorizationCredentials = Security(security)):
    payload = decode_access_token(auth.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload.get("sub")

@router.post("/login", response_model=Token)
async def login(request: AuthRequest):
    # 簡單的登入邏輯：如果使用者不存在，則自動註冊 (與 Streamlit 版本一致)
    user_id = request.username
    stored_creds = load_credentials(user_id)
    
    # 這裡我們假設儲存在 Firestore 的 credentials 裡有一個 hashed_password 欄位
    # 如果是第一次登入，直接建立密碼
    hashed_pwd = stored_creds.get("hashed_password")
    
    if not hashed_pwd:
        # 註冊新密碼
        hashed_pwd = get_password_hash(request.password)
        stored_creds["hashed_password"] = hashed_pwd
        save_credentials(user_id, stored_creds)
    elif not verify_password(request.password, hashed_pwd):
        raise HTTPException(status_code=401, detail="Incorrect password")
        
    access_token = create_access_token(data={"sub": user_id})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me")
async def get_me(user_id: str = Depends(get_current_user)):
    creds = load_credentials(user_id)
    # 不回傳密碼 Hash
    if "hashed_password" in creds:
        del creds["hashed_password"]
    return {"user_id": user_id, "creds": creds}

@router.post("/credentials")
async def update_credentials(update: UserCredentialsUpdate, user_id: str = Depends(get_current_user)):
    existing = load_credentials(user_id)
    # 保留 hashed_password
    hashed_pwd = existing.get("hashed_password")
    new_creds = update.creds
    if hashed_pwd:
        new_creds["hashed_password"] = hashed_pwd
        
    save_credentials(user_id, new_creds)
    return {"status": "success", "message": "Credentials updated"}
