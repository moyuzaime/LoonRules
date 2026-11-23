# LoonRules 规则梳理说明

> 仓库：`moyuzaime/LoonRules` — 面向 Loon 的自定义域名远程规则集仓库。
> 核心定位：**只维护自定义域名规则**，不捆绑大型第三方规则库，也不包含任何订阅 Token / 私有配置 / 证书 / 密码。

## 1. 目录结构

```
LoonRules/
├── README.md                      # 使用说明与维护约定
├── Custom/                        # 远程规则集（.list）
│   ├── 18comic.list               # 禁漫天堂（已启用）
│   ├── Picacomic.list             # 哔咔（已启用）
│   ├── Baozimh.list               # 包子漫画（已启用）
│   ├── Hotmanga.list              # 热辣漫画（已启用）
│   ├── Direct.list                # 直连模板（注释状态）
│   ├── Proxy.list                 # 代理模板（注释状态）
│   ├── Reject.list                # 拦截模板（注释状态）
│   └── ExactDomain.list           # 精确匹配模板（注释状态）
└── Plugins/AdBlock/               # 去广告插件
    ├── huangguo-ad.plugin         # 插件主配置
    ├── huangguo-response.js       # 黄果网页去广告脚本
    └── 2048ai-request.js          # 2048AI 接口去广告脚本
```

## 2. 已启用的规则（共 4 个文件、32 条规则）

