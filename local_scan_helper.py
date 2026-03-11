import os
import time
import pickle
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import timedelta, datetime
import requests
import random
import argparse

# 導入 Sinopac API 邏輯
import sinopac_api

# 設定環境
CACHE_DIR = "cache"
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

# 模擬 app.py 中的一些輔助函式
def get_now():
    return datetime.now()

def get_random_ua():
    ua_list = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    ]
    return random.choice(ua_list)

# 建立專屬 Session
YF_SESSION = requests.Session()
YF_SESSION.headers.update({"User-Agent": get_random_ua()})

def fetch_and_analyze_local(watchlist, market_type='TW'):
    """本地端運行的分析邏輯，完全模仿 app.py"""
    data_list = []
    start_date = (get_now() - timedelta(days=365)).strftime("%Y-%m-%d")
    
    # 建立映射
    # 注意：本地端需要 shioaji api 才能獲取台股名單
    # 但如果是美股或加密貨幣，get_mass_scan_list 內部有寫死或邏輯
    code_to_name = {} 
    # 這裡我們嘗試不依賴 api 物件獲取名單，改從 sinopac_api.py 邏輯獲取
    # 如果是台股，通常本地端執行也會有 shioaji api 權限，這裡暫設為空
    
    print(f"🚀 開始分析 {len(watchlist)} 檔標的 (市場: {market_type})...")
    
    # 批次下載優化 (yf.download)
    chunk_size = 100
    all_dfs = {}
    
    for k in range(0, len(watchlist), chunk_size):
        chunk = watchlist[k:k+chunk_size]
        print(f"📥 正在下載批次 {k//chunk_size + 1} ({min(k+chunk_size, len(watchlist))}/{len(watchlist)})...")
        
        # 轉換代碼格式
        tickers = []
        ticker_to_code = {}
        for c in chunk:
            if market_type == 'TW':
                t_suffix = ".TW" if len(c) == 4 else ".TWO"
                t_code = c + t_suffix
            else:
                t_code = c.replace('.', '-')
            tickers.append(t_code)
            ticker_to_code[t_code] = c
            
        try:
            batch_data = yf.download(
                tickers, 
                period="1y", 
                group_by='ticker', 
                threads=True, 
                progress=False, 
                timeout=30, 
                auto_adjust=True
            )
            
            for t in tickers:
                if t in batch_data:
                    d = batch_data[t].dropna()
                    if not d.empty:
                        d = d.reset_index()
                        d.columns = [c.lower() for c in d.columns]
                        if 'date' in d.columns: d = d.rename(columns={'date': 'ts'})
                        all_dfs[ticker_to_code[t]] = d
        except Exception as e:
            print(f"❌ 批次下載失敗: {e}")
            
    # 開始分析
    for i, code in enumerate(watchlist):
        stock_name = code # 簡化
        df = all_dfs.get(code)
        
        if df is None or df.empty:
            continue
            
        try:
            # 統一技術指標計算
            df.columns = [c.lower() for c in df.columns]
            df['ma20'] = df['close'].rolling(window=20).mean()
            df['ma50'] = df['close'].rolling(window=50).mean()
            df['ma100'] = df['close'].rolling(window=100).mean()
            df['ma60'] = df['close'].rolling(window=60).mean()
            df['ma240'] = df['close'].rolling(window=240).mean()
            
            ema12 = df['close'].ewm(span=12).mean()
            ema26 = df['close'].ewm(span=26).mean()
            df['macd'] = ema12 - ema26
            df['signal'] = df['macd'].ewm(span=9).mean()
            df['hist'] = df['macd'] - df['signal']
            
            last_price = df['close'].iloc[-1]
            year_high = df['close'].max()
            year_low = df['close'].min()
            level_percentile = (last_price - year_low) / (year_high - year_low) if (year_high - year_low) != 0 else 0
            
            ma20_last = df['ma20'].iloc[-1]
            ma60_last = df['ma60'].iloc[-1]
            ma240_last = df['ma240'].iloc[-1]
            ma100_last = df['ma100'].iloc[-1]
            ma50_last = df['ma50'].iloc[-1]
            
            dist_to_ma20 = (last_price / ma20_last - 1) if not np.isnan(ma20_last) else 0
            
            if market_type == 'CRYPTO':
                has_defense_ma = not np.isnan(ma100_last)
                defense_base = ma100_last if has_defense_ma else ma50_last
                atr_multiplier = 3.0
            else:
                has_ma240 = not np.isnan(ma240_last)
                defense_base = ma240_last if has_ma240 else ma60_last
                atr_multiplier = 2.5
                
            dist_to_defense = (last_price / defense_base - 1) if not np.isnan(defense_base) else 0
            
            # MACD 狀態
            is_gold_cross = False
            macd_status = "整理"
            if len(df) >= 30:
                is_above_zero = df['macd'].iloc[-1] > 0 and df['signal'].iloc[-1] > 0
                zone_prefix = "🎯強勢" if is_above_zero else "🩹弱勢"
                last_hist = df['hist'].iloc[-1]
                prev_hist = df['hist'].iloc[-2]
                if prev_hist <= 0 and last_hist > 0:
                    macd_status = f"{zone_prefix}金叉"
                    is_gold_cross = True
                elif prev_hist >= 0 and last_hist < 0:
                    macd_status = f"{zone_prefix}死叉"
                else:
                    macd_status = f"{zone_prefix}整理" if is_above_zero else "低檔盤整"

            # 分數計算
            defense_weight = 0.5
            value_score = (1 - level_percentile) * 50
            if -0.05 < dist_to_defense < 0.05: value_score += 30
            if is_gold_cross: value_score += 20
            
            pullback_score = (1 - min(abs(dist_to_ma20), 0.1)/0.1) * 50
            if is_gold_cross: pullback_score += 30
            
            final_score = (defense_weight * value_score) + ((1 - defense_weight) * pullback_score)
            
            # 操作建議
            suggestion = "⚖️ 觀望"
            if final_score >= 80: suggestion = "🚀 強力買入"
            elif final_score >= 65: suggestion = "📈 買入"
            elif final_score <= 35: suggestion = "📉 賣出"
            
            data_list.append({
                "代碼": code, "名稱": stock_name, "最新價格": round(last_price, 2),
                "一年位階": f"{level_percentile:.1%}",
                "年線乖離": f"{dist_to_defense:+.1%}",
                "MA20乖離": f"{dist_to_ma20:+.1%}",
                "MACD狀態": macd_status,
                "綜合評分": round(final_score, 1),
                "操作建議": suggestion,
                "_ma_base": defense_base # 用於排序
            })
            
        except Exception as e:
            print(f"⚠️ 分析 {code} 失敗: {e}")
            
    print(f"✅ 分析完成，成功取得 {len(data_list)} 筆數據。")
    return pd.DataFrame(data_list), all_dfs

