<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import AppHeader from '@/components/AppHeader.vue'
import ConversationList from '@/components/ConversationList.vue'
import ComposerBar from '@/components/ComposerBar.vue'
import MessageBubble from '@/components/MessageBubble.vue'
import * as chatApi from '@/api/chat'
import * as agentApi from '@/api/agent'
import { errorMessage } from '@/api/http'
import { useConversationStore } from '@/stores/conversation'
import { useUserStore } from '@/stores/user'
import type { ChatMessagePayload, ChatMode, SearchHit, UiMessage } from '@/types'
import { fileKind, formatBytes } from '@/utils/format'

const userStore = useUserStore()
const store = useConversationStore()

const input = ref('')
const mode = ref<ChatMode>('chat')
const indexId = ref<string | null>(null)
const indexName = ref<string | null>(null)
const uploading = ref(false)
const imageFile = ref<File | null>(null)
const imagePreview = ref('')
const scrollRef = ref<HTMLElement | null>(null)
const sidebarOpen = ref(false)
const abortController = ref<AbortController | null>(null)

const busy = computed(() => store.streaming)
const currentModeHint = computed(() => {
  if (mode.value === 'rag' && !indexId.value) return '上传文档后即可基于文档内容提问'
  if (mode.value === 'agent' && imageFile.value) return `已附加图片：${imageFile.value.name}`
  return ''
})

const latestSources = computed<SearchHit[]>(() => {
  for (let i = store.messages.length - 1; i >= 0; i -= 1) {
    const message = store.messages[i]
    if (message.role === 'assistant' && message.sources.length) return message.sources
  }
  return []
})

const quickPrompts = [
  '介绍一下你能提供哪些客服能力',
  '帮我整理一份常见售后问题处理流程',
  '用户反馈订单迟迟未发货，应该如何回复？',
  '把下面的问题改写成礼貌、清晰的客服回复：',
]

