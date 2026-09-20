/** 流式问答接口：普通问答 / 深度思考 / 联网检索 / 文档问答 */
import { authHeaders, getUserId } from './http'
import { postStream, type StreamEvent } from '@/utils/sse'
import type { ChatMessagePayload } from '@/types'

const JSON_HEADERS = { 'Content-Type': 'application/json' }

function body(payload: Record<string, unknown>, signal?: AbortSignal): RequestInit {
  return {
    method: 'POST',
    headers: authHeaders(JSON_HEADERS),
    body: JSON.stringify(payload),
    signal,
  }
}

/** 组装发送给后端的消息数组：历史 + 本轮提问 */
export function toPayload(history: ChatMessagePayload[], question: string): ChatMessagePayload[] {
  return [...history, { role: 'user', content: question }]
}

export function streamChat(
  messages: ChatMessagePayload[],
  conversationId: number,
  onEvent: (e: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<Response> {
  return postStream(
    '/api/chat',
    body({ messages, user_id: getUserId(), conversation_id: conversationId }, signal),
    onEvent,
  )
}

export function streamReason(
  messages: ChatMessagePayload[],
  conversationId: number,
  onEvent: (e: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<Response> {
  return postStream(
    '/api/reason',
    body({ messages, user_id: getUserId(), conversation_id: conversationId }, signal),
    onEvent,
  )
}

export function streamSearch(
  messages: ChatMessagePayload[],
  conversationId: number,
  onEvent: (e: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<Response> {
  return postStream(
    '/api/search',
    body({ messages, user_id: getUserId(), conversation_id: conversationId }, signal),
    onEvent,
  )
}

/** 文档问答：index_id 来自 /api/upload 的返回值 */
export function streamRag(
  messages: ChatMessagePayload[],
  indexId: string,
  conversationId: number | null,
  onEvent: (e: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<Response> {
  return postStream(
    '/chat-rag',
    body({
      messages,
      index_id: indexId,
      user_id: getUserId(),
      conversation_id: conversationId,
    }, signal),
    onEvent,
  )
}
