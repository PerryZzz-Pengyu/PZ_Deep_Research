# PZ Deep Research 登录与历史绑定配置

## 文档维护规则

这份文档用于记录身份服务、会话验证、匿名历史归并和账号数据隔离的配置方法。只要登录 Provider、环境变量、归并规则或授权边界发生变化，都需要同步更新本文档和 `project-docs/changelog.md`。

## 当前方案

项目使用 Clerk 提供注册、登录和会话，FastAPI 使用 Clerk JWT 公钥在本地验证会话 token。SQLite/PostgreSQL 保存研究任务，`research_jobs.user_id` 保存 Clerk token 的 `sub`。

未配置 Clerk 时应用仍可使用访客模式，历史按当前浏览器生成的匿名 ID 保存。

## Clerk Dashboard 配置

1. 在 Clerk 创建应用。
2. 开启需要的登录方式，例如邮箱验证码、Google 或 GitHub。
3. 在 API Keys 页面复制 Publishable key。
4. 在 Clerk 的会话 JWT 验证页面复制 PEM Public key。
5. 本地开发域名使用 `http://localhost:3000`；生产上线后把正式域名加入 Clerk Allowed Origins，并同步更新后端 `CLERK_AUTHORIZED_PARTIES`。

官方入口：

- <https://clerk.com/docs/quickstarts/nextjs>
- <https://clerk.com/docs/guides/sessions/manual-jwt-verification>

## 本地环境变量

前端 `frontend/.env.local`：

```text
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
```

根目录 `.env`：

```text
CLERK_JWT_KEY=-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----
CLERK_AUTHORIZED_PARTIES=http://localhost:3000,http://127.0.0.1:3000
CLERK_CLOCK_SKEW_SECONDS=5
```

`CLERK_JWT_KEY` 可以使用真实换行，也可以把换行写成 `\n`。这里填写的是公钥，不是 Clerk Secret Key。当前后端不调用 Clerk Management API，因此不需要 `CLERK_SECRET_KEY`。

修改后需要重启前端和后端。

## 历史归属规则

1. 未登录创建的任务只绑定浏览器匿名 ID。
2. 用户登录后，前端同时发送匿名 ID 和 Clerk Bearer token。
3. 后端验签成功后，把当前匿名 ID 下尚未归属账号的任务更新到 Clerk `user_id`。
4. 后续任务直接写入 `user_id`，同一账号可跨设备查看。
5. 退出登录后，已归并任务不会重新出现在访客历史。
6. 其他账号或访客访问任务详情、事件、SSE、重跑、重试、取消或导出时返回 404。

## 手动验收

1. 不登录创建一个 mock 研究任务，并确认它出现在访客历史。
2. 注册或登录 Clerk 账号。
3. 打开历史，确认刚才的匿名任务仍存在，页面显示“当前账号”。
4. 退出登录，确认已归并任务不再出现在访客历史。
5. 在另一个浏览器或无痕窗口登录同一账号，确认可以读取该任务和报告。
6. 使用另一个 Clerk 账号登录，确认不能通过任务 ID 读取第一个账号的任务。
7. 运行研究任务，确认 SSE 进度、刷新恢复、取消、重跑和 PDF 导出仍正常。

## 生产注意事项

- `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` 可以公开；模型、搜索、Jina、数据库和 Clerk Secret Key 不能进入浏览器。
- 生产环境必须把正式站点域名写入 `CLERK_AUTHORIZED_PARTIES`，不要保留不需要的来源。
- 当前自动归并依据“登录请求携带的当前浏览器匿名 ID”。共享设备登录前应理解该浏览器中的匿名任务会归入当前账号。
- 后续增加账号删除时，需要同时定义 Clerk 用户删除、业务用户状态、研究任务保留/删除和审计日志策略。
- 后续增加额度时，应建立本地业务用户表，不要把额度只保存在 Clerk metadata。
