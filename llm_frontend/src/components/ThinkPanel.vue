<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{ reasoning: string; loading: boolean }>()

// 流式输出时默认展开，让用户看到推理过程；结束后自动收起，避免占据正文空间
const expanded = ref(true)
watch(
  () => props.loading,
  (loading) => {
    if (!loading) expanded.value = false
  },
)
</script>

<template>
  <div v-if="reasoning" class="think">
    <button type="button" class="think-head" @click="expanded = !expanded">
      <el-icon :size="13" class="think-icon">
        <Loading v-if="loading" />
        <MagicStick v-else />
      </el-icon>
      <span class="think-label">{{ loading ? '正在思考…' : '思考过程' }}</span>
      <span class="think-len">{{ reasoning.length }} 字</span>
      <el-icon :size="12" class="think-arrow" :class="{ 'is-open': expanded }"><ArrowRight /></el-icon>
    </button>
    <div v-show="expanded" class="think-body">{{ reasoning }}</div>
  </div>
</template>

<style scoped>
.think {
  margin-bottom: 10px;
  border: 1px solid var(--think-border);
  border-radius: 6px;
  background: var(--think-soft);
  overflow: hidden;
}

.think-head {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  padding: 6px 10px;
  border: 0;
  background: transparent;
  color: var(--think);
  font-family: inherit;
  font-size: 12px;
  cursor: pointer;
  text-align: left;
}

.think-icon {
  flex: 0 0 auto;
}

.think-icon.is-loading,
.think-head .el-icon:first-child {
  animation: none;
}

.think-label {
  font-weight: 600;
  white-space: nowrap;
}

.think-len {
  color: var(--text-muted);
  font-size: 11px;
  white-space: nowrap;
}

.think-arrow {
  margin-left: auto;
  transition: transform 0.15s;
  flex: 0 0 auto;
}

.think-arrow.is-open {
  transform: rotate(90deg);
}

.think-body {
  padding: 0 10px 9px;
  font-size: 12.5px;
  line-height: 1.7;
  color: var(--text-secondary);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 260px;
  overflow-y: auto;
  border-top: 1px dashed var(--think-border);
  padding-top: 8px;
}
</style>
