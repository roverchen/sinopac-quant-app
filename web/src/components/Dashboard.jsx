import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { ArrowUpRight, ArrowDownRight, Activity, Zap, Target, BarChart3, TrendingUp, Wallet, Landmark, Database } from 'lucide-react';
import { tradeService, quantService } from '../services/api';

// [v2.1.60] Removed mockChartData in favor of live API results

const StatCard = ({ label, value, change, color, icon: Icon, subValue }) => (
  <div className="p-6 bg-slate-900/40 border border-slate-800 rounded-3xl hover:border-slate-700 transition-all group relative overflow-hidden">
    <div className="flex items-start justify-between mb-4">
      <div className={`p-3 rounded-2xl bg-${color}-500/10 text-${color}-400`}>
        <Icon className="w-6 h-6" />
      </div>
      {change !== undefined && (
        <span className={`flex items-center gap-1 text-xs font-bold px-2 py-1 rounded-full ${
          Number(change) >= 0 ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'
        }`}>
          {Number(change) >= 0 ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
          {Math.abs(Number(change))}%
        </span>
      )}
    </div>
    <p className="text-sm text-slate-500 font-medium mb-1">{label}</p>
    <h3 className="text-3xl font-bold font-inter text-white">{value}</h3>
    {subValue && <p className="text-xs text-slate-500 mt-2 font-mono">{subValue}</p>}
  </div>
);

const Dashboard = ({ onNavigate }) => {
  const [summary, setSummary] = useState(null);
  const [balance, setBalance] = useState(null);
  const [focusTargets, setFocusTargets] = useState([]);
  const [chartData, setChartData] = useState([]);
  const [trendMarket, setTrendMarket] = useState('TW');
  const [trendDays, setTrendDays] = useState(7);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchSummary();
    fetchBalance();
    fetchFocusTargets();
    fetchTrendData();
  }, [trendMarket, trendDays]);

  const fetchTrendData = async () => {
    try {
      const data = await quantService.getTrend(trendMarket, trendDays);
      setChartData(data.chart_data || []);
    } catch (err) {
      console.error("Failed to fetch trend data:", err);
    }
  };

  const fetchSummary = async () => {
    try {
      const data = await tradeService.getSummary();
      const autoData = await tradeService.getSummary('system_auto');
      setSummary({
        ...data,
        system_auto: autoData.mock
      });
    } catch (err) {
      console.error("Failed to fetch summary:", err);
    }
  };

  const fetchBalance = async () => {
    try {
      const data = await tradeService.getBalance();
      setBalance(data);
    } catch (err) {
      console.error("Failed to fetch balance:", err);
    } finally {
      setLoading(false);
    }
  };

  const fetchFocusTargets = async () => {
    try {
      // Fetch top 1 from each market
      const tw = await quantService.getResults('TW', 1, 1);
      const us = await quantService.getResults('US', 1, 1);
      const crypto = await quantService.getResults('CRYPTO', 1, 1);
      
      const combined = [
        ...(tw.results || []),
        ...(us.results || []),
        ...(crypto.results || [])
      ].sort((a, b) => b.score - a.score);
      
      setFocusTargets(combined.slice(0, 3));
    } catch (err) {
      console.error("Failed to fetch focus targets:", err);
    }
  };

  return (
    <div className="space-y-8">
      {/* Real-time Balances */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="p-8 bg-gradient-to-br from-indigo-600/20 to-purple-600/10 border border-indigo-500/20 rounded-[2.5rem] relative overflow-hidden group">
          <div className="absolute top-0 right-0 p-8 opacity-10 group-hover:scale-110 transition-transform">
            <Landmark className="w-24 h-24 text-white" />
          </div>
          <div className="relative z-10">
            <div className="flex items-center gap-2 text-indigo-400 mb-2">
              <Landmark className="w-5 h-5" />
              <span className="text-xs font-black uppercase tracking-widest">永豐金證券 (Sinopac)</span>
            </div>
            <h2 className="text-4xl font-black text-white font-inter">
              ${balance?.sinopac_twd !== undefined ? balance.sinopac_twd.toLocaleString() : '...'}
              <span className="text-sm font-medium text-slate-500 ml-2">TWD</span>
            </h2>
            <p className="text-xs text-slate-400 mt-2 font-medium">可用交割金額 (已串接 API)</p>
          </div>
        </div>

        <div className="p-8 bg-gradient-to-br from-emerald-600/20 to-teal-600/10 border border-emerald-500/20 rounded-[2.5rem] relative overflow-hidden group">
          <div className="absolute top-0 right-0 p-8 opacity-10 group-hover:scale-110 transition-transform">
            <Database className="w-24 h-24 text-white" />
          </div>
          <div className="relative z-10">
            <div className="flex items-center gap-2 text-emerald-400 mb-2">
              <Database className="w-5 h-5" />
              <span className="text-xs font-black uppercase tracking-widest">MAX 交易所 (Crypto)</span>
            </div>
            <h2 className="text-4xl font-black text-white font-inter">
              ${balance?.max?.total_twd_estimate !== undefined ? balance.max.total_twd_estimate.toLocaleString() : '0'}
              <span className="text-sm font-medium text-slate-500 ml-2">TWD (估值)</span>
            </h2>
            <div className="flex gap-4 mt-2">
              <p className="text-[10px] text-slate-400 font-bold uppercase">TWD: ${balance?.max?.twd !== undefined ? balance.max.twd.toLocaleString() : 0}</p>
              <p className="text-[10px] text-slate-400 font-bold uppercase">USDT: {balance?.max?.usdt !== undefined ? balance.max.usdt.toLocaleString() : 0}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Performance Summary */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard 
          label="模擬總盈利率" 
          value={`${summary?.mock?.return_rate ?? 0}%`} 
          change={summary?.mock?.return_rate} 
          color="indigo" 
          icon={TrendingUp}
          subValue={`累計盈虧: $${summary?.mock?.total?.toLocaleString() || 0}`}
        />
        <StatCard 
          label="實盤總盈利率" 
          value={`${summary?.live?.return_rate ?? 0}%`} 
          change={summary?.live?.return_rate} 
          color="rose" 
          icon={Wallet}
          subValue={`累計盈虧: $${summary?.live?.total?.toLocaleString() || 0}`}
        />
        <StatCard 
          label="系統自動下單模擬總成效" 
          value={`${summary?.system_auto?.return_rate ?? 0}%`} 
          change={summary?.system_auto?.return_rate} 
          color="emerald" 
          icon={Zap} 
          subValue={`回報率(百分比)`}
        />
        <StatCard label="策略平均勝率" value="78.2%" change="+2.4" color="amber" icon={BarChart3} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Main Chart */}
        <div className="lg:col-span-2 p-8 bg-slate-900/40 border border-slate-800 rounded-[2.5rem] backdrop-blur-sm">
          <div className="flex items-center justify-between mb-8">
            <div>
              <h3 className="text-xl font-bold text-white">市場趨勢分析</h3>
              <p className="text-sm text-slate-500">市場指數與核心選股池 (Top 5) 之相關性趨勢</p>
            </div>
            <div className="flex gap-2">
              <select 
                value={trendMarket}
                onChange={(e) => setTrendMarket(e.target.value)}
                className="bg-slate-800 border-none rounded-xl text-[10px] px-3 py-2 text-slate-300 focus:ring-2 focus:ring-indigo-500 font-bold"
              >
                <option value="TW">TW (台股)</option>
                <option value="US">US (美股)</option>
                <option value="CRYPTO">Crypto (加密貨幣)</option>
              </select>
              <select 
                value={trendDays}
                onChange={(e) => setTrendDays(Number(e.target.value))}
                className="bg-slate-800 border-none rounded-xl text-[10px] px-3 py-2 text-slate-300 focus:ring-2 focus:ring-indigo-500 font-bold"
              >
                <option value={7}>過去 7 天</option>
                <option value={14}>過去 14 天</option>
                <option value={30}>過去 30 天</option>
              </select>
            </div>
          </div>
          
          <div className="h-80 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData}>
                <defs>
                  <linearGradient id="colorPool" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.2}/>
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                  </linearGradient>
                  <linearGradient id="colorIndex" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#64748b" stopOpacity={0.1}/>
                    <stop offset="95%" stopColor="#64748b" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                <XAxis dataKey="name" stroke="#64748b" fontSize={10} tickLine={false} axisLine={false} />
                <YAxis domain={['auto', 'auto']} stroke="#64748b" fontSize={10} tickLine={false} axisLine={false} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '12px' }}
                  itemStyle={{ fontSize: '12px' }}
                />
                <Area name="核心選股池 (Top 5)" type="monotone" dataKey="pool" stroke="#10b981" strokeWidth={3} fillOpacity={1} fill="url(#colorPool)" />
                <Area name="市場基準指數" type="monotone" dataKey="index" stroke="#64748b" strokeWidth={2} strokeDasharray="5 5" fillOpacity={1} fill="url(#colorIndex)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-4 flex justify-center gap-6">
             <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-emerald-500 rounded-full"></div>
                <span className="text-[10px] text-slate-400 font-bold">選股池表現</span>
             </div>
             <div className="flex items-center gap-2">
                <div className="w-3 h-3 border-2 border-slate-500 border-dashed rounded-full"></div>
                <span className="text-[10px] text-slate-400 font-bold">大盤指數</span>
             </div>
          </div>
        </div>

        {/* Side Info */}
        <div className="p-8 bg-slate-900/40 border border-slate-800 rounded-[2.5rem] backdrop-blur-sm">
          <h3 className="text-xl font-bold text-white mb-6">今日焦點標的</h3>
          <div className="space-y-4">
            {focusTargets.length > 0 ? (
              focusTargets.map((item) => (
                <div key={item.symbol} className="p-4 bg-slate-800/30 rounded-2xl flex items-center justify-between border border-transparent hover:border-slate-700 transition-all cursor-pointer group">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-indigo-500/10 flex items-center justify-center font-bold text-indigo-400">
                      {item.symbol[0]}
                    </div>
                    <div>
                      <p className="text-sm font-bold text-white uppercase">{item.symbol}</p>
                      <p className="text-xs text-slate-500">{item.name}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-bold text-white font-inter">{item.price.toLocaleString()}</p>
                    <p className="text-[10px] text-emerald-400 font-bold">Score: {item.score}</p>
                  </div>
                </div>
              ))
            ) : (
              <div className="py-10 text-center opacity-20">
                <Target className="w-8 h-8 mx-auto mb-2" />
                <p className="text-xs">等待掃描數據...</p>
              </div>
            )}
          </div>
          
          <button 
            onClick={() => onNavigate && onNavigate('watchlist')}
            className="w-full mt-6 py-3 border border-indigo-500/30 text-indigo-400 rounded-xl text-sm font-bold hover:bg-indigo-500/10 transition-all"
          >
            查看更多機會
          </button>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
