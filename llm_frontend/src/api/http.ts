/** axios 实例与凭据存取
 *
 * 流式接口走原生 fetch（需要 ReadableStream），非流式接口走 axios，
 * 两者共用同一份 token / user_id 读写逻辑，避免出现两套凭据来源。
 */
import axios from 'axios'
import router from '@/router'

const TOKEN_KEY = 'token'
const USER_ID_KEY = 'user_id'

export const getToken = (): string => localStorage.getItem(TOKEN_KEY) || ''
export const setToken = (token: string): void => localStorage.setItem(TOKEN_KEY, token)
export const clearToken = (): void => {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_ID_KEY)
}

export const getUserId = (): number => Number(localStorage.getItem(USER_ID_KEY) || 0)
export const setUserId = (id: number | string): void =>
  localStorage.setItem(USER_ID_KEY, String(id))

/** 流式请求也要带上 Authorization，这里给 fetch 复用 */
export function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}`, ...extra } : { ...extra }
}

const http = axios.create({
  // 生产环境前端由 FastAPI 同源托管，开发环境由 vite proxy 转发，因此 baseURL 留空
  baseURL: '',
  timeout: 30000,
})

http.interceptors.request.use((config) => {
  const token = getToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

http.interceptors.response.use(
  (response) => response,
  (error) => {
    // 401 表示 token 失效：清掉本地凭据并回到登录页，避免停在无数据的界面
    if (error?.response?.status === 401) {
      clearToken()
      if (router.currentRoute.value.path !== '/login') router.push('/login')
    }
    return Promise.reject(error)
  },
)

/** 从 axios 错误里取出后端 detail 文案，没有就退回状态码 */
export function errorMessage(error: unknown): string {
  const anyErr = error as { response?: { data?: { detail?: unknown }; status?: number } }
  const detail = anyErr?.response?.data?.detail
  if (typeof detail === 'string' && detail) return detail
  if (detail) return JSON.stringify(detail)
  if (error instanceof Error && error.message) return error.message
  return '请求失败，请稍后重试'
}

export default http
