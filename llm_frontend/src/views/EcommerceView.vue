<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import AppHeader from '@/components/AppHeader.vue'
import MessageBubble from '@/components/MessageBubble.vue'
import * as agentApi from '@/api/agent'
import { errorMessage } from '@/api/http'
import { uid, fileKind, formatBytes } from '@/utils/format'
import type { UiMessage } from '@/types'

const input = ref('')
const messages = ref<UiMessage[]>([])
const threadId = ref<string | null>(null)
const imageFile = ref<File | null>(null)
const imagePreview = ref('')
const sending = ref(false)
const controller = ref<AbortController | null>(null)
const scrollRef = ref<HTMLElement | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)

const suggestions = [
  { icon: 'Search', title: '查询商品', text: '帮我查询适合敏感肌使用的面霜' },
  { icon: 'Tickets', title: '订单与物流', text: '订单发货后一般多久能送达？' },
  { icon: 'RefreshLeft', title: '退换售后', text: '商品拆封后还能申请退货吗？' },
  { icon: 'Picture', title: '图片识别', text: '请识别图片中的商品并给出购买建议' },
]

const hasImage = computed(() => !!imageFile.value)

watch(
  () => [messages.value.length, messages.value.at(-1)?.content, messages.value.at(-1)?.reasoning],
  async () => {
    await nextTick()
    const el = scrollRef.value
    if (el) el.scrollTop = el.scrollHeight
  },
)

onBeforeUnmount(() => {
  controller.value?.abort()
  if (imagePreview.value) URL.revokeObjectURL(imagePreview.value)
})

function clearImage(): void {
  if (imagePreview.value) URL.revokeObjectURL(imagePreview.value)
  imagePreview.value = ''
  imageFile.value = null
  if (fileInput.value) fileInput.value.value = ''
}

function chooseImage(): void {
  fileInput.value?.click()
}

function onImageChange(event: Event): void {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return
  if (!file.type.startsWith('image/')) {
    ElMessage.error('请选择图片文件')
    return
  }
  if (file.size > 8 * 1024 * 1024) {
    ElMessage.error('图片不能超过 8 MB')
    return
  }
  clearImage()
  imageFile.value = file
  imagePreview.value = URL.createObjectURL(file)
}

function applyEvent(message: UiMessage, event: Parameters<typeof agentApi.askAgent> extends never ? never : import('@/utils/sse').StreamEvent): void {
  switch (event.kind) {
    case 'text':
      message.content += event.text
      break
    case 'think':
      message.reasoning += event.text
      break
    case 'search_results':
      message.sources = event.results
      break
    case 'interruption':
      message.content += message.content ? '\n\n' : ''
      message.content += '请补充必要信息，我会继续处理。'
      break
    case 'search_start':
    case 'direct_answer':
    case 'done':
      break
  }
}

function useSuggestion(text: string): void {
  if (sending.value) return
  input.value = text
}

async function send(): Promise<void> {
  const query = input.value.trim()
  if (!query || sending.value) return

  const image = imageFile.value
  messages.value.push({
    id: uid(),
    role: 'user',
    content: image ? `${query}\n[图片：${image.name}]` : query,
    reasoning: '',
    sources: [],
    loading: false,
    error: '',
    mode: 'agent',
  })
  const assistant: UiMessage = {
    id: uid(),
    role: 'assistant',
    content: '',
    reasoning: '',
    sources: [],
    loading: true,
    error: '',
    mode: 'agent',
  }
  messages.value.push(assistant)
  input.value = ''
  clearImage()
  sending.value = true
  const abort = new AbortController()
  controller.value = abort

  try {
    const onEvent = (event: import('@/utils/sse').StreamEvent) => applyEvent(assistant, event)
    const result = image
      ? await agentApi.askAgentWithImage(query, image, threadId.value, onEvent, abort.signal)
      : await agentApi.askAgent(query, threadId.value, onEvent, abort.signal)
    if (result.conversationId) threadId.value = result.conversationId
  } catch (error) {
    if ((error as { name?: string })?.name === 'AbortError') {
      if (!assistant.content) assistant.content = '已停止生成。'
    } else {
      assistant.error = errorMessage(error)
    }
  } finally {
    assistant.loading = false
    sending.value = false
    controller.value = null
  }
}

function stop(): void {
  controller.value?.abort()
  controller.value = null
}

function reset(): void {
  if (sending.value) return
  messages.value = []
  threadId.value = null
  clearImage()
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key !== 'Enter' || event.shiftKey || event.isComposing) return
  event.preventDefault()
  void send()
}
</script>

