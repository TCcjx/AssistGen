/** 认证相关接口。口令在客户端先做 SHA-256，与后端注册/登录两端的约定保持一致。 */
import http, { clearToken, setToken, setUserId } from './http'
import { sha256Hex } from '@/utils/crypto'
import type { LoginResponse, UserInfo } from '@/types'

export async function register(username: string, email: string, password: string): Promise<UserInfo> {
  const digest = await sha256Hex(password)
  const { data } = await http.post<UserInfo>('/api/register', { username, email, password: digest })
  return data
}

export async function login(email: string, password: string): Promise<LoginResponse> {
  const digest = await sha256Hex(password)
  const { data } = await http.post<LoginResponse>('/api/token', { email, password: digest })
  setToken(data.access_token)
  return data
}

/** 拉取当前用户信息，并把 user_id 落到 localStorage 供后续接口使用 */
export async function fetchUserInfo(): Promise<UserInfo> {
  const { data } = await http.get<UserInfo>('/api/users/me')
  setUserId(data.id)
  return data
}

/** 校验本地 token 是否仍然有效；无效时后端返回 401，由拦截器统一清理 */
export async function validateToken(): Promise<boolean> {
  try {
    await http.get('/api/validate-token')
    return true
  } catch {
    return false
  }
}

export function logout(): void {
  clearToken()
}
