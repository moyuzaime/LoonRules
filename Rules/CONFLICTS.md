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
| 统一库跨来源类型冲突 | 35 |
| 来源一下载失败文件 | 0 |
| 来源二下载失败文件 | 2 |

## 类型冲突

同一域名在两个来源中使用不同规则类型。统一库保留来源一（QuixoticHeart）写法，另一写法不再重复收录；如需以来源二为准，请修改 `scripts/sync.py` 中 `CONFIG['unified']['priority']` 的顺序。

| 分类 | 域名 | 类型 | 明细 |
| --- | --- | --- | --- |
| adrules | `trace.qq.com` | DOMAIN-KEYWORD / DOMAIN-SUFFIX | DOMAIN-SUFFIX(quixoticheart); DOMAIN-KEYWORD(quixoticheart) |
| ai | `alkalimakersuite-pa.clients6.google.com` | DOMAIN / DOMAIN-KEYWORD | DOMAIN(quixoticheart); DOMAIN-KEYWORD(quixoticheart) |
| ai | `labs.google` | DOMAIN-KEYWORD / DOMAIN-SUFFIX | DOMAIN-SUFFIX(quixoticheart); DOMAIN-KEYWORD(quixoticheart) |
| ai | `notebooklm.google` | DOMAIN-KEYWORD / DOMAIN-SUFFIX | DOMAIN-SUFFIX(quixoticheart); DOMAIN-KEYWORD(quixoticheart) |
| apple | `com.apple.maps` | PROCESS-NAME / USER-AGENT | PROCESS-NAME(quixoticheart); USER-AGENT(shuntrules) |
| bahamut | `bahamut.akamaized.net` | DOMAIN / DOMAIN-SUFFIX | DOMAIN-SUFFIX(quixoticheart); DOMAIN(shuntrules) |
| cdn | `cdn.trustpilot.net` | DOMAIN / DOMAIN-KEYWORD | DOMAIN(quixoticheart); DOMAIN-KEYWORD(quixoticheart) |
| cdn | `static.grammarly.com` | DOMAIN / DOMAIN-KEYWORD | DOMAIN(quixoticheart); DOMAIN-KEYWORD(quixoticheart) |
| dmca | `aria2` | DOMAIN-KEYWORD / PROCESS-NAME | DOMAIN-KEYWORD(quixoticheart); PROCESS-NAME(quixoticheart) |
| dmca | `thunder` | DOMAIN-KEYWORD / PROCESS-NAME | DOMAIN-KEYWORD(quixoticheart); PROCESS-NAME(quixoticheart) |
| google | `gmail` | DOMAIN-KEYWORD / DOMAIN-SUFFIX | DOMAIN-SUFFIX(quixoticheart); DOMAIN-KEYWORD(quixoticheart) |
| google | `google` | DOMAIN-KEYWORD / DOMAIN-SUFFIX | DOMAIN-SUFFIX(quixoticheart); DOMAIN-KEYWORD(quixoticheart) |
| microsoft | `microsoft` | DOMAIN-KEYWORD / DOMAIN-SUFFIX | DOMAIN-SUFFIX(quixoticheart); DOMAIN-KEYWORD(quixoticheart) |
| microsoft | `onedrive` | DOMAIN-KEYWORD / DOMAIN-SUFFIX / PROCESS-NAME | DOMAIN-SUFFIX(quixoticheart); DOMAIN-KEYWORD(quixoticheart); PROCESS-NAME(quixoticheart) |
| microsoft | `onedriveupdater` | DOMAIN-SUFFIX / PROCESS-NAME | DOMAIN-SUFFIX(quixoticheart); PROCESS-NAME(quixoticheart) |
| netflix | `netflix.com.edgesuite.net` | DOMAIN / DOMAIN-SUFFIX | DOMAIN-SUFFIX(quixoticheart); DOMAIN(shuntrules) |
| onedrive | `onedrive` | DOMAIN-KEYWORD / DOMAIN-SUFFIX / PROCESS-NAME | DOMAIN-SUFFIX(quixoticheart); DOMAIN-KEYWORD(quixoticheart); PROCESS-NAME(quixoticheart) |
| onedrive | `onedriveupdater` | DOMAIN-SUFFIX / PROCESS-NAME | DOMAIN-SUFFIX(quixoticheart); PROCESS-NAME(quixoticheart) |
| proxy | `musical.ly` | DOMAIN-KEYWORD / DOMAIN-SUFFIX | DOMAIN-SUFFIX(quixoticheart); DOMAIN-KEYWORD(quixoticheart) |
| socialmedia-cn | `weibo` | DOMAIN-KEYWORD / DOMAIN-SUFFIX | DOMAIN-SUFFIX(quixoticheart); DOMAIN-KEYWORD(quixoticheart) |
| spotify | `spotify.com.edgesuite.net` | DOMAIN / DOMAIN-SUFFIX | DOMAIN-SUFFIX(quixoticheart); DOMAIN(shuntrules) |
| tiktok | `musical.ly` | DOMAIN-KEYWORD / DOMAIN-SUFFIX | DOMAIN-SUFFIX(quixoticheart); DOMAIN-KEYWORD(quixoticheart) |
| tiktok | `p16-tiktokcdn-com.akamaized.net` | DOMAIN / DOMAIN-SUFFIX | DOMAIN-SUFFIX(quixoticheart); DOMAIN(shuntrules) |
| youtube | `youtube` | DOMAIN-KEYWORD / DOMAIN-SUFFIX | DOMAIN-SUFFIX(quixoticheart); DOMAIN-KEYWORD(quixoticheart) |
| AbemaTV | `abematv.akamaized.net` | DOMAIN-KEYWORD / DOMAIN-SUFFIX | DOMAIN-SUFFIX(shuntrules); DOMAIN-KEYWORD(shuntrules) |
| ChinaMax | `alipay` | DOMAIN-KEYWORD / DOMAIN-SUFFIX | DOMAIN-SUFFIX(shuntrules); DOMAIN-KEYWORD(shuntrules) |
| ChinaMax | `baidu` | DOMAIN-KEYWORD / DOMAIN-SUFFIX | DOMAIN-SUFFIX(shuntrules); DOMAIN-KEYWORD(shuntrules) |
| ChinaMax | `taobao` | DOMAIN-KEYWORD / DOMAIN-SUFFIX | DOMAIN-SUFFIX(shuntrules); DOMAIN-KEYWORD(shuntrules) |
| ChinaMax | `weibo` | DOMAIN-KEYWORD / DOMAIN-SUFFIX | DOMAIN-SUFFIX(shuntrules); DOMAIN-KEYWORD(shuntrules) |
| ChinaTest | `alipay` | DOMAIN-KEYWORD / DOMAIN-SUFFIX | DOMAIN-SUFFIX(shuntrules); DOMAIN-KEYWORD(shuntrules) |
| ChinaTest | `baidu` | DOMAIN-KEYWORD / DOMAIN-SUFFIX | DOMAIN-SUFFIX(shuntrules); DOMAIN-KEYWORD(shuntrules) |
| ChinaTest | `taobao` | DOMAIN-KEYWORD / DOMAIN-SUFFIX | DOMAIN-SUFFIX(shuntrules); DOMAIN-KEYWORD(shuntrules) |
| Emby | `emby.wtf` | DOMAIN-KEYWORD / DOMAIN-SUFFIX | DOMAIN-SUFFIX(shuntrules); DOMAIN-KEYWORD(shuntrules) |
| Global | `musical.ly` | DOMAIN-KEYWORD / DOMAIN-SUFFIX | DOMAIN-KEYWORD(shuntrules); DOMAIN-SUFFIX(shuntrules) |
| GlobalMedia | `youtube` | DOMAIN-KEYWORD / DOMAIN-SUFFIX | DOMAIN-SUFFIX(shuntrules); DOMAIN-KEYWORD(shuntrules) |

## 来源二下载失败

以下规则集在直连与 blackmatrix7 回退中均未取到，已保留上一版本文件：

- `ChinaIPs_No_IPv6`
- `ChinaMax_No_IPv6`
