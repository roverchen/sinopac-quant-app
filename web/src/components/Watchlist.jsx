import { useState, useEffect } from 'react';
import { quantService } from '../services/api';
import { RefreshCw, Search, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { motion } from 'framer-motion';

const Watchlist = () => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [marketType, setMarketType] = useState('TW');
  const [selectedStock, setSelectedStock] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [qty, setQty] = useState(1);
  const [orderLoading, setOrderLoading] = useState(false);
  
  const fetchData = async () => {
    setLoading(true);
    try {
      // 1. 先取得使用者儲存的追蹤清單代碼
      const watchlistResp = await quantService.getWatchlist(marketType);
      const symbols = watchlistResp.watchlist || [];
      
      if (symbols.length === 0) {
        setData([]);
        return;
      }

      // 2. 分析這些代碼
      const resp = await quantService.analyze(symbols, 0.5, marketType);
      // 3. 按照綜合評分由大到小排序
      const sortedData = (resp.results || []).sort((a, b) => b.綜合評分 - a.綜合評分);
      setData(sortedData);
    } catch (err) {
      console.error('Fetch error:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [marketType]);

  const filteredData = data.filter(item => 
    item.代碼.toLowerCase().includes(search.toLowerCase()) ||
    item.名稱.toLowerCase().includes(search.toLowerCase())
  );

  const handleRowClick = (stock) => {
    setSelectedStock(stock);
    // 設置預設股數：台股 1000, 美股 10, 加密貨幣 0.1
    if (marketType === 'TW') setQty(1000);
    else if (marketType === 'US') setQty(10);
    else setQty(0.1);
    setIsModalOpen(true);
  };

  const handleOrder = async (isSimulation) => {
    setOrderLoading(true);
    try {
      const { tradeService } = await import('../services/api');
      const resp = await tradeService.placeOrder({
        symbol: selectedStock.代碼,
        qty: parseFloat(qty),
        price: selectedStock.最新價格,
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
    if (!window.confirm(`確定要將 ${selectedStock.代碼} 從追蹤清單移除嗎？`)) return;
    try {
      await quantService.removeFromWatchlist(selectedStock.代碼, marketType);
      setIsModalOpen(false);
      fetchData();
    } catch (err) {
      alert("移除失敗");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="bg-slate-900/80 p-1 rounded-xl border border-slate-800 flex">
            {['TW', 'US', 'CRYPTO'].map((m) => (
              <button
                key={m}
                onClick={() => setMarketType(m)}
                className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-all ${
                  marketType === m ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-500/20' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {m === 'TW' ? '台股' : m === 'US' ? '美股' : '加密貨幣'}
              </button>
            ))}
          </div>
          
          <div className="relative w-64">
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
        
        <button 
          onClick={fetchData}
          disabled={loading}
          className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 rounded-xl text-sm font-bold transition-all shadow-lg shadow-indigo-600/20"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          刷新分析
        </button>
      </div>

      <div className="bg-slate-900/40 border border-slate-800 rounded-3xl overflow-hidden backdrop-blur-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-slate-800 bg-slate-800/20">
                <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider">標的</th>
                <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider">最新價格</th>
                <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider">一年位階</th>
                <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider">MACD 狀態</th>
                <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider text-center">綜合評分</th>
                <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider">操作建議</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50">
              {filteredData.map((item, idx) => (
                <motion.tr 
                  key={item.代碼}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: idx * 0.03 }}
                  onClick={() => handleRowClick(item)}
                  className="hover:bg-indigo-500/5 cursor-pointer transition-colors group"
                >
                  <td className="px-6 py-5">
                    <div className="flex flex-col">
                      <span className="font-bold text-slate-100 font-inter text-base">{item.代碼}</span>
                      <span className="text-xs text-slate-500 font-medium">{item.名稱}</span>
                    </div>
                  </td>
                  <td className="px-6 py-5 font-inter text-indigo-400 font-bold text-lg">
                    {item.最新價格.toLocaleString()}
                  </td>
                  <td className="px-6 py-5">
                    <div className="flex items-center gap-3">
                      <div className="w-24 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                        <div 
                          className="h-full bg-gradient-to-r from-indigo-500 to-purple-500"
                          style={{ width: item.一年位階 }}
                        ></div>
                      </div>
                      <span className="text-xs text-slate-500 font-inter">{item.一年位階}</span>
                    </div>
                  </td>
                  <td className="px-6 py-5">
                    <span className={`text-[10px] px-2 py-1 rounded-md font-bold uppercase ${
                      item.MACD狀態.includes('🚀') ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 
                      item.MACD狀態.includes('🔴') ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20' : 'bg-slate-800 text-slate-500'
                    }`}>
                      {item.MACD狀態}
                    </span>
                  </td>
                  <td className="px-6 py-5 text-center">
                    <div className={`inline-flex items-center justify-center w-10 h-10 rounded-full font-inter font-black text-sm border-2 ${
                      item.綜合評分 >= 80 ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 
                      item.綜合評分 >= 60 ? 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20' : 'bg-slate-800/50 text-slate-500 border-transparent'
                    }`}>
                      {item.綜合評分}
                    </div>
                  </td>
                  <td className="px-6 py-5">
                    <p className="text-xs text-slate-400 leading-relaxed max-w-xs font-medium">{item.操作建議}</p>
                  </td>
                </motion.tr>
              ))}
              {!loading && filteredData.length === 0 && (
                <tr>
                  <td colSpan="6" className="px-6 py-24 text-center">
                    <div className="flex flex-col items-center opacity-30">
                      <Minus className="w-12 h-12 mb-3 text-slate-400" />
                      <p className="text-slate-400 font-bold text-lg">尚無追蹤數據</p>
                      <p className="text-slate-500 text-sm">請切換市場或添加標的後重新刷新。</p>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* 買入對話框 Modal */}
      {isModalOpen && selectedStock && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md">
          <motion.div 
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-3xl shadow-2xl overflow-hidden"
          >
            <div className="p-8 space-y-6">
              <div className="flex justify-between items-start">
                <div>
                  <h3 className="text-2xl font-black text-white">{selectedStock.名稱}</h3>
                  <p className="text-slate-400 font-mono text-sm">{selectedStock.代碼}</p>
                </div>
                <div className="text-right">
                  <p className="text-3xl font-black text-indigo-400 font-inter">${selectedStock.最新價格.toLocaleString()}</p>
                  <p className="text-xs text-slate-500">最新收盤價</p>
                </div>
              </div>

              <div className="bg-slate-800/30 p-4 rounded-2xl border border-slate-800/50">
                <label className="text-xs font-bold text-slate-500 uppercase mb-2 block">下單數量</label>
                <div className="flex items-center gap-4">
                  <input 
                    type="number" 
                    value={qty}
                    onChange={(e) => setQty(e.target.value)}
                    className="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white font-inter font-bold focus:ring-2 focus:ring-indigo-500/50 outline-none"
                  />
                  <span className="text-slate-400 font-bold">{marketType === 'TW' ? '股' : marketType === 'US' ? '股' : '單位'}</span>
                </div>
                <p className="text-[10px] text-indigo-400 mt-2 font-medium">✨ 已根據市場慣例自動填入預設數量</p>
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
                  disabled={orderLoading}
                  className="py-4 bg-indigo-600 hover:bg-indigo-500 text-white rounded-2xl font-bold transition-all shadow-lg shadow-indigo-600/20 disabled:opacity-50"
                >
                  實盤交易
                </button>
              </div>

              <div className="flex items-center justify-between pt-4 border-t border-slate-800">
                <button 
                  onClick={handleDelete}
                  className="flex items-center gap-2 text-rose-500 hover:text-rose-400 text-sm font-bold transition-colors"
                >
                  <Minus className="w-4 h-4" />
                  移出追蹤清單
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
    </div>
  );
};

export default Watchlist;
