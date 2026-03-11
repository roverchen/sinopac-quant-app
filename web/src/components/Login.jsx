import { useState } from 'react';
import { authService } from '../services/api';
import { Cpu, Loader2, ShieldCheck } from 'lucide-react';
import { motion } from 'framer-motion';
import { GoogleLogin } from '@react-oauth/google';

const Login = ({ onLoginSuccess }) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleGoogleSuccess = async (credentialResponse) => {
    setLoading(true);
    setError('');
    try {
      await authService.login(credentialResponse.credential);
      onLoginSuccess();
    } catch (err) {
      setError(err.response?.data?.detail || '驗證失敗，請再試一次');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full flex items-center justify-center bg-[radial-gradient(circle_at_center,rgba(30,41,59,1),rgba(2,6,23,1))] p-6 relative overflow-hidden">
      {/* 裝飾背景 */}
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-indigo-500/20 rounded-full blur-[100px] pointer-events-none" />
      <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-purple-500/20 rounded-full blur-[100px] pointer-events-none" />

      <motion.div 
        initial={{ opacity: 0, scale: 0.95, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ duration: 0.5, ease: "easeOut" }}
        className="relative w-full max-w-md bg-slate-900/60 border border-slate-700/50 backdrop-blur-2xl rounded-[2.5rem] p-10 shadow-2xl flex flex-col items-center text-center z-10"
      >
        <div className="p-4 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-3xl shadow-lg shadow-indigo-500/20 mb-6">
          <Cpu className="w-10 h-10 text-white" />
        </div>
        
        <h1 className="text-3xl font-bold bg-gradient-to-r from-white to-slate-300 bg-clip-text text-transparent tracking-tight">Quant Pro</h1>
        <p className="text-slate-400 mt-2 mb-10 font-medium">您的專業量化交易工作站</p>

        <div className="w-full flex flex-col items-center justify-center min-h-[120px] bg-slate-800/30 rounded-3xl border border-slate-700/50 p-6">
          {loading ? (
            <motion.div 
              initial={{ opacity: 0 }} 
              animate={{ opacity: 1 }} 
              className="flex flex-col items-center justify-center text-indigo-400"
            >
              <Loader2 className="w-8 h-8 animate-spin mb-4" />
              <p className="text-sm font-medium">正在建立專屬加密環境...</p>
            </motion.div>
          ) : (
            <motion.div 
              initial={{ opacity: 0 }} 
              animate={{ opacity: 1 }}
              transition={{ delay: 0.2 }}
            >
              <GoogleLogin
                onSuccess={handleGoogleSuccess}
                onError={() => setError('Google 登入失敗')}
                theme="filled_black"
                shape="pill"
                text="signin_with"
                size="large"
                width="300"
              />
            </motion.div>
          )}
        </div>

        {error && (
          <motion.p 
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-rose-400 text-sm bg-rose-500/10 p-4 rounded-2xl border border-rose-500/20 w-full mt-6 text-center font-medium"
          >
            {error}
          </motion.p>
        )}

        <div className="flex items-center gap-2 mt-10 text-xs text-slate-500 font-medium bg-slate-800/50 px-4 py-2 rounded-full border border-slate-700/50">
          <ShieldCheck className="w-4 h-4 text-emerald-500" />
          <span>使用 Google 身分驗證，登入即自動同步雲端設定</span>
        </div>
      </motion.div>
    </div>
  );
};

export default Login;
