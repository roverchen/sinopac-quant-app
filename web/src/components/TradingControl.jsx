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
  const [pending, setPending] = useState([]);
  const [summary, setSummary] = useState(null);

  useEffect(() => {
    fetchStatus();
    refreshAll();
    const interval = setInterval(refreshAll, 60000);
    return () => clearInterval(interval);
  }, [viewAccount]);

  const refreshAll = () => {
    fetchAccount();
    fetchPending();
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
              <span className="text-xs font-bold text-slate-500 uppercase tracking-widest">
                {viewAccount === 'personal' ? '個人帳戶市值' : '機器人帳戶市值'}
              </span>
            </div>
            <p className="text-3xl font-black text-white font-inter">
              ${account.balance.toLocaleString()}
            </p>
            {summary && (
              <div className={`text-sm font-bold mt-1 ${
                (viewAccount === 'personal' ? summary.mock.total : summary.mock.total) >= 0 ? 'text-emerald-400' : 'text-rose-400'
              }`}>
                P/L: ${(viewAccount === 'personal' ? summary.mock.total : summary.mock.total).toLocaleString()}
                <span className="ml-1 text-[10px] opacity-60">
                  ({viewAccount === 'personal' ? '個人模擬' : '機器人全域'})
                </span>
              </div>
            )}
        </div>
      </div>

      {/* Account Selector & Pending Orders Hook */}
      <div className="flex items-center justify-between gap-4 bg-slate-900/40 p-2 rounded-[2rem] border border-slate-800/50">
        <div className="flex p-1.5 bg-slate-950/50 rounded-2xl gap-2">
          <button 
            onClick={() => setViewAccount('personal')}
            className={`px-6 py-2 rounded-xl text-xs font-black uppercase tracking-widest transition-all ${
              viewAccount === 'personal' ? 'bg-indigo-600 text-white shadow-lg' : 'text-slate-500 hover:text-slate-300'
            }`}
          >
            個人帳戶
          </button>
          <button 
            onClick={() => setViewAccount('system_auto')}
            className={`px-6 py-2 rounded-xl text-xs font-black uppercase tracking-widest transition-all ${
              viewAccount === 'system_auto' ? 'bg-indigo-600 text-white shadow-lg' : 'text-slate-500 hover:text-slate-300'
            }`}
          >
            系統自動 (Robot)
          </button>
        </div>
        
        {pending.length > 0 && (
          <div className="flex items-center gap-2 px-6 py-2 bg-indigo-500/10 border border-indigo-500/30 rounded-2xl">
            <Clock className="w-4 h-4 text-indigo-400 animate-pulse" />
            <span className="text-xs font-bold text-indigo-400 uppercase tracking-widest">
              {pending.length} 筆掛單執行中
            </span>
          </div>
        )}
      </div>

      {/* Pending Orders Table (If any) */}
      {pending.length > 0 && (
        <div className="bg-slate-900/20 border border-indigo-500/10 rounded-[2.5rem] overflow-hidden">
          <div className="px-8 py-5 border-b border-indigo-500/10 flex items-center gap-3">
             <Clock className="w-5 h-5 text-indigo-500" />
             <h3 className="text-sm font-black text-indigo-400 uppercase tracking-widest">待成交委託 (Pending Orders)</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="bg-indigo-500/5">
                  <th className="px-8 py-4 text-[9px] font-black text-slate-500 uppercase tracking-widest">標的</th>
                  <th className="px-8 py-4 text-[9px] font-black text-slate-500 uppercase tracking-widest">方向</th>
                  <th className="px-8 py-4 text-[9px] font-black text-slate-500 uppercase tracking-widest text-right">數量</th>
                  <th className="px-8 py-4 text-[9px] font-black text-slate-500 uppercase tracking-widest text-right">委託價</th>
                  <th className="px-8 py-4 text-[9px] font-black text-slate-500 uppercase tracking-widest text-right text-indigo-500">當前狀態</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-indigo-500/10">
                {pending.map((p, idx) => (
                  <tr key={idx} className="bg-indigo-500/5">
                    <td className="px-8 py-4 font-inter font-bold text-white">{p.symbol}</td>
                    <td className="px-8 py-4">
                      <span className={`px-2 py-0.5 rounded text-[9px] font-black uppercase ${
                        p.action === 'Buy' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'
                      }`}>
                        {p.action === 'Buy' ? '買入' : '賣出'}
                      </span>
                    </td>
                    <td className="px-8 py-4 text-right font-inter text-xs text-slate-300">{p.qty}</td>
                    <td className="px-8 py-4 text-right font-inter text-xs text-slate-300">${p.price}</td>
                    <td className="px-8 py-4 text-right">
                       <div className="flex items-center justify-end gap-2 text-indigo-400">
                          <span className="text-[10px] font-bold uppercase tracking-widest animate-pulse">撮合中</span>
                          <Clock className="w-3 h-3" />
                       </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Current Positions - Main Focus */}
      <div className="bg-slate-900/40 border border-slate-800 rounded-[3rem] overflow-hidden backdrop-blur-sm">
        <div className="p-8 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-emerald-500/10 rounded-2xl">
              <TrendingUp className="w-6 h-6 text-emerald-400" />
            </div>
            <div>
              <h3 className="text-xl font-bold text-white">當前持倉 (Positions)</h3>
              <p className="text-slate-500 text-xs mt-1">點擊項目執行平倉/賣出委託</p>
            </div>
          </div>
          
          <div className="flex items-center gap-4">
            <div className="hidden md:flex items-center gap-2 px-4 py-2 bg-slate-800/50 rounded-xl border border-slate-700">
               <Clock className="w-3.5 h-3.5 text-slate-500" />
               <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">自動更新週期: 60s</span>
            </div>
            <button 
                onClick={handleManualOrder}
                disabled={loading || viewAccount === 'system_auto'}
                className="px-5 py-2.5 bg-slate-800 hover:bg-slate-700 text-indigo-400 rounded-xl text-xs font-black transition-all border border-indigo-500/20 flex items-center gap-2 disabled:opacity-30 disabled:cursor-not-allowed"
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
                  <tr 
                    key={pos.symbol} 
                    onClick={() => viewAccount === 'personal' && openSellModal(pos)}
                    className={`hover:bg-slate-800/30 transition-colors group ${viewAccount === 'personal' ? 'cursor-pointer' : 'cursor-default'}`}
                  >
                    <td className="px-8 py-6">
                       <span className="text-lg font-black text-white group-hover:text-indigo-400 transition-colors font-inter">{pos.symbol}</span>
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
