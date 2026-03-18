import { useState, useEffect } from 'react';
import { authService, tradeService } from '../services/api';
import { Save, Shield, Key, Landmark, Database, CheckCircle2, Settings as SettingsIcon, Clock, Mail } from 'lucide-react';
import { motion } from 'framer-motion';

const Skeleton = ({ className }) => (
  <div className={`animate-pulse bg-slate-800/50 rounded-2xl ${className}`} />
);

const Settings = () => {
  const [creds, setCreds] = useState({
    shioaji_api_key: '',
    shioaji_secret_key: '',
    max_api_key: '',
    max_api_secret: '',
  });
  const [settings, setSettings] = useState({
    email_notifications_enabled: true
  });
  const [balance, setBalance] = useState(null);
  const [loading, setLoading] = useState(false);
  const [balanceLoading, setBalanceLoading] = useState(true);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setBalanceLoading(true);
    authService.getMe().then(user => {
      if (user?.creds) {
        setCreds({
          shioaji_api_key: user.creds.shioaji_api_key || '',
          shioaji_secret_key: user.creds.shioaji_secret_key || '',
          shioaji_person_id: user.creds.shioaji_person_id || '',
          shioaji_ca_password: user.creds.shioaji_ca_password || '',
          shioaji_ca_base64: user.creds.shioaji_ca_base64 || '',
          ca_filename: user.creds.shioaji_ca_base64 ? '(已儲存的憑證)' : '',
          max_api_key: user.creds.max_api_key || '',
          max_api_secret: user.creds.max_api_secret || '',
        });
      }
    });

    authService.getSettings().then(data => {
      if (data) setSettings(data);
    });

    try {
      const data = await tradeService.getBalance();
      setBalance(data);
    } catch (err) {
      console.error("Failed to fetch balance in settings:", err);
    } finally {
      setBalanceLoading(false);
    }
  };

  const handleSave = async () => {
    setLoading(true);
    try {
      await Promise.all([
        authService.updateCredentials(creds),
        authService.updateSettings(settings)
      ]);
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
        <p className="text-slate-400 text-sm">設定您的券商 API 憑證，並即時查閱帳戶資產餘額。</p>
      </div>

      {/* Balance Cards (Moved from Dashboard) */}
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
              {balanceLoading ? (
                <Skeleton className="w-48 h-10 my-1" />
              ) : (
                <>
                  ${balance?.sinopac_twd !== undefined ? balance.sinopac_twd.toLocaleString() : '0'}
                  <span className="text-sm font-medium text-slate-500 ml-2">TWD</span>
                </>
              )}
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
              {balanceLoading ? (
                <Skeleton className="w-48 h-10 my-1" />
              ) : (
                <>
                  ${balance?.max?.total_twd_estimate !== undefined ? balance.max.total_twd_estimate.toLocaleString() : '0'}
                  <span className="text-sm font-medium text-slate-500 ml-2">TWD (估值)</span>
                </>
              )}
            </h2>
            <div className="flex gap-4 mt-2">
              {balanceLoading ? (
                <Skeleton className="w-32 h-3" />
              ) : (
                <>
                  <p className="text-[10px] text-slate-400 font-bold uppercase">TWD: ${balance?.max?.twd !== undefined ? balance.max.twd.toLocaleString() : 0}</p>
                  <p className="text-[10px] text-slate-400 font-bold uppercase">USDT: {balance?.max?.usdt !== undefined ? balance.max.usdt.toLocaleString() : 0}</p>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {/* Sinopac Section */}
        <section className="p-8 bg-slate-900/40 border border-slate-800 rounded-[2rem] space-y-6">
          <div className="flex items-center gap-3 mb-2">
            <Landmark className="w-5 h-5 text-indigo-400" />
            <h3 className="text-lg font-semibold">永豐金證券 (Shioaji)</h3>
          </div>
          
          <div className="space-y-4">
            <div className="space-y-1.5 text-right mb-2">
              <span className="text-[10px] bg-indigo-500/10 text-indigo-400 px-2 py-0.5 rounded-full font-bold">
                實盤交易必填 - 包含憑證 (CA)
              </span>
            </div>
            
            <div className="grid grid-cols-1 gap-4">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider ml-1">身分證字號</label>
                <input 
                  type="text"
                  placeholder="A123456789"
                  className="w-full px-4 py-3 bg-slate-800/50 border border-slate-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/50 transition-all font-inter"
                  value={creds.shioaji_person_id || ''}
                  onChange={(e) => setCreds({...creds, shioaji_person_id: e.target.value.toUpperCase()})}
                />
              </div>
            </div>

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

            <div className="border-t border-slate-800/50 pt-4 mt-2 space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-indigo-400 uppercase tracking-wider ml-1">下單憑證 (.pfx / .p12)</label>
                <div className="relative group">
                  <input 
                    type="file"
                    accept=".pfx,.p12"
                    onChange={(e) => {
                      const file = e.target.files[0];
                      if (file) {
                        const reader = new FileReader();
                        reader.onload = (readerEvt) => {
                          const binaryString = readerEvt.target.result;
                          const base64 = btoa(binaryString);
                          setCreds({...creds, shioaji_ca_base64: base64, ca_filename: file.name});
                        };
                        reader.readAsBinaryString(file);
                      }
                    }}
                    className="w-full px-4 py-3 bg-indigo-600/5 border border-dashed border-indigo-500/30 rounded-xl focus:outline-none cursor-pointer text-xs"
                  />
                  {creds.ca_filename && (
                    <div className="mt-2 text-[10px] text-emerald-400 font-bold flex items-center gap-1">
                      <CheckCircle2 className="w-3 h-3" /> 已選取憑證: {creds.ca_filename}
                    </div>
                  )}
                </div>
              </div>
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider ml-1">憑證密碼</label>
                <input 
                  type="password"
                  placeholder="CA Password"
                  className="w-full px-4 py-3 bg-slate-800/50 border border-slate-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/50 transition-all font-inter"
                  value={creds.shioaji_ca_password || ''}
                  onChange={(e) => setCreds({...creds, shioaji_ca_password: e.target.value})}
                />
              </div>
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

      {/* Notification Settings */}
      <section className="p-8 bg-slate-900/40 border border-slate-800 rounded-[2rem] space-y-6">
        <div className="flex items-center gap-3 mb-2">
          <Mail className="w-5 h-5 text-indigo-400" />
          <h3 className="text-lg font-semibold">通知設定 (Notification Settings)</h3>
        </div>
        
        <div className="flex items-center justify-between p-4 bg-slate-800/30 rounded-2xl border border-slate-700/50">
          <div className="space-y-1">
            <p className="font-semibold text-white text-sm">每日交易郵件通知</p>
            <p className="text-xs text-slate-500">當自動交易機器人執行買入或賣出操作時，發送郵件通知至您的註冊信箱。</p>
          </div>
          <button 
            onClick={() => setSettings({ ...settings, email_notifications_enabled: !settings.email_notifications_enabled })}
            className={`w-14 h-8 rounded-full transition-all relative ${settings.email_notifications_enabled ? 'bg-indigo-600' : 'bg-slate-700'}`}
          >
            <div className={`absolute top-1 w-6 h-6 bg-white rounded-full transition-all ${settings.email_notifications_enabled ? 'left-7' : 'left-1'}`} />
          </button>
        </div>
      </section>

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
