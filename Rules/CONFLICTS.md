# 冲突与去重报告

> 本文件由 `scripts/sync.py` 自动生成，请勿手工编辑。

## 统计

| 项目 | 数量 |
| --- | ---: |
| 来源一文件内去重 | 0 |
| 来源二文件内去重 | 8738 |
| 来源一无法解析的行 | 0 |
| 来源二无法解析的行 | 0 |
| 统一库跨来源重复（保留来源一） | 12155 |
| 统一库跨来源类型冲突 | 4 |
| 来源一下载失败文件 | 0 |
| 来源二下载失败文件 | 2 |

## 类型冲突

同一域名在两个来源中使用不同规则类型。统一库保留来源一（QuixoticHeart）写法，另一写法不再重复收录；如需以来源二为准，请修改 `scripts/sync.py` 中 `CONFIG['unified']['priority']` 的顺序。

| 分类 | 域名 | 类型 | 明细 |
| --- | --- | --- | --- |
| bahamut | `bahamut.akamaized.net` | DOMAIN / DOMAIN-SUFFIX | DOMAIN-SUFFIX(quixoticheart); DOMAIN(shuntrules) |
| netflix | `netflix.com.edgesuite.net` | DOMAIN / DOMAIN-SUFFIX | DOMAIN-SUFFIX(quixoticheart); DOMAIN(shuntrules) |
| spotify | `spotify.com.edgesuite.net` | DOMAIN / DOMAIN-SUFFIX | DOMAIN-SUFFIX(quixoticheart); DOMAIN(shuntrules) |
| tiktok | `p16-tiktokcdn-com.akamaized.net` | DOMAIN / DOMAIN-SUFFIX | DOMAIN-SUFFIX(quixoticheart); DOMAIN(shuntrules) |

## 来源二下载失败

以下规则集在直连与 blackmatrix7 回退中均未取到，已保留上一版本文件：

- `ChinaIPs_No_IPv6`
- `ChinaMax_No_IPv6`
