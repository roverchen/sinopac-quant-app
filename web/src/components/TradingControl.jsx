import { useState, useEffect } from 'react';
import { Shield, Play, Pause, Wallet, TrendingUp, Send, Smartphone, Clock, X, AlertCircle } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { tradeService } from '../services/api';

const TradingControl = () => {
  const [status, setStatus] = useState({ auto_trade_enabled: false, mode: 'Simulation' });
  const [account, setAccount] = useState({ balance: 0, positions: [], status: 'loading' });
  const [loading, setLoading] = useState(false);
  const [selectedPosition, setSelectedPosition] = useState(null);
  const [sellForm, setSellForm] = useState({ price: 0, qty: 0 });
  const [viewType, setViewType] = useState('positions'); // 'positions' or 'history'
  const [history, setHistory] = useState([]);

  useEffect(() => {
    fetchStatus();
    refreshAll();
    const interval = setInterval(refreshAll, 60000);
    return () => clearInterval(interval);
  }, [viewAccount, viewType]);

  const refreshAll = () => {
    if (viewType === 'positions') {
      fetchAccount();
      fetchPending();
    } else {
      fetchHistory();
    }
    fetchSummary();
  };

  const fetchHistory = async () => {
    setLoading(true);
    try {
      const userId = viewAccount === 'system_auto' ? 'system_auto' : null;
      const resp = await tradeService.getHistory(userId);
      setHistory(resp.history || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // Skip handlers for toggleAutoTrade, openSellModal, handleSellSubmit for brevity in this chunk

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      {/* Performance Summary Header */}
      <div className="p-8 bg-slate-900/40 border border-slate-800 rounded-[2.5rem] flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div className="flex items-center gap-6">
          <div className="w-16 h-16 rounded-2xl bg-indigo-600/10 flex items-center justify-center text-indigo-400">
            <TrendingUp className="w-8 h-8" />
          </div>
          <div className="flex flex-col">
            <h2 className="text-2xl font-bold text-white tracking-tight">
              交易環境控管
            </h2>
            <div className="flex gap-2 mt-2">
              <button 
                onClick={() => setViewAccount('personal')}
                className={`px-4 py-1.5 rounded-xl text-xs font-bold transition-all border ${
                  viewAccount === 'personal' 
                    ? 'bg-indigo-600 border-indigo-500 text-white shadow-lg shadow-indigo-600/20' 
                    : 'bg-slate-800/50 border-slate-700 text-slate-400 hover:text-white'
                }`}
              >
                個人手動帳戶
              </button>
              <button 
                onClick={() => setViewAccount('system_auto')}
                className={`px-4 py-1.5 rounded-xl text-xs font-bold transition-all border ${
                  viewAccount === 'system_auto' 
                    ? 'bg-indigo-600 border-indigo-500 text-white shadow-lg shadow-indigo-600/20' 
                    : 'bg-slate-800/50 border-slate-700 text-slate-400 hover:text-white'
                }`}
              >
                系統自動帳戶
              </button>
            </div>
          </div>
        </div>
        
        {summary && (
          <div className="flex gap-8">
            <div className="text-right">
              <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1">
                {viewAccount === 'personal' ? '個人' : '系統'}累計損益
              </p>
              <p className={`text-2xl font-black font-inter ${summary.mock.total >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                ${summary.mock.total.toLocaleString()}
              </p>
              <p className="text-[10px] text-slate-500 mt-1 font-bold">
                回報率: {summary.mock.return_rate}%
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Operation Tabs */}
      <div className="flex items-center gap-4 border-b border-slate-800 pb-1">
          <button 
            onClick={() => setViewType('positions')}
            className={`px-6 py-3 text-sm font-bold transition-all relative ${
              viewType === 'positions' ? 'text-indigo-400' : 'text-slate-500 hover:text-slate-300'
            }`}
          >
            當前持倉
            {viewType === 'positions' && <motion.div layoutId="tab" className="absolute bottom-0 left-0 right-0 h-0.5 bg-indigo-500" />}
          </button>
          <button 
            onClick={() => setViewType('history')}
            className={`px-6 py-3 text-sm font-bold transition-all relative ${
              viewType === 'history' ? 'text-indigo-400' : 'text-slate-500 hover:text-slate-300'
            }`}
          >
            歷史紀錄
            {viewType === 'history' && <motion.div layoutId="tab" className="absolute bottom-0 left-0 right-0 h-0.5 bg-indigo-500" />}
          </button>
      </div>

      {viewType === 'positions' ? (
        <>
          {/* Pending Orders Table */}
          {pending.length > 0 && (
            <div className="bg-slate-900/20 border border-indigo-500/10 rounded-[2.5rem] overflow-hidden">
                {/* ... existing table code ... */}
            </div>
          )}

          {/* Current Positions */}
          <div className="bg-slate-900/40 border border-slate-800 rounded-[3rem] overflow-hidden backdrop-blur-sm">
            <div className="p-8 border-b border-slate-800 flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="p-3 bg-emerald-500/10 rounded-2xl">
                  <TrendingUp className="w-6 h-6 text-emerald-400" />
                </div>
                <div>
                  <h3 className="text-xl font-bold text-white">資產分佈 (Holdings)</h3>
                  <p className="text-slate-500 text-xs mt-1">點擊持有標的進行平倉委託</p>
                </div>
              </div>
              <div className="flex items-center gap-4">
                  <button onClick={refreshAll} className="p-2 hover:bg-slate-800 rounded-lg text-slate-400 transition-colors">
                      <Clock className="w-5 h-5" />
                  </button>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="bg-slate-800/20 border-b border-slate-800">
                    <th className="px-8 py-5 text-[10px] font-black text-slate-500 uppercase tracking-widest">代碼</th>
                    <th className="px-8 py-5 text-[10px] font-black text-slate-500 uppercase tracking-widest">模式</th>
                    <th className="px-8 py-5 text-[10px] font-black text-slate-500 uppercase tracking-widest text-right">數量</th>
                    <th className="px-8 py-5 text-[10px] font-black text-slate-500 uppercase tracking-widest text-right">成本價</th>
                    <th className="px-8 py-5 text-[10px] font-black text-slate-500 uppercase tracking-widest text-right">現價</th>
                    <th className="px-8 py-5 text-[10px] font-black text-slate-500 uppercase tracking-widest text-right">未實現損益</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/50">
                  {account.positions?.length > 0 ? (
                    account.positions.map((pos) => (
                      <tr 
                        key={pos.symbol} 
                        onClick={() => openSellModal(pos)}
                        className="hover:bg-slate-800/30 transition-colors group cursor-pointer"
                      >
                        <td className="px-8 py-6">
                           <span className="text-lg font-black text-white group-hover:text-indigo-400 font-inter">{pos.symbol}</span>
                        </td>
                        <td className="px-8 py-6">
                           <span className={`px-2 py-0.5 rounded text-[10px] font-black ${
                             pos.is_simulation ? 'bg-amber-500/10 text-amber-500' : 'bg-rose-500/10 text-rose-500'
                           }`}>
                             {pos.is_simulation ? 'SIM' : 'LIVE'}
                           </span>
                        </td>
                        <td className="px-8 py-6 text-right font-inter font-bold text-slate-300">{pos.qty.toLocaleString()}</td>
                        <td className="px-8 py-6 text-right font-inter font-bold text-slate-400">${pos.buy_price.toLocaleString()}</td>
                        <td className="px-8 py-6 text-right font-inter font-bold text-indigo-400">${pos.current_price?.toLocaleString() || '-'}</td>
                        <td className="px-8 py-6 text-right">
                           <div className={`font-inter font-black text-lg ${pos.pnl_percent >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                             {pos.pnl_percent >= 0 ? '+' : ''}{pos.pnl_percent}%
                           </div>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr><td colSpan="6" className="px-8 py-32 text-center opacity-30 text-xl font-bold">目前無持倉部位</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      ) : (
        <div className="bg-slate-900/40 border border-slate-800 rounded-[3rem] overflow-hidden backdrop-blur-sm">
          <div className="p-8 border-b border-slate-800 flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="p-3 bg-indigo-500/10 rounded-2xl">
                  <Clock className="w-6 h-6 text-indigo-400" />
                </div>
                <h3 className="text-xl font-bold text-white">成交歷史紀錄 (Trade History)</h3>
              </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="bg-slate-800/20 border-b border-slate-800">
                  <th className="px-8 py-5 text-[10px] font-black text-slate-500 uppercase tracking-widest">時間</th>
                  <th className="px-8 py-5 text-[10px] font-black text-slate-500 uppercase tracking-widest">標的</th>
                  <th className="px-8 py-5 text-[10px] font-black text-slate-500 uppercase tracking-widest">動作</th>
                  <th className="px-8 py-5 text-[10px] font-black text-slate-500 uppercase tracking-widest text-right">數量/價格</th>
                  <th className="px-8 py-5 text-[10px] font-black text-slate-500 uppercase tracking-widest text-right">實現損益</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/50">
                {history.length > 0 ? history.map((h, i) => (
                  <tr key={i} className="hover:bg-slate-800/30 transition-colors">
                    <td className="px-8 py-6 text-xs text-slate-500 font-inter">{h.timestamp?.split('T')[0] || '-'}</td>
                    <td className="px-8 py-6 font-bold text-white font-inter">{h.symbol}</td>
                    <td className="px-8 py-6">
                      <span className={`px-2 py-0.5 rounded text-[9px] font-black uppercase ${
                        h.action === 'Buy' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'
                      }`}>
                        {h.action === 'Buy' ? '買入' : '賣出'}
                      </span>
                    </td>
                    <td className="px-8 py-6 text-right font-inter text-xs text-slate-300">
                      {h.qty} @ ${h.price}
                    </td>
                    <td className="px-8 py-6 text-right">
                       <span className={`font-inter font-bold ${h.realized_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                         {h.realized_pnl ? `${h.realized_pnl >= 0 ? '+' : ''}${h.realized_pnl}` : '-'}
                       </span>
                    </td>
                  </tr>
                )) : (
                  <tr><td colSpan="5" className="px-8 py-32 text-center opacity-30 text-xl font-bold">目前無成交紀錄</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Sell Modal */}
      <AnimatePresence>
        {selectedPosition && (
          <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setSelectedPosition(null)}
              className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm"
            />
            
            <motion.div
              initial={{ scale: 0.95, opacity: 0, y: 20 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.95, opacity: 0, y: 20 }}
              className="relative w-full max-w-lg bg-slate-900 border border-slate-800 rounded-[2.5rem] shadow-2xl overflow-hidden"
            >
              <div className="p-8 border-b border-slate-800 flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="p-3 bg-rose-500/10 rounded-2xl">
                    <Send className="w-6 h-6 text-rose-500 rotate-180" />
                  </div>
                  <div>
                    <h3 className="text-xl font-bold text-white">賣出委託 (Sell)</h3>
                    <p className="text-slate-500 text-xs mt-1">標的：{selectedPosition.symbol}</p>
                  </div>
                </div>
                <button 
                  onClick={() => setSelectedPosition(null)}
                  className="p-2 hover:bg-slate-800 rounded-xl text-slate-500 transition-colors"
                >
                  <X className="w-6 h-6" />
                </button>
              </div>

              <div className="p-8 space-y-6">
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-4 bg-slate-800/50 rounded-2xl border border-slate-700">
                    <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1">現有庫存</p>
                    <p className="text-xl font-bold text-white font-inter">{selectedPosition.qty.toLocaleString()}</p>
                  </div>
                  <div className="p-4 bg-slate-800/50 rounded-2xl border border-slate-700">
                    <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1">買入均價</p>
                    <p className="text-xl font-bold text-white font-inter">${selectedPosition.buy_price.toLocaleString()}</p>
                  </div>
                </div>

                <div className="space-y-4">
                  <div>
                    <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest ml-1 mb-2 block">委託單價</label>
                    <div className="relative">
                      <span className="absolute left-5 top-1/2 -translate-y-1/2 text-slate-500 font-bold">$</span>
                      <input 
                        type="number"
                        value={sellForm.price}
                        onChange={(e) => setSellForm({...sellForm, price: e.target.value})}
                        className="w-full bg-slate-800 border-2 border-slate-700 focus:border-indigo-500/50 rounded-2xl py-4 pl-10 pr-6 text-white font-bold font-inter transition-all"
                      />
                    </div>
                  </div>

                  <div>
                    <div className="flex items-center justify-between ml-1 mb-2">
                      <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest">賣出數量</label>
                      <button 
                        onClick={() => setSellForm({...sellForm, qty: selectedPosition.qty})}
                        className="text-[10px] font-black text-indigo-400 uppercase tracking-widest hover:text-indigo-300"
                      >
                        全部平倉
                      </button>
                    </div>
                    <input 
                      type="number"
                      value={sellForm.qty}
                      onChange={(e) => setSellForm({...sellForm, qty: e.target.value})}
                      className="w-full bg-slate-800 border-2 border-slate-700 focus:border-indigo-500/50 rounded-2xl py-4 px-6 text-white font-bold font-inter transition-all"
                      max={selectedPosition.qty}
                    />
                  </div>
                </div>

                {sellForm.price && (
                  <div className={`p-4 rounded-2xl border flex items-center gap-3 ${
                    (sellForm.price - selectedPosition.buy_price) >= 0 
                      ? 'bg-emerald-500/5 border-emerald-500/20 text-emerald-400' 
                      : 'bg-rose-500/5 border-rose-500/20 text-rose-400'
                  }`}>
                    <TrendingUp className="w-5 h-5" />
                    <div className="text-sm font-bold">
                      預估實現損益: 
                      <span className="ml-2 font-inter">
                        ${((sellForm.price - selectedPosition.buy_price) * sellForm.qty).toLocaleString()}
                      </span>
                    </div>
                  </div>
                )}
              </div>

              <div className="p-8 pt-0">
                <button
                  onClick={handleSellSubmit}
                  disabled={loading}
                  className="w-full bg-rose-600 hover:bg-rose-500 text-white font-black py-5 rounded-2xl transition-all transform active:scale-95 shadow-xl shadow-rose-600/20 disabled:opacity-50 flex items-center justify-center gap-3"
                >
                  {loading ? (
                    <div className="w-6 h-6 border-3 border-white/30 border-t-white rounded-full animate-spin" />
                  ) : (
                    <>
                      確認賣出委託
                      <Smartphone className="w-5 h-5" />
                    </>
                  )}
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default TradingControl;
