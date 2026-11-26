# 第三方 Loon 规则：镜像、统一库与自动同步

本仓库除了 `Custom/` 下自维护的规则外，还把两个第三方规则来源中的 **Loon 规则**镜像进来，
并在同名分类上合并成一套「统一规则库」。全部内容由 GitHub Actions 每天自动更新，
只有内容变化时才会产生提交。

## 1. 数据来源

| 简称 | 上游 | 取用范围 | 许可 |
| --- | --- | --- | --- |
| 来源一 | [QuixoticHeart/rule-set](https://github.com/QuixoticHeart/rule-set/tree/ruleset) | `ruleset` 分支 `loon/` 目录，约 52 个 `.list` | GPL-3.0 |
| 来源二 | [luestr/ShuntRules](https://github.com/luestr/ShuntRules) | README 目录表中的 668 个 Loon 规则（`https://rule.kelee.one/Loon/<name>.lsr`） | 仓库无 LICENSE 文件；数据来自 [blackmatrix7/ios_rule_script](https://github.com/blackmatrix7/ios_rule_script)（GPL-2.0） |

只提取 Loon 规则：来源一里 Surge / Clash / Shadowrocket / Quantumult X / Egern / sing-box 等
目录一律忽略；来源二只解析 README 中「Loon 规则」列（`.../Loon/*.lsr`），Clash 列不处理。

## 2. 目录结构

```text
Rules/
├── QuixoticHeart/            # 来源一镜像，保留上游文件名，如 abema.list
├── ShuntRules/               # 来源二镜像，保留 .lsr 后缀，如 Apple.lsr
├── Unified/                  # 统一规则库：同名分类合并去重，来源一优先
│   ├── abema.list            # 同一分类在两来源都有时命名取来源一
│   └── Apple.list            # 仅来源二有的分类直接收录
├── INDEX.md                  # 自动生成的索引 + 一键导入链接
├── CONFLICTS.md              # 去重统计与跨来源类型冲突
└── .sync-manifest.json       # 机器可读清单（路径/条数/字节数/sha256/上游地址）
```

命名规则：

- 镜像目录严格沿用上游文件名（来源一 `.list`，来源二 `.lsr`），方便和上游对照、便于 `git diff` 溯源。
- 统一库按「分类」出文件；分类名归一化后（忽略大小写与标点）相同的规则集会合并，
  例如 `abema` 与 `Abema` 合并为 `Rules/Unified/abema.list`。
- 每个生成文件顶部有静态注释头（来源、上游地址、规则数），不含时间戳，所以规则没变时文件字节不变。

## 3. 抓取与回退

```text
来源一：GitHub API 读取 ruleset 分支 loon/ 文件树
        └─ API 失败 → 解析 ruleset 分支 README 里的 loon 链接
        └─ 逐个 raw 下载

来源二：解析 README 目录表得到 668 个名字
        ├─ 探测 rule.kelee.one：可直连 → 下载 <name>.lsr
        └─ 被 Cloudflare 拦截（403/挑战页）→ 回退重建：
              <name>.list + <name>_Domain.list + <name>_Resolve.list
              （blackmatrix7 的 Loon 三件套，按该顺序合并去重）
```

回退重建的依据：ShuntRules 自己的说明是「把 `Apple.list`、`Apple_Domain.list`、
`Apple_Resolve.list` 合并为 `Apple.lsr`」。回退时按同样口径合并，因此匹配语义一致；
文件头会注明本次是直连还是回退、用了哪些分片。

## 4. 去重、冲突与保护

- **文件内**：完全相同的 `(规则类型, 值, 参数)` 只保留第一次出现，顺序不变。
- **统一库**：先来源一、后来源二逐条合入；重复项保留来源一（`CONFIG['unified']['priority']` 可调整）。
- **类型冲突**：同一域名在两个来源里类型不同（如 `DOMAIN` 与 `DOMAIN-SUFFIX`）时，
  统一库保留来源一的写法，并把冲突写入 `Rules/CONFLICTS.md`。
- **防误删**：来源二失败超过 20%、或任一来源整体失败时，脚本直接中止且不写文件，保留上一版本；
  `--limit` 调试模式也不做删除。
- **上游删除**：上游确实下架的规则集会被清理；下载失败的名字会保留旧文件。

## 5. 定时任务

| 项目 | 值 |
| --- | --- |
| 工作流 | [.github/workflows/sync-loon-rules.yml](../.github/workflows/sync-loon-rules.yml) |
| 频率 | `cron: "0 0 * * *"`（UTC）= 每天 **08:00（北京时间）** |
| 手动触发 | Actions → Sync Loon rules → Run workflow（可选 `dry_run`） |
| 提交方式 | `github-actions[bot]` 直接提交到当前分支，内容无变化则跳过 |
| 并发 | 同一组串行执行，不会两个任务同时写 |

选 08:00 的原因：来源一每天 07:30（北京时间）自动构建，08:00 抓取能拿到当天最新结果。

> GitHub 的定时任务在高峰期可能延迟数分钟到数十分钟；仓库连续 60 天无提交时，
> GitHub 会自动暂停 `schedule`，需要手动 Run 一次或提交一次以恢复。

### 手动 / 本地运行

```bash
# 只统计，不写文件
python scripts/sync.py --repo-root . --dry-run

# 完整生成
python scripts/sync.py --repo-root . --summary-out /tmp/sync.json

# 只处理前 3 个文件（调试）
python scripts/sync.py --repo-root . --limit 3
```

脚本只依赖 Python 3.10+ 标准库。`GITHUB_TOKEN` 可选，用于把 GitHub API 的限额从
60 次/小时提高到 5000 次/小时（Actions 中自动注入）。

需要换源或换目录时，改 `scripts/sync.py` 顶部的 `CONFIG`；本地联调可用环境变量覆盖地址：
`QX_TREE_API`、`QX_RAW_BASE`、`QX_README`、`SHUNT_README`、`SHUNT_BASE`、`BMX_RAW_BASE`。

## 6. 在 Loon 中使用

1. 打开 [Rules/INDEX.md](INDEX.md)，每个分类都有「一键导入」链接（Loon 通用链接）。
2. 也可以把 raw 地址直接加进「远程规则订阅」，例如：

   ```text
   https://raw.githubusercontent.com/moyuzaime/LoonRules/main/Rules/Unified/Apple.list
   ```

3. 规则文件只负责「匹配」，**策略在 Loon 的订阅项里单独指定**（直连 / 代理 / 拦截）。
4. 想用上游原始粒度：订阅 `Rules/QuixoticHeart/*.list` 或 `Rules/ShuntRules/*.lsr`；
   想要跨来源合并后的结果：订阅 `Rules/Unified/*.list`。

## 7. 许可与合规

- 来源一为 **GPL-3.0**，来源二的数据上游 blackmatrix7 为 **GPL-2.0**；本仓库若公开分发这些
  生成文件，应遵守相应许可证（保留来源与许可说明，并按 GPL 要求提供相应授权）。
  仓库根目录目前没有 LICENSE 文件，对外分发前建议补上（例如 GPL-3.0），或把本目录改为私有。
- 来源一 README 明确写着「禁止任何形式转载或发布至中国大陆地区」。把规则镜像到公开仓库
  属于再分发行为，请自行评估合规性；如不接受，可将仓库设为私有，或删除来源一相关内容。
- `Rules/` 全部为脚本生成，手工修改会在下次同步时被覆盖。

## 8. 排错

| 现象 | 原因与处理 |
| --- | --- |
| 日志出现 `直连不可用…改用 blackmatrix7` | `rule.kelee.one` 被 Cloudflare 拦截，属预期回退，不影响结果 |
| `来源二失败 N 个，超过 20%，中止` | 上游改名或网络异常；查看 `CONFLICTS.md` 的失败清单，修好后重跑 |
| 生成文件 0 条规则 | 上游文件只有注释或下载到错误页面；检查该文件名是否仍存在于上游 |
| 提交了但 Loon 不刷新 | Loon 对远程规则有缓存，手动在订阅项里下拉刷新 |
| Actions 报 `403` 推送失败 | 仓库 Settings → Actions → General 里把 Workflow permissions 设为 Read and write |