def main():
    parser = argparse.ArgumentParser(description='Sinopac Local Scan Helper')
    parser.add_argument('--market', type=str, default='CRYPTO', choices=['TW', 'US', 'CRYPTO'], help='市場類型')
    args = parser.parse_args()
    
    market = args.market
    
    # 獲交代碼名單
    # 注意：本地運行時如果要掃台股，需要 SINOPAC 帳密設定在環境變數或 secrets.toml 中
    # 這裡我們主要針對被 YF 封鎖的 CRYPTO/US
    print(f"🔍 正在獲取 {market} 代碼清單...")
    watchlist = sinopac_api.get_mass_scan_list(None, market=market)
    
    if not watchlist:
        print("❌ 無法獲取名單，請檢查 sinopac_api.py 或相關權限。")
        return
        
    df_results, all_dfs = fetch_and_analyze_local(watchlist, market_type=market)
    
    if not df_results.empty:
        # 排序
        df_results = df_results.sort_values(by="綜合評分", ascending=False)
        
        # 封裝成 app.py 識別的格式，並打包所有 K 線歷史 (解決 Cloud 版缺少 CSV 問題)
        data = {
            "df": df_results,
            "dfs": all_dfs,  # 將所有標的的詳細歷史也打包進去
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "is_big_scan": True,
            "scan_market": market
        }
        
        filename = f"shared_results_{market}.pkl"
        with open(filename, "wb") as f:
            pickle.dump(data, f)
            
        print(f"\n✨ 掃描成功！請將產生的檔案 '{filename}' 上傳至 Cloud 版 Settings 頁面。")
    else:
        print("\n❌ 掃描失敗，未取得任何有效數據。")

if __name__ == "__main__":
    main()
