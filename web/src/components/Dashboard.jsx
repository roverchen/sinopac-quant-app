import { motion } from 'framer-motion';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { ArrowUpRight, ArrowDownRight, Activity, Zap, Target, BarChart3 } from 'lucide-react';

const mockChartData = [
  { name: 'Mon', value: 4000 },
  { name: 'Tue', value: 3000 },
  { name: 'Wed', value: 5000 },
  { name: 'Thu', value: 4780 },
  { name: 'Fri', value: 5890 },
  { name: 'Sat', value: 5390 },
  { name: 'Sun', value: 6490 },
];

const StatCard = ({ label, value, change, color, icon: Icon }) => (
  <div className="p-6 bg-slate-900/40 border border-slate-800 rounded-3xl hover:border-slate-700 transition-all group">
    <div className="flex items-start justify-between mb-4">
      <div className={`p-3 rounded-2xl bg-${color}-500/10 text-${color}-400`}>
        <Icon className="w-6 h-6" />
      </div>
      <span className={`flex items-center gap-1 text-xs font-bold px-2 py-1 rounded-full ${
        change.startsWith('+') ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'
      }`}>
        {change.startsWith('+') ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
        {change}
      </span>
    </div>
    <p className="text-sm text-slate-500 font-medium mb-1">{label}</p>
    <h3 className="text-3xl font-bold font-inter text-white">{value}</h3>
  </div>
);

const Dashboard = () => {
  return (
    <div className="space-y-8">
      {/* Top Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard label="追蹤中標的" value="42" change="+12%" color="indigo" icon={Activity} />
        <StatCard label="今日海選量" value="1,935" change="+0.5%" color="emerald" icon={Zap} />
        <StatCard label="高評分機會" value="12" change="-5%" color="amber" icon={Target} />
        <StatCard label="策略勝率" value="78.2%" change="+2.4%" color="rose" icon={BarChart3} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Main Chart */}
        <div className="lg:col-span-2 p-8 bg-slate-900/40 border border-slate-800 rounded-[2.5rem] backdrop-blur-sm">
          <div className="flex items-center justify-between mb-8">
            <div>
              <h3 className="text-xl font-bold text-white">市場趨勢分析</h3>
              <p className="text-sm text-slate-500">加權指數與選股池相關性</p>
            </div>
            <select className="bg-slate-800 border-none rounded-xl text-xs px-3 py-2 text-slate-300 focus:ring-2 focus:ring-indigo-500">
              <option>過去 7 天</option>
              <option>過去 30 天</option>
            </select>
          </div>
          
          <div className="h-80 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={mockChartData}>
                <defs>
                  <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#4f46e5" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#4f46e5" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                <XAxis dataKey="name" stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '12px' }}
                  itemStyle={{ color: '#818cf8' }}
                />
                <Area type="monotone" dataKey="value" stroke="#4f46e5" strokeWidth={3} fillOpacity={1} fill="url(#colorValue)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Side Info */}
        <div className="p-8 bg-slate-900/40 border border-slate-800 rounded-[2.5rem] backdrop-blur-sm">
          <h3 className="text-xl font-bold text-white mb-6">今日焦點標的</h3>
          <div className="space-y-4">
            {[
              { code: '2330', name: '台積電', price: '1,045', score: 92 },
              { code: 'NVDA', name: 'Nvidia', price: '141.2', score: 88 },
              { code: 'BTC', name: 'Bitcoin', price: '98,240', score: 85 },
            ].map((item) => (
              <div key={item.code} className="p-4 bg-slate-800/30 rounded-2xl flex items-center justify-between border border-transparent hover:border-slate-700 transition-all">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-indigo-500/10 flex items-center justify-center font-bold text-indigo-400">
                    {item.code[0]}
                  </div>
                  <div>
                    <p className="text-sm font-bold text-white uppercase">{item.code}</p>
                    <p className="text-xs text-slate-500">{item.name}</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-sm font-bold text-white font-inter">{item.price}</p>
                  <p className="text-[10px] text-emerald-400 font-bold">Score: {item.score}</p>
                </div>
              </div>
            ))}
          </div>
          
          <button className="w-full mt-6 py-3 border border-indigo-500/30 text-indigo-400 rounded-xl text-sm font-bold hover:bg-indigo-500/10 transition-all">
            查看更多機會
          </button>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
