import os
import time
import hmac
import hashlib
import json
import base64
import requests

class MaxExchangeAPI:
    def __init__(self, access_key: str, secret_key: str):
        self.access_key = access_key
        self.secret_key = secret_key
        self.base_url = "https://max-api.maicoin.com"

    def _get_auth_payload(self, path: str, payload_dict: dict = None):
        """
        MAX API v2 驗證機制: 回傳 headers 與 確實要送出的 json 字串
        """
        if payload_dict is None:
            payload_dict = {}
            
        nonce = int(time.time() * 1000)
        payload_dict['nonce'] = nonce
        payload_dict['path'] = path
        
        # 1. 產生與 API 嚴格一致的 JSON 字串 (移除空白，排序 Keys 以確保一致性)
        json_payload = json.dumps(payload_dict, separators=(',', ':'), sort_keys=True)
        b64_payload = base64.b64encode(json_payload.encode('utf-8')).decode('utf-8')
        
        # 2. 產生 Signature (對應 Base64 字串進行 HMAC-SHA256)
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            b64_payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        headers = {
            'X-MAX-ACCESSKEY': self.access_key,
            'X-MAX-PAYLOAD': b64_payload,
            'X-MAX-SIGNATURE': signature,
            'Content-Type': 'application/json'
        }
        
        return headers, json_payload

    def get_account_balance(self) -> dict:
        """
        獲取帳戶餘額 (使用 v2)
        """
        endpoint = "/api/v2/members/me"
        url = self.base_url + endpoint
        
        try:
            # [FIX] GET 請求雖然通常無 body，但 MAX V2 要求 Payload 與 Body 必須一致
            # 這裡產生含有 nonce 與 path 的 JSON 並透過 requests.request("GET", ..., data=) 送出
            headers, json_payload = self._get_auth_payload(endpoint)
            response = requests.request("GET", url, headers=headers, data=json_payload)
            
            if response.status_code == 200:
                data = response.json()
                accounts = data.get('accounts', [])
                balance_dict = {}
                for acc in accounts:
                    if float(acc['balance']) > 0 or float(acc['locked']) > 0:
                        balance_dict[acc['currency']] = {
                            'balance': float(acc['balance']),
                            'locked': float(acc['locked'])
                        }
                return balance_dict
            else:
                return {"error": f"API Error {response.status_code}: {response.text}"}
        except Exception as e:
            return {"error": str(e)}

    def place_order(self, market: str, side: str, volume: float, price: float = None, ord_type: str = "limit") -> dict:
        """
        下單委託 (使用 v2)
        """
        endpoint = "/api/v2/orders"
        url = self.base_url + endpoint
        
        # 準備訂單參數
        payload = {
            "market": market.lower(),
            "side": side.lower(),
            "volume": str(volume),
            "ord_type": ord_type.lower()
        }
        
        if ord_type.lower() == "limit" and price is not None:
            payload["price"] = str(price)
            
        # 取得 Headers 與準備確切送出的 json 字串
        headers, json_payload = self._get_auth_payload(endpoint, payload_dict=payload.copy())
        
        try:
            # 使用 data= 送出原始字串，避免 requests.post(json=) 擅自加上空白破壞驗證
            response = requests.post(url, headers=headers, data=json_payload)
            if response.status_code in [200, 201]:
                return response.json()
            else:
                return {"error": f"Order Failed {response.status_code}: {response.text}"}
        except Exception as e:
            return {"error": str(e)}

    def get_markets(self) -> list:
        """
        獲取所有可交易的市場清單
        """
        url = f"{self.base_url}/api/v2/markets"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                return response.json()
            else:
                return []
        except Exception:
            return []

if __name__ == "__main__":
    from dotenv import load_dotenv
    import os
    load_dotenv()
    
    key = os.getenv("MAX_API_KEY")
    secret = os.getenv("MAX_API_SECRET")
    
    if key and secret:
        api = MaxExchangeAPI(key, secret)
        print("Fetching balance...")
        bal = api.get_account_balance()
        print(bal)
    else:
        print("No API keys found in .env")
