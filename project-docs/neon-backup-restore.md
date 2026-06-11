# Neon 备份与恢复演练

## 文档维护规则

只要 Neon 的备份策略、恢复窗口、演练步骤、数据库连接方式或验收标准发生变化，都需要更新本文档，并同步更新 `project-docs/changelog.md`。

## 当前策略

PZ Deep Research 使用两层数据库保护：

1. Neon 时间点恢复与分支：用于快速恢复误删、错误迁移或错误写入。
2. PostgreSQL `pg_dump`：后续用于生成可迁移到其他 PostgreSQL 服务的独立备份文件。

第一轮演练优先使用 Neon 分支，避免直接修改生产分支。Neon 的恢复窗口取决于当前套餐和项目设置，执行前需要在 Neon 控制台确认可选时间范围。

官方说明：

- <https://neon.com/docs/introduction/branch-restore>
- <https://neon.com/docs/manage/backups>
- <https://neon.com/docs/import/import-from-postgres>

## 安全演练步骤

### 1. 记录基线

在生产分支只读记录：

- `research_jobs` 总数。
- 一个已完成任务的任务 ID。
- 该任务状态。
- 最终报告字符数。
- 对应 `research_events` 数量。
- 当前 Alembic 版本。

不要复制报告正文、数据库密码或连接字符串到演练记录。

### 2. 创建恢复分支

在 Neon 控制台从生产分支创建一个恢复分支：

```text
restore-drill-YYYYMMDD-HHmm
```

优先选择报告已经生成之后、演练开始之前的时间点。不要在第一次演练中原地恢复生产分支。

### 3. 使用恢复分支连接

复制恢复分支的 pooled 和 direct 连接字符串，但不要覆盖正式 `.env`。在单独终端或临时环境中启动验证实例：

```bash
DATABASE_URL="<恢复分支 pooled URL>" \
DATABASE_MIGRATION_URL="<恢复分支 direct URL>" \
PYTHONPATH=. \
.venv/bin/python scripts/check_database.py
```

验证实例必须使用不同端口，不能替换当前生产或本地正式进程。

### 4. 验证数据完整性

确认以下项目与基线一致：

- 已完成任务存在。
- 任务状态正确。
- 最终报告字符数一致。
- 任务事件数量一致。
- Alembic 版本正确。
- API 可以按原归属读取任务、事件和报告。

### 5. 记录 RPO 与 RTO

- RPO：恢复点距离故障时间的差值。
- RTO：从开始恢复到验证通过所需时间。

演练记录至少包含时间、恢复点、验证结果、RPO、RTO 和发现的问题，不记录凭据。

### 6. 清理

验证完成后删除演练分支和临时连接配置。生产分支与正式 `.env` 保持不变。

## 独立备份

Neon 分支适合快速恢复，但不能替代可迁移的独立备份。上线前应在受控环境安装与 Neon PostgreSQL 主版本兼容的 `pg_dump` / `pg_restore`，使用 direct URL 定期生成 custom-format dump，并在独立空数据库执行恢复验证。

备份文件必须：

- 加密存储。
- 不进入 Git。
- 有保留周期。
- 定期实际恢复验证，不能只检查文件是否存在。

## 当前验收状态

- 已完成真实 Neon 连接和 Alembic 迁移。
- 已完成后端重启恢复：任务 `c5db24ca5f5c4ffcbf9166b2e019272a` 的 3298 字报告和 16 条事件可通过 API 完整恢复。
- 2026-06-11 已从 `production` 当前时刻创建 `restore-drill-20260611` 分支，并设置 1 天后自动删除。
- 恢复分支 pooled 与 direct 连接均通过只读 `SELECT 1` 验证，且确认连接目标与 production 分离。
- production 与恢复分支快照一致：
  - `research_jobs`：2 条
  - Alembic：`20260611_04`
  - 最新报告状态：`completed`
  - 最新报告字符数：3298
  - 对应事件：16 条
- 本次为“当前时刻分支恢复”演练，RPO 近似为 0；从创建分支到完整验证通过约 5 分钟，可作为本轮 RTO 记录。
- 尚未演练“指定历史时间点恢复”和 `pg_dump` / `pg_restore` 独立备份恢复。
