<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const isDark = computed(() => userStore.theme === 'dark')
const displayName = computed(() => userStore.username || userStore.email || '未登录')

const NAV = [
  { path: '/', label: '智能客服' },
  { path: '/ecommerce', label: '电商智能体' },
] as const

function go(path: string): void {
  if (route.path !== path) void router.push(path)
}

async function onCommand(command: string): Promise<void> {
  if (command !== 'logout') return
  try {
    await ElMessageBox.confirm('确定要退出登录吗？', '退出登录', {
      confirmButtonText: '退出',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return // 用户取消
  }
  userStore.signOut()
  void router.push('/login')
}
</script>

<template>
  <header class="hdr">
    <div class="hdr-brand" @click="go('/')">
      <span class="hdr-logo" aria-hidden="true">
        <el-icon :size="17"><ChatDotSquare /></el-icon>
      </span>
      <span class="hdr-name">AssistGen</span>
    </div>

    <nav class="hdr-nav">
      <button
        v-for="item in NAV"
        :key="item.path"
        type="button"
        class="hdr-nav-btn"
        :class="{ 'is-active': route.path === item.path }"
        @click="go(item.path)"
      >
        {{ item.label }}
      </button>
    </nav>

    <div class="hdr-actions">
      <el-tooltip :content="isDark ? '切换到浅色' : '切换到深色'" placement="bottom">
        <button type="button" class="icon-btn" @click="userStore.toggleTheme()">
          <el-icon :size="16">
            <Sunny v-if="isDark" />
            <Moon v-else />
          </el-icon>
        </button>
      </el-tooltip>

      <el-dropdown trigger="click" @command="onCommand">
        <button type="button" class="hdr-user">
          <span class="hdr-avatar">{{ displayName.slice(0, 1).toUpperCase() }}</span>
          <span class="hdr-username">{{ displayName }}</span>
          <el-icon :size="12"><ArrowDown /></el-icon>
        </button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item disabled>{{ userStore.email || '—' }}</el-dropdown-item>
            <el-dropdown-item command="logout" divided>
              <el-icon><SwitchButton /></el-icon>
              退出登录
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </header>
</template>

<style scoped>
.hdr {
  display: flex;
  align-items: center;
  gap: 16px;
  height: 52px;
  padding: 0 14px;
  background: var(--bg-panel);
  border-bottom: 1px solid var(--border-soft);
}

.hdr-brand {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  flex: 0 0 auto;
}

.hdr-logo {
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  border-radius: 6px;
  background: var(--accent);
  color: var(--accent-text);
}

.hdr-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.hdr-nav {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 2px;
  background: var(--bg-sunken);
  border-radius: 7px;
  flex: 0 1 auto;
  min-width: 0;
}

.hdr-nav-btn {
  border: 0;
  background: transparent;
  color: var(--text-secondary);
  font-size: 13px;
  font-family: inherit;
  padding: 4px 12px;
  border-radius: 5px;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s, color 0.15s;
}

.hdr-nav-btn:hover {
  color: var(--text-primary);
}

.hdr-nav-btn.is-active {
  background: var(--bg-panel);
  color: var(--accent);
  font-weight: 600;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.08);
}

.hdr-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
  flex: 0 0 auto;
}

.icon-btn {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border: 1px solid var(--border-soft);
  border-radius: 6px;
  background: var(--bg-panel);
  color: var(--text-secondary);
  cursor: pointer;
  transition: color 0.15s, border-color 0.15s;
}

.icon-btn:hover {
  color: var(--accent);
  border-color: var(--accent);
}

.hdr-user {
  display: flex;
  align-items: center;
  gap: 7px;
  height: 30px;
  padding: 0 8px 0 4px;
  border: 1px solid var(--border-soft);
  border-radius: 6px;
  background: var(--bg-panel);
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  max-width: 180px;
}

.hdr-user:hover {
  border-color: var(--accent);
}

.hdr-avatar {
  display: grid;
  place-items: center;
  width: 22px;
  height: 22px;
  border-radius: 5px;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 12px;
  font-weight: 600;
  flex: 0 0 auto;
}

.hdr-username {
  font-size: 13px;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.hdr-user :deep(.el-icon) {
  flex: 0 0 auto;
}

@media (max-width: 720px) {
  .hdr-name,
  .hdr-username {
    display: none;
  }
  .hdr {
    gap: 10px;
  }
}
</style>