<template>
  <div class="app-shell">
    <AppHeader />

    <div class="agent-layout">
      <aside class="agent-side">
        <div class="side-head">
          <span>智能体能力</span>
          <el-button size="small" plain :disabled="sending || !messages.length" @click="reset">
            <el-icon><RefreshLeft /></el-icon>
            重置
          </el-button>
        </div>

        <div class="capability-list">
          <button
            v-for="item in suggestions"
            :key="item.text"
            type="button"
            class="capability"
            :disabled="sending"
            @click="useSuggestion(item.text)"
          >
            <span class="capability-icon"><el-icon :size="16"><component :is="item.icon" /></el-icon></span>
            <span>
              <strong>{{ item.title }}</strong>
              <small>{{ item.text }}</small>
            </span>
          </button>
        </div>

        <div class="agent-note">
          <el-icon :size="14"><InfoFilled /></el-icon>
          <span>商品信息以知识图谱与售后知识库为准；涉及订单状态时请提供订单号。</span>
        </div>
      </aside>

      <main class="agent-main">
        <header class="agent-head">
          <div>
            <h1>电商智能体</h1>
            <p>{{ threadId ? `会话 ${threadId.slice(0, 8)}` : '商品咨询、售后处理与图片识别' }}</p>
          </div>
          <span class="status-dot" :class="{ 'is-busy': sending }">
            {{ sending ? '处理中' : '就绪' }}
          </span>
        </header>

        <section ref="scrollRef" class="agent-messages">
          <div v-if="!messages.length" class="agent-welcome">
            <div class="agent-visual">
              <el-icon :size="30"><Goods /></el-icon>
            </div>
            <h2>告诉我你要咨询的商品或售后问题</h2>
            <p>可以输入订单、物流、退换货问题，也可以上传商品图片进行识别。</p>
            <div class="welcome-actions">
              <button type="button" @click="useSuggestion(suggestions[0].text)">
                <el-icon><Search /></el-icon>
                查询商品
              </button>
              <button type="button" @click="chooseImage">
                <el-icon><Picture /></el-icon>
                上传图片
              </button>
            </div>
          </div>

          <div v-else class="agent-message-list">
            <MessageBubble v-for="message in messages" :key="message.id" :message="message" />
          </div>
        </section>

        <div v-if="imagePreview" class="agent-image">
          <img :src="imagePreview" alt="待发送商品图片" />
          <div>
            <strong>{{ imageFile?.name }}</strong>
            <span>{{ imageFile ? `${fileKind(imageFile.name)} · ${formatBytes(imageFile.size)}` : '' }}</span>
          </div>
          <button type="button" title="移除图片" @click="clearImage">
            <el-icon><Close /></el-icon>
          </button>
        </div>

        <div class="agent-composer">
          <el-input
            v-model="input"
            type="textarea"
            :autosize="{ minRows: 2, maxRows: 6 }"
            resize="none"
            placeholder="输入商品或售后问题，Enter 发送，Shift+Enter 换行"
            @keydown="onKeydown"
          />
          <div class="agent-toolbar">
            <button type="button" class="tool-button" :disabled="sending" @click="chooseImage">
              <el-icon><Picture /></el-icon>
              {{ hasImage ? '更换图片' : '添加图片' }}
            </button>
            <span class="char-count">{{ input.length }}</span>
            <el-button v-if="sending" type="danger" plain size="small" @click="stop">
              <el-icon><VideoPause /></el-icon>
              停止
            </el-button>
            <el-button v-else type="primary" size="small" :disabled="!input.trim()" @click="send">
              <el-icon><Promotion /></el-icon>
              发送
            </el-button>
          </div>
        </div>

        <input ref="fileInput" type="file" accept="image/*" hidden @change="onImageChange" />
      </main>
    </div>
  </div>
</template>

<style scoped>
.agent-layout {
  display: grid;
  grid-template-columns: 270px minmax(0, 1fr);
  min-height: 0;
}

.agent-side {
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 12px;
  border-right: 1px solid var(--border-soft);
  background: var(--bg-panel);
}

.side-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 34px;
  margin-bottom: 8px;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 600;
}

