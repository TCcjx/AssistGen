<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import * as authApi from '@/api/auth'
import { errorMessage } from '@/api/http'
import { useUserStore } from '@/stores/user'

type AuthMode = 'login' | 'register'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const mode = ref<AuthMode>(route.meta.mode === 'register' ? 'register' : 'login')
const formRef = ref<FormInstance>()
const submitting = ref(false)
const form = reactive({ username: '', email: '', password: '', confirm: '' })

const isRegister = computed(() => mode.value === 'register')
const isDark = computed(() => userStore.theme === 'dark')

const rules = computed<FormRules>(() => ({
  username: isRegister.value
    ? [
        { required: true, message: '请输入用户名', trigger: 'blur' },
        { min: 2, max: 32, message: '用户名长度为 2-32 个字符', trigger: 'blur' },
      ]
    : [],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '邮箱格式不正确', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 64, message: '密码长度为 6-64 个字符', trigger: 'blur' },
  ],
  confirm: isRegister.value
    ? [
        { required: true, message: '请再次输入密码', trigger: 'blur' },
        {
          validator: (_rule, value: string, callback) => {
            if (value !== form.password) callback(new Error('两次输入的密码不一致'))
            else callback()
          },
          trigger: 'blur',
        },
      ]
    : [],
}))

watch(
  () => route.meta.mode,
  (value) => {
    mode.value = value === 'register' ? 'register' : 'login'
    formRef.value?.clearValidate()
  },
)

function switchMode(next: AuthMode): void {
  if (submitting.value) return
  mode.value = next
  void router.replace(next === 'register' ? '/register' : '/login')
}

async function submit(): Promise<void> {
  if (!formRef.value || submitting.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    if (isRegister.value) {
      await authApi.register(form.username.trim(), form.email.trim(), form.password)
      ElMessage.success('注册成功，正在登录')
    }
    const result = await authApi.login(form.email.trim(), form.password)
    if (!result.access_token) throw new Error('登录响应缺少访问令牌')
    const info = await authApi.fetchUserInfo()
    userStore.setUserInfo(info)
    await router.replace('/')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <main class="auth-page">
    <button
      type="button"
      class="theme-btn"
      :title="isDark ? '切换到浅色主题' : '切换到深色主题'"
      @click="userStore.toggleTheme()"
    >
      <el-icon :size="17">
        <Sunny v-if="isDark" />
        <Moon v-else />
      </el-icon>
    </button>

    <section class="auth-panel">
      <div class="brand">
        <span class="brand-mark"><el-icon :size="21"><ChatDotSquare /></el-icon></span>
        <div>
          <h1>AssistGen</h1>
          <p>智能客服工作台</p>
        </div>
      </div>

      <div class="auth-tabs" role="tablist">
        <button
          type="button"
          role="tab"
          :aria-selected="!isRegister"
          :class="{ 'is-active': !isRegister }"
          @click="switchMode('login')"
        >
          登录
        </button>
        <button
          type="button"
          role="tab"
          :aria-selected="isRegister"
          :class="{ 'is-active': isRegister }"
          @click="switchMode('register')"
        >
          注册
        </button>
      </div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        size="large"
        @submit.prevent="submit"
      >
        <el-form-item v-if="isRegister" label="用户名" prop="username">
          <el-input v-model="form.username" autocomplete="username" placeholder="用于在系统中显示">
            <template #prefix><el-icon><User /></el-icon></template>
          </el-input>
        </el-form-item>

        <el-form-item label="邮箱" prop="email">
          <el-input
            v-model="form.email"
            type="email"
            autocomplete="email"
            placeholder="name@example.com"
            @keyup.enter="submit"
          >
            <template #prefix><el-icon><Message /></el-icon></template>
          </el-input>
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            :autocomplete="isRegister ? 'new-password' : 'current-password'"
            placeholder="至少 6 个字符"
            @keyup.enter="submit"
          >
            <template #prefix><el-icon><Lock /></el-icon></template>
          </el-input>
        </el-form-item>

        <el-form-item v-if="isRegister" label="确认密码" prop="confirm">
          <el-input
            v-model="form.confirm"
            type="password"
            show-password
            autocomplete="new-password"
            placeholder="再次输入密码"
            @keyup.enter="submit"
          >
            <template #prefix><el-icon><Lock /></el-icon></template>
          </el-input>
        </el-form-item>

        <el-button class="submit-btn" type="primary" :loading="submitting" @click="submit">
          {{ isRegister ? '创建账号并登录' : '进入工作台' }}
        </el-button>
      </el-form>
    </section>
  </main>
</template>

<style scoped>
.auth-page {
  position: relative;
  display: grid;
  place-items: center;
  min-height: 100%;
  padding: 24px;
  background:
    linear-gradient(135deg, color-mix(in srgb, var(--accent) 12%, transparent), transparent 42%),
    var(--bg-app);
}

.theme-btn {
  position: absolute;
  top: 18px;
  right: 18px;
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border: 1px solid var(--border-soft);
  border-radius: 7px;
  background: var(--bg-panel);
  color: var(--text-secondary);
  cursor: pointer;
}

.theme-btn:hover {
  color: var(--accent);
  border-color: var(--accent);
}

.auth-panel {
  width: min(100%, 410px);
  padding: 30px;
  border: 1px solid var(--border-soft);
  border-radius: 10px;
  background: var(--bg-panel);
  box-shadow: 0 18px 50px rgba(0, 0, 0, 0.12);
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
}

.brand-mark {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border-radius: 9px;
  background: var(--accent);
  color: var(--accent-text);
}

.brand h1,
.brand p {
  margin: 0;
}

.brand h1 {
  font-size: 21px;
  line-height: 1.25;
}

.brand p {
  color: var(--text-muted);
  font-size: 12px;
}

.auth-tabs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 3px;
  padding: 3px;
  margin-bottom: 22px;
  border-radius: 7px;
  background: var(--bg-sunken);
}

.auth-tabs button {
  height: 34px;
  border: 0;
  border-radius: 5px;
  background: transparent;
  color: var(--text-secondary);
  font: inherit;
  font-size: 13px;
  cursor: pointer;
}

.auth-tabs button.is-active {
  background: var(--bg-panel);
  color: var(--accent);
  font-weight: 600;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.submit-btn {
  width: 100%;
  margin-top: 4px;
}

@media (max-width: 520px) {
  .auth-page {
    padding: 14px;
  }

  .auth-panel {
    padding: 24px 20px;
  }
}
</style>