onMounted(async () => {
  try {
    if (!userStore.username && userStore.userId) await userStore.restore()
    await store.refresh()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
})

onBeforeUnmount(() => {
  abortController.value?.abort()
  if (imagePreview.value) URL.revokeObjectURL(imagePreview.value)
})

watch(
  () => [store.messages.length, store.messages.at(-1)?.content, store.messages.at(-1)?.reasoning],
  async () => {
    await nextTick()
    const el = scrollRef.value
    if (el) el.scrollTop = el.scrollHeight
  },
)

function historyPayload(): ChatMessagePayload[] {
  return store.messages
    .filter((message) => message.content.trim())
    .map((message) => ({ role: message.role, content: message.content }))
}

function resetTransientState(): void {
  if (imagePreview.value) URL.revokeObjectURL(imagePreview.value)
  imagePreview.value = ''
  imageFile.value = null
}

function onModeChange(next: ChatMode): void {
  if (busy.value) return
  mode.value = next
  if (next !== 'agent') resetTransientState()
}

function onImage(file: File): void {
  resetTransientState()
  imageFile.value = file
  imagePreview.value = URL.createObjectURL(file)
}

async function onFile(file: File): Promise<void> {
  if (uploading.value || busy.value) return
  uploading.value = true
  try {
    const result = await agentApi.uploadDocument(file)
    if (!result.index_id) throw new Error(result.status || '文档未生成可用索引')
    indexId.value = result.index_id
    indexName.value = file.name
    ElMessage.success(`《${file.name}》已建立索引`)
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    uploading.value = false
  }
}

function clearFile(): void {
  indexId.value = null
  indexName.value = null
}

function applyEvent(message: UiMessage, event: Parameters<Parameters<typeof chatApi.streamChat>[2]>[0]): void {
  switch (event.kind) {
    case 'text':
      message.content += event.text
      break
    case 'think':
      message.reasoning += event.text
      break
    case 'search_start':
      message.sources = []
      break
    case 'search_results':
      message.sources = event.results
      break
    case 'interruption':
      message.error = '智能体需要补充信息，请在下方直接回复以继续'
      break
    case 'done':
    case 'direct_answer':
      break
  }
}

async function send(): Promise<void> {
  const question = input.value.trim()
  if (!question || busy.value) return
  if (mode.value === 'rag' && !indexId.value) {
    ElMessage.warning('请先上传并索引一份文档')
    return
  }

  const history = historyPayload()
  const selectedImage = imageFile.value
  const controller = new AbortController()
  abortController.value = controller
  input.value = ''
  resetTransientState()

  store.pushUser(question)
  const assistant = store.pushAssistant(mode.value)

  try {
    if (mode.value === 'agent') {
      const onEvent = (event: Parameters<typeof applyEvent>[1]) => applyEvent(assistant, event)
      const result = selectedImage
        ? await agentApi.askAgentWithImage(
            question,
            selectedImage,
            store.agentThreadId,
            onEvent,
            controller.signal,
          )
        : await agentApi.askAgent(question, store.agentThreadId, onEvent, controller.signal)
      if (result.conversationId) store.agentThreadId = result.conversationId
      return
    }

    const conversationId = await store.ensureConversation()
    const payload = chatApi.toPayload(history, question)
    const onEvent = (event: Parameters<typeof applyEvent>[1]) => applyEvent(assistant, event)

    if (mode.value === 'reason') {
      await chatApi.streamReason(payload, conversationId, onEvent, controller.signal)
    } else if (mode.value === 'search') {
      await chatApi.streamSearch(payload, conversationId, onEvent, controller.signal)
    } else if (mode.value === 'rag') {
      await chatApi.streamRag(payload, indexId.value as string, conversationId, onEvent, controller.signal)
    } else {
      await chatApi.streamChat(payload, conversationId, onEvent, controller.signal)
    }
    await store.refresh()
  } catch (error) {
    if ((error as { name?: string })?.name === 'AbortError') {
      if (!assistant.content) assistant.content = '已停止生成。'
    } else {
      assistant.error = errorMessage(error)
    }
  } finally {
    assistant.loading = false
    abortController.value = null
  }
}

function stop(): void {
  abortController.value?.abort()
  abortController.value = null
}

function usePrompt(prompt: string): void {
  if (busy.value) return
  input.value = prompt
}

function startNew(): void {
  if (busy.value) return
  store.startDraft()
  clearFile()
  resetTransientState()
  mode.value = 'chat'
  sidebarOpen.value = false
}
</script>

<template>
  <div class="app-shell">
    <AppHeader />

    <div class="app-body" :class="{ 'sidebar-collapsed': !sidebarOpen }">
      <div class="sidebar" :class="{ 'is-open': sidebarOpen }">
        <ConversationList @select="sidebarOpen = false" />
      </div>

      <main class="workspace">
        <header class="workspace-head">
          <button type="button" class="mobile-menu" title="打开会话列表" @click="sidebarOpen = !sidebarOpen">
            <el-icon :size="16"><Menu /></el-icon>
          </button>
          <div class="workspace-title">
            <h2>{{ store.current?.title || '新会话' }}</h2>
            <p v-if="currentModeHint">{{ currentModeHint }}</p>
            <p v-else>支持普通问答、深度思考、联网检索、文档问答与商品智能体</p>
          </div>
          <el-button size="small" plain :disabled="busy" @click="startNew">
            <el-icon><Plus /></el-icon>
            新建
          </el-button>
        </header>

        <section ref="scrollRef" class="messages">
          <div v-if="store.loadingMessages" class="center-state">
            <el-icon class="is-loading" :size="24"><Loading /></el-icon>
            <span>正在加载会话</span>
          </div>

          <div v-else-if="!store.messages.length" class="welcome">
            <span class="welcome-icon"><el-icon :size="26"><Service /></el-icon></span>
            <h1>今天需要处理什么问题？</h1>
            <p>选择一种回答模式，或直接输入客户问题开始处理。</p>
            <div class="prompt-list">
              <button
                v-for="prompt in quickPrompts"
                :key="prompt"
                type="button"
                class="prompt-btn"
                @click="usePrompt(prompt)"
              >
                <span>{{ prompt }}</span>
                <el-icon :size="13"><ArrowRight /></el-icon>
              </button>
            </div>
          </div>

          <div v-else class="message-list">
            <MessageBubble v-for="message in store.messages" :key="message.id" :message="message" />
          </div>
        </section>

        <div v-if="imagePreview" class="image-strip">
          <img :src="imagePreview" alt="待发送图片预览" />
          <div class="image-meta">
            <strong>{{ imageFile?.name }}</strong>
            <span>{{ imageFile ? formatBytes(imageFile.size) : '' }}</span>
          </div>
          <button type="button" title="移除图片" @click="resetTransientState">
            <el-icon><Close /></el-icon>
          </button>
        </div>

        <div v-if="uploading" class="upload-state">
          <el-icon class="is-loading"><Loading /></el-icon>
          正在解析文档并建立索引…
        </div>

        <ComposerBar
          v-model="input"
          :mode="mode"
          :busy="busy"
          :index-id="indexId"
          :index-name="indexName"
          @update:mode="onModeChange"
          @send="send"
          @stop="stop"
          @file="onFile"
          @image="onImage"
          @clear-file="clearFile"
        />

        <aside v-if="latestSources.length" class="source-rail">
          <div class="source-rail-head">
            <span>最近检索来源</span>
            <span>{{ latestSources.length }} 条</span>
          </div>
          <div class="source-rail-body">
            <a
              v-for="(source, index) in latestSources"
              :key="source.url + index"
              :href="source.url"
              target="_blank"
              rel="noopener noreferrer"
            >
              <span class="source-index">{{ index + 1 }}</span>
              <span>
                <strong>{{ source.title || source.url }}</strong>
                <small>{{ source.snippet }}</small>
              </span>
            </a>
          </div>
        </aside>
      </main>
    </div>
  </div>
</template>

<style scoped>
.app-shell {
  grid-template-rows: 52px minmax(0, 1fr);
}

.app-body {
  grid-template-columns: 264px minmax(0, 1fr);
}

.sidebar {
  min-width: 0;
  min-height: 0;
  display: flex;
}

.sidebar :deep(.conv) {
  width: 100%;
}

.workspace {
  position: relative;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto auto;
  min-width: 0;
  min-height: 0;
  background: var(--bg-app);
}

.workspace-head {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 56px;
  padding: 8px 18px;
  border-bottom: 1px solid var(--border-soft);
  background: var(--bg-panel);
}

.workspace-title {
  min-width: 0;
  flex: 1 1 auto;
}

.workspace-title h2,
.workspace-title p {
  margin: 0;
}

.workspace-title h2 {
  font-size: 15px;
  line-height: 1.35;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.workspace-title p {
  margin-top: 1px;
  color: var(--text-muted);
  font-size: 11.5px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.mobile-menu {
  display: none;
  place-items: center;
  width: 30px;
  height: 30px;
  border: 1px solid var(--border-soft);
  border-radius: 6px;
  background: var(--bg-panel);
  color: var(--text-secondary);
  cursor: pointer;
}

.messages {
  min-height: 0;
  overflow-y: auto;
  padding: 22px 24px 18px;
  scroll-behavior: smooth;
}

.message-list {
  width: min(100%, 980px);
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.welcome {
  width: min(100%, 680px);
  margin: max(5vh, 36px) auto 0;
  text-align: center;
}

.welcome-icon {
  display: grid;
  place-items: center;
  width: 50px;
  height: 50px;
  margin: 0 auto 14px;
  border-radius: 11px;
  background: var(--accent-soft);
  color: var(--accent);
}

.welcome h1 {
  margin: 0 0 6px;
  font-size: 22px;
  line-height: 1.35;
}

.welcome > p {
  margin: 0 0 22px;
  color: var(--text-muted);
  font-size: 13px;
}

.prompt-list {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.prompt-btn {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  min-height: 46px;
  padding: 9px 12px;
  border: 1px solid var(--border-soft);
  border-radius: 7px;
  background: var(--bg-panel);
  color: var(--text-secondary);
  font: inherit;
  font-size: 12.5px;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s, transform 0.15s;
}

.prompt-btn:hover {
  color: var(--text-primary);
  border-color: var(--accent);
  transform: translateY(-1px);
}

.prompt-btn .el-icon {
  flex: 0 0 auto;
  color: var(--accent);
}

.center-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 180px;
  color: var(--text-muted);
  font-size: 13px;
}

.image-strip,
.upload-state {
  display: flex;
  align-items: center;
  gap: 10px;
  width: min(100% - 36px, 980px);
  margin: 0 auto 8px;
  padding: 7px 9px;
  border: 1px solid var(--border-soft);
  border-radius: 7px;
  background: var(--bg-panel);
}

.image-strip img {
  width: 42px;
  height: 42px;
  border-radius: 5px;
  object-fit: cover;
}

.image-meta {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.image-meta strong {
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.image-meta span,
.upload-state {
  color: var(--text-muted);
  font-size: 11px;
}

.image-strip button {
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  margin-left: auto;
  border: 0;
  border-radius: 5px;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
}

.image-strip button:hover {
  background: var(--danger-soft);
  color: var(--danger);
}

.source-rail {
  position: absolute;
  top: 68px;
  right: 14px;
  width: 280px;
  max-height: min(420px, calc(100% - 220px));
  border: 1px solid var(--border-soft);
  border-radius: 8px;
  background: var(--bg-panel);
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.12);
  overflow: hidden;
}

.source-rail-head {
  display: flex;
  justify-content: space-between;
  padding: 8px 10px;
  border-bottom: 1px solid var(--border-soft);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 600;
}

.source-rail-body {
  max-height: 360px;
  overflow-y: auto;
  padding: 5px;
}

.source-rail-body a {
  display: grid;
  grid-template-columns: 18px minmax(0, 1fr);
  gap: 7px;
  padding: 7px;
  border-radius: 5px;
  color: inherit;
  text-decoration: none;
}

.source-rail-body a:hover {
  background: var(--bg-hover);
}

.source-rail-body strong,
.source-rail-body small {
  display: block;
}

.source-rail-body strong {
  font-size: 12px;
  line-height: 1.45;
}

.source-rail-body small {
  margin-top: 2px;
  color: var(--text-muted);
  font-size: 11px;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.source-index {
  display: grid;
  place-items: center;
  width: 18px;
  height: 18px;
  border-radius: 4px;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 10px;
}

@media (max-width: 900px) {
  .app-body {
    grid-template-columns: 1fr;
  }

  .sidebar {
    position: fixed;
    top: 52px;
    bottom: 0;
    left: 0;
    z-index: 30;
    width: 264px;
    transform: translateX(-100%);
    transition: transform 0.18s ease;
    box-shadow: 12px 0 28px rgba(0, 0, 0, 0.16);
  }

  .sidebar.is-open {
    transform: translateX(0);
  }

  .mobile-menu {
    display: grid;
  }

  .source-rail {
    display: none;
  }
}

@media (max-width: 640px) {
  .messages {
    padding: 16px 12px;
  }

  .workspace-head {
    padding: 8px 10px;
  }

  .workspace-head .el-button {
    padding-left: 8px;
    padding-right: 8px;
  }

  .prompt-list {
    grid-template-columns: 1fr;
  }

  .welcome {
    margin-top: 20px;
  }

  .welcome h1 {
    font-size: 19px;
  }
}
</style>
