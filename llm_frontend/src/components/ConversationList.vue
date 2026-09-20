<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useConversationStore } from '@/stores/conversation'
import { errorMessage } from '@/api/http'
import { formatRelative } from '@/utils/format'

const store = useConversationStore()
const renamingId = ref<number | null>(null)
const renameText = ref('')

function startRename(id: number, title: string): void {
  renamingId.value = id
  renameText.value = title
}

async function commitRename(id: number): Promise<void> {
  const name = renameText.value.trim()
  renamingId.value = null
  if (!name) return
  try {
    await store.rename(id, name)
    ElMessage.success('会话名称已更新')
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}

async function confirmDelete(id: number, title: string): Promise<void> {
  try {
    await ElMessageBox.confirm(`删除会话「${title}」及其全部消息？`, '删除会话', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await store.remove(id)
    ElMessage.success('会话已删除')
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}

async function onSelect(id: number): Promise<void> {
  if (store.currentId === id) return
  try {
    await store.select(id)
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}
</script>

<template>
  <aside class="panel conv">
    <div class="panel-head">
      <span class="panel-title">历史会话</span>
      <el-tooltip content="新建会话" placement="right">
        <button type="button" class="icon-btn" @click="store.startDraft()">
          <el-icon :size="15"><Plus /></el-icon>
        </button>
      </el-tooltip>
    </div>

    <div class="scroll-y conv-list">
      <div v-if="store.loadingList" class="empty-hint">加载中…</div>
      <div v-else-if="!store.items.length" class="empty-hint">
        还没有历史会话<br />点击左上角 + 开始新对话
      </div>

      <div
        v-for="item in store.items"
        :key="item.id"
        class="conv-item"
        :class="{ 'is-active': store.currentId === item.id }"
        @click="onSelect(item.id)"
      >
        <el-icon class="conv-icon" :size="14"><ChatLineSquare /></el-icon>

        <div class="conv-main">
          <input
            v-if="renamingId === item.id"
            v-model="renameText"
            class="conv-rename"
            @click.stop
            @keyup.enter="commitRename(item.id)"
            @keyup.esc="renamingId = null"
            @blur="commitRename(item.id)"
          />
          <span v-else class="conv-title">{{ item.title }}</span>
          <span class="conv-meta">{{ formatRelative(item.created_at) }}</span>
        </div>

        <div class="conv-ops" @click.stop>
          <el-tooltip content="重命名" placement="top">
            <button type="button" class="op-btn" @click="startRename(item.id, item.title)">
              <el-icon :size="13"><EditPen /></el-icon>
            </button>
          </el-tooltip>
          <el-tooltip content="删除" placement="top">
            <button type="button" class="op-btn op-btn--danger" @click="confirmDelete(item.id, item.title)">
              <el-icon :size="13"><Delete /></el-icon>
            </button>
          </el-tooltip>
        </div>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.conv-list {
  padding: 6px;
}

.conv-item {
  display: grid;
  grid-template-columns: 16px minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  padding: 7px 8px;
  border-radius: 6px;
  cursor: pointer;
  border: 1px solid transparent;
  transition: background 0.13s;
}

.conv-item:hover {
  background: var(--bg-hover);
}

.conv-item.is-active {
  background: var(--bg-active);
  border-color: var(--accent);
}

.conv-icon {
  color: var(--text-muted);
  flex: 0 0 auto;
}

.conv-item.is-active .conv-icon {
  color: var(--accent);
}

.conv-main {
  display: flex;
  flex-direction: column;
  min-width: 0;
  gap: 1px;
}

.conv-title {
  font-size: 13px;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.conv-meta {
  font-size: 11px;
  color: var(--text-muted);
}

.conv-rename {
  width: 100%;
  font-size: 13px;
  font-family: inherit;
  padding: 1px 4px;
  border: 1px solid var(--accent);
  border-radius: 4px;
  background: var(--bg-panel);
  color: var(--text-primary);
  outline: none;
}

.conv-ops {
  display: flex;
  gap: 2px;
  opacity: 0;
  transition: opacity 0.13s;
}

.conv-item:hover .conv-ops,
.conv-item.is-active .conv-ops {
  opacity: 1;
}

.op-btn {
  display: grid;
  place-items: center;
  width: 22px;
  height: 22px;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
}

.op-btn:hover {
  background: var(--bg-panel);
  color: var(--accent);
}

.op-btn--danger:hover {
  color: var(--danger);
}

.icon-btn {
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  border: 1px solid var(--border-soft);
  border-radius: 6px;
  background: var(--bg-panel);
  color: var(--text-secondary);
  cursor: pointer;
}

.icon-btn:hover {
  color: var(--accent);
  border-color: var(--accent);
}
</style>
