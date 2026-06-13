import sys
import os
import asyncio

sys.path.append(os.getcwd())

from api.routes.trade import get_performance_summary

async def main():
    for user_id in ["system_auto", "system_eric"]:
        summary = await get_performance_summary(user_id=user_id, current_user=user_id)
        print(f"\n==================== {user_id} Performance Summary ====================")
        print(f"Simulation Portfolio (Mock):")
        print(f"  Realized PnL  : {summary['mock']['realized']:.2f} TWD")
        print(f"  Unrealized PnL: {summary['mock']['unrealized']:.2f} TWD")
        print(f"  Total PnL     : {summary['mock']['total']:.2f} TWD")
        print(f"  Invested Cap  : {summary['mock']['invested']:.2f} TWD")
        print(f"  Return Rate   : {summary['mock']['return_rate']:.2f}%")
        
        print(f"Live Portfolio:")
        print(f"  Realized PnL  : {summary['live']['realized']:.2f} TWD")
        print(f"  Unrealized PnL: {summary['live']['unrealized']:.2f} TWD")
        print(f"  Total PnL     : {summary['live']['total']:.2f} TWD")
        print(f"  Invested Cap  : {summary['live']['invested']:.2f} TWD")
        print(f"  Return Rate   : {summary['live']['return_rate']:.2f}%")

if __name__ == "__main__":
    asyncio.run(main())
