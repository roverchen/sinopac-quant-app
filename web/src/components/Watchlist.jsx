import { useState, useEffect } from 'react';
import { quantService } from '../services/api';
import { RefreshCw, Search, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { motion } from 'framer-motion';

const Watchlist = () => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  
  const symbols = ['2330', '2317', '0050', 'NVDA', 'TSLA', 'AAPL', 'BTC-USD'];

  const fetchData = async () => {
    setLoading(true);
    try {
      const resp = await quantService.analyze(symbols);
      setData(resp.results);
    } catch (err) {
      console.error('Fetch error:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const filteredData = data.filter(item => 
    item.代碼.toLowerCase().includes(search.toLowerCase()) ||
    item.名稱.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="relative w-80">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <input 
            type="text" 
            placeholder="搜尋代碼或名稱..."
            className="w-full pl-10 pr-4 py-2 bg-slate-900/50 border border-slate-800 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/50 transition-all font-inter"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        
        <button 
          onClick={fetchData}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 rounded-xl text-sm font-medium transition-all"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          立即更新
        </button>
      </div>

      <div className="bg-slate-900/40 border border-slate-800 rounded-3xl overflow-hidden backdrop-blur-sm">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-slate-800 bg-slate-800/20">
              <th className="px-6 py-4 text-sm font-semibold text-slate-400">標的</th>
              <th className="px-6 py-4 text-sm font-semibold text-slate-400">最新價格</th>
              <th className="px-6 py-4 text-sm font-semibold text-slate-400">一年位階</th>
              <th className="px-6 py-4 text-sm font-semibold text-slate-400">MACD 狀態</th>
              <th className="px-6 py-4 text-sm font-semibold text-slate-400">綜合評分</th>
              <th className="px-6 py-4 text-sm font-semibold text-slate-400">操作建議</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/50">
            {filteredData.map((item, idx) => (
              <motion.tr 
                key={item.代碼}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: idx * 0.05 }}
                className="hover:bg-slate-800/30 transition-colors group"
              >
                <td className="px-6 py-4">
                  <div className="flex flex-col">
                    <span className="font-bold text-slate-100 font-inter">{item.代碼}</span>
                    <span className="text-xs text-slate-500">{item.名稱}</span>
                  </div>
                </td>
                <td className="px-6 py-4 font-inter text-indigo-400 font-semibold text-lg">
                  {item.最新價格.toLocaleString()}
                </td>
                <td className="px-6 py-4">
                  <div className="w-32 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-gradient-to-r from-indigo-500 to-purple-500"
                      style={{ width: item.一年位階 }}
                    ></div>
                  </div>
                  <span className="text-xs text-slate-500 mt-1 block font-inter">{item.一年位階}</span>
                </td>
                <td className="px-6 py-4">
                  <span className={`text-xs px-2 py-1 rounded-lg ${
                    item.MACD狀態.includes('🚀') ? 'bg-emerald-500/10 text-emerald-400' : 
                    item.MACD狀態.includes('🔴') ? 'bg-rose-500/10 text-rose-400' : 'bg-slate-700/50 text-slate-400'
                  }`}>
                    {item.MACD狀態}
                  </span>
                </td>
                <td className="px-6 py-4 font-inter">
                  <span className={`text-lg font-bold ${
                    item.綜合評分 >= 80 ? 'text-emerald-400' : 
                    item.綜合評分 >= 60 ? 'text-indigo-400' : 'text-slate-500'
                  }`}>
                    {item.綜合評分}
                  </span>
                </td>
                <td className="px-6 py-4">
                  <p className="text-xs text-slate-400 max-w-xs">{item.操作建議}</p>
                </td>
              </motion.tr>
            ))}
            {!loading && filteredData.length === 0 && (
              <tr>
                <td colSpan="6" className="px-6 py-20 text-center text-slate-500">
                  <Minus className="w-8 h-8 mx-auto mb-2 opacity-20" />
                  <p>尚無追蹤數據，請點擊更新按鈕。</p>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default Watchlist;
