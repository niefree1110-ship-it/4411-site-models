# 4411-site-models

[4411.site](https://4411.site) 模型工作台 `/models/` 的数据构建与发布仓库。

- 每天 UTC 01:00（北京时间 09:00）由 GitHub Actions 抓取公开数据、重建快照并提交
- 更新范围：OpenRouter 免费模型目录、aihot.news 模型榜 / 额度重置监控 / 核实日期
- 服务器侧用 `server/pull-models.sh` 定时拉取，脚本自带完整性校验、备份与失败回滚
- 全部为第三方**快照**，页面会如实标注快照时间；具体额度以厂商官方公告为准

数据来源：`openrouter.ai/api/v1/models`、`aihot.news/free-tokens`、`aihot.news/leaderboard`、`aihot.news/resets`。

本仓库只放需要公开分发的构建脚本与静态页面，不含任何密钥或服务器凭据。
