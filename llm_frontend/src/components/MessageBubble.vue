<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import ThinkPanel from './ThinkPanel.vue'
import SourcePanel from './SourcePanel.vue'
import { renderMarkdown, highlightWithin } from '@/utils/markdown'
import { CHAT_MODES, type UiMessage } from '@/types'

const props = defineProps<{ message: UiMessage }>()

const bodyRef = ref<HTMLElement | null>(null)

const html = computed(() => renderMarkdown(props.message.content))

const modeLabel = computed(
  () => CHAT_MODES.find((m) => m.value === props.message.mode)?.label ?? '',
)

/** 流式增量到达后重新高亮新增的代码块，并保持在底部 */
watch(
  () => props.message.content,
  async () => {
    await nextTick()
    highlightWithin(bodyRef.value)
  },
)

async function copyText(): Promise<void> {
  try {
    await navigator.clipboard.writeText(props.message.content)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败，请手动选择文本')
  }
}
</script>

<template>
  <div class="row" :class="message.role === 'user' ? 'row--user' : 'row--bot'">
    <div class="avatar" :class="message.role === 'user' ? 'avatar--user' : 'avatar--bot'">
      <el-icon :size="15">
        <User v-if="message.role === 'user'" />
        <Service v-else />
      </el-icon>
    </div>

    <div class="bubble-wrap">
      <div class="bubble" :class="message.role === 'user' ? 'bubble--user' : 'bubble--bot'">
        <!-- 用户消息按纯文本渲染，避免把输入内容当 Markdown 解释 -->
        <div v-if="message.role === 'user'" class="plain">{{ message.content }}</div>

        <template v-else>
          <ThinkPanel :reasoning="message.reasoning" :loading="message.loading" />
          <SourcePanel :sources="message.sources" />

          <div v-if="message.content" ref="bodyRef" class="md" v-html="html" />

          <div v-if="message.loading && !message.content && !message.reasoning" class="typing">
            <span /><span /><span />
          </div>

          <div v-if="message.error" class="err">
            <el-icon :size="13"><WarningFilled /></el-icon>
            <span>{{ message.error }}</span>
          </div>
        </template>
      </div>

      <div v-if="message.role === 'assistant'" class="bubble-foot">
        <span v-if="modeLabel" class="tag">{{ modeLabel }}</span>
        <button
          v-if="message.content && !message.loading"
          type="button"
          class="foot-btn"
          @click="copyText"
        >
          <el-icon :size="12"><CopyDocument /></el-icon>
          复制
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.row {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.row--user {
  flex-direction: row-reverse;
}

.avatar {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: 7px;
  flex: 0 0 auto;
  margin-top: 2px;
}

.avatar--bot {
  background: var(--accent-soft);
  color: var(--accent);
}

.avatar--user {
  background: var(--bg-hover);
  color: var(--text-secondary);
}

.bubble-wrap {
  display: flex;
  flex-direction: column;
  min-width: 0;
  max-width: min(78%, 860px);
}

.row--user .bubble-wrap {
  align-items: flex-end;
}

.bubble {
  padding: 9px 13px;
  border-radius: 8px;
  border: 1px solid var(--border-soft);
  min-width: 0;
  overflow-wrap: anywhere;
}

.bubble--bot {
  background: var(--bg-panel);
  border-top-left-radius: 3px;
}

.bubble--user {
  background: var(--user-bubble);
  color: var(--user-bubble-text);
  border-color: transparent;
  border-top-right-radius: 3px;
}

.plain {
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 14px;
  line-height: 1.7;
}

.bubble-foot {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
  padding-left: 2px;
  min-height: 18px;
}

.tag {
  font-size: 11px;
  color: var(--text-muted);
  background: var(--bg-sunken);
  border: 1px solid var(--border-soft);
  border-radius: 4px;
  padding: 0 5px;
  line-height: 16px;
}

.foot-btn {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  border: 0;
  background: transparent;
  color: var(--text-muted);
  font-size: 11px;
  font-family: inherit;
  cursor: pointer;
  padding: 0 2px;
  border-radius: 3px;
}

.foot-btn:hover {
  color: var(--accent);
}

.err {
  display: flex;
  align-items: center;
  gap: 5px;
  color: var(--danger);
  font-size: 13px;
}

.typing {
  display: inline-flex;
  gap: 4px;
  align-items: center;
  height: 18px;
}

.typing span {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--text-muted);
  animation: blink 1.2s infinite ease-in-out;
}

.typing span:nth-child(2) {
  animation-delay: 0.18s;
}
.typing span:nth-child(3) {
  animation-delay: 0.36s;
}

@keyframes blink {
  0%,
  80%,
  100% {
    opacity: 0.25;
    transform: translateY(0);
  }
  40% {
    opacity: 1;
    transform: translateY(-2px);
  }
}

@media (max-width: 720px) {
  .bubble-wrap {
    max-width: 88%;
  }
}
</style>
