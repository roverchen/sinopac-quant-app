from fastapi import APIRouter, HTTPException, Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from api.models.schemas import AuthRequest, Token, UserCredentialsUpdate
from api.services.auth_service import create_access_token, decode_access_token
from api.services.storage_service import load_credentials, save_credentials
from google.oauth2 import id_token
from google.auth.transport import requests

router = APIRouter(prefix="/auth", tags=["auth"])
security = HTTPBearer()

GOOGLE_CLIENT_ID = "666086971776-7o105jsjrdjcnc3j4scgl37s6q67o3l8.apps.googleusercontent.com"

async def get_current_user(auth: HTTPAuthorizationCredentials = Security(security)):
    payload = decode_access_token(auth.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload.get("sub")

@router.post("/login", response_model=Token)
async def login(request: AuthRequest):
    try:
        # Verify Google Token
        idinfo = id_token.verify_oauth2_token(
            request.credential, requests.Request(), GOOGLE_CLIENT_ID
        )
        user_id = idinfo.get('email')
        if not user_id:
            raise ValueError("Token missing email field")
    except ValueError as e:
        raise HTTPException(status_code=401, detail=f"Google token verification failed: {e}")

    # Initialize or load credentials
    stored_creds = load_credentials(user_id)
    if stored_creds is None or stored_creds == {}:
        save_credentials(user_id, {})

    access_token = create_access_token(data={"sub": user_id})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me")
async def get_me(user_id: str = Depends(get_current_user)):
    creds = load_credentials(user_id)
    return {"user_id": user_id, "creds": creds}

@router.post("/credentials")
async def update_credentials(update: UserCredentialsUpdate, user_id: str = Depends(get_current_user)):
    save_credentials(user_id, update.creds)
    return {"status": "success", "message": "Credentials updated"}
