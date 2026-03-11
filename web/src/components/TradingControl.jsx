import { useState, useEffect } from 'react';
import { Shield, Play, Pause, Landmark, Wallet, TrendingUp, History, Send } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { tradeService } from '../services/api';

const TradingControl = () => {
  const [status, setStatus] = useState({ auto_trade_enabled: false, mode: 'Simulation' });
  const [account, setAccount] = useState({ balance: 0, positions: [], status: 'loading' });
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchStatus();
    fetchAccount();
    fetchOrders();
  }, []);

  const fetchOrders = async () => {
    try {
      const resp = await tradeService.getOrders();
      setOrders(resp.orders || []);
    } catch (err) {
      console.error(err);
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
    try {
      const resp = await tradeService.getAccount();
      setAccount(resp);
    } catch (err) {
      console.error(err);
    }
  };

  const toggleAutoTrade = async () => {
    setLoading(true);
    try {
      const resp = await tradeService.toggleAutoTrade(!status.auto_trade_enabled);
      await fetchStatus();
      alert(resp.message || "設定已更新");
    } catch (err) {
      console.error(err);
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
        price: 0, // 市價或現價處理邏輯在後端
        action: "Buy"
      });
      alert(`下單成功！單號: ${resp.trade_id}`);
      fetchAccount();
      fetchOrders();
    } catch (err) {
      console.error(err);
      alert("下單失敗: " + (err.response?.data?.detail || "未知錯誤"));
    } finally {
      setLoading(false);
    }
  };

  const showPlaceholderAlert = (feature) => {
    alert(`${feature} 功能開發中，敬請期待！`);
  };

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      {/* Robot Status Card */}
      <div className={`p-8 rounded-[3rem] border-2 transition-all ${
        status.auto_trade_enabled 
          ? 'bg-emerald-500/5 border-emerald-500/20 shadow-2xl shadow-emerald-500/10' 
          : 'bg-slate-900/40 border-slate-800'
      }`}>
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-8">
          <div className="flex items-center gap-6">
            <div className={`w-20 h-20 rounded-3xl flex items-center justify-center transition-all ${
              status.auto_trade_enabled ? 'bg-emerald-500 text-white animate-pulse' : 'bg-slate-800 text-slate-500'
            }`}>
              <Shield className="w-10 h-10" />
            </div>
            <div>
              <div className="flex items-center gap-3">
                <h2 className="text-3xl font-bold text-white font-inter">自動交易機器人</h2>
                <span className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider ${
                  status.mode === 'Simulation' ? 'bg-amber-500/10 text-amber-500' : 'bg-rose-500/10 text-rose-500'
                }`}>
                  {status.mode === 'Simulation' ? '模擬模式' : '實盤模式'}
                </span>
              </div>
              <p className="text-slate-400 mt-2 font-medium">
                {status.auto_trade_enabled 
                  ? '系統已啟動：正在監測市場信號並執行自動套利。' 
                  : '系統已停止：自動交易功能已禁用，目前僅執行分析。'}
              </p>
            </div>
          </div>

          <button
            onClick={toggleAutoTrade}
            disabled={loading}
            className={`flex items-center gap-4 px-10 py-5 rounded-[2rem] font-black text-lg transition-all transform active:scale-95 ${
              status.auto_trade_enabled 
                ? 'bg-slate-800 text-rose-500 hover:bg-slate-700' 
                : 'bg-indigo-600 text-white hover:bg-indigo-500 shadow-xl shadow-indigo-600/30'
            }`}
          >
            {loading ? (
              <div className="w-6 h-6 border-2 border-current border-t-transparent rounded-full animate-spin" />
            ) : status.auto_trade_enabled ? (
              <>
                <Pause className="w-6 h-6 fill-current" />
                停止運行
              </>
            ) : (
              <>
                <Play className="w-6 h-6 fill-current" />
                啟動機器人
              </>
            )}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Account Info */}
        <div className="lg:col-span-1 space-y-8">
          <div className="p-8 bg-slate-900/40 border border-slate-800 rounded-[2.5rem] space-y-6">
            <div className="flex items-center gap-3">
              <Wallet className="w-6 h-6 text-indigo-400" />
              <h3 className="text-xl font-bold text-white">資產概況</h3>
            </div>
            
            <div className="space-y-4">
              <div className="p-6 bg-slate-800/50 rounded-2xl border border-slate-700">
                <p className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-1">可用餘額</p>
                <p className="text-3xl font-black text-white font-inter">
                  ${account.balance.toLocaleString()}
                </p>
              </div>
              
              <div className="p-6 bg-slate-800/50 rounded-2xl border border-slate-700">
                <p className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-1">帳戶狀態</p>
                <div className="flex items-center gap-2 mt-1">
                  <div className={`w-2 h-2 rounded-full ${account.status === 'connected' ? 'bg-emerald-500' : 'bg-rose-500'}`} />
                  <p className="font-bold text-white">
                    {account.status === 'connected' ? '連線正常' : '連線失敗'}
                  </p>
                </div>
              </div>
            </div>
            
            <button 
              onClick={() => showPlaceholderAlert('資金明細')}
              className="w-full py-4 bg-slate-800 hover:bg-slate-700 rounded-2xl text-slate-300 font-bold transition-all flex items-center justify-center gap-3"
            >
              <Landmark className="w-5 h-5" />
              資金明細
            </button>
          </div>
        </div>

        {/* Positions & Activity */}
        <div className="lg:col-span-2 space-y-8">
          <div className="p-8 bg-slate-900/40 border border-slate-800 rounded-[2.5rem] h-full flex flex-col">
            <div className="flex items-center justify-between mb-8">
              <div className="flex items-center gap-3">
                <TrendingUp className="w-6 h-6 text-emerald-400" />
                <h3 className="text-xl font-bold text-white">當前持倉</h3>
              </div>
              <button 
                onClick={() => showPlaceholderAlert('交易歷史')}
                className="text-indigo-400 text-sm font-bold hover:text-indigo-300 transition-all flex items-center gap-2"
              >
                <History className="w-4 h-4" />
                交易歷史
              </button>
            </div>

            {orders.length === 0 ? (
              <div className="flex-1 flex flex-col items-center justify-center py-12 text-center">
                <div className="w-20 h-20 bg-slate-800/50 rounded-full flex items-center justify-center mb-4 border border-slate-700">
                  <TrendingUp className="w-10 h-10 text-slate-600" />
                </div>
                <h4 className="text-lg font-bold text-slate-400">尚無持倉/委託部位</h4>
                <p className="text-slate-500 text-sm mt-2 max-w-xs">
                  機器人啟動後，若篩選到符合條件的優質標的將自動在此顯示。
                </p>
              </div>
            ) : (
              <div className="space-y-4 flex-1 overflow-y-auto pr-2 custom-scrollbar">
                {orders.map((order) => (
                  <div key={order.order_id} className="p-5 bg-slate-800/40 border border-slate-700 rounded-2xl flex items-center justify-between hover:bg-slate-800/60 transition-all">
                    <div className="flex items-center gap-4">
                      <div className={`w-12 h-12 rounded-xl flex items-center justify-center font-bold ${
                        order.action === "Buy" ? "bg-emerald-500/10 text-emerald-500" : "bg-rose-500/10 text-rose-500"
                      }`}>
                        {order.action === "Buy" ? "買" : "賣"}
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <p className="font-bold text-white text-lg">{order.symbol}</p>
                          <span className="text-xs px-2 py-0.5 bg-slate-700 text-slate-400 rounded-md uppercase font-mono">{order.order_id}</span>
                        </div>
                        <p className="text-sm text-slate-500 font-medium">
                          {order.qty} 股 · ${order.price} · {order.time}
                        </p>
                      </div>
                    </div>
                    <div className="text-right">
                      <span className={`px-3 py-1 rounded-full text-xs font-bold ${
                        order.status === "Filled" ? "bg-emerald-500/20 text-emerald-500" : "bg-amber-500/20 text-amber-500"
                      }`}>
                        {order.status === "Filled" ? "已成交" : "委託中"}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
            
            <div className="mt-auto pt-8 border-t border-slate-800">
              <div className="flex items-center justify-between p-6 bg-indigo-600/5 border border-indigo-500/20 rounded-2xl">
                <div className="flex items-center gap-4">
                  <Send className="w-6 h-6 text-indigo-400" />
                  <div>
                    <p className="font-bold text-indigo-300">手動緊急下單</p>
                    <p className="text-xs text-slate-500">直接對接 Shioaji API 執行即時委託</p>
                  </div>
                </div>
                <button 
                  onClick={handleManualOrder}
                  disabled={loading}
                  className="px-6 py-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl font-black transition-all disabled:opacity-50"
                >
                  立即執行
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TradingControl;
