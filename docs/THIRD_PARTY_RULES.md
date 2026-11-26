# 第三方 Loon 规则：镜像、统一库与自动同步

本仓库除了 `Custom/` 下自维护的规则外，还把两个第三方规则来源中的 **Loon 规则**镜像进来，
并在同名分类上合并成一套「统一规则库」。全部内容由 GitHub Actions 每天自动更新，
只有内容变化时才会产生提交。

## 1. 数据来源

| 简称 | 上游 | 取用范围 | 许可 |
| --- | --- | --- | --- |
| 来源一 | [QuixoticHeart/rule-set](https://github.com/QuixoticHeart/rule-set/tree/ruleset) | `ruleset` 分支 `loon/` 目录，约 52 个 `.list` | GPL-3.0 |
| 来源二 | [blackmatrix7/ios_rule_script](https://github.com/blackmatrix7/ios_rule_script/tree/master/rule/Loon) | `master` 分支 `rule/Loon/` 下 668 个分类目录中的 `.list` 文件 | GPL-2.0 |

只提取 Loon 规则：来源一里 Surge / Clash / Shadowrocket / Quantumult X / Egern / sing-box 等
目录一律忽略；来源二只取 `rule/Loon/`（其他工具的 `rule/` 子目录不处理）。

## 2. 目录结构

```text
Rules/
├── QuixoticHeart/                    # 来源一镜像，保留上游文件名
│   └── abema.list
├── blackmatrix7/                     # 来源二镜像，保留上游目录与文件名
│   └── Apple/
│       ├── Apple.list                # 规则（DOMAIN-KEYWORD / USER-AGENT / IP-CIDR 等）
│       ├── Apple_Domain.list         # 域名列表（.example.com = 后缀，example.com = 精确）
│       └── Apple_Resolve.list        # 与 Apple.list 相同，但 IP 规则不带 no-resolve
├── Unified/                          # 统一规则库：同名分类合并去重，来源一优先
│   ├── abema.list
│   └── Apple.list
├── INDEX.md                          # 自动生成的索引 + 一键导入链接
├── CONFLICTS.md                      # 去重统计、跨来源类型冲突、失败清单
└── .sync-manifest.json               # 机器可读清单（路径/条数/字节/sha256/上游地址）
```

命名规则：

- 镜像目录严格沿用上游目录与文件名，方便和上游对照、便于 `git diff` 溯源。
- 统一库按「分类」出文件；分类名归一化后（忽略大小写与标点）相同的规则集会合并，
  例如来源一的 `apple` 与来源二的 `Apple` 合并为 `Rules/Unified/apple.list`。
- 每个生成文件顶部有静态注释头（来源、上游地址、规则数），**不含时间戳**，
  所以规则没变时文件字节不变，不会产生空提交。

## 3. 抓取与归一化

```text
来源一：GitHub API 读取 ruleset 分支 loon/ 文件树
        └─ API 失败 → 解析 ruleset 分支 README 里的 loon 链接
        └─ 逐个 raw 下载

来源二：GitHub API 读取 rule/Loon/ 下的分类目录
        └─ API 失败 → 解析 rule/Loon/README.md 里的分类链接
        └─ 每个分类固定尝试三个文件（404 视为不存在）：
              <Category>.list
              <Category>_Domain.list
              <Category>_Resolve.list
```

镜像与统一库对 `_Domain.list` 的处理不同，这是刻意的：

- **镜像**（`Rules/blackmatrix7/Apple/Apple_Domain.list`）保留原始写法（`.example.com`），
  它本身就是 Loon 的 DOMAIN-SET 资源，可直接单独订阅；
- **统一库**把 `.example.com` 转成 `DOMAIN-SUFFIX,example.com`、裸域转成 `DOMAIN,example.com`，
  再按 `<Category>.list` → `_Domain.list` → `_Resolve.list` 的顺序合并去重。

## 4. 去重、冲突与保护

- **文件内**：完全相同的 `(规则类型, 值, 参数)` 只保留第一次出现，顺序不变；
  域名列表文件按整行去重。
- **统一库**：先来源一、后来源二逐条合入；重复项保留来源一
  （`CONFIG['unified']['priority']` 可调整）。
- **类型冲突**：同一域名在两个来源里类型不同（如 `DOMAIN` 与 `DOMAIN-SUFFIX`）时，
  统一库保留来源一的写法，并把冲突写入 `Rules/CONFLICTS.md`。
- **防误删**：分类整体失败（三个文件都取不到或网络错误）、或失败超过 20% 时，
  脚本中止且不写文件；`--limit` 调试模式也不做删除。
- **上游删除**：上游确实下架的规则集/分类会被清理；失败的名字会保留旧文件。

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

# 只处理前 3 个文件/分类（调试）
python scripts/sync.py --repo-root . --limit 3
```

脚本只依赖 Python 3.10+ 标准库。`GITHUB_TOKEN` 可选，用于把 GitHub API 的限额从
60 次/小时提高到 5000 次/小时（Actions 中自动注入）。

需要换源或换目录时，改 `scripts/sync.py` 顶部的 `CONFIG`；本地联调可用环境变量覆盖地址：
`QX_TREE_API`、`QX_RAW_BASE`、`QX_README`、`BMX_LISTING_API`、`BMX_RAW_BASE`、`BMX_README`。

## 6. 在 Loon 中使用

1. 打开 [Rules/INDEX.md](INDEX.md)，每个分类都有「一键导入」链接（Loon 通用链接）。
2. 也可以把 raw 地址直接加进「远程规则订阅」，例如：

   ```text
   https://raw.githubusercontent.com/moyuzaime/LoonRules/main/Rules/Unified/Apple.list
   ```

3. 规则文件只负责「匹配」，**策略在 Loon 的订阅项里单独指定**（直连 / 代理 / 拦截）。
4. 想用上游原始粒度：

   ```text
   Rules/QuixoticHeart/<name>.list
   Rules/blackmatrix7/<Category>/<Category>.list
   Rules/blackmatrix7/<Category>/<Category>_Domain.list
   ```

   按 blackmatrix7 的建议，`<Category>.list` 与 `<Category>_Domain.list` 一起使用；
   想要合并结果则直接用 `Rules/Unified/<name>.list`。

## 7. 许可与合规

- 来源一为 **GPL-3.0**，来源二为 **GPL-2.0**；本仓库若公开分发这些生成文件，应遵守相应
  许可证（保留来源与许可说明，并按 GPL 要求提供相应授权）。仓库根目录目前没有 LICENSE
  文件，对外分发前建议补上（例如 GPL-3.0），或把本仓库设为私有。
- 来源一 README 明确写着「禁止任何形式转载或发布至中国大陆地区」。把规则镜像到公开仓库
  属于再分发行为，请自行评估合规性；如不接受，可将仓库设为私有，或从
  `scripts/sync.py` 的 `CONFIG` 中移除来源一。
- `Rules/` 全部为脚本生成，手工修改会在下次同步时被覆盖。

## 8. 排错

| 现象 | 原因与处理 |
| --- | --- |
| 生成文件 0 条规则 | 上游文件只有注释或下载到错误页面；检查该分类是否仍存在于上游 |
| `blackmatrix7 缺失 N 个分类` | 三个 `.list` 都取不到（网络或上游改名）；查看 `CONFLICTS.md` 的清单，修好后重跑 |
| 提交了但 Loon 不刷新 | Loon 对远程规则有缓存，手动在订阅项里下拉刷新 |
| Actions 报 `403` 推送失败 | 仓库 Settings → Actions → General 里把 Workflow permissions 设为 Read and write |
| 定时任务没跑 | 检查 Actions 是否被暂停（仓库 60 天无提交会自动暂停），手动 Run 一次 |
