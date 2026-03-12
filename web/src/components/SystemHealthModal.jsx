import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, RefreshCcw, ShieldAlert, ShieldCheck, Terminal, Trash2, Info } from 'lucide-react';
import { diagService } from '../services/api';

const SystemHealthModal = ({ isOpen, onClose }) => {
  const [logs, setLogs] = useState([]);
  const [sysInfo, setSysInfo] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  const fetchData = async () => {
    setIsLoading(true);
    try {
      const data = await diagService.getLogs();
      setLogs(data.logs || []);
      setSysInfo(data.system_info);
    } catch (error) {
      console.error("Failed to fetch logs", error);
    } finally {
      setIsLoading(false);
    }
  };

  const clearLogs = async () => {
    if (confirm("確定要清空所有日誌嗎？")) {
      await diagService.clearLogs();
      fetchData();
    }
  };

  useEffect(() => {
    if (isOpen) fetchData();
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
          className="absolute inset-0 bg-black/80 backdrop-blur-sm"
        />
        
        <motion.div
          initial={{ scale: 0.95, opacity: 0, y: 20 }}
          animate={{ scale: 1, opacity: 1, y: 0 }}
          exit={{ scale: 0.95, opacity: 0, y: 20 }}
          className="relative w-full max-w-2xl bg-slate-900 border border-slate-800 rounded-[2rem] shadow-2xl overflow-hidden flex flex-col max-h-[80vh]"
        >
          {/* Header */}
          <div className="p-6 border-b border-white/5 flex items-center justify-between bg-slate-900/50 backdrop-blur-md">
            <div className="flex items-center gap-3">
              <div className={`p-2 rounded-xl ${sysInfo?.status === 'healthy' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'}`}>
                {sysInfo?.status === 'healthy' ? <ShieldCheck className="w-5 h-5" /> : <ShieldAlert className="w-5 h-5" />}
              </div>
              <div>
                <h2 className="text-lg font-bold text-white">系統狀態診斷中心</h2>
                <p className="text-xs text-slate-500 font-inter">System Health & Error Monitoring</p>
              </div>
            </div>
            <button onClick={onClose} className="p-2 hover:bg-white/5 rounded-xl transition-colors">
              <X className="w-5 h-5 text-slate-400" />
            </button>
          </div>

          {/* System Info Cards */}
          <div className="grid grid-cols-2 gap-4 p-6 bg-slate-950/30">
            <div className="p-4 bg-slate-800/20 border border-slate-700/30 rounded-2xl">
              <p className="text-[10px] text-slate-500 uppercase tracking-wider mb-1">應用版本</p>
              <p className="text-lg font-bold text-indigo-400 font-mono">{sysInfo?.version || 'v2.0.6'}</p>
            </div>
            <div className="p-4 bg-slate-800/20 border border-slate-700/30 rounded-2xl">
              <p className="text-[10px] text-slate-500 uppercase tracking-wider mb-1">環境狀態</p>
              <p className="text-lg font-bold text-emerald-400 font-mono capitalize">{sysInfo?.environment || 'Production'}</p>
            </div>
          </div>

          {/* Tabs/Actions */}
          <div className="px-6 py-2 flex items-center justify-between border-b border-white/5">
            <div className="flex items-center gap-2 text-slate-400 text-xs font-semibold">
              <Terminal className="w-4 h-4" />
              最近日誌 ({logs.length})
            </div>
            <div className="flex gap-2">
              <button 
                onClick={fetchData} 
                disabled={isLoading}
                className="p-2 hover:bg-white/5 text-slate-400 rounded-lg transition-all"
                title="重新整理"
              >
                <RefreshCcw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
              </button>
              <button 
                onClick={clearLogs}
                className="p-2 hover:bg-rose-500/10 text-slate-400 hover:text-rose-400 rounded-lg transition-all"
                title="清除日誌"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Logs Area */}
          <div className="flex-1 overflow-y-auto p-4 space-y-2 bg-slate-950 font-mono text-[11px]">
            {logs.length === 0 ? (
              <div className="h-40 flex flex-col items-center justify-center text-slate-600 italic">
                <Info className="w-8 h-8 opacity-20 mb-2" />
                目前沒有異常紀錄
              </div>
            ) : (
              logs.map((log, i) => (
                <div key={i} className={`p-3 rounded-xl border ${
                  log.level === 'ERROR' ? 'bg-rose-500/5 border-rose-500/20' : 'bg-amber-500/5 border-amber-500/20'
                } group`}>
                  <div className="flex items-center justify-between mb-1 opacity-60 group-hover:opacity-100 transition-opacity">
                    <span className={`px-2 py-0.5 rounded-md text-[9px] font-bold ${
                      log.level === 'ERROR' ? 'bg-rose-500/20 text-rose-400' : 'bg-amber-500/20 text-amber-400'
                    }`}>
                      {log.level}
                    </span>
                    <span className="text-slate-500">{log.timestamp} • {log.module}</span>
                  </div>
                  <p className="text-slate-300 leading-relaxed break-all">{log.message}</p>
                </div>
              ))
            )}
          </div>

          {/* Footer */}
          <div className="p-4 border-t border-white/5 text-center bg-slate-900/50">
            <p className="text-[10px] text-slate-600 uppercase tracking-widest font-inter">
              Sinopac Quant Pro Diagnostic Module
            </p>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};

export default SystemHealthModal;
