import { useState } from 'react';
import { Play, ShieldAlert, CheckCircle2, Loader2, Search, Filter } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { quantService } from '../services/api';

const StrategyScan = () => {
  const [scanning, setScanning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [market, setMarket] = useState('TW');
  const [results, setResults] = useState([]);

  const startScan = async () => {
    try {
      setScanning(true);
      setProgress(0);
      setResults([]);
      
      // 呼叫後端 API 啟動海選
      await quantService.startScan(market, 0.5);
      
      // 每 1.5 秒輪詢進度
      const poll = setInterval(async () => {
        try {
          const resp = await quantService.getScanProgress();
          setProgress(resp.progress || 0);
          
          if (resp.status === 'completed' || resp.status === 'error') {
            clearInterval(poll);
            setScanning(false);
            
            // 將後端回傳的真實 Top 10 更新至畫面
            if (resp.top_results && resp.top_results.length > 0) {
              const formattedResults = resp.top_results.map(r => ({
                code: r.代碼,
                name: r.名稱,
                score: r.綜合評分,
                reason: r.操作建議
              }));
              setResults(formattedResults);
            }
          }
        } catch (err) {
          console.error("Failed to fetch scan progress", err);
        }
      }, 1500);
      
    } catch (err) {
      console.error("Failed to start scan", err);
      // 若後端回傳 400 Scan already in progress 等，需解除鎖定並接續進度
      setScanning(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      {/* Header & Controls */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div>
          <h2 className="text-2xl font-bold font-inter text-white">策略海選系統</h2>
          <p className="text-slate-500 text-sm mt-1">針對全市場標的進行深度量化掃描與評分</p>
        </div>

        <div className="flex items-center gap-4">
          <select 
            className="bg-slate-900 border border-slate-800 rounded-2xl px-4 py-3 text-sm text-slate-300 focus:ring-2 focus:ring-indigo-500 transition-all"
            value={market}
            onChange={(e) => setMarket(e.target.value)}
          >
            <option value="TW">台股全市場 (1,935 標的)</option>
            <option value="US">美股標普 500</option>
            <option value="CRYPTO">加密貨幣前 100 名</option>
          </select>
          
          <button
            onClick={startScan}
            disabled={scanning}
            className={`flex items-center gap-3 px-8 py-3 rounded-2xl font-bold transition-all shadow-xl ${
              scanning 
                ? 'bg-slate-800 text-slate-500' 
                : 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-indigo-600/20'
            }`}
          >
            {scanning ? <Loader2 className="w-5 h-5 animate-spin" /> : <Play className="w-5 h-5" />}
            {scanning ? `正在分析 ${progress}%` : '啟動海選'}
          </button>
        </div>
      </div>

      {/* Progress Bar */}
      <AnimatePresence>
        {scanning && (
          <motion.div 
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="w-full bg-slate-900/50 border border-slate-800 rounded-3xl p-8 overflow-hidden"
          >
            <div className="flex items-center justify-between mb-4">
              <span className="text-sm font-medium text-slate-400">正在處理數據池與計算指標...</span>
              <span className="text-sm font-bold text-indigo-400 font-inter">{progress}%</span>
            </div>
            <div className="w-full h-3 bg-slate-800 rounded-full overflow-hidden">
              <motion.div 
                className="h-full bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500"
                initial={{ width: 0 }}
                animate={{ width: `${progress}%` }}
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Results Grid */}
      {results.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {results.map((item, i) => (
            <motion.div 
              key={item.code}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.1 }}
              className="p-8 bg-slate-900/40 border-2 border-slate-800 rounded-[2.5rem] relative overflow-hidden group hover:border-indigo-500/50 transition-all"
            >
              <div className="absolute top-0 right-0 p-6">
                <div className="w-12 h-12 rounded-2xl bg-emerald-500/10 flex items-center justify-center font-bold text-emerald-400 text-xl font-inter">
                  {item.score}
                </div>
              </div>
              
              <div className="mb-6">
                <h4 className="text-2xl font-bold text-white mb-1">{item.code}</h4>
                <p className="text-slate-500 font-medium">{item.name}</p>
              </div>
              
              <div className="p-4 bg-slate-800/30 rounded-2xl border border-slate-800 mb-6">
                <p className="text-xs text-slate-500 uppercase tracking-widest font-bold mb-2 flex items-center gap-2">
                  <Filter className="w-3 h-3 text-indigo-400" />
                  篩選依據
                </p>
                <p className="text-sm text-slate-300 leading-relaxed italic">"{item.reason}"</p>
              </div>
              
              <button className="w-full py-3 bg-indigo-600/10 hover:bg-indigo-600 text-indigo-400 hover:text-white rounded-xl text-sm font-bold transition-all border border-indigo-600/20">
                加入追蹤清單
              </button>
            </motion.div>
          ))}
        </div>
      )}

      {/* Placeholder */}
      {!scanning && results.length === 0 && (
        <div className="flex flex-col items-center justify-center py-24 border-2 border-dashed border-slate-800 rounded-[3rem] bg-slate-900/20">
          <Search className="w-16 h-16 text-slate-800 mb-6" />
          <h3 className="text-xl font-bold text-slate-600">尚未執行海選</h3>
          <p className="text-slate-500 mt-2 max-w-sm text-center">選擇您感興趣的市場並點擊上方「啟動海選」按鈕，系統將自動從上千檔標的中篩選出最佳機會。</p>
        </div>
      )}
    </div>
  );
};

export default StrategyScan;
