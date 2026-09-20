/** 前端口令摘要工具
 *
 * 后端 UserService.authenticate_user 收到的 password 已经是 SHA-256 摘要，
 * 再用 bcrypt 落库。因此注册与登录都必须在客户端先做一次 SHA-256，
 * 否则同一口令在两个接口之间会对不上。
 */
export async function sha256Hex(plain: string): Promise<string> {
  const bytes = new TextEncoder().encode(plain)
  const digest = await crypto.subtle.digest('SHA-256', bytes)
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('')
}
