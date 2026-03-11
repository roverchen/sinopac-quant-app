import axios from 'axios';

const API_BASE_URL = '/api'; // Proxied to localhost:8000 in dev

const api = axios.create({
  baseURL: API_BASE_URL,
});

// 資料攔截器：自動加入 JWT Token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const authService = {
  login: async (credential) => {
    const response = await api.post('/auth/login', { credential });
    if (response.data.access_token) {
      localStorage.setItem('token', response.data.access_token);
    }
    return response.data;
  },
  getMe: async () => {
    const response = await api.get('/auth/me');
    return response.data;
  },
  logout: () => {
    localStorage.removeItem('token');
  },
  updateCredentials: async (creds) => {
    const response = await api.post('/auth/credentials', { creds });
    return response.data;
  }
};

export const quantService = {
  analyze: async (watchlist, defenseWeight = 0.5, marketType = 'TW') => {
    const response = await api.post('/quant/analyze', {
      watchlist,
      defense_weight: defenseWeight,
      market_type: marketType
    });
    return response.data;
  },
  startScan: async (marketType = 'TW', defenseWeight = 0.5) => {
    const response = await api.post('/quant/scan', {
      market_type: marketType,
      defense_weight: defenseWeight
    });
    return response.data;
  },
  getScanProgress: async () => {
    const response = await api.get('/quant/scan/progress');
    return response.data;
  },
  getWatchlist: async (marketType = 'TW') => {
    const response = await api.get(`/quant/watchlist?market_type=${marketType}`);
    return response.data;
  },
  addToWatchlist: async (symbol, marketType = 'TW') => {
    const response = await api.post(`/quant/watchlist?symbol=${symbol}&market_type=${marketType}`);
    return response.data;
  },
  removeFromWatchlist: async (symbol, marketType = 'TW') => {
    const response = await api.delete(`/quant/watchlist?symbol=${symbol}&market_type=${market_type}`);
    return response.data;
  }
};

export const tradeService = {
  async getStatus() {
    const response = await api.get('/trade/status');
    return response.data;
  },
  async toggleAutoTrade(enabled) {
    const response = await api.post(`/trade/toggle?enabled=${enabled}`);
    return response.data;
  },
  async getAccount() {
    const response = await api.get('/trade/account');
    return response.data;
  },
  async placeOrder(orderData) {
    const response = await api.post('/trade/order', orderData);
    return response.data;
  },
  async getOrders() {
    const response = await api.get('/trade/orders');
    return response.data;
  }
};

export default api;
