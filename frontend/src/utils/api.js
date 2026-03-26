import axios from 'axios'

// 创建 axios 实例
const api = axios.create({
  baseURL: '/api',
  timeout: 30000
})

// 请求拦截器 - 从 localStorage 直接读取 token
api.interceptors.request.use(
  config => {
    const accessToken = localStorage.getItem('access_token')
    if (accessToken) {
      config.headers.Authorization = `Bearer ${accessToken}`
    }
    return config
  },
  error => {
    return Promise.reject(error)
  }
)

// 响应拦截器
api.interceptors.response.use(
  response => response,
  async error => {
    // Token 过期，尝试刷新
    if (error.response?.status === 401 && error.response?.data?.error === 'token_expired') {
      const refreshToken = localStorage.getItem('refresh_token')
      if (refreshToken) {
        try {
          const res = await axios.post('/api/auth/refresh', {}, {
            headers: {
              Authorization: `Bearer ${refreshToken}`
            }
          })
          if (res.data.access_token) {
            localStorage.setItem('access_token', res.data.access_token)
            // 重试原请求
            error.config.headers.Authorization = `Bearer ${res.data.access_token}`
            return api(error.config)
          }
        } catch {
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
        }
      }
    }

    return Promise.reject(error)
  }
)

export default api
