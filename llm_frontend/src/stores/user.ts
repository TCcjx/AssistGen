import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as authApi from '@/api/auth'
import { getToken, getUserId } from '@/api/http'

export type ThemeMode = 'light' | 'dark'

const THEME_KEY = 'theme'

/** 把主题同时写到 data-theme 属性与 html.dark 类：
 *  前者驱动本项目的 CSS 变量，后者驱动 Element Plus 的暗色主题。 */
function applyTheme(mode: ThemeMode): void {
  const root = document.documentElement
  root.setAttribute('data-theme', mode)
  root.classList.toggle('dark', mode === 'dark')
}

export const useUserStore = defineStore('user', () => {
  const username = ref('')
  const email = ref('')
  const userId = ref<number>(getUserId())
  const theme = ref<ThemeMode>((localStorage.getItem(THEME_KEY) as ThemeMode) || 'dark')

  applyTheme(theme.value)

  function setUserInfo(info: { username: string; email: string; id?: number }): void {
    username.value = info.username
    email.value = info.email
    if (info.id) userId.value = info.id
  }

  function toggleTheme(): void {
    theme.value = theme.value === 'dark' ? 'light' : 'dark'
    localStorage.setItem(THEME_KEY, theme.value)
    applyTheme(theme.value)
  }

  /** 应用启动时调用：token 存在则校验有效性并拉回用户信息 */
  async function restore(): Promise<boolean> {
    if (!getToken()) return false
    const valid = await authApi.validateToken()
    if (!valid) return false
    try {
      const info = await authApi.fetchUserInfo()
      setUserInfo(info)
      return true
    } catch {
      return false
    }
  }

  function signOut(): void {
    authApi.logout()
    username.value = ''
    email.value = ''
    userId.value = 0
  }

  return { username, email, userId, theme, setUserInfo, toggleTheme, restore, signOut }
})
