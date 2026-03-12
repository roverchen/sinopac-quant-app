import { useState, useEffect } from 'react';
import { Shield, Play, Pause, Wallet, TrendingUp, Send, Smartphone, Clock } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { tradeService } from '../services/api';

const TradingControl = () => {
  const [status, setStatus] = useState({ auto_trade_enabled: false, mode: 'Simulation' });
  const [account, setAccount] = useState({ balance: 0, positions: [], status: 'loading' });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchStatus();
    fetchAccount();
    // 每一分鐘自動更新一次價格與損益
    const interval = setInterval(fetchAccount, 60000);
    return () => clearInterval(interval);
  }, []);

  const fetchStatus = async () => {
    try {
      const resp = await tradeService.getStatus();
      setStatus(resp);
    } catch (err) {
      console.error(err);
    }
  };

  const fetchAccount = async () => {
    setLoading(true);
    try {
      const resp = await tradeService.getAccount();
      setAccount(resp);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const toggleAutoTrade = async () => {
    setLoading(true);
    try {
      await tradeService.toggleAutoTrade(!status.auto_trade_enabled);
      await fetchStatus();
    } catch (err) {
      alert("切換失敗，請檢查網路連線");
    } finally {
      setLoading(false);
    }
  };

  const handleManualOrder = async () => {
    const symbol = prompt("請輸入下單代碼 (例如 2330):", "2330");
    if (!symbol) return;
    
    setLoading(true);
    try {
      const resp = await tradeService.placeOrder({
        symbol,
        qty: 1,
        price: 0, 
        action: "Buy",
        is_simulation: status.mode === 'Simulation'
      });
      alert(`下單成功！單號: ${resp.trade_id}`);
      fetchAccount();
    } catch (err) {
      alert("下單失敗: " + (err.response?.data?.detail || "未知錯誤"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      {/* Trading Status Dashboard */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <div className={`lg:col-span-3 p-8 rounded-[2.5rem] border-2 transition-all ${
          status.auto_trade_enabled 
            ? 'bg-emerald-500/5 border-emerald-500/20 shadow-2xl shadow-emerald-500/10' 
            : 'bg-slate-900/40 border-slate-800'
        }`}>
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-8">
            <div className="flex items-center gap-6">
              <div className={`w-16 h-16 rounded-2xl flex items-center justify-center transition-all ${
                status.auto_trade_enabled ? 'bg-emerald-500 text-white shadow-lg shadow-emerald-500/40' : 'bg-slate-800 text-slate-500'
              }`}>
                <Shield className="w-8 h-8" />
              </div>
              <div>
                <div className="flex items-center gap-3">
                  <h2 className="text-2xl font-bold text-white tracking-tight">自動交易系統</h2>
                  <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase tracking-widest ${
                    status.mode === 'Simulation' ? 'bg-amber-500/10 text-amber-500 border border-amber-500/20' : 'bg-rose-500/10 text-rose-500 border border-rose-500/30'
                  }`}>
                    {status.mode === 'Simulation' ? '模擬下單' : '實盤交易'}
                  </span>
                </div>
                <p className="text-slate-400 mt-1 text-sm font-medium">
                  {status.auto_trade_enabled ? '運作中：系統正根據海選結果自動執行策略' : '已停止：目前僅供手動監控與分析'}
                </p>
              </div>
            </div>

            <button
              onClick={toggleAutoTrade}
              disabled={loading}
              className={`flex items-center gap-3 px-8 py-4 rounded-2xl font-black text-sm transition-all transform active:scale-95 ${
                status.auto_trade_enabled 
                  ? 'bg-slate-800 text-rose-500 hover:bg-slate-700' 
                  : 'bg-indigo-600 text-white hover:bg-indigo-500 shadow-xl shadow-indigo-600/30'
              }`}
            >
              {loading ? (
                <div className="w-5 h-5 border-2 border-current border-t-transparent rounded-full animate-spin" />
              ) : status.auto_trade_enabled ? (
                <><Pause className="w-5 h-5 fill-current" /> 停止交易</>
              ) : (
                <><Play className="w-5 h-5 fill-current" /> 啟動系統</>
              )}
            </button>
          </div>
        </div>

        <div className="p-8 bg-slate-900/40 border border-slate-800 rounded-[2.5rem] flex flex-col justify-center">
            <div className="flex items-center gap-3 mb-2">
              <Wallet className="w-5 h-5 text-indigo-400" />
              <span className="text-xs font-bold text-slate-500 uppercase tracking-widest">帳戶餘額</span>
            </div>
            <p className="text-3xl font-black text-white font-inter">
              ${account.balance.toLocaleString()}
            </p>
        </div>
      </div>

      {/* Current Positions - Main Focus */}
      <div className="bg-slate-900/40 border border-slate-800 rounded-[3rem] overflow-hidden backdrop-blur-sm">
        <div className="p-8 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-emerald-500/10 rounded-2xl">
              <TrendingUp className="w-6 h-6 text-emerald-400" />
            </div>
            <div>
              <h3 className="text-xl font-bold text-white">當前持倉 (Positions)</h3>
              <p className="text-slate-500 text-xs mt-1">即時同步庫存數據與未實現損益試算</p>
            </div>
          </div>
          
          <div className="flex items-center gap-4">
            <div className="hidden md:flex items-center gap-2 px-4 py-2 bg-slate-800/50 rounded-xl border border-slate-700">
               <Clock className="w-3.5 h-3.5 text-slate-500" />
               <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">自動更新週期: 60s</span>
            </div>
            <button 
                onClick={handleManualOrder}
                className="px-5 py-2.5 bg-slate-800 hover:bg-slate-700 text-indigo-400 rounded-xl text-xs font-black transition-all border border-indigo-500/20 flex items-center gap-2"
            >
                <Send className="w-3.5 h-3.5" />
                緊急手動下單
            </button>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="bg-slate-800/20 border-b border-slate-800">
                <th className="px-8 py-5 text-[10px] font-black text-slate-500 uppercase tracking-widest">標的代碼</th>
                <th className="px-8 py-5 text-[10px] font-black text-slate-500 uppercase tracking-widest">類型</th>
                <th className="px-8 py-5 text-[10px] font-black text-slate-500 uppercase tracking-widest text-right">持有數量</th>
                <th className="px-8 py-5 text-[10px] font-black text-slate-500 uppercase tracking-widest text-right">買入均價</th>
                <th className="px-8 py-5 text-[10px] font-black text-slate-500 uppercase tracking-widest text-right">目前市價</th>
                <th className="px-8 py-5 text-[10px] font-black text-slate-500 uppercase tracking-widest text-right">損益試算 (P/L)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50">
              {account.positions?.length > 0 ? (
                account.positions.map((pos) => (
                  <tr key={pos.symbol} className="hover:bg-slate-800/30 transition-colors group">
                    <td className="px-8 py-6">
                       <span className="text-lg font-black text-white font-inter">{pos.symbol}</span>
                    </td>
                    <td className="px-8 py-6">
                       <span className={`px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-tighter ${
                         pos.is_simulation ? 'bg-amber-500/10 text-amber-500' : 'bg-rose-500/10 text-rose-500'
                       }`}>
                         {pos.is_simulation ? '模擬' : '實盤'}
                       </span>
                    </td>
                    <td className="px-8 py-6 text-right font-inter font-bold text-slate-300">
                      {pos.qty.toLocaleString()}
                    </td>
                    <td className="px-8 py-6 text-right font-inter font-bold text-slate-400">
                      ${pos.buy_price.toLocaleString()}
                    </td>
                    <td className="px-8 py-6 text-right font-inter font-bold text-indigo-400">
                      ${pos.current_price?.toLocaleString() || '-'}
                    </td>
                    <td className="px-8 py-6 text-right">
                       <div className={`inline-flex items-center gap-1 font-inter font-black text-lg ${
                         pos.pnl_percent >= 0 ? 'text-emerald-400' : 'text-rose-400'
                       }`}>
                         {pos.pnl_percent >= 0 ? '+' : ''}{pos.pnl_percent}%
                       </div>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="6" className="px-8 py-24 text-center">
                    <div className="flex flex-col items-center opacity-20">
                      <TrendingUp className="w-16 h-16 mb-4" />
                      <p className="text-xl font-black uppercase tracking-widest">目前無持倉部位</p>
                      <p className="text-sm font-medium mt-1">自動交易系統啟動後將在此顯示您的投資組合</p>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default TradingControl;
