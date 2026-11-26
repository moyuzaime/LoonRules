# 冲突与去重报告

> 本文件由 `scripts/sync.py` 自动生成，请勿手工编辑。

## 统计

| 项目 | 数量 |
| --- | ---: |
| 来源一文件内去重 | 0 |
| 来源二文件内去重 | 0 |
| 来源一无法解析的行 | 0 |
| 来源二无法解析的行 | 0 |
| 统一库跨来源重复（保留来源一） | 12155 |
| 统一库跨来源类型冲突 | 4 |
| 来源一下载失败文件 | 0 |
| 来源二缺失分类 | 1 |

## 类型冲突

同一域名在两个来源中使用不同规则类型。统一库保留来源一（QuixoticHeart）写法，另一写法不再重复收录；如需以来源二为准，请修改 `scripts/sync.py` 中 `CONFIG['unified']['priority']` 的顺序。

| 分类 | 域名 | 类型 | 明细 |
| --- | --- | --- | --- |
| bahamut | `bahamut.akamaized.net` | DOMAIN / DOMAIN-SUFFIX | DOMAIN-SUFFIX(quixoticheart); DOMAIN(blackmatrix7) |
| netflix | `netflix.com.edgesuite.net` | DOMAIN / DOMAIN-SUFFIX | DOMAIN-SUFFIX(quixoticheart); DOMAIN(blackmatrix7) |
| spotify | `spotify.com.edgesuite.net` | DOMAIN / DOMAIN-SUFFIX | DOMAIN-SUFFIX(quixoticheart); DOMAIN(blackmatrix7) |
| tiktok | `p16-tiktokcdn-com.akamaized.net` | DOMAIN / DOMAIN-SUFFIX | DOMAIN-SUFFIX(quixoticheart); DOMAIN(blackmatrix7) |

## 来源二缺失分类

以下分类在 rule/Loon 下存在，但三个 .list 都未取到（已保留上一版本文件）：

- `Cloud`
