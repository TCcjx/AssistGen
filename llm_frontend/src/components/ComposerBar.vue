<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { CHAT_MODES, type ChatMode } from '@/types'
import { fileKind, formatBytes } from '@/utils/format'

const props = defineProps<{
  modelValue: string
  mode: ChatMode
  busy: boolean
  /** 文档问答模式下已建立的索引 */
  indexId: string | null
  indexName: string | null
}>()

const emit = defineEmits<{
  'update:modelValue': [string]
  'update:mode': [ChatMode]
  send: []
  stop: []
  file: [File]
  image: [File]
  'clear-file': []
}>()

const areaRef = ref<{ focus: () => void } | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
const imageInput = ref<HTMLInputElement | null>(null)

const currentMeta = computed(() => CHAT_MODES.find((m) => m.value === props.mode))
const canSend = computed(() => props.modelValue.trim().length > 0 && !props.busy)

/** 文档问答必须先有索引，否则后端无法检索 */
const blockedReason = computed(() => {
  if (props.mode === 'rag' && !props.indexId) return '请先上传文档'
  return ''
})

function onInput(value: string | number): void {
  emit('update:modelValue', String(value))
}

function onKeydown(event: KeyboardEvent): void {
  // Enter 发送，Shift+Enter 换行；中文输入法组合态下的回车不触发发送
  if (event.key !== 'Enter' || event.shiftKey || event.isComposing) return
  event.preventDefault()
  submit()
}

function submit(): void {
  if (!canSend.value) {
    if (blockedReason.value) ElMessage.warning(blockedReason.value)
    return
  }
  emit('send')
  void nextTick(() => areaRef.value?.focus())
}

function pickFile(): void {
  fileInput.value?.click()
}

function pickImage(): void {
  imageInput.value?.click()
}

function onFileChange(event: Event): void {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = '' // 允许重复选择同一文件
  if (!file) return
  if (file.size > 30 * 1024 * 1024) {
    ElMessage.error('文件不能超过 30 MB')
    return
  }
  emit('file', file)
}

function onImageChange(event: Event): void {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  if (!file.type.startsWith('image/')) {
    ElMessage.error('请选择图片文件')
    return
  }
  if (file.size > 8 * 1024 * 1024) {
    ElMessage.error('图片不能超过 8 MB')
    return
  }
  emit('image', file)
}
</script>

<template>
  <div class="composer">
    <div class="modes">
      <div class="seg">
        <el-tooltip
          v-for="m in CHAT_MODES"
          :key="m.value"
          :content="m.hint"
          placement="top"
          :show-after="350"
        >
          <button
            type="button"
            class="seg-btn"
            :class="{ 'is-active': mode === m.value }"
            @click="emit('update:mode', m.value)"
          >
            {{ m.label }}
          </button>
        </el-tooltip>
      </div>
      <span class="mode-hint">{{ currentMeta?.hint }}</span>
    </div>

    <div v-if="mode === 'rag' && indexId" class="chip-row">
      <span class="chip">
        <el-icon :size="12"><Document /></el-icon>
        <span class="chip-name">{{ indexName || '已索引文档' }}</span>
        <button type="button" class="chip-x" title="移除文档" @click="emit('clear-file')">
          <el-icon :size="11"><Close /></el-icon>
        </button>
      </span>
    </div>

    <div class="input-box" :class="{ 'is-blocked': !!blockedReason }">
      <el-input
        ref="areaRef"
        :model-value="modelValue"
        type="textarea"
        :autosize="{ minRows: 2, maxRows: 8 }"
        resize="none"
        :placeholder="
          blockedReason || '输入问题，Enter 发送，Shift+Enter 换行'
        "
        @update:model-value="onInput"
        @keydown="onKeydown"
      />

      <div class="toolbar">
        <el-tooltip v-if="mode === 'rag'" content="上传文档建立索引" placement="top">
          <button type="button" class="tool-btn" @click="pickFile">
            <el-icon :size="15"><FolderOpened /></el-icon>
          </button>
        </el-tooltip>

        <el-tooltip v-if="mode === 'agent'" content="附加图片，让视觉模型识别" placement="top">
          <button type="button" class="tool-btn" @click="pickImage">
            <el-icon :size="15"><Picture /></el-icon>
          </button>
        </el-tooltip>

        <span class="counter" :class="{ 'is-over': modelValue.length > 4000 }">
          {{ modelValue.length }}
        </span>

        <el-button
          v-if="busy"
          type="danger"
          plain
          size="small"
          class="send-btn"
          @click="emit('stop')"
        >
          <el-icon><VideoPause /></el-icon>
          停止
        </el-button>
        <el-button
          v-else
          type="primary"
          size="small"
          class="send-btn"
          :disabled="!canSend"
          @click="submit"
        >
          <el-icon><Promotion /></el-icon>
          发送
        </el-button>
      </div>
    </div>

    <input
      ref="fileInput"
      type="file"
      accept=".pdf,.txt,.md,.csv,.docx,.json"
      hidden
      @change="onFileChange"
    />
    <input ref="imageInput" type="file" accept="image/*" hidden @change="onImageChange" />
  </div>
