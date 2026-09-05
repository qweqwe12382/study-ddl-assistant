# 前端检查目录

`contracts/` 保存不依赖浏览器的前端契约和构建预算检查；这些检查由 `npm run verify` 统一调用。

| 文件 | 检查内容 |
| --- | --- |
| `check-material-source-navigation.mjs` | 来源导航白名单和异常目标 |
| `check-edit-precondition.mjs` | 编辑身份、版本和实体删除前置条件 |
| `check-first-learning-loop-placement.mjs` | 首轮学习闭环入口挂载与优先级 |
| `check-plan-delta-display.mjs` | 计划差异的完整展示 |
| `check-bundle-budget.mjs` | production 构建产物 gzip 预算 |

从 `frontend/` 目录执行：

```powershell
npm.cmd run verify
```

