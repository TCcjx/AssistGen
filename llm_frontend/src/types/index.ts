/** 与后端 pydantic 模型一一对应的前端类型定义 */

export interface ChatMessagePayload {
  role: 'system' | 'user' | 'assistant'
  content: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
}

export interface UserInfo {
  id: number
  username: string
  email: string
  status: string
  created_at: string
  last_login: string | null
}

export interface ConversationSummary {
  id: number
  title: string
  created_at: string
  status: string
  dialogue_type: string
}

export interface StoredMessage {
  id: number
  sender: 'user' | 'assistant'
  content: string
  created_at: string
  message_type: string
}

export interface UploadResponse {
  status: string
  index_id: string | null
  filename: string
  original_name: string
  size: number
  type: string
  chunks?: number
}

export interface SearchHit {
  title: string
  url: string
  snippet: string
}

export type ChatMode = 'chat' | 'reason' | 'search' | 'rag' | 'agent'

/** 对话气泡的渲染状态 */
export interface UiMessage {
  id: string
  role: 'user' | 'assistant'
  /** 正式回答正文（Markdown） */
  content: string
  /** 深度思考模式下模型的推理过程 */
  reasoning: string
  /** 联网检索命中的网页 */
  sources: SearchHit[]
  loading: boolean
  error: string
  mode: ChatMode
}

export interface ModeMeta {
  value: ChatMode
  label: string
  hint: string
}

export const CHAT_MODES: ModeMeta[] = [
  { value: 'chat', label: '普通问答', hint: '直接由大模型作答，不检索外部资料' },
  { value: 'reason', label: '深度思考', hint: '推理模型逐步分析，展示思考过程' },
  { value: 'search', label: '联网检索', hint: '先搜索实时信息再综合作答' },
  { value: 'rag', label: '文档问答', hint: '基于你上传的文档内容作答' },
  { value: 'agent', label: '智能体', hint: '查询商品图谱与售后知识库，支持图片' },
]
