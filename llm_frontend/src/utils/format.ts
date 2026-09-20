/** 展示层格式化工具 */

export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 B'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

export function formatDateTime(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** 会话列表用的紧凑时间：当天显示时分，其余显示月日 */
export function formatRelative(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const now = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  const sameDay =
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate()
  if (sameDay) return `${pad(d.getHours())}:${pad(d.getMinutes())}`
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

export function fileKind(name: string): string {
  const n = name.toLowerCase()
  if (n.endsWith('.pdf')) return 'PDF'
  if (n.endsWith('.doc') || n.endsWith('.docx')) return 'DOC'
  if (n.endsWith('.xls') || n.endsWith('.xlsx') || n.endsWith('.csv')) return '表格'
  if (n.endsWith('.ppt') || n.endsWith('.pptx')) return 'PPT'
  if (n.endsWith('.txt') || n.endsWith('.md')) return 'TXT'
  if (/\.(png|jpe?g|gif|webp|bmp|svg)$/.test(n)) return '图片'
  return '文件'
}

export function hostOf(url: string): string {
  try {
    return new URL(url).hostname
  } catch {
    return url
  }
}

export function uid(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 9)}`
}
