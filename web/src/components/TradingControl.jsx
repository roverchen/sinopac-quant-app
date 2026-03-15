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
  const [viewAccount, setViewAccount] = useState('personal'); // 'personal' or 'system_auto'
  const [viewType, setViewType] = useState('positions'); // 'positions' or 'history'
  const [pending, setPending] = useState([]);
  const [summary, setSummary] = useState(null);
  const [history, setHistory] = useState([]);
  const [robotStatus, setRobotStatus] = useState({ status: 'Idle', message: 'System Ready' });

  useEffect(() => {
    fetchStatus();
    refreshAll();
    const interval = setInterval(refreshAll, 60000);
    return () => clearInterval(interval);
  }, [viewAccount, viewType]);

  const refreshAll = () => {
    fetchStatus();
    if (viewType === 'positions') {
      fetchAccount();
      fetchPending();
    } else {
      fetchHistory();
    }
    fetchSummary();
    if (viewAccount === 'system_auto') {
      fetchRobotStatus();
    }
  };

  const fetchRobotStatus = async () => {
    try {
      const resp = await tradeService.getRobotStatus();
      if (resp && resp.status) setRobotStatus(resp);
    } catch (err) {
      console.error("Failed to fetch robot status", err);
    }
  };

  const triggerRobot = async (market) => {
    setLoading(true);
    try {
      await tradeService.triggerAutoTradeScan(market);
      alert(`${market} 自動掃描與交易已手動觸發！`);
      // Start polling for status
      const poll = setInterval(async () => {
        const resp = await tradeService.getRobotStatus();
        setRobotStatus(resp);
        if (resp.status === 'Idle' || resp.status === 'error') clearInterval(poll);
      }, 3000);
    } catch (err) {
      alert("觸發失敗: " + err.message);
    } finally {
      setLoading(false);
    }
  };

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
      const userId = viewAccount === 'system_auto' ? 'system_auto' : null;
      const resp = await tradeService.getAccount(userId);
      setAccount(resp);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const fetchPending = async () => {
    try {
      const userId = viewAccount === 'system_auto' ? 'system_auto' : null;
      const resp = await tradeService.getPending(userId);
      setPending(resp.pending || []);
    } catch (err) {
      console.error(err);
    }
  };

  const fetchSummary = async () => {
    try {
      const userId = viewAccount === 'system_auto' ? 'system_auto' : null;
      const resp = await tradeService.getSummary(userId);
      setSummary(resp);
    } catch (err) {
      console.error(err);
    }
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

  const openSellModal = (pos) => {
    setSelectedPosition(pos);
    setSellForm({ price: pos.current_price || pos.buy_price, qty: pos.qty });
  };

  const handleSellSubmit = async () => {
    if (sellForm.qty <= 0 || sellForm.qty > selectedPosition.qty) {
      alert("數量不正確");
      return;
    }
    
    setLoading(true);
    try {
      await tradeService.placeOrder({
        symbol: selectedPosition.symbol,
        qty: Number(sellForm.qty),
        price: Number(sellForm.price),
        action: "Sell",
        is_simulation: selectedPosition.is_simulation
      });
      alert("賣出委託已送出");
      setSelectedPosition(null);
      fetchAccount();
    } catch (err) {
      alert("交易失敗: " + (err.response?.data?.detail || "未知錯誤"));
    } finally {
      setLoading(false);
    }
  };

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
                個人
              </button>
              <button 
                onClick={() => setViewAccount('system_auto')}
                className={`px-4 py-1.5 rounded-xl text-xs font-bold transition-all border ${
                  viewAccount === 'system_auto' 
                    ? 'bg-indigo-600 border-indigo-500 text-white shadow-lg shadow-indigo-600/20' 
                    : 'bg-slate-800/50 border-slate-700 text-slate-400 hover:text-white'
                }`}
              >
                系統
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
              {viewAccount === 'personal' && (
                <p className={`text-2xl font-black font-inter ${ (summary?.mock?.total ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                  ${(summary?.mock?.total ?? 0).toLocaleString()}
                </p>
              )}
              <p className={`text-[10px] ${viewAccount === 'system_auto' ? 'text-2xl mt-0' : 'text-slate-500 mt-1'} font-bold ${viewAccount === 'system_auto' && (summary?.mock?.return_rate ?? 0) >= 0 ? 'text-emerald-400' : viewAccount === 'system_auto' ? 'text-rose-400' : ''}`}>
                回報率: {summary?.mock?.return_rate ?? 0}%
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Robot Status Bar (Only for system_auto) */}
      <AnimatePresence>
        {viewAccount === 'system_auto' && (
          <motion.div 
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="p-6 bg-indigo-600/10 border border-indigo-500/20 rounded-[2rem] flex items-center justify-between"
          >
            <div className="flex items-center gap-4">
              <div className={`p-2 rounded-full ${robotStatus.status === 'Idle' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-amber-500/20 text-amber-400 animate-pulse'}`}>
                <Smartphone className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-bold text-white">機器人狀態: {robotStatus.status}</span>
                  <span className="px-2 py-0.5 rounded text-[10px] bg-slate-800 text-slate-400 font-inter">
                    更新: {robotStatus.last_updated ? new Date(robotStatus.last_updated).toLocaleTimeString() : 'N/A'}
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-0.5">{robotStatus.message}</p>
              </div>
            </div>
            
            <div className="flex gap-2">
              <button 
                onClick={() => triggerRobot('TW')}
                disabled={loading || robotStatus.status !== 'Idle'}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white text-xs font-bold rounded-xl transition-all disabled:opacity-50"
              >
                手動觸發台股
              </button>
              <button 
                onClick={() => triggerRobot('US')}
                disabled={loading || robotStatus.status !== 'Idle'}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white text-xs font-bold rounded-xl transition-all disabled:opacity-50"
              >
                手動觸發美股
              </button>
              <button 
                onClick={() => triggerRobot('CRYPTO')}
                disabled={loading || robotStatus.status !== 'Idle'}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white text-xs font-bold rounded-xl transition-all disabled:opacity-50"
              >
                手動觸發加密
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

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
        <div className="bg-slate-900/40 border border-slate-800 rounded-[3rem] overflow-hidden backdrop-blur-sm">
          <div className="p-8 border-b border-slate-800 flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-indigo-500/10 rounded-2xl">
                <Shield className="w-6 h-6 text-indigo-400" />
              </div>
              <div>
                <h3 className="text-xl font-bold text-white">資產與委託 (Assets & Orders)</h3>
                <p className="text-slate-500 text-xs mt-1">整合持倉與未成交委託，點擊持倉可快速平倉</p>
              </div>
            </div>
            <button onClick={refreshAll} className="p-2 hover:bg-slate-800 rounded-lg text-slate-400 transition-colors">
              <Clock className="w-5 h-5" />
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="bg-slate-800/20 border-b border-slate-800">
                  <th className="px-8 py-5 text-[10px] font-black text-slate-500 uppercase tracking-widest">標的/名稱</th>
                  <th className="px-8 py-5 text-[10px] font-black text-slate-500 uppercase tracking-widest">狀態</th>
                  <th className="px-8 py-5 text-[10px] font-black text-slate-500 uppercase tracking-widest">模式</th>
                  <th className="px-8 py-5 text-[10px] font-black text-slate-500 uppercase tracking-widest text-right">數量</th>
                  <th className="px-8 py-5 text-[10px] font-black text-slate-500 uppercase tracking-widest text-right">現價/成本</th>
                  <th className="px-8 py-5 text-[10px] font-black text-slate-500 uppercase tracking-widest text-right">損益 (%)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/50">
                {/* Pending Orders First */}
                {pending.map((o, i) => (
                  <tr key={`pending-${i}`} 
                      className="bg-indigo-500/5 hover:bg-indigo-500/10 transition-colors border-b border-slate-800/30">
                    <td className="px-8 py-6">
                      <div className="flex flex-col">
                        <span className="text-lg font-black text-white font-inter">{o.symbol}</span>
                        <span className="text-[10px] text-slate-500 font-bold">{o.name || '-'}</span>
                      </div>
                    </td>
                    <td className="px-8 py-6">
                      <span className="px-3 py-1 bg-amber-500/10 text-amber-400 text-[10px] font-black rounded-full border border-amber-500/20 uppercase">
                        {o.action === 'Buy' ? '委託買入中' : '委託賣出中'}
                      </span>
                    </td>
                    <td className="px-8 py-6">
                      <span className="text-xs font-bold text-slate-400">{o.is_simulation ? '模擬' : '實盤'}</span>
                    </td>
                    <td className="px-8 py-6 text-right">
                      <span className="text-sm font-bold text-slate-300">{o.qty}</span>
                    </td>
                    <td className="px-8 py-6 text-right">
                      <span className="text-sm font-black text-white font-inter">${o.price}</span>
                    </td>
                    <td className="px-8 py-6 text-right">
                      <span className="text-sm font-bold text-slate-600">等待成交...</span>
                    </td>
                  </tr>
                ))}

                {/* Positions */}
                {account.positions.map((pos, i) => (
                  <tr key={`pos-${i}`} 
                      onClick={() => openSellModal(pos)}
                      className="group hover:bg-slate-800/40 cursor-pointer transition-all border-b border-slate-800/50">
                    <td className="px-8 py-6">
                      <div className="flex flex-col">
                        <span className="text-lg font-black text-white group-hover:text-indigo-400 font-inter leading-tight">{pos.symbol}</span>
                        <span className="text-[10px] text-slate-500 font-bold">{pos.name || '-'}</span>
                      </div>
                    </td>
                    <td className="px-8 py-6">
                      <span className="px-3 py-1 bg-emerald-500/10 text-emerald-400 text-[10px] font-black rounded-full border border-emerald-500/20 uppercase">
                        持倉中 (Holding)
                      </span>
                    </td>
                    <td className="px-8 py-6">
                      <span className="text-xs font-bold text-slate-400">{pos.is_simulation ? '模擬' : '實盤'}</span>
                    </td>
                    <td className="px-8 py-6 text-right">
                      <span className="text-sm font-black text-white font-inter">{pos.qty}</span>
                    </td>
                    <td className="px-8 py-6 text-right">
                      <div className="flex flex-col items-end">
                        <span className="text-sm font-black text-white font-inter">${pos.current_price || pos.buy_price}</span>
                        <span className="text-[10px] text-slate-500 font-bold">成本: ${pos.buy_price}</span>
                      </div>
                    </td>
                    <td className="px-8 py-6 text-right">
                      <div className="flex flex-col items-end">
                        <span className={`text-base font-black font-inter ${pos.realized_pl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                          {pos.pnl_percent > 0 ? '+' : ''}{pos.pnl_percent}%
                        </span>
                        <span className={`text-[10px] font-bold ${pos.realized_pl >= 0 ? 'text-emerald-500/60' : 'text-rose-500/60'}`}>
                          ${pos.unrealized_pl?.toLocaleString() || '0'}
                        </span>
                      </div>
                    </td>
                  </tr>
                ))}

                {pending.length === 0 && (!account.positions || account.positions.length === 0) && (
                  <tr><td colSpan="6" className="px-8 py-32 text-center opacity-30 text-xl font-bold">目前無任何委託或持倉</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
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
                  <th className="px-8 py-5 text-[10px] font-black text-slate-500 uppercase tracking-widest">標的/名稱</th>
                  <th className="px-8 py-5 text-[10px] font-black text-slate-500 uppercase tracking-widest">模式</th>
                  <th className="px-8 py-5 text-[10px] font-black text-slate-500 uppercase tracking-widest">動作</th>
                  <th className="px-8 py-5 text-[10px] font-black text-slate-500 uppercase tracking-widest text-right">數量/價格</th>
                  <th className="px-8 py-5 text-[10px] font-black text-slate-500 uppercase tracking-widest text-right">實現損益</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/50">
                {history.length > 0 ? history.map((h, i) => (
                  <tr key={i} className="hover:bg-slate-800/30 transition-colors">
                    <td className="px-8 py-6 text-xs text-slate-500 font-inter">{h.timestamp?.split('T')[0] || '-'}</td>
                    <td className="px-8 py-6">
                      <div className="flex flex-col">
                        <span className="font-bold text-white font-inter leading-tight">{h.symbol}</span>
                        <span className="text-[10px] text-slate-500 font-bold mt-0.5 line-clamp-1">{h.name || '-'}</span>
                      </div>
                    </td>
                    <td className="px-8 py-6">
                      <span className={`px-2 py-0.5 rounded text-[9px] font-black ${
                        h.is_simulation ? 'bg-amber-500/10 text-amber-500' : 'bg-rose-500/10 text-rose-500'
                      }`}>
                        {h.is_simulation ? '模擬' : '實盤'}
                      </span>
                    </td>
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
                       {h.is_simulation ? (
                         <span className={`font-inter font-bold ${h.pnl_percent >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                           {h.action === 'Sell' ? (h.pnl_percent != null ? `${h.pnl_percent >= 0 ? '+' : ''}${h.pnl_percent}%` : '-') : '-'}
                         </span>
                       ) : (
                         <span className={`font-inter font-bold ${h.realized_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                           {h.realized_pnl ? `${h.realized_pnl >= 0 ? '+' : ''}${h.realized_pnl}` : '-'}
                         </span>
                       )}
                    </td>
                  </tr>
                )) : (
                  <tr><td colSpan="6" className="px-8 py-32 text-center opacity-30 text-xl font-bold">目前無成交紀錄</td></tr>
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
