/** Server-Sent Events 解析
 *
 * 后端各流式接口统一输出 `data: <json>\n\n`，其中 <json> 有两种形态：
 *   1. JSON 字符串 —— 普通文本增量（DeepseekService / OllamaService / lg_builder）
 *   2. JSON 对象   —— 带 type 字段的结构化事件（SearchService）或中断信号（LangGraph）
 * 这里统一解析并按事件类型分发，避免各视图重复实现拆包逻辑。
 */
import type { SearchHit } from '@/types'

export type StreamEvent =
  | { kind: 'text'; text: string }
  | { kind: 'think'; text: string }
  | { kind: 'search_start' }
  | { kind: 'search_results'; total: number; query: string; results: SearchHit[] }
  | { kind: 'direct_answer' }
  | { kind: 'interruption'; conversationId: string }
  | { kind: 'done' }

// 推理模型会在正文里夹带成对的 think 标记。用拼接方式声明常量，
// 避免源码里出现字面量闭合标记而影响构建工具的解析。
const THINK_OPEN = '<' + 'think>'
const THINK_CLOSE = '<' + '/think>'

/** 跨 chunk 维护 think 标记状态：标记本身不进正文，标记之间的内容归入思考过程 */
export class ThinkTagParser {
  private inThink = false
  /** 结尾可能是被截断的标记前缀，先挂起等待下一个 chunk */
  private pending = ''

  feed(chunk: string): StreamEvent[] {
    const out: StreamEvent[] = []
    let buf = this.pending + chunk
    this.pending = ''

    for (;;) {
      const nextTag = buf.indexOf(this.inThink ? THINK_CLOSE : THINK_OPEN)

      if (nextTag === -1) {
        // 没有完整标记：把可能是标记前缀的尾巴挂起，其余立即吐出
        const hold = this.holdbackLength(buf)
        const emit = buf.slice(0, buf.length - hold)
        this.pending = buf.slice(buf.length - hold)
        if (emit) out.push(this.event(emit))
        break
      }

      const before = buf.slice(0, nextTag)
      if (before) out.push(this.event(before))
      const tagLen = this.inThink ? THINK_CLOSE.length : THINK_OPEN.length
      this.inThink = !this.inThink
      buf = buf.slice(nextTag + tagLen)
    }
    return out
  }

  /** 流结束时把挂起的尾巴也吐出来 */
  flush(): StreamEvent[] {
    if (!this.pending) return []
    const emit = this.pending
    this.pending = ''
    return [this.event(emit)]
  }

  private event(text: string): StreamEvent {
    return this.inThink ? { kind: 'think', text } : { kind: 'text', text }
  }

  /** 计算结尾有多长一段可能是被截断的标记前缀 */
  private holdbackLength(buf: string): number {
    const tag = this.inThink ? THINK_CLOSE : THINK_OPEN
    const max = Math.min(tag.length - 1, buf.length)
    for (let n = max; n > 0; n--) {
      if (tag.startsWith(buf.slice(buf.length - n))) return n
    }
    return 0
  }
}

/** 把一条 `data:` 负载解析成事件列表 */
export function parsePayload(raw: string, parser: ThinkTagParser): StreamEvent[] {
  const payload = raw.trim()
  if (!payload) return []
  if (payload === '[DONE]') return [{ kind: 'done' }]

  let value: unknown
  try {
    value = JSON.parse(payload)
  } catch {
    // 不是合法 JSON 时按裸文本处理，避免个别异常帧中断整条流
    return parser.feed(payload)
  }

  if (typeof value === 'string') return parser.feed(value)
  if (!value || typeof value !== 'object') return []

  const obj = value as Record<string, unknown>

  // LangGraph 的人工干预中断信号
  if (obj.interruption === true) {
    return [{ kind: 'interruption', conversationId: String(obj.conversation_id ?? '') }]
  }

  switch (obj.type) {
    case 'search_start':
      return [{ kind: 'search_start' }]
    case 'search_results':
      return [
        {
          kind: 'search_results',
          total: Number(obj.total ?? 0),
          query: String(obj.query ?? ''),
          results: Array.isArray(obj.results) ? (obj.results as SearchHit[]) : [],
        },
      ]
    case 'direct_answer':
      return [{ kind: 'direct_answer' }]
    case 'direct_content':
      return parser.feed(String(obj.content ?? ''))
    default:
      return []
  }
}

function findFrameEnd(buf: string): number {
  const lf = buf.indexOf('\n\n')
  const crlf = buf.indexOf('\r\n\r\n')
  if (lf === -1) return crlf
  if (crlf === -1) return lf
  return Math.min(lf, crlf)
}

/** 逐帧读取 SSE 响应体并回调事件 */
export async function consumeSse(
  response: Response,
  onEvent: (event: StreamEvent) => void,
): Promise<void> {
  if (!response.body) throw new Error('响应没有可读的数据流')

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  const parser = new ThinkTagParser()
  let buffer = ''

  const drainFrame = (frame: string) => {
    for (const line of frame.split(/\r?\n/)) {
      if (!line.startsWith('data:')) continue
      for (const ev of parsePayload(line.slice(5).trim(), parser)) onEvent(ev)
    }
  }

  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      // SSE 以空行分帧，兼容 \r\n
      let sep: number
      while ((sep = findFrameEnd(buffer)) !== -1) {
        const frame = buffer.slice(0, sep)
        buffer = buffer.slice(sep).replace(/^(\r?\n){1,2}/, '')
        drainFrame(frame)
      }
    }
    drainFrame(buffer) // 冲刷残留的半帧
    for (const ev of parser.flush()) onEvent(ev)
  } finally {
    reader.releaseLock()
  }
}

/** 统一的流式请求封装：POST 后校验状态码，再交给 consumeSse */
export async function postStream(
  url: string,
  init: RequestInit,
  onEvent: (event: StreamEvent) => void,
): Promise<Response> {
  const response = await fetch(url, init)
  if (!response.ok) {
    let detail = `HTTP ${response.status}`
    try {
      const body = await response.json()
      if (body?.detail) detail = String(body.detail)
    } catch {
      /* 响应体不是 JSON 时保留状态码即可 */
    }
    throw new Error(detail)
  }
  await consumeSse(response, onEvent)
  return response
}
