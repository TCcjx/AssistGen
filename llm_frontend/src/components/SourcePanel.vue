<script setup lang="ts">
import type { SearchHit } from '@/types'
import { hostOf } from '@/utils/format'

defineProps<{ sources: SearchHit[]; query?: string; total?: number }>()

function faviconOf(url: string): string {
  return `https://www.google.com/s2/favicons?domain=${encodeURIComponent(hostOf(url))}&sz=32`
}
</script>

<template>
  <div v-if="sources.length" class="src">
    <div class="src-head">
      <el-icon :size="13"><Link /></el-icon>
      <span>检索来源</span>
      <span v-if="total" class="src-count">{{ total }} 条</span>
    </div>
    <ol class="src-list">
      <li v-for="(hit, i) in sources" :key="hit.url + i" class="src-item">
        <a :href="hit.url" target="_blank" rel="noopener noreferrer" class="src-link">
          <img class="src-fav" :src="faviconOf(hit.url)" alt="" loading="lazy" />
          <span class="src-body">
            <span class="src-title">{{ hit.title || hit.url }}</span>
            <span class="src-host">{{ hostOf(hit.url) }}</span>
            <span v-if="hit.snippet" class="src-snippet">{{ hit.snippet }}</span>
          </span>
          <span class="src-idx">{{ i + 1 }}</span>
        </a>
      </li>
    </ol>
  </div>
</template>

<style scoped>
.src {
  margin-bottom: 10px;
  border: 1px solid var(--border-soft);
  border-radius: 6px;
  background: var(--bg-sunken);
  overflow: hidden;
}

.src-head {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  border-bottom: 1px solid var(--border-soft);
}

.src-count {
  margin-left: auto;
  font-weight: 400;
  color: var(--text-muted);
  font-size: 11px;
}

.src-list {
  list-style: none;
  margin: 0;
  padding: 4px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.src-link {
  display: grid;
  grid-template-columns: 16px minmax(0, 1fr) auto;
  gap: 8px;
  align-items: start;
  padding: 6px;
  border-radius: 5px;
  text-decoration: none;
  transition: background 0.13s;
}

.src-link:hover {
  background: var(--bg-hover);
}

.src-fav {
  width: 16px;
  height: 16px;
  border-radius: 3px;
  margin-top: 2px;
  background: var(--bg-panel);
}

.src-body {
  display: flex;
  flex-direction: column;
  min-width: 0;
  gap: 1px;
}

.src-title {
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.45;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.src-host {
  font-size: 11px;
  color: var(--accent);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.src-snippet {
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.55;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.src-idx {
  font-size: 11px;
  color: var(--text-muted);
  padding-top: 2px;
}
</style>
