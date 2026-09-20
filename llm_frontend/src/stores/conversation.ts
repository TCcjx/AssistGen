import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import * as convoApi from '@/api/conversation'
import { uid } from '@/utils/format'
import type { ChatMode, ConversationSummary, UiMessage } from '@/types'

export function blankAssistant(mode: ChatMode): UiMessage {
  return {
    id: uid(),
    role: 'assistant',
    content: '',
    reasoning: '',
    sources: [],
    loading: true,
    error: '',
    mode,
  }
}

export const useConversationStore = defineStore('conversation', () => {
  const items = ref<ConversationSummary[]>([])
  const messages = ref<UiMessage[]>([])
  /** 普通问答用后端自增 id；智能体用后端返回的 UUID 字符串 */
  const currentId = ref<number | null>(null)
  const agentThreadId = ref<string | null>(null)
  const loadingList = ref(false)
  const loadingMessages = ref(false)
  /** 新建但还没产生首条消息的会话，不应出现在历史列表里 */
  const isDraft = ref(true)

  const current = computed(() => items.value.find((c) => c.id === currentId.value) ?? null)
  const streaming = computed(() => messages.value.some((m) => m.loading))

  async function refresh(): Promise<void> {
    loadingList.value = true
    try {
      items.value = await convoApi.listConversations()
    } finally {
      loadingList.value = false
    }
  }

  /** 开启一段新对话：先不落库，等首条消息发出后再创建，避免堆积空会话 */
  function startDraft(): void {
    currentId.value = null
    agentThreadId.value = null
    messages.value = []
    isDraft.value = true
  }

  async function ensureConversation(): Promise<number> {
    if (currentId.value) return currentId.value
    const id = await convoApi.createConversation()
    currentId.value = id
    isDraft.value = false
    return id
  }

  async function select(id: number): Promise<void> {
    loadingMessages.value = true
    try {
      const stored = await convoApi.listMessages(id)
      currentId.value = id
      agentThreadId.value = null
      isDraft.value = false
      messages.value = stored.map((m) => ({
        id: `db-${m.id}`,
        role: m.sender === 'user' ? 'user' : 'assistant',
        content: m.content,
        reasoning: '',
        sources: [],
        loading: false,
        error: '',
        mode: 'chat' as ChatMode,
      }))
    } finally {
      loadingMessages.value = false
    }
  }

  async function remove(id: number): Promise<void> {
    await convoApi.deleteConversation(id)
    items.value = items.value.filter((c) => c.id !== id)
    if (currentId.value === id) startDraft()
  }

  async function rename(id: number, name: string): Promise<void> {
    await convoApi.renameConversation(id, name)
    const target = items.value.find((c) => c.id === id)
    if (target) target.title = name
  }

  function pushUser(content: string): UiMessage {
    const msg: UiMessage = {
      id: uid(),
      role: 'user',
      content,
      reasoning: '',
      sources: [],
      loading: false,
      error: '',
      mode: 'chat',
    }
    messages.value.push(msg)
    return msg
  }

  function pushAssistant(mode: ChatMode): UiMessage {
    const msg = blankAssistant(mode)
    messages.value.push(msg)
    return msg
  }

  function clearMessages(): void {
    messages.value = []
  }

  return {
    items,
    messages,
    currentId,
    agentThreadId,
    loadingList,
    loadingMessages,
    isDraft,
    current,
    streaming,
    refresh,
    startDraft,
    ensureConversation,
    select,
    remove,
    rename,
    pushUser,
    pushAssistant,
    clearMessages,
  }
})
