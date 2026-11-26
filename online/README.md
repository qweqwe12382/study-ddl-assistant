# 在线版部署

这里是与本地演示版隔离的在线部署入口。它复用现有 `backend/` 和 `frontend/` 源码，但不修改这些源码，也不使用根目录的本地 `data/` 数据。

在线注册创建普通账号和独立的 SQLite 工作区。对外测试请注册单独的普通账号，实例管理员账号由运营者保管。已有实例的账号角色在升级时保留。

## 服务器要求

- Linux 服务器（Ubuntu 22.04/24.04 均可）
- Docker Engine 与 Docker Compose Plugin
- 域名 DNS 的 A/AAAA 记录指向服务器
- 防火墙放行 TCP 80、443

## 首次部署

先为 `xuebanguanjia.cc.cd` 添加指向 `107.173.123.218` 的 A 记录。在 Windows 的项目根目录执行以下命令，脚本通过 SSH 从 GitHub 拉取代码并启动 Docker Compose。

```powershell
.\online\deploy.ps1
```

默认连接 `deploy@107.173.123.218`，部署目录为服务器上的 `~/apps/study-ddl-assistant`。应用只在服务器的 `127.0.0.1:18080` 上提供 HTTP。用服务器已有的反向代理为 `xuebanguanjia.cc.cd` 新增 HTTPS 站点，将整个域名转发到 `http://127.0.0.1:18080`。反向代理若在独立容器中，需要先配置该容器到应用的网络连接。配置完成后访问 `https://xuebanguanjia.cc.cd/` 和 `/api/health`。如果 `18080` 已被占用，脚本可通过 `-LocalPort` 改用其他端口。

如果服务器的 80/443 端口可用于本项目，可以用 `.\online\deploy.ps1 -DirectHttps` 让项目内的 Caddy 直接提供 HTTPS。

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

如果还没有域名，可以把 `.env` 中的 `SITE_ADDRESS` 改为 `:80`，将 `CORS_ORIGINS` 改为服务器访问地址（例如 `http://107.173.123.218`），同时设置 `AUTH_COOKIE_SECURE=false`，然后执行：

```bash
docker compose up -d --build
```

此时使用 `http://服务器IP/` 访问，不会有自动 HTTPS。HTTP 下必须关闭 Cookie 的 Secure 标记，否则浏览器无法保持登录。绑定域名并启用 HTTPS 后，将 `AUTH_COOKIE_SECURE` 恢复为 `true`。

## 端口与安全边界

- 只有 Caddy 的 80/443 端口映射到服务器。
- FastAPI 的 8000 端口只在 Docker 内网可见。
- 除公开主页、注册登录和健康检查外，业务 API 需要有效账号会话；所有写操作还需 CSRF token。
- `DEMO_MODE` 在线版强制为 `false`，不会自动写入演示数据。
- 多账号数据使用同一卷内的独立 SQLite 文件和上传子目录；这不是高并发租户数据库或对象存储方案。
- 在邮件验证、账号恢复、限流、备份恢复和真实服务器安全验收完成前，不应向陌生用户公开注册。
