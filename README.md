# LoonRules

面向 Loon 的自定义域名远程规则集仓库。

## 设计原则

- 只维护自定义域名规则，不默认捆绑大型第三方规则库。
- 规则文件使用 Loon 支持的规则语法。
- DNS 处理遵循 Loon 默认行为；不主动添加 DNS 服务器设置或 `no-resolve` 标记。
- 不把订阅 Token、私有配置、证书或密码提交到仓库。
- 每个规则集只负责匹配规则；在 Loon 的远程规则订阅项中选择对应策略。

## 目录

| 文件 | 用途 |
| --- | --- |
| [Custom/Direct.list](Custom/Direct.list) | 自定义直连域名 |
| [Custom/Proxy.list](Custom/Proxy.list) | 自定义代理域名 |
| [Custom/Reject.list](Custom/Reject.list) | 自定义拦截域名 |
| [Custom/ExactDomain.list](Custom/ExactDomain.list) | 精确域名匹配示例与模板 |

目前尚未添加有效域名条目。请将自己的域名加入相应文件，并删除或替换文件中的示例注释。

## 规则写法示例

```text
DOMAIN,api.example.com
DOMAIN-SUFFIX,example.com
```

- `DOMAIN`：只匹配指定的完整域名。
- `DOMAIN-SUFFIX`：匹配域名本身及其子域名。
- 上述域名仅为格式示例，不是已启用的规则。
- 不需要在规则文件中写入 DNS 服务器；在 Loon 远程规则订阅中按需要指定策略。

## 在 Loon 中订阅

在 Loon 的远程规则订阅中添加对应的 Raw 文件链接，并选择策略。例如：

```text
https://raw.githubusercontent.com/moyuzaime/LoonRules/main/Custom/Direct.list
```

其他文件路径依此类推。请使用 Loon 的远程规则订阅功能，并按当前 Loon 版本支持的格式配置策略。

## 维护约定

1. 每行一条规则，使用英文逗号分隔字段。
2. 域名规则优先使用 `DOMAIN` 或 `DOMAIN-SUFFIX`，避免不必要的关键词匹配。
3. 新增规则前确认域名归属及匹配范围，避免使用过宽的后缀。
4. 修改后先在 Loon 中更新订阅并检查请求记录，再作为稳定规则发布。
5. 本仓库中的规则应仅包含明确需要自定义的域名，不复制私人配置。

## 许可

规则内容由仓库维护者自行添加。引入第三方规则时，请保留来源、许可和版权说明。
