import { useState, useEffect } from 'react';
import { Shield, Play, Pause, Wallet, TrendingUp, Send, Smartphone, Clock, X, AlertCircle, RefreshCw } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { tradeService } from '../services/api';

const SkeletonRow = ({ cols = 6 }) => (
  <tr className="animate-pulse border-b border-slate-800/30">
    {[...Array(cols)].map((_, i) => (
      <td key={i} className="px-8 py-6">
        <div className="h-5 bg-slate-800 rounded-md w-full max-w-[100px]" />
      </td>
    ))}
  </tr>
);

const TradingControl = () => {
  const [status, setStatus] = useState({ auto_trade_enabled: false, mode: 'Simulation', backend_version: "2.1.77" });
  const [account, setAccount] = useState({ balance: 0, positions: [], status: 'loading' });
  const [loading, setLoading] = useState(false);
  const [selectedPosition, setSelectedPosition] = useState(null);
  const [sellForm, setSellForm] = useState({ price: 0, qty: 0 });
  const [viewAccount, setViewAccount] = useState('personal'); // 'personal' or 'system_auto'
  const [viewType, setViewType] = useState('positions'); // 'positions' or 'history'
  const [pending, setPending] = useState([]);
  const [summary, setSummary] = useState(null);
  const [history, setHistory] = useState([]);
  const [selectedPending, setSelectedPending] = useState(null);

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
      fetchPending();
      fetchHistory();
    } catch (err) {
      alert("交易失敗: " + (err.response?.data?.detail || "未知錯誤"));
    } finally {
      setLoading(false);
    }
  };

  const handleCancelOrder = async () => {
    if (!selectedPending) return;
    
    setLoading(true);
    try {
      const idToCancel = selectedPending.trade_id || selectedPending.order_id;
      await tradeService.cancelOrder(idToCancel);
      alert("委託已成功撤單");
      setSelectedPending(null);
      fetchPending();
      fetchHistory(); // Added history refresh
    } catch (err) {
      alert("撤單失敗: " + (err.response?.data?.detail || "未知錯誤"));
    } finally {
      setLoading(false);
    }
  };

  const handleSyncBroker = async () => {
    setLoading(true);
    try {
      const resp = await tradeService.syncWithBroker();
      alert(`同步完成！已從券商更新最新狀態。`);
      refreshAll();
    } catch (err) {
      alert("同步失敗: " + (err.response?.data?.detail || "未知錯誤"));
    } finally {
      setLoading(false);
    }
  };


  return (
    <div className="max-w-6xl mx-auto space-y-8">
      {/* Top Header & Actions */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 px-4">
        <div className="flex items-center gap-4">
          <div className="p-3 bg-indigo-500/10 rounded-2xl border border-indigo-500/20">
            <TrendingUp className="w-6 h-6 text-indigo-400" />
          </div>
          <div>
            <h2 className="text-2xl font-black text-white tracking-tight">交易環境控管</h2>
            <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mt-1">
              Backend Version: <span className="text-slate-400">v{status.backend_version || '2.1.75'}</span>
            </p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <button 
            onClick={handleSyncBroker}
            disabled={loading}
            className="flex items-center gap-2 px-6 py-3 bg-slate-800/80 hover:bg-slate-700 text-white rounded-2xl text-xs font-bold transition-all border border-slate-700 shadow-xl disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            同步券商資料
          </button>
        </div>
      </div>

      {/* Account Type Tabs */}
      <div className="bg-slate-900/40 p-1.5 border border-slate-800 rounded-3xl flex w-fit mx-auto md:mx-4">
        <button 
          onClick={() => setViewAccount('personal')}
          className={`flex items-center gap-2 px-8 py-3 rounded-2xl text-sm font-black transition-all ${
            viewAccount === 'personal' 
              ? 'bg-indigo-600 text-white shadow-xl shadow-indigo-600/30' 
              : 'text-slate-500 hover:text-slate-300'
          }`}
        >
          <Wallet className="w-4 h-4" />
          個人實盤/模擬
        </button>
        <button 
          onClick={() => setViewAccount('system_auto')}
          className={`flex items-center gap-2 px-8 py-3 rounded-2xl text-sm font-black transition-all ${
            viewAccount === 'system_auto' 
              ? 'bg-indigo-600 text-white shadow-xl shadow-indigo-600/30' 
              : 'text-slate-500 hover:text-slate-300'
          }`}
        >
          <RefreshCw className="w-4 h-4" />
          系統自動跟單
        </button>
      </div>

      {/* ROI & Status Banner */}
      {summary && (
        <div className="mx-4 p-8 bg-gradient-to-br from-slate-900/60 to-slate-900/20 border border-slate-800 rounded-[2.5rem] flex flex-col md:flex-row md:items-center justify-between gap-6 relative overflow-hidden group">
          <div className="absolute top-0 right-0 p-8 opacity-[0.03] group-hover:scale-110 transition-transform">
             <TrendingUp className="w-32 h-32 text-white" />
          </div>
          
          <div className="relative z-10">
            <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-2 flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${viewAccount === 'personal' ? 'bg-indigo-500' : 'bg-emerald-500'} animate-pulse`} />
              {viewAccount === 'personal' ? '個人帳戶' : '系統自動'} 績效快報
            </p>
            <div className="flex items-baseline gap-4">
              <h3 className={`text-4xl font-black font-inter tracking-tight ${ (summary?.mock?.total ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                ${(summary?.mock?.total ?? 0).toLocaleString()}
                <span className="text-sm font-medium text-slate-500 ml-2">TWD</span>
              </h3>
              <div className={`px-4 py-1.5 rounded-xl text-sm font-black border ${
                (summary?.mock?.return_rate ?? 0) >= 0 
                  ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' 
                  : 'bg-rose-500/10 border-rose-500/20 text-rose-400'
              }`}>
                {summary?.mock?.return_rate ?? 0}% ROI
              </div>
            </div>
          </div>

          <div className="flex items-center gap-8 relative z-10">
            <div className="h-12 w-px bg-slate-800 hidden md:block" />
            <div className="text-right">
              <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1">今日交易活躍度</p>
              <p className="text-lg font-bold text-white font-inter">穩定運作中</p>
            </div>
          </div>
        </div>
      )}


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
                  <th className="px-8 py-5 text-[10px] font-black text-slate-500 uppercase tracking-widest">模式</th>
                  <th className="px-8 py-5 text-[10px] font-black text-slate-500 uppercase tracking-widest">標的/名稱</th>
                  <th className="px-8 py-5 text-[10px] font-black text-slate-500 uppercase tracking-widest">狀態</th>
                  <th className="px-8 py-5 text-[10px] font-black text-slate-500 uppercase tracking-widest text-right">數量</th>
                  <th className="px-8 py-5 text-[10px] font-black text-slate-500 uppercase tracking-widest text-right">現價/成本</th>
                  <th className="px-8 py-5 text-[10px] font-black text-slate-500 uppercase tracking-widest text-right">損益 (%)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/50">
                {loading ? (
                  [...Array(5)].map((_, i) => <SkeletonRow key={i} cols={6} />)
                ) : (
                  <>
                    {/* Pending Orders First */}
                    {pending.map((o, i) => (
                      <tr key={`pending-${i}`} 
                          onClick={() => setSelectedPending(o)}
                          className="bg-indigo-500/5 hover:bg-slate-800/60 cursor-pointer transition-all border-b border-slate-800/30 group">
                        <td className="px-8 py-6">
                          <span className="text-xs font-bold text-slate-400">{o.is_simulation ? '模擬' : '實盤'}</span>
                        </td>
                        <td className="px-8 py-6">
                          <div className="flex flex-col">
                            <span className="text-lg font-black text-white group-hover:text-amber-400 font-inter leading-tight">{o.symbol}</span>
                            <span className="text-[10px] text-slate-500 font-bold">{o.name || '-'}</span>
                          </div>
                        </td>
                        <td className="px-8 py-6">
                          <span className="px-3 py-1 bg-amber-500/10 text-amber-400 text-[10px] font-black rounded-full border border-amber-500/20 uppercase">
                            {o.action === 'Buy' ? '委託買入中' : '委託賣出中'}
                          </span>
                        </td>
                        <td className="px-8 py-6 text-right">
                          <span className="text-sm font-bold text-slate-300">{o.qty}</span>
                        </td>
                        <td className="px-8 py-6 text-right">
                          <span className="text-sm font-black text-white font-inter">${o.price}</span>
                        </td>
                        <td className="px-8 py-6 text-right">
                          <div className="flex items-center justify-end gap-2 text-amber-500/40 group-hover:text-amber-500 transition-colors">
                            <span className="text-[10px] font-bold">點擊查看/撤單</span>
                            <X className="w-4 h-4" />
                          </div>
                        </td>
                      </tr>
                    ))}

                    {/* Positions */}
                    {account.positions.map((pos, i) => (
                      <tr key={`pos-${i}`} 
                          onClick={() => openSellModal(pos)}
                          className="group hover:bg-slate-800/40 cursor-pointer transition-all border-b border-slate-800/50">
                        <td className="px-8 py-6">
                          <span className="text-xs font-bold text-slate-400">{pos.is_simulation ? '模擬' : '實盤'}</span>
                        </td>
                        <td className="px-8 py-6">
                          <div className="flex flex-col">
                            <span className="text-lg font-black text-white group-hover:text-indigo-400 font-inter leading-tight">{pos.symbol}</span>
                            <span className="text-[10px] text-slate-500 font-bold">{pos.name || '-'}</span>
                            {/* Sub-Orders History Display */}
                            {pos.sub_orders && pos.sub_orders.length > 1 && (
                              <>
                                <div className="mt-1 text-[9px] text-indigo-400/50 font-bold group-hover:hidden flex items-center gap-1">
                                  <span>↳</span> {pos.sub_orders.length} 筆歷史加碼紀錄 (懸停查看)
                                </div>
                                <div className="mt-2 space-y-1 hidden group-hover:block transition-all">
                                  <div className="text-[9px] text-indigo-400/50 font-bold mb-1 border-b border-indigo-500/10 pb-1">歷史買進軌跡</div>
                                  {pos.sub_orders.map((sub, idx) => (
                                    <div key={idx} className="flex items-center justify-between gap-3 text-[9px] text-slate-400 font-inter bg-slate-900/50 w-full px-2 py-1 rounded-md border border-slate-800/80 hover:border-slate-700/80 transition-colors">
                                      <span className="text-slate-500">{sub.buy_order_time ? sub.buy_order_time.split('T')[0] : sub.fill_time?.split('T')[0]}</span>
                                      <span className="font-bold text-white">{sub.qty} <span className="text-slate-500 font-normal">單位</span></span>
                                      <span className="font-black">${typeof sub.buy_price === 'number' ? sub.buy_price.toFixed(2) : sub.buy_price}</span>
                                    </div>
                                  ))}
                                </div>
                              </>
                            )}
                          </div>
                        </td>
                        <td className="px-8 py-6">
                          <span className="px-3 py-1 bg-emerald-500/10 text-emerald-400 text-[10px] font-black rounded-full border border-emerald-500/20 uppercase">
                            持倉中 (Holding)
                          </span>
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
                          <div className="flex items-center justify-end gap-4">
                            <div className="flex flex-col items-end">
                              <span className={`text-base font-black font-inter ${pos.pnl_percent >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                                {pos.pnl_percent > 0 ? '+' : ''}{pos.pnl_percent}%
                              </span>
                              <span className={`text-[10px] font-bold ${pos.unrealized_pnl >= 0 ? 'text-emerald-500/60' : 'text-rose-500/60'}`}>
                                ${pos.unrealized_pl?.toLocaleString() || '0'}
                              </span>
                            </div>
                            <div className="p-2 bg-rose-500/10 text-rose-500 rounded-lg opacity-0 group-hover:opacity-100 transition-all transform translate-x-4 group-hover:translate-x-0">
                              發起賣單
                            </div>
                          </div>
                        </td>
                      </tr>
                    ))}

                    {pending.length === 0 && (!account.positions || account.positions.length === 0) && (
                      <tr><td colSpan="6" className="px-8 py-32 text-center opacity-30 text-xl font-bold">目前無任何委託或持倉</td></tr>
                    )}
                  </>
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
                <h3 className="text-xl font-bold text-white">歷史紀錄 (Trade History)</h3>
              </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="bg-slate-800/20 border-b border-slate-800">
                  <th className="px-8 py-5 text-[10px] font-black text-slate-500 uppercase tracking-widest">模式</th>
                  <th className="px-8 py-5 text-[10px] font-black text-slate-500 uppercase tracking-widest">標的/名稱/時間</th>
                  <th className="px-8 py-5 text-[10px] font-black text-slate-500 uppercase tracking-widest">狀態</th>
                  <th className="px-8 py-5 text-[10px] font-black text-slate-500 uppercase tracking-widest text-right">數量</th>
                  <th className="px-8 py-5 text-[10px] font-black text-slate-500 uppercase tracking-widest text-right">成交價格</th>
                  <th className="px-8 py-5 text-[10px] font-black text-slate-500 uppercase tracking-widest text-right">實現損益 (%)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/50">
                {loading ? (
                  [...Array(5)].map((_, i) => <SkeletonRow key={i} cols={6} />)
                ) : history.length > 0 ? (
                  history.map((h, i) => (
                    <tr key={i} className="hover:bg-slate-800/30 transition-colors border-b border-slate-800/50">
                      <td className="px-8 py-6">
                        <span className="text-xs font-bold text-slate-400">{h.is_simulation ? '模擬' : '實盤'}</span>
                      </td>
                      <td className="px-8 py-6">
                        <div className="flex flex-col">
                          <span className="text-lg font-black text-white font-inter leading-tight">{h.symbol}</span>
                          <div className="flex items-center gap-2 mt-0.5">
                            <span className="text-[10px] text-slate-500 font-bold">{h.name || '-'}</span>
                            <span className="text-[10px] text-slate-400/50 font-inter">
                              {h.timestamp?.split('T')[0]} {h.timestamp?.split('T')[1]?.slice(0, 5)}
                            </span>
                          </div>
                        </div>
                      </td>
                      <td className="px-8 py-6">
                        {h.status === 'CANCELLED' ? (
                          <span className="px-3 py-1 bg-slate-700/20 text-slate-400 text-[10px] font-black rounded-full border border-slate-700/30 uppercase">
                            已取消 (Cancelled)
                          </span>
                        ) : (
                          <span className={`px-3 py-1 text-[10px] font-black rounded-full border uppercase ${
                            h.action === 'Buy' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                          }`}>
                            {h.action === 'Buy' ? '買入 (Buy)' : '賣出 (Sell)'}
                          </span>
                        )}
                      </td>
                      <td className="px-8 py-6 text-right">
                        <span className="text-sm font-black text-white font-inter">{h.qty}</span>
                      </td>
                      <td className="px-8 py-6 text-right">
                        <span className="text-sm font-black text-white font-inter">${h.price}</span>
                      </td>
                      <td className="px-8 py-6 text-right">
                        {h.status === 'CANCELLED' ? (
                          <span className="text-slate-600 font-inter">-</span>
                        ) : h.action === 'Sell' ? (
                          <div className="flex flex-col items-end">
                            <span className={`text-base font-black font-inter ${h.pnl_percent >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                              {h.pnl_percent != null ? `${h.pnl_percent >= 0 ? '+' : ''}${h.pnl_percent}%` : '-'}
                            </span>
                            {h.realized_pnl != null && (
                              <span className={`text-[10px] font-bold ${h.realized_pnl >= 0 ? 'text-emerald-500/60' : 'text-rose-500/60'}`}>
                                ${h.realized_pnl.toLocaleString()}
                              </span>
                            )}
                          </div>
                        ) : (
                          <span className="text-slate-600 font-inter">-</span>
                        )}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr><td colSpan="6" className="px-8 py-32 text-center opacity-30 text-xl font-bold">目前無成交紀錄</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Order Cancel Modal */}
      <AnimatePresence>
        {selectedPending && (
          <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setSelectedPending(null)}
              className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm"
            />
            
            <motion.div
              initial={{ scale: 0.95, opacity: 0, y: 20 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.95, opacity: 0, y: 20 }}
              className="relative w-full max-w-md bg-slate-900 border border-slate-800 rounded-[2.5rem] shadow-2xl overflow-hidden"
            >
              <div className="p-8 border-b border-slate-800 flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="p-3 bg-amber-500/10 rounded-2xl">
                    <AlertCircle className="w-6 h-6 text-amber-500" />
                  </div>
                  <div>
                    <h3 className="text-xl font-bold text-white">委託詳情 (Pending)</h3>
                    <p className="text-slate-500 text-[10px] mt-1 font-inter">
                      ID: {(selectedPending.trade_id || selectedPending.order_id || 'UNKNOWN').slice(-8)}
                    </p>
                  </div>
                </div>
                <button 
                  onClick={() => setSelectedPending(null)}
                  className="p-2 hover:bg-slate-800 rounded-xl text-slate-500 transition-colors"
                >
                  <X className="w-6 h-6" />
                </button>
              </div>

              <div className="p-8 space-y-6">
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-4 bg-slate-800/50 rounded-2xl border border-slate-700">
                    <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1">標的/動作</p>
                    <p className="text-lg font-bold text-white font-inter">{selectedPending.symbol} • {selectedPending.action === 'Buy' ? '買入' : '賣出'}</p>
                  </div>
                  <div className="p-4 bg-slate-800/50 rounded-2xl border border-slate-700">
                    <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1">當前狀態</p>
                    <p className="text-lg font-bold text-amber-400 font-inter">PENDING</p>
                  </div>
                </div>

                <div className="space-y-2">
                  <p className="text-sm text-slate-400">
                    委託數量：<span className="text-white font-bold">{selectedPending.qty}</span>
                  </p>
                  <p className="text-sm text-slate-400">
                    委託價格：<span className="text-white font-bold">${selectedPending.price}</span>
                  </p>
                  <p className="text-sm text-slate-400">
                    交易模式：<span className="text-white font-bold">{selectedPending.is_simulation ? '模擬交易' : '實盤交易'}</span>
                  </p>
                  <p className="text-sm text-slate-400">
                    委託時間：<span className="text-white font-bold whitespace-nowrap">
                      {selectedPending.order_time && selectedPending.order_time !== 'None' ? new Date(selectedPending.order_time).toLocaleString() : 
                       (selectedPending.timestamp && selectedPending.timestamp !== 'None' ? new Date(selectedPending.timestamp).toLocaleString() : '系統升級前')}
                    </span>
                  </p>
                </div>

                <div className="pt-4 border-t border-slate-800 flex flex-col gap-3">
                  <button
                    onClick={handleCancelOrder}
                    disabled={loading}
                    className="w-full bg-rose-600/10 hover:bg-rose-600/20 text-rose-400 font-black py-4 rounded-2xl transition-all border border-rose-600/20 flex items-center justify-center gap-2"
                  >
                    {loading ? "處理中..." : "撤銷此筆委託 (Cancel Order)"}
                  </button>
                  <button
                    onClick={() => setSelectedPending(null)}
                    className="w-full bg-slate-800 hover:bg-slate-700 text-white font-black py-4 rounded-2xl transition-all"
                  >
                    關閉視窗
                  </button>
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

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

                {/* [v2.1.65] Added Buy Timestamps */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-4 bg-slate-800/30 rounded-2xl border border-slate-700/50">
                    <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1">買入委託時間</p>
                    <p className="text-xs font-bold text-slate-300 font-inter">
                      {selectedPosition.buy_order_time && selectedPosition.buy_order_time !== 'None' ? new Date(selectedPosition.buy_order_time).toLocaleString() : '系統升級前'}
                    </p>
                  </div>
                  <div className="p-4 bg-slate-800/30 rounded-2xl border border-slate-700/50">
                    <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1">買入確認時間</p>
                    <p className="text-xs font-bold text-slate-300 font-inter">
                      {selectedPosition.buy_filled_time && selectedPosition.buy_filled_time !== 'None' ? new Date(selectedPosition.buy_filled_time).toLocaleString() : '系統升級前'}
                    </p>
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
