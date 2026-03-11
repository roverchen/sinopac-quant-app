import { useState } from 'react';
import { Play, ShieldAlert, CheckCircle2, Loader2, Search, Filter } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const StrategyScan = () => {
  const [scanning, setScanning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [market, setMarket] = useState('TW');
  const [results, setResults] = useState([]);

  const startScan = () => {
    setScanning(true);
    setProgress(0);
    // Simulate progress
    const interval = setInterval(() => {
      setProgress(prev => {
        if (prev >= 100) {
          clearInterval(interval);
          setScanning(false);
          setResults([
            { code: '2330', name: '台積電', score: 92, reason: '價值位階極低 + MA20 金叉' },
            { code: '2454', name: '聯發科', score: 85, reason: '季線支撐守穩 + MACD 翻紅' },
            { code: '2317', name: '鴻海', score: 78, reason: '量價齊揚突破頸線' },
          ]);
          return 100;
        }
        return prev + 2;
      });
    }, 100);
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
