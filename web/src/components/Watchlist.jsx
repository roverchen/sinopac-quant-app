import { useState, useEffect, useCallback } from 'react';
import { quantService } from '../services/api';
import { RefreshCw, Search, TrendingUp, TrendingDown, Minus, Plus, ChevronLeft, ChevronRight, X } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  ComposedChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  Cell
} from 'recharts';

const Watchlist = () => {
  const [data, setData] = useState([]);
  const [cachedData, setCachedData] = useState({}); // 快取各市場的數據
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [marketType, setMarketType] = useState('ALL');
  const [defenseWeight, setDefenseWeight] = useState(0.5); // 動態權重
  const [selectedStock, setSelectedStock] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [qty, setQty] = useState(1);
  const [price, setPrice] = useState(0);
  const [orderLoading, setOrderLoading] = useState(false);
  
  // Pagination State
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [pageSize] = useState(20);

  // Scan Progress State
  const [scanProgress, setScanProgress] = useState(null);
  
  // Chart & Details State
  const [history, setHistory] = useState([]);
  const [isChartLoading, setIsChartLoading] = useState(false);
  const [trackedSymbols, setTrackedSymbols] = useState([]); // 追蹤中的代碼列表
  
  const fetchData = async (forceScan = false) => {
    const cacheKey = `${marketType}_${defenseWeight}`;
    // 如果不是強制掃描，且快取中有該權重下的資料，則先顯示快取以達到「秒開」
    if (!forceScan && cachedData[cacheKey] && !search && page === 1) {
      setData(cachedData[cacheKey].results || []);
      setTotal(cachedData[cacheKey].total || 0);
      // 仍然在後台偷偷更新一下，但不要切換 loading 狀態以維持流暢
    } else {
      setLoading(true);
      // Clear data to avoid showing stale results during loading
      setData([]);
    }

    try {
      // 獲取追蹤清單
      if (trackedSymbols.length === 0) {
        const allWatch = await quantService.getWatchlist('ALL');
        const unified = [
          ...(allWatch.TW || []),
          ...(allWatch.US || []),
          ...(allWatch.CRYPTO || [])
        ];
        setTrackedSymbols(unified);
      }

      if (marketType === 'ALL') {
        const resp = await quantService.analyze([], defenseWeight, 'ALL');
        let sortedData = (resp.results || []).sort((a, b) => b.score - a.score);
        
        if (search) {
          const q = search.toUpperCase();
          sortedData = sortedData.filter(item => 
            item.symbol.toUpperCase().includes(q) || item.name.toUpperCase().includes(q)
          );
        }
        
        setData(sortedData);
        setTotal(sortedData.length);
        setCachedData(prev => ({ ...prev, ALL: { results: sortedData, total: sortedData.length } }));
      } else {
        if (forceScan) {
          await quantService.startScan(marketType, defenseWeight);
          startPollingProgress();
          return;
        }
        // 使用新 API 傳入 defenseWeight
        const resp = await quantService.getResults(marketType, page, pageSize, search, defenseWeight);
        setData(resp.results || []);
        setTotal(resp.total || 0);
        
        // 只有在非搜尋且第一頁時快取
        if (!search && page === 1) {
          setCachedData(prev => ({ ...prev, [cacheKey]: resp }));
        }
      }
    } catch (err) {
      console.error('Fetch error:', err);
    } finally {
      setLoading(false);
    }
  };


  const startPollingProgress = () => {
    const interval = setInterval(async () => {
      try {
        const prog = await quantService.getScanProgress();
        setScanProgress(prog);
        if (prog.status === 'completed' || prog.status === 'error') {
          clearInterval(interval);
          setScanProgress(null);
          // 掃描完畢，重新抓取資料
          setPage(1);
          fetchData();
        }
      } catch (err) {
        clearInterval(interval);
        setScanProgress(null);
      }
    }, 2000);
  };

  useEffect(() => {
    // 切換市場時重置頁碼並立即清除當前資料，防止閃爍舊資料
    setData([]);
    setPage(1);
    fetchData();
  }, [marketType]);

  // 搜尋防抖處理
  useEffect(() => {
    const timer = setTimeout(() => {
      if (page !== 1) setPage(1);
      else fetchData();
    }, 500);
    return () => clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    // Check if a scan is already running on mount
    const checkInitialScan = async () => {
      try {
        const prog = await quantService.getScanProgress();
        if (prog && prog.status === 'running') {
          setScanProgress(prog);
          startPollingProgress();
        }
      } catch (err) {
        // Silently ignore
      }
    };
    checkInitialScan();
  }, []);

  useEffect(() => {
    fetchData();
  }, [marketType, page]);

  // Debounced effect for defenseWeight slider
  useEffect(() => {
    const handler = setTimeout(() => {
      fetchData();
    }, 400); // 400ms debounce
    return () => clearTimeout(handler);
  }, [defenseWeight]);

  const filteredData = data.filter(item => 
    item.symbol.toLowerCase().includes(search.toLowerCase()) ||
    item.name.toLowerCase().includes(search.toLowerCase())
  );

  const handleRowClick = async (stock) => {
    setSelectedStock(stock);
    const m = stock.market || marketType;
    if (m === 'TW') setQty(1000);
    else if (m === 'US') setQty(10);
    else if (m === 'CRYPTO') setQty(0.1);
    else setQty(1);
    
    setPrice(stock.price); // Initialize limit price
    setIsModalOpen(true);
    
    // 異步抓取歷史資料
    setIsChartLoading(true);
    try {
      const hist = await quantService.getHistory(stock.symbol, m);
      setHistory(hist);
    } catch (err) {
      console.error("Failed to load history", err);
      setHistory([]);
    } finally {
      setIsChartLoading(false);
    }
  };

  const handleToggleWatchlist = async () => {
    const isTracked = trackedSymbols.includes(selectedStock.symbol);
    const m = selectedStock.market || marketType;
    try {
      if (isTracked) {
        if (!window.confirm(`確定要將 ${selectedStock.symbol} 從我的清單移除嗎？`)) return;
        await quantService.removeFromWatchlist(selectedStock.symbol, m);
      } else {
        await quantService.addToWatchlist(selectedStock.symbol, m);
        alert(`已將 ${selectedStock.symbol} 加入我的清單`);
      }
      fetchData(); // 重新整理列表與狀態
    } catch (err) {
      alert("操作失敗");
    }
  };

  const handleOrder = async (isSimulation) => {
    setOrderLoading(true);
    try {
      const { tradeService } = await import('../services/api');
      const resp = await tradeService.placeOrder({
        symbol: selectedStock.symbol,
        qty: parseFloat(qty),
        price: parseFloat(price),
        action: "Buy",
        is_simulation: isSimulation
      });
      alert(`下單成功！單號: ${resp.trade_id}`);
      setIsModalOpen(false);
    } catch (err) {
      alert("下單失敗: " + (err.response?.data?.detail || "未知錯誤"));
    } finally {
      setOrderLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm(`確定要將 ${selectedStock.symbol} 從追蹤清單移除嗎？`)) return;
    try {
      await quantService.removeFromWatchlist(selectedStock.symbol, selectedStock.market || marketType);
      setIsModalOpen(false);
      fetchData();
    } catch (err) {
      alert("移除失敗");
    }
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-4 w-full sm:w-auto">
          <div className="bg-slate-900/80 p-1 rounded-xl border border-slate-800 flex overflow-x-auto no-scrollbar">
            {['ALL', 'TW', 'US', 'CRYPTO'].map((m) => (
              <button
                key={m}
                onClick={() => setMarketType(m)}
                className={`px-4 py-1.5 rounded-lg text-[10px] sm:text-xs font-bold transition-all whitespace-nowrap ${
                  marketType === m ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-500/20' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {m === 'ALL' ? '我的清單' : m === 'TW' ? '台股' : m === 'US' ? '美股' : '加密貨幣'}
              </button>
            ))}
          </div>
          
          <div className="relative w-full sm:w-64">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
            <input 
              type="text" 
              placeholder="搜尋代碼或名稱..."
              className="w-full pl-10 pr-4 py-2 bg-slate-900/50 border border-slate-800 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/50 transition-all font-inter text-sm"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </div>
        
        <div className="flex items-center gap-6">
          <div className="flex flex-col gap-1 w-48">
            <div className="flex justify-between text-[10px] font-black uppercase tracking-widest text-slate-500">
              <span>🛡 價值</span>
              <span>成長 🚀</span>
            </div>
            <input 
              type="range" 
              min="0" 
              max="1" 
              step="0.1" 
              value={defenseWeight}
              onChange={(e) => setDefenseWeight(parseFloat(e.target.value))}
              className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-indigo-500"
            />
            <div className="text-[10px] text-center font-bold text-indigo-400">
              比重配置: {Math.round(defenseWeight * 100)}% / {Math.round((1 - defenseWeight) * 100)}%
            </div>
          </div>
        </div>
      </div>

      {scanProgress && (
        <motion.div 
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-indigo-600/10 border border-indigo-500/20 rounded-2xl p-4 mb-6"
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-bold text-indigo-400">{scanProgress.message}</span>
            <span className="text-sm font-black text-indigo-400">{scanProgress.progress}%</span>
          </div>
          <div className="w-full h-2 bg-slate-800 rounded-full overflow-hidden">
            <motion.div 
              className="h-full bg-indigo-500"
              initial={{ width: 0 }}
              animate={{ width: `${scanProgress.progress}%` }}
            />
          </div>
        </motion.div>
      )}

      <div className="bg-slate-900/40 border border-slate-800 rounded-3xl overflow-hidden backdrop-blur-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-slate-800 bg-slate-800/20">
                <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider">標的</th>
                <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider">市場</th>
                <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider">最新價格</th>
                <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider text-center">一年位階</th>
                <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider">MACD 狀態</th>
                <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider text-center">綜合評分</th>
                <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider">操作建議</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50">
              {filteredData.map((item, idx) => (
                <motion.tr 
                  key={`${item.symbol}-${item.market}`}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: idx * 0.02 }}
                  onClick={() => handleRowClick(item)}
                  className="hover:bg-indigo-500/5 cursor-pointer transition-colors group"
                >
                  <td className="px-6 py-5">
                    <div className="flex flex-col">
                      <span className="font-bold text-slate-100 font-inter text-base group-hover:text-indigo-400 transition-colors leading-tight">{item.symbol}</span>
                      <span className="text-[10px] text-slate-500 font-bold mt-0.5 line-clamp-1">{item.name}</span>
                    </div>
                  </td>
                  <td className="px-6 py-5">
                    <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold border ${
                      item.market === 'TW' ? 'bg-blue-500/10 text-blue-400 border-blue-500/20' :
                      item.market === 'US' ? 'bg-purple-500/10 text-purple-400 border-purple-500/20' :
                      'bg-amber-500/10 text-amber-500 border-amber-500/20'
                    }`}>
                      {item.market}
                    </span>
                  </td>
                  <td className="px-6 py-5 font-inter text-indigo-400 font-bold text-lg">
                    {item.price.toLocaleString(undefined, { minimumFractionDigits: item.market === 'CRYPTO' ? 2 : (item.price < 10 ? 2 : 1) })}
                  </td>
                  <td className="px-6 py-5">
                    <div className="flex items-center gap-3 justify-center">
                      <div className="w-20 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                        <div 
                          className="h-full bg-gradient-to-r from-indigo-500 to-purple-500"
                          style={{ width: item.level }}
                        ></div>
                      </div>
                      <span className="text-xs text-slate-500 font-inter w-10">{item.level}</span>
                    </div>
                  </td>
                  <td className="px-6 py-5">
                    <span className={`text-[10px] px-2 py-1 rounded-md font-bold uppercase ${
                      item.macd_status.includes('Bullish') ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 
                      item.macd_status.includes('Bearish') ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20' : 'bg-slate-800 text-slate-500'
                    }`}>
                      {item.macd_status}
                    </span>
                  </td>
                  <td className="px-6 py-5 text-center">
                    <div className={`inline-flex items-center justify-center w-10 h-10 rounded-full font-inter font-black text-sm border-2 ${
                      item.score >= 80 ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 
                      item.score >= 60 ? 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20' : 'bg-slate-800/50 text-slate-500 border-transparent'
                    }`}>
                      {item.score}
                    </div>
                  </td>
                  <td className="px-6 py-5">
                    <p className="text-xs text-slate-400 leading-relaxed max-w-xs font-medium">{item.suggestion}</p>
                  </td>
                </motion.tr>
              ))}
              {!loading && filteredData.length === 0 && (
                <tr>
                  <td colSpan="7" className="px-6 py-24 text-center">
                    <div className="flex flex-col items-center opacity-30">
                      <Minus className="w-12 h-12 mb-3 text-slate-400" />
                      <p className="text-slate-400 font-bold text-lg">尚無數據</p>
                      <p className="text-slate-500 text-sm">請確認是否已完成海選掃描或已添加目標標的至我的清單。</p>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        
        {/* Pagination Controls */}
        {marketType !== 'ALL' && totalPages > 1 && (
          <div className="px-6 py-4 bg-slate-800/10 border-t border-slate-800 flex items-center justify-between">
            <div className="text-xs text-slate-500 font-medium">
              顯示第 {(page - 1) * pageSize + 1} 至 {Math.min(page * pageSize, total)} 筆，共 {total} 筆
            </div>
            <div className="flex items-center gap-2">
              <button 
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1 || loading}
                className="p-2 hover:bg-slate-800 rounded-lg disabled:opacity-30 transition-colors"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <span className="text-xs font-bold text-slate-300 px-2">頁次 {page} / {totalPages}</span>
              <button 
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page === totalPages || loading}
                className="p-2 hover:bg-slate-800 rounded-lg disabled:opacity-30 transition-colors"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* 買入對話框 Modal */}
      <AnimatePresence>
        {isModalOpen && selectedStock && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md">
            <motion.div 
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-3xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]"
            >
              <div className="overflow-y-auto p-8 space-y-6 custom-scrollbar">
                <div className="flex justify-between items-start">
                  <div>
                    <h3 className="text-2xl font-black text-white">{selectedStock.name}</h3>
                    <p className="text-slate-400 font-mono text-sm">{selectedStock.symbol}</p>
                  </div>
                  <button onClick={() => setIsModalOpen(false)} className="text-slate-500 hover:text-white transition-colors">
                    <X className="w-6 h-6" />
                  </button>
                </div>


                <div className="flex justify-between items-end bg-slate-800/20 p-4 rounded-2xl border border-slate-800/50">
                  <div className="space-y-1">
                    <p className="text-xs text-slate-500 font-bold uppercase">最新價格</p>
                    <p className="text-3xl font-black text-indigo-400 font-inter">
                      ${selectedStock.price.toLocaleString(undefined, { minimumFractionDigits: selectedStock.market === 'CRYPTO' ? 2 : 1 })}
                    </p>
                  </div>
                  <div className="text-right">
                    <span className={`text-xs px-2 py-1 rounded-md font-bold ${
                      selectedStock.score >= 80 ? 'text-emerald-400 bg-emerald-500/10' : 'text-indigo-400 bg-indigo-500/10'
                    }`}>
                      評分: {selectedStock.score}
                    </span>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-slate-800/30 p-4 rounded-2xl border border-slate-800/50">
                    <label className="text-xs font-bold text-slate-500 uppercase mb-2 block">委託數量</label>
                    <div className="flex items-center gap-4">
                      <input 
                        type="number" 
                        value={qty}
                        onChange={(e) => setQty(e.target.value)}
                        className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white font-inter font-bold focus:ring-2 focus:ring-indigo-500/50 outline-none"
                      />
                    </div>
                  </div>
                  <div className="bg-slate-800/30 p-4 rounded-2xl border border-slate-800/50">
                    <label className="text-xs font-bold text-slate-500 uppercase mb-2 block">委託價格</label>
                    <div className="flex items-center gap-4">
                      <input 
                        type="number" 
                        step="0.01"
                        value={price}
                        onChange={(e) => setPrice(e.target.value)}
                        className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white font-inter font-bold focus:ring-2 focus:ring-indigo-500/50 outline-none"
                      />
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <button 
                    onClick={() => handleOrder(true)}
                    disabled={orderLoading}
                    className="py-4 bg-slate-800 hover:bg-slate-700 text-white rounded-2xl font-bold transition-all disabled:opacity-50"
                  >
                    模擬下單
                  </button>
                  <button 
                    onClick={() => handleOrder(false)}
                    disabled={orderLoading || (
                      selectedStock?.market !== 'TW' && 
                      selectedStock?.market !== 'TSE' && 
                      selectedStock?.market !== 'OTC' &&
                      selectedStock?.market !== 'US' &&
                      selectedStock?.market !== 'CRYPTO'
                    )}
                    className="py-4 bg-indigo-600 hover:bg-indigo-500 text-white rounded-2xl font-bold transition-all shadow-lg shadow-indigo-600/20 disabled:opacity-30 disabled:cursor-not-allowed"
                  >
                    實盤交易
                  </button>
                </div>

                {/* K-Line Chart Section (Moved to Bottom) */}
                <div className="bg-slate-950/50 rounded-2xl p-4 border border-slate-800/50">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">3個月走勢參考</span>
                    {!isChartLoading && history.length > 0 && (
                      <span className="text-[10px] text-slate-600 font-inter">資料點: {history.length}</span>
                    )}
                  </div>
                  <StockChart data={history} loading={isChartLoading} />
                </div>

                <div className="flex items-center justify-between pt-4 border-t border-slate-800">
                  <button 
                    onClick={handleToggleWatchlist}
                    className={`flex items-center gap-2 text-sm font-bold transition-colors ${
                      trackedSymbols.includes(selectedStock.symbol) ? 'text-rose-500 hover:text-rose-400' : 'text-indigo-400 hover:text-indigo-300'
                    }`}
                  >
                    {trackedSymbols.includes(selectedStock.symbol) ? (
                      <><Minus className="w-4 h-4" /> 移出追蹤清單</>
                    ) : (
                      <><Plus className="w-4 h-4" /> 加入追蹤清單</>
                    )}
                  </button>
                  <button 
                    onClick={() => setIsModalOpen(false)}
                    className="text-slate-500 hover:text-slate-300 text-sm font-bold transition-colors"
                  >
                    取消
                  </button>
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
};

const StockChart = ({ data, loading }) => {
  if (loading) return <div className="h-48 flex items-center justify-center text-slate-500 text-xs font-bold animate-pulse">載入趨勢中...</div>;
  if (!data || data.length === 0) return <div className="h-48 flex items-center justify-center text-slate-500 text-xs">暫無歷史數據</div>;

  return (
    <div className="h-48 w-full mt-2">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} opacity={0.3} />
          <XAxis 
            dataKey="date" 
            axisLine={false} 
            tickLine={false} 
            tick={{ fill: '#475569', fontSize: 9, fontWeight: 600 }} 
            minTickGap={20}
          />
          <YAxis 
            hide 
            domain={['auto', 'auto']} 
          />
          <Tooltip 
            contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '12px', fontSize: '10px', boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1)' }}
            itemStyle={{ color: '#818cf8', fontWeight: 'bold' }}
            cursor={{ stroke: '#334155', strokeWidth: 1 }}
          />
          <Bar dataKey="close">
            {data.map((entry, index) => (
              <Cell 
                key={`cell-${index}`} 
                fill={entry.close >= entry.open ? '#10b981' : '#f43f5e'} 
                fillOpacity={0.8}
              />
            ))}
          </Bar>
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
};

export default Watchlist;
