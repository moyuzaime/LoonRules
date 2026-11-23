# LoonRules

面向 Loon 的自定义域名远程规则集仓库。

## 设计原则

- 只维护自定义域名规则，不默认捆绑大型第三方规则库。
- 规则文件使用 Loon 支持的规则语法。
- DNS 处理遵循 Loon 默认行为；不主动添加 DNS 服务器设置或 `no-resolve` 标记。
- 不把订阅 Token、私有配置、证书或密码提交到仓库。
- 每个规则集只负责匹配规则；在 Loon 的远程规则订阅项中选择对应策略。

## 目录

| 文件 | 用途 | 一键导入 |
| --- | --- | --- |
| [Custom/Direct.list](Custom/Direct.list) | 自定义直连域名 | [一键导入](https://www.nsloon.com/openloon/import?rules=https%3A%2F%2Fraw.githubusercontent.com%2Fmoyuzaime%2FLoonRules%2Fmain%2FCustom%2FDirect.list) |
| [Custom/Proxy.list](Custom/Proxy.list) | 自定义代理域名 | [一键导入](https://www.nsloon.com/openloon/import?rules=https%3A%2F%2Fraw.githubusercontent.com%2Fmoyuzaime%2FLoonRules%2Fmain%2FCustom%2FProxy.list) |
| [Custom/Reject.list](Custom/Reject.list) | 自定义拦截域名 | [一键导入](https://www.nsloon.com/openloon/import?rules=https%3A%2F%2Fraw.githubusercontent.com%2Fmoyuzaime%2FLoonRules%2Fmain%2FCustom%2FReject.list) |
| [Custom/ExactDomain.list](Custom/ExactDomain.list) | 精确域名匹配示例与模板 | [一键导入](https://www.nsloon.com/openloon/import?rules=https%3A%2F%2Fraw.githubusercontent.com%2Fmoyuzaime%2FLoonRules%2Fmain%2FCustom%2FExactDomain.list) |
| [Custom/18comic.list](Custom/18comic.list) | 禁漫天堂：按域名关键字匹配 | [一键导入](https://www.nsloon.com/openloon/import?rules=https%3A%2F%2Fraw.githubusercontent.com%2Fmoyuzaime%2FLoonRules%2Fmain%2FCustom%2F18comic.list) |
| [Custom/Picacomic.list](Custom/Picacomic.list) | 哔咔：按域名关键字匹配 | [一键导入](https://www.nsloon.com/openloon/import?rules=https%3A%2F%2Fraw.githubusercontent.com%2Fmoyuzaime%2FLoonRules%2Fmain%2FCustom%2FPicacomic.list) |
| [Custom/Baozimh.list](Custom/Baozimh.list) | 包子漫画：精确域名匹配 | [一键导入](https://www.nsloon.com/openloon/import?rules=https%3A%2F%2Fraw.githubusercontent.com%2Fmoyuzaime%2FLoonRules%2Fmain%2FCustom%2FBaozimh.list) |
| [Custom/Hotmanga.list](Custom/Hotmanga.list) | 热辣漫画：精确域名匹配 | [一键导入](https://www.nsloon.com/openloon/import?rules=https%3A%2F%2Fraw.githubusercontent.com%2Fmoyuzaime%2FLoonRules%2Fmain%2FCustom%2FHotmanga.list) |
| [Custom/Mangacopy.list](Custom/Mangacopy.list) | 拷贝漫画：精确域名匹配 | [一键导入](https://www.nsloon.com/openloon/import?rules=https%3A%2F%2Fraw.githubusercontent.com%2Fmoyuzaime%2FLoonRules%2Fmain%2FCustom%2FMangacopy.list) |
| [Plugins/AdBlock/huangguo-ad.plugin](Plugins/AdBlock/huangguo-ad.plugin) | 黄果与2048AI去广告插件 | [一键导入](https://www.nsloon.com/openloon/import?plugin=https%3A%2F%2Fraw.githubusercontent.com%2Fmoyuzaime%2FLoonRules%2Fmain%2FPlugins%2FAdBlock%2Fhuangguo-ad.plugin) |

已添加 `Custom/18comic.list`，使用 `DOMAIN-KEYWORD,18comic` 匹配包含 `18comic` 的域名；`Custom/Picacomic.list` 使用 `DOMAIN-KEYWORD,picacomic` 和 `DOMAIN-KEYWORD,picaapi` 匹配哔咔相关域名关键字；`Custom/Baozimh.list` 使用 `DOMAIN` 精确匹配包子漫画相关域名（baozimh / webmota / kukuc / twmanga / dinnerku 等，共 20 条）；`Custom/Hotmanga.list` 使用 `DOMAIN-SUFFIX` 与 `DOMAIN` 匹配热辣漫画相关域名（hotmanga / elfgjfghkk / fgjfghkk 系列用后缀匹配覆盖裸域与 mapi 子域，manga2025 等用精确匹配，共 12 条）；`Custom/Mangacopy.list` 使用 `DOMAIN` 精确匹配拷贝漫画相关域名（mangacopy / copy20 / copy3000 / 2026copy 等，共 13 条）。其余模板中的示例仍处于注释状态。

## 规则写法示例

```text
DOMAIN,api.example.com
DOMAIN-SUFFIX,example.com
```

- `DOMAIN`：只匹配指定的完整域名。
- `DOMAIN-SUFFIX`：匹配域名本身及其子域名。
- `DOMAIN-KEYWORD`：匹配域名中包含指定关键字的请求，匹配范围比精确域名更广。
- 上述域名仅为格式示例，不是已启用的规则。
- 不需要在规则文件中写入 DNS 服务器；在 Loon 远程规则订阅中按需要指定策略。

## 在 Loon 中订阅

在 Loon 的远程规则订阅中添加对应的 Raw 文件链接，并选择策略。例如：

```text
https://raw.githubusercontent.com/moyuzaime/LoonRules/main/Custom/Direct.list
```

其他文件路径依此类推。请使用 Loon 的远程规则订阅功能，并按当前 Loon 版本支持的格式配置策略。

## 一键导入 Loon

目录表中的「一键导入」链接使用 Loon 官方通用链接（Universal Link），在网页上可直接点击，并在装有 Loon 的 iOS 设备上唤起 Loon 进入导入流程：

- 规则订阅：`https://www.nsloon.com/openloon/import?rules=<urlencode(规则文件URL)>`（URL 需百分号编码，如 `:` → `%3A`、`/` → `%2F`）
- 插件：`https://www.nsloon.com/openloon/import?plugin=<urlencode(插件URL)>`

> 通用链接等价于自定义 Scheme `loon://import?…`（`loon://` 会被 GitHub 安全过滤而无法在网页上点击，故统一改用通用链接）。Loon 只能按「文件 / 订阅」导入，无法直接导入单条规则行；导入后策略仍在远程规则订阅项中单独指定。

## 维护约定

1. 每行一条规则，使用英文逗号分隔字段。
2. 域名规则优先使用 `DOMAIN` 或 `DOMAIN-SUFFIX`，避免不必要的关键词匹配。
3. 新增规则前确认域名归属及匹配范围，避免使用过宽的后缀。
4. 修改后先在 Loon 中更新订阅并检查请求记录，再作为稳定规则发布。
5. 本仓库中的规则应仅包含明确需要自定义的域名，不复制私人配置。

## 许可

规则内容由仓库维护者自行添加。引入第三方规则时，请保留来源、许可和版权说明。
