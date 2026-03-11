import { useState, useEffect } from 'react';
import { authService } from '../services/api';
import { Save, Shield, Key, Landmark, Database, CheckCircle2, Settings as SettingsIcon } from 'lucide-react';
import { motion } from 'framer-motion';

const Settings = () => {
  const [creds, setCreds] = useState({
    shioaji_api_key: '',
    shioaji_secret_key: '',
    max_api_key: '',
    max_api_secret: '',
  });
  const [loading, setLoading] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    authService.getMe().then(user => {
      if (user?.creds) {
        setCreds({
          shioaji_api_key: user.creds.shioaji_api_key || '',
          shioaji_secret_key: user.creds.shioaji_secret_key || '',
          max_api_key: user.creds.max_api_key || '',
          max_api_secret: user.creds.max_api_secret || '',
        });
      }
    });
  }, []);

  const handleSave = async () => {
    setLoading(true);
    try {
      await authService.updateCredentials(creds);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      console.error('Save error:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div className="flex flex-col gap-2">
        <h2 className="text-2xl font-bold text-white flex items-center gap-3">
          <SettingsIcon className="w-6 h-6 text-indigo-400" />
          交易環境設定
        </h2>
        <p className="text-slate-400 text-sm">設定您的券商 API 憑證，這將永久儲存於加密資料庫中。</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {/* Sinopac Section */}
        <section className="p-8 bg-slate-900/40 border border-slate-800 rounded-[2rem] space-y-6">
          <div className="flex items-center gap-3 mb-2">
            <Landmark className="w-5 h-5 text-indigo-400" />
            <h3 className="text-lg font-semibold">永豐金證券 (Shioaji)</h3>
          </div>
          
          <div className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider ml-1">API Key</label>
              <input 
                type="password"
                className="w-full px-4 py-3 bg-slate-800/50 border border-slate-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/50 transition-all font-inter"
                value={creds.shioaji_api_key}
                onChange={(e) => setCreds({...creds, shioaji_api_key: e.target.value})}
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider ml-1">Secret Key</label>
              <input 
                type="password"
                className="w-full px-4 py-3 bg-slate-800/50 border border-slate-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/50 transition-all font-inter"
                value={creds.shioaji_secret_key}
                onChange={(e) => setCreds({...creds, shioaji_secret_key: e.target.value})}
              />
            </div>
          </div>
        </section>

        {/* MAX Section */}
        <section className="p-8 bg-slate-900/40 border border-slate-800 rounded-[2rem] space-y-6">
          <div className="flex items-center gap-3 mb-2">
            <Database className="w-5 h-5 text-indigo-400" />
            <h3 className="text-lg font-semibold">MAX 交易所 (Crypto)</h3>
          </div>
          
          <div className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider ml-1">API Key</label>
              <input 
                type="password"
                className="w-full px-4 py-3 bg-slate-800/50 border border-slate-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/50 transition-all font-inter"
                value={creds.max_api_key}
                onChange={(e) => setCreds({...creds, max_api_key: e.target.value})}
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider ml-1">Secret Key</label>
              <input 
                type="password"
                className="w-full px-4 py-3 bg-slate-800/50 border border-slate-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/50 transition-all font-inter"
                value={creds.max_api_secret}
                onChange={(e) => setCreds({...creds, max_api_secret: e.target.value})}
              />
            </div>
          </div>
        </section>
      </div>

      <div className="p-6 bg-indigo-600/5 border border-indigo-500/20 rounded-2xl flex items-start gap-4">
        <Shield className="w-6 h-6 text-indigo-400 mt-1 flex-shrink-0" />
        <div className="space-y-1">
          <p className="font-semibold text-indigo-300">隱私與安全保護</p>
          <p className="text-sm text-slate-400 leading-relaxed">
            所有憑證在傳輸過程中皆經過 AES-256 加密，並存儲於 Google Cloud 的受保護區域。
            系統僅在執行自動交易或獲取即時帳戶資訊時才會使用這些金鑰。
          </p>
        </div>
      </div>

      <div className="flex justify-end pt-4">
        <button
          onClick={handleSave}
          disabled={loading}
          className={`flex items-center gap-3 px-8 py-4 rounded-2xl font-bold transition-all ${
            saved 
              ? 'bg-emerald-500 text-white' 
              : 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-xl shadow-indigo-600/20'
          }`}
        >
          {loading ? (
            <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
          ) : saved ? (
            <CheckCircle2 className="w-5 h-5" />
          ) : (
            <Save className="w-5 h-5" />
          )}
          {saved ? '已成功儲存' : '儲存所有設定'}
        </button>
      </div>
    </div>
  );
};

export default Settings;
