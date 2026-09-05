# 在线版部署

这里是与本地演示版隔离的在线部署入口。它复用现有 `backend/` 和 `frontend/` 源码，但不修改这些源码，也不使用根目录的本地 `data/` 数据。

当前代码已经具备邮箱账号、Cookie 会话、CSRF 以及按账号拆分的 SQLite 学习工作区；第一个注册账号为实例管理员，后续账号不能修改实例级外部 AI 配置。但它仍缺少邮箱验证、找回密码、生产级登录限流、静态加密、备份恢复和运维审计，因此本目录只能作为待验证部署起点，不能直接当作成熟 SaaS 公开运营。

## 服务器要求

- Linux 服务器（Ubuntu 22.04/24.04 均可）
- Docker Engine 与 Docker Compose Plugin
- 域名 DNS 的 A/AAAA 记录指向服务器
- 防火墙放行 TCP 80、443

## 首次部署

在服务器上取得项目代码后执行：

```bash
cd huatai_proj/online
cp .env.example .env
```

编辑 `.env`：

1. 将 `SITE_ADDRESS` 改为真实域名，例如 `study.example.com`。
2. 将 `TLS_EMAIL` 改为接收证书通知的邮箱。
3. 将 `CORS_ORIGINS` 改为 `https://study.example.com`。
4. 保持 `AUTH_COOKIE_SECURE=true`；如果需要外部 AI Provider，再填写 `LLM_BASE_URL`、`LLM_API_KEY` 和 `LLM_MODEL`，不需要时留空即可。

启动在线版：

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f --tail=100
```

浏览器访问 `https://study.example.com/`。Caddy 会自动申请并续期 HTTPS 证书；如果域名尚未解析完成，证书申请会失败，解析完成后重新执行 `docker compose restart web` 即可。

## 数据隔离与备份

在线数据保存在 Docker 卷 `online_data` 中，与本地版的 `data/` 完全分开。在线版首次启动是空数据，这是刻意设计的，避免服务器和本地开发数据互相覆盖。

查看卷名：

```bash
docker volume ls | grep online_data
```

备份在线数据库和上传文件：

```bash
docker run --rm \
  -v learning-assistant-online-data:/data:ro \
  -v "$PWD":/backup \
  alpine:3.20 tar czf /backup/online-data-$(date +%F).tar.gz -C /data .
```

## 更新在线版

```bash
cd huatai_proj
git pull
cd online
docker compose up -d --build
```

更新前建议先备份 `online_data`。本地版仍然使用原来的：

```powershell
.\scripts\start-dev.ps1
```

两套启动方式互不覆盖。

## 临时用 IP 测试

如果还没有域名，可以把 `.env` 中的 `SITE_ADDRESS` 改为 `:80`，同时将 `CORS_ORIGINS` 改为服务器访问地址或暂时留空，然后执行：

```bash
docker compose up -d --build
```

此时使用 `http://服务器IP/` 访问，不会有自动 HTTPS。正式使用仍建议绑定域名并启用 HTTPS。

## 端口与安全边界

- 只有 Caddy 的 80/443 端口映射到服务器。
- FastAPI 的 8000 端口只在 Docker 内网可见。
- 除公开主页、注册登录和健康检查外，业务 API 需要有效账号会话；所有写操作还需 CSRF token。
- `DEMO_MODE` 在线版强制为 `false`，不会自动写入演示数据。
- 多账号数据使用同一卷内的独立 SQLite 文件和上传子目录；这不是高并发租户数据库或对象存储方案。
- 在邮件验证、账号恢复、限流、备份恢复和真实服务器安全验收完成前，不应向陌生用户公开注册。
