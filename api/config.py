import os
from dotenv import load_dotenv

load_dotenv()

# Google Cloud Project Config
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "sinopac-quant-app")
FIRESTORE_DB = DEFAULT = "(default)"

# Broker API Config
SHIOAJI_API_KEY = os.getenv("SHIOAJI_API_KEY")
SHIOAJI_SECRET_KEY = os.getenv("SHIOAJI_SECRET_KEY")
MAX_API_KEY = os.getenv("MAX_API_KEY")
MAX_API_SECRET = os.getenv("MAX_API_SECRET")

# App Config
CACHE_DIR = "cache"
SYNC_DIR = "sync"

# JWT Secret
JWT_SECRET = os.getenv("JWT_SECRET", "super-secret-quant-pro")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 # 1 day
