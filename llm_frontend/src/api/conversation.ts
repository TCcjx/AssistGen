/** 会话与历史消息接口 */
import http from './http'
import { getUserId } from './http'
import type { ConversationSummary, StoredMessage } from '@/types'

export async function createConversation(): Promise<number> {
  const { data } = await http.post<{ conversation_id: number }>('/api/conversations', {
    user_id: getUserId(),
  })
  return data.conversation_id
}

export async function listConversations(): Promise<ConversationSummary[]> {
  const { data } = await http.get<ConversationSummary[]>(`/api/conversations/user/${getUserId()}`)
  return data
}

export async function listMessages(conversationId: number): Promise<StoredMessage[]> {
  const { data } = await http.get<StoredMessage[]>(
    `/api/conversations/${conversationId}/messages`,
    { params: { user_id: getUserId() } },
  )
  return data
}

export async function deleteConversation(conversationId: number): Promise<void> {
  await http.delete(`/api/conversations/${conversationId}`)
}

export async function renameConversation(conversationId: number, name: string): Promise<void> {
  await http.put(`/api/conversations/${conversationId}/name`, { name })
}