</template>

<style scoped>
.composer {
  border-top: 1px solid var(--border-soft);
  background: var(--bg-panel);
  padding: 10px 18px 14px;
  flex: 0 0 auto;
}

.modes {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
  min-width: 0;
}

.seg {
  display: flex;
  gap: 2px;
  padding: 2px;
  background: var(--bg-sunken);
  border-radius: 7px;
  flex: 0 0 auto;
}

.seg-btn {
  border: 0;
  background: transparent;
  color: var(--text-secondary);
  font-size: 12.5px;
  font-family: inherit;
  padding: 4px 10px;
  border-radius: 5px;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s, color 0.15s;
}

.seg-btn:hover {
  color: var(--text-primary);
}

.seg-btn.is-active {
  background: var(--bg-panel);
  color: var(--accent);
  font-weight: 600;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.08);
}

.mode-hint {
  font-size: 12px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}

.chip-row {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  max-width: 100%;
  padding: 2px 4px 2px 8px;
  border: 1px solid var(--border-soft);
  border-radius: 5px;
  background: var(--bg-sunken);
  font-size: 12px;
  color: var(--text-secondary);
}

.chip-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 220px;
}

.chip-x {
  display: grid;
  place-items: center;
  width: 16px;
  height: 16px;
  border: 0;
  border-radius: 3px;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  flex: 0 0 auto;
}

.chip-x:hover {
  background: var(--danger-soft);
  color: var(--danger);
}

.input-box {
  border: 1px solid var(--border-strong);
  border-radius: 8px;
  background: var(--bg-panel);
  overflow: hidden;
  transition: border-color 0.15s;
}

.input-box:focus-within {
  border-color: var(--accent);
}

.input-box.is-blocked {
  border-color: var(--think-border);
}

.input-box :deep(.el-textarea__inner) {
  border: 0;
  box-shadow: none;
  background: transparent;
  padding: 9px 12px 4px;
  font-size: 14px;
  color: var(--text-primary);
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 8px 7px 10px;
}

.tool-btn {
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  border: 1px solid var(--border-soft);
  border-radius: 5px;
  background: var(--bg-panel);
  color: var(--text-secondary);
  cursor: pointer;
  flex: 0 0 auto;
}

.tool-btn:hover {
  color: var(--accent);
  border-color: var(--accent);
}

.counter {
  margin-left: auto;
  font-size: 11px;
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
}

.counter.is-over {
  color: var(--danger);
}

.send-btn {
  flex: 0 0 auto;
}

@media (max-width: 900px) {
  .mode-hint {
    display: none;
  }
  .seg {
    overflow-x: auto;
    max-width: 100%;
  }
}
</style>
