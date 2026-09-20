// These are local navigation actions. Opening an entry never writes learning data.
export const QUICK_COMMANDS = [
  { id: 'quick-task', label: '记一项任务', keywords: '新建 添加 作业 速记 task', icon: 'EditPen', to: { path: '/tasks', query: { action: 'quick-task' } }, group: '快速开始' },
  { id: 'add-material', label: '添加资料', keywords: '文件 上传 笔记 文字 导入 提纲 material', icon: 'Document', to: { path: '/materials', query: { action: 'upload' } }, group: '快速开始' },
  { id: 'paste-notice', label: '粘贴课程通知', keywords: '原文 提取 识别 notice', icon: 'Document', to: { path: '/materials', query: { action: 'paste-notice' } }, group: '快速开始' },
  { id: 'create-plan', label: '安排复习', keywords: '新建 创建 学习 计划 plan', icon: 'Calendar', to: { path: '/study-plans', query: { action: 'create' } }, group: '快速开始' },
  { id: 'import-schedule', label: '导入课表与考试', keywords: '教务 日程 日历 ics schedule', icon: 'Calendar', to: { path: '/schedule', query: { action: 'import' } }, group: '快速开始' },
  { id: 'start-focus', label: '开始专注', keywords: '番茄钟 计时 focus', icon: 'Timer', to: '/focus', group: '快速开始' },
]

export function filterWorkspaceCommands(commands, query) {
  const terms = String(query || '').trim().toLocaleLowerCase().split(/\s+/).filter(Boolean)
  return commands.filter(command => terms.every(term => `${command.label} ${command.keywords || ''}`.toLocaleLowerCase().includes(term)))
}

export function isCommandShortcut(event) {
  return !event.isComposing && event.keyCode !== 229 && !event.repeat && !event.altKey && !event.shiftKey
    && Boolean(event.ctrlKey || event.metaKey) && event.key?.toLowerCase() === 'k'
}