| 文件 | 用途 | 实际生效规则 | Loon 一键导入 |
| --- | --- | --- | --- |
| `Custom/18comic.list` | 禁漫天堂，按域名关键字匹配 | `DOMAIN-KEYWORD,18comic` | [一键导入](https://www.nsloon.com/openloon/import?rules=https%3A%2F%2Fraw.githubusercontent.com%2Fmoyuzaime%2FLoonRules%2Fmain%2FCustom%2F18comic.list) |
| `Custom/Picacomic.list` | 哔咔，按域名关键字匹配 | `DOMAIN-KEYWORD,picacomic`<br>`DOMAIN-KEYWORD,picaapi` | [一键导入](https://www.nsloon.com/openloon/import?rules=https%3A%2F%2Fraw.githubusercontent.com%2Fmoyuzaime%2FLoonRules%2Fmain%2FCustom%2FPicacomic.list) |
| `Custom/Baozimh.list` | 包子漫画，精确域名匹配 | 共 20 条 `DOMAIN` 精确匹配（baozimh / webmota / kukuc / twmanga / dinnerku / twbzmg 等，详见文件） | [一键导入](https://www.nsloon.com/openloon/import?rules=https%3A%2F%2Fraw.githubusercontent.com%2Fmoyuzaime%2FLoonRules%2Fmain%2FCustom%2FBaozimh.list) |
| `Custom/Hotmanga.list` | 热辣漫画，精确域名匹配 | 共 9 条 `DOMAIN` 精确匹配（hotmanga 系列、elfgjfghkk、fgjfghkkcenter、2024manga、relamanhua、manga2024） | [一键导入](https://www.nsloon.com/openloon/import?rules=https%3A%2F%2Fraw.githubusercontent.com%2Fmoyuzaime%2FLoonRules%2Fmain%2FCustom%2FHotmanga.list) |

要点：
- 前两个文件使用 `DOMAIN-KEYWORD`，匹配范围更广（只要域名里含该关键字就命中）。
- 包子漫画、热辣漫画使用 `DOMAIN` 精确匹配，避免误伤其他子域。

## 3. 模板文件（4 个，均为注释状态、不执行）

这些文件只有以 `#` 开头的示例行，作用是提供复制粘贴自定义域名的骨架：

| 文件 | 用途 | 建议写法 | Loon 一键导入 |
| --- | --- | --- | --- |
| `Custom/Direct.list` | 指定域名走直连 | `DOMAIN,api.example.com` / `DOMAIN-SUFFIX,example.com` | [一键导入](https://www.nsloon.com/openloon/import?rules=https%3A%2F%2Fraw.githubusercontent.com%2Fmoyuzaime%2FLoonRules%2Fmain%2FCustom%2FDirect.list) |
| `Custom/Proxy.list` | 指定域名走代理策略 | 同上 | [一键导入](https://www.nsloon.com/openloon/import?rules=https%3A%2F%2Fraw.githubusercontent.com%2Fmoyuzaime%2FLoonRules%2Fmain%2FCustom%2FProxy.list) |
| `Custom/Reject.list` | 拦截指定域名 | `DOMAIN,ads.example.com` 等（谨慎，避免误拦登录/支付/更新） | [一键导入](https://www.nsloon.com/openloon/import?rules=https%3A%2F%2Fraw.githubusercontent.com%2Fmoyuzaime%2FLoonRules%2Fmain%2FCustom%2FReject.list) |
| `Custom/ExactDomain.list` | 精确匹配（不匹配子域） | 只写 `DOMAIN,...`，不用 `DOMAIN-SUFFIX` | [一键导入](https://www.nsloon.com/openloon/import?rules=https%3A%2F%2Fraw.githubusercontent.com%2Fmoyuzaime%2FLoonRules%2Fmain%2FCustom%2FExactDomain.list) |

## 4. 规则语法（README 约定）

- `DOMAIN` — 只匹配完整域名，**不**匹配其子域。
- `DOMAIN-SUFFIX` — 匹配域名本身及所有子域。
- `DOMAIN-KEYWORD` — 匹配域名中包含该关键字的请求，范围最广。
- 每行一条规则，字段用**英文逗号**分隔；`#` 开头的行不执行。
- 规则文件里**不写 DNS 服务器、不加 `no-resolve`**，DNS 走 Loon 默认行为。

## 5. 去广告插件（`Plugins/AdBlock/`）

插件名：**黄果与2048AI去广告**，作者 moyuzaime，要求 Loon ≥ 3.5.1(983)。

[一键导入插件](https://www.nsloon.com/openloon/import?plugin=https%3A%2F%2Fraw.githubusercontent.com%2Fmoyuzaime%2FLoonRules%2Fmain%2FPlugins%2FAdBlock%2Fhuangguo-ad.plugin)

### huangguo-ad.plugin

| 脚本规则 | 触发条件 | 作用 |
| --- | --- | --- |
| `huangguo-response.js`（response） | URL 匹配 `huangguo.video` 且响应为 HTML | 注入 CSS 隐藏广告位 |
| `huangguo-response.js`（response） | URL 匹配 `huangguoai.com` 且响应为 HTML | 注入 CSS 隐藏广告位 |
| `2048ai-request.js`（request） | URL 匹配 `2048ai.vip/api/v1/ads` 或 `ai-selection/config?productId=1&device=h5` | 直接返回空 JSON，拦截广告接口 |

MITM 需要的域名：`huangguo.video`、`huangguoai.com`、`2048ai.vip`。

### huangguo-response.js

按请求域名注入不同的 CSS 选择器：

- 黄果视频：隐藏 `div.hg-exo-slot`、`div.hg-exo-slot-list`、`.hg-tile-slot-list`
- 黄果AI：隐藏 `.hg-hero`、`.hg-ssp-slot`、`.hg-ssp-pause`

### 2048ai-request.js

对命中接口返回 `HTTP 200` + `Content-Type: application/json` + `Cache-Control: no-store` + 空 body `{}`。

## 6. 在 Loon 中的使用方式

1. 在 Loon「远程规则订阅」里添加 Raw 链接，例如：

   ```text
   https://raw.githubusercontent.com/moyuzaime/LoonRules/main/Custom/Direct.list
   ```

2. 每个规则集只负责「匹配」，**策略在选择订阅项时指定**（直连 / 代理 / 拦截等）。
3. 插件在 Loon「插件」中添加 `huangguo-ad.plugin` 的 Raw 链接。

> 一键导入链接说明：上表中的「一键导入」使用 Loon 官方通用链接（Universal Link）
> `https://www.nsloon.com/openloon/import?rules=<URL编码后的规则文件地址>`（插件为 `.../import?plugin=...`），
> 在网页上可直接点击，并在装有 Loon 的 iOS 设备上唤起 Loon 导入对应的**规则订阅文件**。
> 自定义 Scheme `loon://` 会被 GitHub 安全过滤而无法点击，故统一改用通用链接。Loon 只能按「文件 / 订阅」导入，
> 无法直接导入单条规则行；如需新增单条规则，请先写入对应的 `.list` 文件，再用上表链接导入。

## 7. 维护约定要点（README）

1. 每行一条规则，英文逗号分隔字段。
2. 优先 `DOMAIN` / `DOMAIN-SUFFIX`，避免过宽的关键词匹配。
3. 新增规则前先确认域名归属与匹配范围。
4. 修改后先在 Loon 更新订阅并核对请求记录再发布。
5. 引入第三方规则需保留来源、许可与版权说明。