.capability-list {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.capability {
  display: grid;
  grid-template-columns: 30px minmax(0, 1fr);
  gap: 8px;
  align-items: center;
  padding: 8px;
  border: 1px solid transparent;
  border-radius: 7px;
  background: transparent;
  color: var(--text-secondary);
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.capability:hover {
  border-color: var(--border-soft);
  background: var(--bg-hover);
  color: var(--text-primary);
}

.capability:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.capability-icon {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border-radius: 6px;
  background: var(--accent-soft);
  color: var(--accent);
}

.capability strong,
.capability small {
  display: block;
}

.capability strong {
  font-size: 12.5px;
  line-height: 1.4;
}

.capability small {
  margin-top: 1px;
  color: var(--text-muted);
  font-size: 11px;
  line-height: 1.45;
}

.agent-note {
  display: flex;
  gap: 7px;
  margin-top: auto;
  padding: 9px;
  border: 1px solid var(--think-border);
  border-radius: 7px;
  background: var(--think-soft);
  color: var(--think);
  font-size: 11px;
  line-height: 1.55;
}

.agent-note .el-icon {
  flex: 0 0 auto;
  margin-top: 2px;
}

.agent-main {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto auto;
  min-width: 0;
  min-height: 0;
  background: var(--bg-app);
}

.agent-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  min-height: 62px;
  padding: 10px 20px;
  border-bottom: 1px solid var(--border-soft);
  background: var(--bg-panel);
}

.agent-head h1,
.agent-head p {
  margin: 0;
}

.agent-head h1 {
  font-size: 17px;
  line-height: 1.35;
}

.agent-head p {
  color: var(--text-muted);
  font-size: 11.5px;
}

.status-dot {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 7px;
  border: 1px solid var(--border-soft);
  border-radius: 5px;
  color: var(--text-muted);
  font-size: 11px;
}

.status-dot::before {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent);
  content: '';
}

.status-dot.is-busy::before {
  background: var(--think);
  animation: pulse 1s infinite;
}

.agent-messages {
  min-height: 0;
  overflow-y: auto;
  padding: 22px 24px;
}

.agent-message-list {
  width: min(100%, 900px);
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.agent-welcome {
  width: min(100%, 560px);
  margin: 9vh auto 0;
  text-align: center;
}

.agent-visual {
  display: grid;
  place-items: center;
  width: 62px;
  height: 62px;
  margin: 0 auto 16px;
  border-radius: 14px;
  background: var(--accent-soft);
  color: var(--accent);
}

.agent-welcome h2 {
  margin: 0 0 7px;
  font-size: 20px;
  line-height: 1.4;
}

.agent-welcome p {
  margin: 0 0 20px;
  color: var(--text-muted);
  font-size: 13px;
}

.welcome-actions {
  display: flex;
  justify-content: center;
  gap: 8px;
}

.welcome-actions button,
.tool-button {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border: 1px solid var(--border-soft);
  border-radius: 6px;
  background: var(--bg-panel);
  color: var(--text-secondary);
  font: inherit;
  font-size: 12px;
  cursor: pointer;
}

.welcome-actions button {
  padding: 7px 12px;
}

.welcome-actions button:hover,
.tool-button:hover {
  border-color: var(--accent);
  color: var(--accent);
}

.agent-image {
  display: flex;
  align-items: center;
  gap: 9px;
  width: min(100% - 36px, 900px);
  margin: 0 auto 8px;
  padding: 7px 8px;
  border: 1px solid var(--border-soft);
  border-radius: 7px;
  background: var(--bg-panel);
}

.agent-image img {
  width: 42px;
  height: 42px;
  border-radius: 5px;
  object-fit: cover;
}

.agent-image strong,
.agent-image span {
  display: block;
}

.agent-image strong {
  font-size: 12px;
}

.agent-image span {
  color: var(--text-muted);
  font-size: 11px;
}

.agent-image button {
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

.agent-image button:hover {
  background: var(--danger-soft);
  color: var(--danger);
}

.agent-composer {
  padding: 10px 18px 14px;
  border-top: 1px solid var(--border-soft);
  background: var(--bg-panel);
}

.agent-composer :deep(.el-textarea__inner) {
  border-color: var(--border-strong);
  background: var(--bg-panel);
  color: var(--text-primary);
  box-shadow: none;
  font-size: 14px;
}

.agent-composer :deep(.el-textarea__inner:focus) {
  border-color: var(--accent);
}

.agent-toolbar {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-top: 7px;
}

.tool-button {
  padding: 5px 8px;
}

.tool-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.char-count {
  margin-left: auto;
  color: var(--text-muted);
  font-size: 11px;
  font-variant-numeric: tabular-nums;
}

@keyframes pulse {
  50% {
    opacity: 0.3;
  }
}

@media (max-width: 900px) {
  .agent-layout {
    grid-template-columns: 1fr;
  }

  .agent-side {
    display: none;
  }
}

@media (max-width: 640px) {
  .agent-messages {
    padding: 16px 12px;
  }

  .agent-head {
    padding: 9px 12px;
  }

  .agent-composer {
    padding: 9px 10px 12px;
  }

  .agent-welcome {
    margin-top: 36px;
  }
}
</style>
