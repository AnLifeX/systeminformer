# 简体中文注入工具

本目录是 `zh-CN` 分支的确定性汉化层。上游 C、C++ 和资源文件不会长期保存生成后的中文改动；
CI 会在编译前应用汉化目录，编译结束后 runner 随即销毁。

当前目录覆盖主窗口、常用菜单和对话框、进程/服务/网络列，以及部分内置插件。
由于 System Informer 的可见文本分散在大量源文件中，汉化会根据实际测试逐步扩展。

## 文件说明

- `zh-CN.json`：汉化规则目录；
- `localize.py`：检查、注入和还原工具；
- `tests/`：脚本单元测试；
- `.gitignore`：忽略本地 Python 缓存等生成内容。

## 常用命令

在仓库根目录运行：

```powershell
# 确认所有规则仍能精确匹配上游原文
python tools/localization/localize.py check --state source

# 将简体中文文本注入工作区
python tools/localization/localize.py apply

# 确认所有规则均处于已汉化状态
python tools/localization/localize.py check --state translated

# 将生成的源码改动还原为上游原文
python tools/localization/localize.py revert

# 运行脚本测试
python -m unittest discover -s tools/localization/tests -v
```

`apply` 和 `revert` 都具有幂等性：重复执行不会重复修改。脚本会保留原文件是否含 UTF-8 BOM
以及原有换行符格式。

完成本地查看后务必执行 `revert`，不要把注入后生成的 C/RC 文件提交到 `zh-CN` 分支。

## 目录格式

`zh-CN.json` 中的普通规则包含：

- `id`：稳定且唯一的规则编号；
- `path`：相对于仓库根目录的文件路径；
- `context`：只包含一个 `{text}` 标记的精确上下文；
- `source`：上游原文；
- `translation`：简体中文译文；
- `expected`：可选，预期匹配次数，默认是 `1`。

示例：

```json
{
  "id": "main-tab.processes",
  "path": "SystemInformer/mainwnd.c",
  "context": "PhMwpCreateInternalPage(L\"{text}\", 0, PhMwpProcessesPageCallback);",
  "source": "Processes",
  "translation": "进程"
}
```

同一文件中使用相同字符串格式的多条规则可以放进 `groups`。组统一提供 `id`、`path` 和
`context`，每个 `items` 项只需要自己的 `id` 后缀、`source`、`translation` 和可选的
`expected`。加载后仍会展开为同样严格的精确匹配规则。

## 安全校验

脚本遇到以下情况会直接失败：

- 上游原文或上下文发生变化；
- 实际匹配次数与 `expected` 不同；
- printf 占位符发生增删；
- 大括号占位符、转义序列或 Win32 快捷键标记发生破坏；
- 两条规则生成相同的源文本片段或目标文本片段；
- 路径试图离开仓库，或目标不是 UTF-8 文本文件。

这样设计是为了让上游变化显式暴露，避免“尽力替换”误伤无关的程序逻辑。

## 添加汉化规则

1. 确认可见文本确实面向用户，不是内部协议值；
2. 使用尽量小、但足以唯一定位的 `context`；
3. 使用统一、准确的 Windows 专业术语；
4. 执行源状态检查、注入、已翻译状态检查和测试；
5. 实际打开 CI 产物检查截断、乱码、菜单快捷键和语义；
6. 完成后执行 `revert`，只提交目录与工具修改。

不要翻译 API 名称、命令行开关、文件路径、注册表名称、协议字段、持久化设置键或其他机器可读字符串。

## CI 构建条件

完整 Windows Release 构建只在以下情况运行：

- `zh-CN` 分支提交信息包含 `[build]`；
- 推送一个指向 `zh-CN` 提交的 Tag。

普通提交可能显示为 `skipped`，但不会占用 Windows runner 或上传 Artifact。Artifact 保留期为 1 天。

目前未实现自动同步上游、自动检查上游、自动创建 Tag 或自动修复漂移规则。上游同步完成后应先人工运行
`check --state source` 并完成适配，再决定是否触发构建。
