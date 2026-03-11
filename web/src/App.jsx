import { useState, useEffect } from 'react'
import { LayoutDashboard, ListFilter, Settings, ShieldCheck, TrendingUp, Cpu, LogOut } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import Watchlist from './components/Watchlist'
import Login from './components/Login'
import SettingsPage from './components/Settings'
import Dashboard from './components/Dashboard'
import StrategyScan from './components/StrategyScan'
import { authService } from './services/api'

const navItems = [
  { id: 'dashboard', label: '儀表板', icon: LayoutDashboard },
  { id: 'watchlist', label: '追蹤清單', icon: ListFilter },
  { id: 'strategy', label: '策略海選', icon: TrendingUp },
  { id: 'settings', label: '系統設定', icon: Settings },
]

function App() {
  const [activeTab, setActiveTab] = useState('dashboard')
  const [isAuthenticated, setIsAuthenticated] = useState(!!localStorage.getItem('token'))
  const [user, setUser] = useState(null)

  useEffect(() => {
    if (isAuthenticated) {
      authService.getMe().then(setUser).catch(() => {
        setIsAuthenticated(false)
        localStorage.removeItem('token')
      })
    }
  }, [isAuthenticated])

  if (!isAuthenticated) {
    return <Login onLoginSuccess={() => setIsAuthenticated(true)} />
  }

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 border-r border-slate-800 bg-slate-900/50 backdrop-blur-xl flex flex-col">
        <div className="p-6 flex items-center gap-3">
          <div className="p-2 bg-indigo-600 rounded-lg">
            <Cpu className="w-6 h-6 text-white" />
          </div>
          <h1 className="text-xl font-bold bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent">
            Quant Pro
          </h1>
        </div>

        <nav className="flex-1 px-4 py-4 space-y-2">
          {navItems.map((item) => (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 ${
                activeTab === item.id
                  ? 'bg-indigo-600/10 text-indigo-400 shadow-[inset_0_0_0_1px_rgba(79,70,229,0.2)]'
                  : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
              }`}
            >
              <item.icon className="w-5 h-5" />
              <span className="font-medium">{item.label}</span>
            </button>
          ))}
        </nav>

        <div className="p-6 border-t border-slate-800 space-y-4">
          <div className="p-4 bg-slate-800/50 rounded-2xl flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-indigo-500 to-purple-500 flex items-center justify-center font-bold text-white uppercase">
              {user?.user_id?.[0] || 'U'}
            </div>
            <div className="flex-1 overflow-hidden">
              <p className="text-sm font-semibold truncate text-white">{user?.user_id || 'User'}</p>
              <p className="text-xs text-slate-400 truncate">Pro Account</p>
            </div>
          </div>
          
          <button 
            onClick={() => {
              authService.logout()
              setIsAuthenticated(false)
            }}
            className="w-full flex items-center justify-center gap-2 py-2 text-xs text-slate-500 hover:text-rose-400 transition-colors"
          >
            <LogOut className="w-3 h-3" />
            登出系統
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto bg-[radial-gradient(circle_at_top_right,rgba(37,38,44,1),rgba(15,15,18,1))]">
        <header className="h-20 px-8 flex items-center justify-between border-b border-slate-800/50 sticky top-0 bg-slate-950/50 backdrop-blur-md z-10">
          <div className="flex items-center gap-2 text-slate-400 text-sm">
            <span>首頁</span>
            <span>/</span>
            <span className="text-slate-100 font-medium font-inter">
              {navItems.find(i => i.id === activeTab)?.label}
            </span>
          </div>
          
          <div className="flex items-center gap-4">
            <button className="px-4 py-2 bg-slate-800 hover:bg-slate-700 rounded-lg text-sm transition-colors border border-slate-700">
              重啟掃描
            </button>
            <div className="h-8 w-px bg-slate-800"></div>
            <div className="flex items-center gap-2 text-emerald-400 text-sm font-medium">
              <ShieldCheck className="w-4 h-4" />
              <span>系統正常</span>
            </div>
          </div>
        </header>

        <section className="p-8">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
          >
            {activeTab === 'dashboard' && <Dashboard />}
            {activeTab === 'watchlist' && <Watchlist />}
            {activeTab === 'strategy' && <StrategyScan />}
            {activeTab === 'settings' && <SettingsPage />}
            
            {(['dashboard', 'watchlist', 'strategy', 'settings'].indexOf(activeTab) === -1) && (
              <div className="mt-10 p-12 border-2 border-dashed border-slate-800 rounded-3xl flex flex-col items-center justify-center text-slate-500">
                <Cpu className="w-12 h-12 mb-4 opacity-20" />
                <p className="text-lg font-medium">正在構建 {navItems.find(i => i.id === activeTab)?.label} 模組...</p>
                <p className="text-sm mt-2 font-inter">Quant Pro 架構遷移進行中</p>
              </div>
            )}
          </motion.div>
        </section>
      </main>
    </div>
  )
}

export default App
