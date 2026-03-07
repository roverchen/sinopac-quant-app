import os
import time
import hmac
import hashlib
import requests

class MaxExchangeAPI:
    def __init__(self, access_key: str, secret_key: str):
        self.access_key = access_key
        self.secret_key = secret_key
        self.base_url = "https://max-api.maicoin.com"

    def _generate_signature(self, nonce: str, endpoint: str) -> str:
        message = nonce + endpoint
        signature = hmac.new(
            bytes(self.secret_key, 'utf-8'),
            bytes(message, 'utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature

    def _get_headers(self, endpoint: str) -> dict:
        nonce = str(int(time.time() * 1000))
        signature = self._generate_signature(nonce, endpoint)
        return {
            'X-MAX-ACCESSKEY': self.access_key,
            'X-MAX-PAYLOAD': nonce,
            'X-MAX-SIGNATURE': signature,
            'Content-Type': 'application/json'
        }

    def get_account_balance(self) -> dict:
        """
        獲取帳戶餘額
        回傳結構範例:
        {
            'twd': {'balance': 10000, 'locked': 0},
            'btc': {'balance': 0.1, 'locked': 0.05},
        }
        """
        endpoint = "/api/v3/members/me"
        url = self.base_url + endpoint
        
        try:
            response = requests.get(url, headers=self._get_headers(endpoint))
            if response.status_code == 200:
                data = response.json()
                accounts = data.get('accounts', [])
                balance_dict = {}
                for acc in accounts:
                    # 只過濾出有餘額的資產以節省空間
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
        下單委託
        market: 收斂後的市場代碼，例如 'btctwd', 'ethtwd'
        side: 'buy' 或 'sell'
        volume: 下單數量 (例如 0.01 BTC)
        price: 限價單的價格
        ord_type: 'limit' (限價) 或 'market' (市價)
        """
        endpoint = "/api/v3/orders"
        url = self.base_url + endpoint
        
        payload = {
            "market": market.lower(),
            "side": side.lower(),
            "volume": str(volume),
            "ord_type": ord_type.lower()
        }
        
        if ord_type.lower() == "limit" and price is not None:
            payload["price"] = str(price)

        nonce = str(int(time.time() * 1000))
        
        # 針對有 payload 的 POST 請求，MAX 規定簽名依然是 nonce + endpoint (v3 後有些不需要 json payload 簽名)
        # 根據 MAX API v3 文件: payload 實際上是 base64 encode 後的 json object，但最新 API 可以直接傳 nonce
        # 更保守的做法是參考最新文件：
        
        # 準備送出的 headers (MAX API v3 要求將參數放在 JSON body 裡)
        import json
        
        # MAX API Signature payload
        message = nonce + endpoint
        signature = hmac.new(
            bytes(self.secret_key, 'utf-8'),
            bytes(message, 'utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        headers = {
            'X-MAX-ACCESSKEY': self.access_key,
            'X-MAX-PAYLOAD': nonce,
            'X-MAX-SIGNATURE': signature,
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload)
            if response.status_code in [200, 201]:
                return response.json()
            else:
                return {"error": f"Order Failed {response.status_code}: {response.text}"}
        except Exception as e:
            return {"error": str(e)}

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
