/** LangGraph 智能体接口与文件上传 */
import { authHeaders, getUserId } from './http'
import { consumeSse, type StreamEvent } from '@/utils/sse'
import type { UploadResponse } from '@/types'

/** 智能体会话 id 是后端生成的 UUID 字符串，通过响应头 X-Conversation-ID 回传 */
export interface AgentResult {
  conversationId: string | null
}

async function runAgent(
  init: RequestInit,
  onEvent: (e: StreamEvent) => void,
): Promise<AgentResult> {
  const response = await fetch('/api/langgraph/query', init)
  if (!response.ok) {
    let detail = `HTTP ${response.status}`
    try {
      const body = await response.json()
      if (body?.detail) detail = String(body.detail)
    } catch {
      /* 保留状态码 */
    }
    throw new Error(detail)
  }
  await consumeSse(response, onEvent)
  return { conversationId: response.headers.get('X-Conversation-ID') }
}

/** 纯文本提问：后端同时支持 JSON 与表单，这里用 JSON */
export function askAgent(
  query: string,
  conversationId: string | null,
  onEvent: (e: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<AgentResult> {
  return runAgent(
    {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({
        query,
        user_id: getUserId(),
        conversation_id: conversationId ?? undefined,
      }),
      signal,
    },
    onEvent,
  )
}

/** 带图提问：走 multipart，image 字段名需与后端一致 */
export function askAgentWithImage(
  query: string,
  image: File,
  conversationId: string | null,
  onEvent: (e: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<AgentResult> {
  const form = new FormData()
  form.append('query', query)
  form.append('user_id', String(getUserId()))
  if (conversationId) form.append('conversation_id', conversationId)
  form.append('image', image)
  // 不要手动设置 Content-Type，浏览器需要自行带上 multipart boundary
  return runAgent({ method: 'POST', headers: authHeaders(), body: form, signal }, onEvent)
}

/** 人工干预后继续执行 LangGraph 流程 */
export function resumeAgent(
  query: string,
  conversationId: string,
  onEvent: (e: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<Response> {
  return fetch('/api/langgraph/resume', {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ query, user_id: getUserId(), conversation_id: conversationId }),
    signal,
  }).then(async (response) => {
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    await consumeSse(response, onEvent)
    return response
  })
}

/** 上传文档并建立向量索引，返回的 index_id 用于文档问答 */
export async function uploadDocument(file: File): Promise<UploadResponse> {
  const form = new FormData()
  form.append('file', file)
  form.append('user_id', String(getUserId()))

  const response = await fetch('/api/upload', {
    method: 'POST',
    headers: authHeaders(),
    body: form,
  })
  if (!response.ok) throw new Error(`上传失败：HTTP ${response.status}`)
  return (await response.json()) as UploadResponse
}
