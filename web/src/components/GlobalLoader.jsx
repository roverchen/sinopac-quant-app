import { motion } from 'framer-motion';
import { Cpu } from 'lucide-react';

const GlobalLoader = ({ progress, message = "系統初始化中..." }) => {
  return (
    <div className="fixed inset-0 z-[100] bg-slate-950 flex flex-col items-center justify-center p-6">
      <div className="w-full max-w-xs space-y-8 flex flex-col items-center">
        {/* Animated Logo */}
        <motion.div
          animate={{ 
            scale: [1, 1.1, 1],
            rotate: [0, 5, -5, 0]
          }}
          transition={{ 
            duration: 4,
            repeat: Infinity,
            ease: "easeInOut"
          }}
          className="p-5 bg-indigo-600 rounded-[2rem] shadow-2xl shadow-indigo-500/20"
        >
          <Cpu className="w-12 h-12 text-white" />
        </motion.div>

        <div className="text-center space-y-2">
          <h2 className="text-2xl font-black text-white tracking-tight">股市報明牌</h2>
          <p className="text-slate-500 text-sm font-medium animate-pulse">{message}</p>
        </div>

        {/* Progress Container */}
        <div className="w-full space-y-2">
          <div className="flex justify-between text-[10px] font-black uppercase tracking-widest text-slate-500">
            <span>Loading Assets</span>
            <span>{Math.round(progress)}%</span>
          </div>
          <div className="h-1.5 w-full bg-slate-900 rounded-full overflow-hidden border border-slate-800/50">
            <motion.div 
              className="h-full bg-indigo-500 shadow-[0_0_15px_rgba(99,102,241,0.5)]"
              initial={{ width: 0 }}
              animate={{ width: `${progress}%` }}
              transition={{ type: "spring", stiffness: 50, damping: 20 }}
            />
          </div>
        </div>

        <div className="flex gap-2">
          {[0, 1, 2].map((i) => (
            <motion.div
              key={i}
              animate={{ opacity: [0.2, 1, 0.2] }}
              transition={{ duration: 1.5, repeat: Infinity, delay: i * 0.2 }}
              className="w-1.5 h-1.5 rounded-full bg-indigo-500"
            />
          ))}
        </div>
      </div>
      
      {/* Background Decorative Elements */}
      <div className="absolute top-1/4 -right-20 w-64 h-64 bg-indigo-600/10 blur-[100px] rounded-full" />
      <div className="absolute bottom-1/4 -left-20 w-64 h-64 bg-purple-600/10 blur-[100px] rounded-full" />
    </div>
  );
};

export default GlobalLoader;
