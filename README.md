<p align="center">
    <img src="SystemInformer/resources/systeminformer-128x128.png" alt="System Informer" width="128" height="128">
</p>

<h1 align="center">System Informer 简体中文构建</h1>

<p align="center">
    基于官方 System Informer 源码，通过可验证的自动化脚本注入简体中文文本并由 GitHub Actions 编译。
</p>

<p align="center">
    <a href="https://github.com/Gaq152/systeminformer/actions/workflows/localization-zh-cn.yml"><img src="https://img.shields.io/github/actions/workflow/status/Gaq152/systeminformer/localization-zh-cn.yml?branch=zh-CN&style=for-the-badge&label=zh-CN%20build" alt="zh-CN build"></a>
    <a href="LICENSE.txt"><img src="https://img.shields.io/badge/license-MIT-blue.svg?style=for-the-badge" alt="MIT License"></a>
</p>

> [!IMPORTANT]
> 这是非官方汉化分支，与 System Informer 官方团队无关。程序核心代码、驱动和插件来自
> [官方仓库](https://github.com/winsiderss/systeminformer)；本分支主要维护汉化目录、注入脚本和中文构建流程。

## 当前状态

- 维护分支：`zh-CN`；`master` 用于跟随官方上游。
- 当前已覆盖主窗口、常用菜单和对话框、进程/服务/网络列，以及部分内置插件。
- 汉化仍未覆盖全部深层页面，后续会根据实测逐步补充。
- CI 产物是未签名的 x64 便携版，不是安装程序；Windows SmartScreen 可能提示未知发布者。
- GitHub Actions Artifact 只保留 1 天，避免占用免费账户存储空间。

## 下载和安全测试

在仓库的 [Actions 页面](https://github.com/Gaq152/systeminformer/actions/workflows/localization-zh-cn.yml)
打开最近一次成功的 `zh-CN build`，下载页面底部的 x64 Artifact 并完整解压。

首次仅检查界面时，建议先退出其他 System Informer 实例，然后在解压目录运行：

```powershell
.\SystemInformer.exe -newinstance -nosettings -nokph -noplugins
```

- `-newinstance`：单独启动新实例。
- `-nosettings`：不读取或写入已安装版本的用户配置。
- `-nokph`：不加载 `KSystemInformer` 内核驱动。
- `-noplugins`：不加载插件，避免首次弹出在线文件信誉分析提示。

确认基本界面正常后，可以按需去掉 `-noplugins` 测试插件。不要直接用 CI 便携版覆盖正式安装目录。

## 构建触发规则

普通提交到 `zh-CN` 不再执行完整编译。只有以下情况会构建并上传 Artifact：

1. 提交信息包含区分大小写的 `[build]`；
2. 向 GitHub 推送一个指向 `zh-CN` 提交的 Tag。

示例：

```powershell
git commit -m "feat: update translations [build]"
git push origin zh-CN
```

或者使用 Tag：

```powershell
git tag zh-cn-v0.1.0
git push origin zh-cn-v0.1.0
```

由于 GitHub Actions 不能在 `on.push` 中按提交信息过滤，普通 `zh-CN` 推送可能留下一个
`skipped` 工作流记录，但不会分配 Windows runner、不会编译，也不会上传 Artifact。

目前尚未启用自动同步上游、自动检查上游、自动创建 Tag 或自动适配汉化规则；待汉化目录稳定后再增加。

## 汉化实现

汉化不是直接长期修改上游 C/RC 文件。CI 在编译前读取
[`tools/localization/zh-CN.json`](tools/localization/zh-CN.json)，按文件、上下文、原文和预期出现次数进行精确替换。
只要上游改动导致上下文漂移，脚本就会停止，而不是猜测替换到其他位置。

脚本用法和目录规则见 [`tools/localization/README.md`](tools/localization/README.md)。

## 卸载与恢复 Windows 任务管理器

### 本仓库的 CI 便携版

它没有执行安装，不会自行注册卸载项。卸载步骤如下：

1. 在 System Informer 中选择“系统 → 退出”，确保托盘图标也消失；
2. 如果曾将它设为默认任务管理器，先按下面的方法恢复；
3. 删除解压目录；
4. 若测试时加载过驱动且文件暂时无法删除，重启 Windows 后再删。

如果使用了便携设置文件，配置可能位于程序目录；否则用户配置通常位于
`%APPDATA%\SystemInformer`。只有确定不再需要设置时才手动删除该目录。

### 官方安装版

建议按以下顺序操作：

1. 打开 System Informer，进入“系统 → 选项 → 常规”；
2. 点击任务管理器区域的“恢复默认...”并确认管理员提示；
3. 从 Windows“设置 → 应用 → 已安装的应用”中卸载 **System Informer**；
4. 按 `Ctrl+Shift+Esc`，确认 Windows 任务管理器能够正常启动；
5. 如果卸载程序要求重启，请完成重启。

官方卸载器会清理安装目录、驱动、启动项和任务管理器替换项；先手动恢复可以在卸载异常时保留更安全的退路。

### 第三方汉化版或来源不明的安装包

第三方版本可能修改了名称、安装位置或卸载逻辑：

1. 先在该程序自己的选项中恢复 Windows 默认任务管理器；
2. 再从“已安装的应用”或控制面板卸载对应程序；
3. 不要在仍作为默认任务管理器时直接删除其安装目录；
4. 卸载后检查 `Ctrl+Shift+Esc`，并检查“任务管理器”是否仍启动旧路径；
5. 对残留文件先重启，再根据实际安装路径处理，不要直接照搬其他版本的删除路径。

### 程序已被删除、任务管理器仍被劫持

System Informer 通常通过下面注册表位置的 `Debugger` 值替换任务管理器：

```text
HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\taskmgr.exe
```

先以管理员身份打开 **64 位 PowerShell** 并查看当前值：

```powershell
$taskManagerIfeo = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\taskmgr.exe'
Get-ItemProperty -LiteralPath $taskManagerIfeo -Name Debugger -ErrorAction SilentlyContinue
```

只有确认 `Debugger` 指向已经卸载或不再使用的 System Informer/Process Hacker 路径后，才删除这个值：

```powershell
Remove-ItemProperty -LiteralPath $taskManagerIfeo -Name Debugger
Start-Process taskmgr.exe
```

这里只删除 `Debugger` 值，不删除整个 `taskmgr.exe` 注册表项。如果该值指向其他调试器、安全软件或企业管理工具，先停止并确认来源。

## 自行构建

本地完整编译需要 Visual Studio 2022 或更高版本。克隆后先运行：

```powershell
build\build_init.cmd
build\build_release.cmd
```

没有本地 C/C++ 环境时，可以使用带 `[build]` 的提交或 Tag 让 GitHub Actions 编译。

## 许可证与问题归属

System Informer 使用 [MIT 许可证](LICENSE.txt)。

- 汉化文本、注入脚本或本分支 CI 问题：在本 Fork 中反馈。
- 官方程序功能、稳定性或安全问题：请先在未修改的官方版本复现，再前往
  [官方问题跟踪器](https://github.com/winsiderss/systeminformer/issues)。
