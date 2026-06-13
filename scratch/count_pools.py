import sys
import os

# Add the project root to sys.path
sys.path.append(os.getcwd())

from api.services.quant_service import get_cached_pool

markets = ["TW", "US", "CRYPTO"]
report = []

for m in markets:
    pool = get_cached_pool(m)
    if pool and pool.get("results"):
        count = len(pool["results"])
        timestamp = pool.get("timestamp", "Unknown")
        report.append(f"| {m} | {count} | {timestamp} |")
    else:
        report.append(f"| {m} | 0 | N/A |")

print("### 最新掃描池數據統計")
print("| 市場 | 掃描到檔數 | 最後更新時間 |")
print("| :--- | :--- | :--- |")
for line in report:
    print(line)
