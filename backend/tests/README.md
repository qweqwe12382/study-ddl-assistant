# 后端测试目录

后端测试按关注点分组，pytest 会从 `backend/tests` 递归发现全部 `test_*.py` 文件。

| 目录 | 内容 |
| --- | --- |
| [`api/`](./api/) | 基础 API、认证、容量、课表/考试和智能体接口回归 |
| [`agent/`](./agent/) | M8 智能体能力、反馈、复盘、证据导航、身份和并发保护 |
| [`integration/`](./integration/) | 代表性学习资料解析和南京理工教务适配器 |
| [`fixtures/`](./fixtures/) | 脱敏 PDF/DOCX 等固定测试样本 |
| [`conftest.py`](./conftest.py) | 共享测试客户端、隔离数据库和临时目录配置 |

从项目根目录执行：

```powershell
& .\.venv\Scripts\python.exe -m pytest -q --basetemp .\.pytest-tmp\final-check
```

