import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { ArrowUpRight, ArrowDownRight, Activity, Zap, Target, BarChart3, TrendingUp, Wallet, Landmark, Database } from 'lucide-react';
import { tradeService, quantService } from '../services/api';

// [v2.1.60] Removed mockChartData in favor of live API results

const Skeleton = ({ className }) => (
  <div className={`animate-pulse bg-slate-800/50 rounded-2xl ${className}`} />
);

const STRATEGY_ACCOUNTS = [
  { id: 'system_auto', label: 'Rover Rules 自動下單模擬', icon: Zap, color: 'emerald' },
  { id: 'system_eric', label: 'Eric Rules 台股模擬', icon: BarChart3, color: 'amber' },
];

const StatCard = ({ label, value, change, color, icon: Icon, subValue, loading, onClick }) => (
  <div 
    onClick={onClick}
    className={`p-6 bg-slate-900/40 border border-slate-800 rounded-3xl transition-all group relative overflow-hidden ${
      onClick ? 'cursor-pointer hover:border-indigo-500/50 hover:bg-slate-900/60' : 'hover:border-slate-700'
    }`}
  >
    {loading ? (
      <div className="space-y-4">
        <div className="flex justify-between">
          <Skeleton className="w-12 h-12" />
          <Skeleton className="w-16 h-6 rounded-full" />
        </div>
        <div className="space-y-2">
          <Skeleton className="w-24 h-4" />
          <Skeleton className="w-32 h-8" />
          <Skeleton className="w-20 h-3" />
        </div>
      </div>
    ) : (
      <>
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
      </>
    )}
  </div>
);

const Dashboard = ({ onNavigate }) => {
  const [summary, setSummary] = useState(null);
  const [focusTargets, setFocusTargets] = useState([]);
  const [chartData, setChartData] = useState([]);
  const [trendMarket, setTrendMarket] = useState('TW');
  const [trendDays, setTrendDays] = useState(7);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      try {
        await Promise.all([
          fetchSummary(),
          fetchFocusTargets(),
          fetchTrendData()
        ]);
      } catch (err) {
        console.error("Dashboard data load error:", err);
      } finally {
        setLoading(false);
      }
    };
    loadData();
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
      const [data, roverData, ericData] = await Promise.all([
        tradeService.getSummary(),
        tradeService.getSummary('system_auto'),
        tradeService.getSummary('system_eric')
      ]);
      setSummary({
        ...data,
        system_auto: roverData.mock,
        system_eric: ericData.mock
      });
    } catch (err) {
      console.error("Failed to fetch summary:", err);
    }
  };

  const fetchFocusTargets = async () => {
    try {
      // Fetch top 1 from each market in parallel
      const [tw, us, crypto] = await Promise.all([
        quantService.getResults('TW', 1, 1),
        quantService.getResults('US', 1, 1),
        quantService.getResults('CRYPTO', 1, 1)
      ]);
      
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
      {/* Performance Summary */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard 
          label="模擬總盈利率" 
          value={`${summary?.mock?.return_rate ?? 0}%`} 
          change={summary?.mock?.return_rate} 
          color="indigo" 
          icon={TrendingUp}
          subValue={`累計盈虧: $${summary?.mock?.total?.toLocaleString() || 0}`}
          loading={loading}
        />
        <StatCard 
          label="實盤總盈利率" 
          value={`${summary?.live?.return_rate ?? 0}%`} 
          change={summary?.live?.return_rate} 
          color="rose" 
          icon={Wallet}
          subValue={`累計盈虧: $${summary?.live?.total?.toLocaleString() || 0}`}
          loading={loading}
        />
        <StatCard 
          label={STRATEGY_ACCOUNTS[0].label}
          value={`${summary?.system_auto?.return_rate ?? 0}%`} 
          change={summary?.system_auto?.return_rate} 
          color={STRATEGY_ACCOUNTS[0].color}
          icon={Zap} 
          subValue={summary?.system_auto ? `成本: $${summary.system_auto.invested?.toLocaleString()} | 盈虧: $${summary.system_auto.total?.toLocaleString()}` : '載入中...'}
          loading={loading}
          onClick={() => onNavigate('trading', { viewAccount: 'system_auto' })}
        />
        <StatCard
          label={STRATEGY_ACCOUNTS[1].label}
          value={`${summary?.system_eric?.return_rate ?? 0}%`}
          change={summary?.system_eric?.return_rate}
          color={STRATEGY_ACCOUNTS[1].color}
          icon={BarChart3}
          subValue={summary?.system_eric ? `成本: $${summary.system_eric.invested?.toLocaleString()} | 盈虧: $${summary.system_eric.total?.toLocaleString()}` : '載入中...'}
          loading={loading}
          onClick={() => onNavigate('trading', { viewAccount: 'system_eric' })}
        />
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
            {loading ? (
              [1, 2, 3].map(i => (
                <div key={i} className="p-4 bg-slate-800/30 rounded-2xl flex items-center justify-between border border-transparent">
                  <div className="flex items-center gap-3 w-full">
                    <Skeleton className="w-10 h-10 rounded-xl" />
                    <div className="flex-1 space-y-2">
                      <Skeleton className="w-16 h-4" />
                      <Skeleton className="w-24 h-3" />
                    </div>
                    <div className="text-right space-y-2">
                      <Skeleton className="w-12 h-4 ml-auto" />
                      <Skeleton className="w-16 h-3 ml-auto" />
                    </div>
                  </div>
                </div>
              ))
            ) : focusTargets.length > 0 ? (
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
