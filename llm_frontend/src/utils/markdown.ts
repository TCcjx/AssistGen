/** Markdown 渲染：marked 解析 + DOMPurify 消毒 + highlight.js 代码高亮 */
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import hljs from 'highlight.js/lib/common'

marked.setOptions({
  gfm: true,
  breaks: true,
})

/** 流式渲染时正文可能只有一半（例如未闭合的代码块），任何异常都不能打断打字机效果 */
export function renderMarkdown(source: string): string {
  if (!source) return ''
  try {
    const raw = marked.parse(source, { async: false }) as string
    return DOMPurify.sanitize(raw, { ADD_ATTR: ['target', 'rel'] })
  } catch {
    return DOMPurify.sanitize(source)
  }
}

/** 消息插入 DOM 后对代码块做高亮，并把外链改为新窗口打开 */
export function highlightWithin(root: HTMLElement | null): void {
  if (!root) return
  root.querySelectorAll<HTMLElement>('pre code:not(.hljs)').forEach((block) => {
    try {
      hljs.highlightElement(block)
    } catch {
      /* 无法识别的语言保留原样 */
    }
  })
  root.querySelectorAll<HTMLAnchorElement>('a[href]').forEach((a) => {
    if (a.href.startsWith('http')) {
      a.target = '_blank'
      a.rel = 'noopener noreferrer'
    }
  })
}
