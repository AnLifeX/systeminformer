<p align="center">
    <img src="SystemInformer/resources/systeminformer-128x128.png" alt="System Informer" width="128" height="128">
</p>

<h1 align="center">System Informer 简体中文构建</h1>

<p align="center">
    基于官方 System Informer 源码，通过可验证的自动化脚本注入简体中文文本并由 GitHub Actions 编译。
</p>

<p align="center">
    <a href="https://github.com/AnLifeX/systeminformer/actions/workflows/localization-zh-cn.yml"><img src="https://img.shields.io/github/actions/workflow/status/AnLifeX/systeminformer/localization-zh-cn.yml?branch=zh-CN&style=for-the-badge&label=zh-CN%20build" alt="zh-CN build"></a>
    <a href="LICENSE.txt"><img src="https://img.shields.io/badge/license-MIT-blue.svg?style=for-the-badge" alt="MIT License"></a>
</p>

> [!IMPORTANT]
> 这是非官方汉化分支，与 System Informer 官方团队无关。程序核心代码、驱动和插件来自
> [官方仓库](https://github.com/winsiderss/systeminformer)；本分支主要维护汉化目录、注入脚本和中文构建流程。

## 当前状态

- 唯一维护和发布分支：`zh-CN`；官方上游通过 CI 直接从 `winsiderss/systeminformer` 获取。
- 当前已覆盖主窗口、常用菜单和对话框、进程/服务/网络列，以及部分内置插件。
- 汉化仍未覆盖全部深层页面，后续会根据实测逐步补充。
- `[build]` 测试构建只提供便携 ZIP；手动运行发布工作流时同时提供便携包和安装程序。未配置代码签名证书时，Windows SmartScreen 可能提示未知发布者。
- GitHub Actions Artifact 只保留 1 天，避免占用免费账户存储空间。

## 下载和安全测试

在仓库的 [Actions 页面](https://github.com/AnLifeX/systeminformer/actions/workflows/localization-zh-cn.yml)
打开最近一次成功的 `zh-CN build`，下载页面底部的 portable Artifact。它只包含便携 ZIP，
用于安装前隔离测试；正式安装程序只在 GitHub Release 中发布。

首次仅检查界面时，建议先退出其他 System Informer 实例，然后在解压目录运行：

```powershell
.\SystemInformer.exe -newinstance -nosettings -nokph -noplugins
```

- `-newinstance`：单独启动新实例。
- `-nosettings`：不读取或写入已安装版本的用户配置。
- `-nokph`：不加载 `KSystemInformer` 内核驱动。
- `-noplugins`：不加载插件，避免首次弹出在线文件信誉分析提示。

确认基本界面正常后，可以按需去掉 `-noplugins` 测试插件。不要直接用 CI 便携版覆盖正式安装目录。
便携版检测到新版本时只会打开本仓库的 Release 页面，需要手动下载并覆盖 ZIP；安装版才会下载、验证并启动更新安装程序。

## 同时启用管理员启动和默认任务管理器替换时的快捷键

本节所说的 Shift 逃生现象只会在 System Informer 同时启用“启动时请求管理员权限（实验性）”并
替换默认任务管理器后出现。不同设置下，`Ctrl+Shift+Esc` 的实际行为如下：

| 设置状态 | `Ctrl+Shift+Esc` 的行为 |
| --- | --- |
| 未替换默认任务管理器 | 打开原生 Windows 任务管理器 |
| 已替换，但未启用管理员启动 | 打开 System Informer |
| 已替换，并启用管理员启动 | 触发 Shift 逃生机制，打开原生 Windows 任务管理器 |

因此，普通安装不会出现“替换后又被切回原生任务管理器”的情况；只替换默认任务管理器也仍可使用
`Ctrl+Shift+Esc` 打开 System Informer。只有同时启用上述两项设置后，不同入口才会表现为：

- 不含 Shift 的自定义快捷键：以管理员权限启动或激活 System Informer；
- `Ctrl+Shift+Esc`：打开原生 Windows 任务管理器；
- 任务栏右键菜单中的“任务管理器”：正常打开 System Informer；按住 Shift 再点击时打开原生任务管理器。

为了避开 `Ctrl+Shift+Esc` 与 Shift 逃生机制的冲突，建议为 System Informer 单独创建一个不含 Shift 的
Windows 快捷键，例如 `Ctrl+Alt+I`。
“快捷键”不是 System Informer 内的设置，也不是 `SystemInformer.exe` 的属性，而是开始菜单中
Windows 快捷方式（`.lnk`）的属性。安装版的快捷方式通常位于：

```text
C:\ProgramData\Microsoft\Windows\Start Menu\Programs\System Informer.lnk
```

安装程序创建的桌面快捷方式通常位于 `C:\Users\Public\Desktop\System Informer.lnk`。
它和开始菜单快捷方式是两个独立文件，只是都指向同一个 `SystemInformer.exe`；修改其中一个的
快捷键、启动方式或工作目录不会同步到另一个。设置开始菜单快捷方式的快捷键后即可在系统中使用，
不需要再给桌面快捷方式设置相同的快捷键。

设置步骤如下：

1. 在开始菜单中搜索 **System Informer**，右键选择“打开文件所在的位置”；
2. 右键其中的 System Informer 快捷方式，选择“属性”；
3. 在“快捷方式”选项卡的“快捷键”栏中按 `I`，Windows 会将其设置为 `Ctrl+Alt+I`；
4. 点击“应用”或“确定”。

如果“打开文件所在的位置”进入的是 `C:\Program Files\SystemInformer`，当前选中的是
`SystemInformer.exe` 程序本体，不是开始菜单快捷方式，因此不会显示“快捷方式”选项卡和
“快捷键”栏。不要再从桌面快捷方式选择“打开文件所在的位置”，因为该操作也会跳到 EXE 目录；
应直接修改开始菜单打开的 `.lnk` 文件属性。

建议同时启用“只允许运行一个实例”，这样按自定义快捷键时会激活已有窗口，不会重复启动多个实例。
不要在 EXE 的“兼容性”页强制勾选“以管理员身份运行此程序”；该兼容性设置可能影响默认任务管理器替换，
应使用 System Informer 自带的管理员启动选项。

## 构建与发布触发规则

每次提交到 `zh-CN` 都会先在 Ubuntu runner 上运行汉化单元测试、上下文检查、可见文本审计和翻译后检查。普通提交不启动 Windows 编译，也不上传 Artifact。以下情况会继续构建：

1. 提交信息包含区分大小写的 `[build]`：只构建便携 ZIP，并上传保留 1 天的 Artifact；
2. 在 Actions 中手动运行 `zh-CN build`：用于发布你自己的汉化改动；
3. 上游出现新的正式版本 Tag 且同步检查通过：自动将上游 Tag 合并到 `zh-CN`，再自动构建并发布。

示例：

```powershell
git commit -m "feat: update translations [build]"
git push origin zh-CN
```

`[build]` 只用于测试便携包，不会发布正式版本。发布你自己的汉化改动时，在 Actions 中手动运行
`zh-CN build`；不需要手工填写 Tag，工作流会读取安装程序的实际四段版本号并自动创建同名 Tag，
例如 `zh-cn-v4.0.26242.1512`。工作流还会拒绝从未包含最新官方 Tag 的旧 `zh-CN` 提交发布。

每天会检查一次官方 `winsiderss/systeminformer` 的 `master`。普通上游提交只进入兼容性检查，
不会发布；当官方最新正式 Tag 发生变化时，工作流会从当前 `zh-CN` 创建候选合并，运行完整汉化检查。
检查通过后才会自动合并到 `zh-CN`，并由 `zh-CN build` 自动创建 Tag 和发布 Release；检查失败则不修改
正式分支，也不会发布，下一次任务会继续重试。`automation/upstream-check` 只保存检查状态，不能作为发布来源。
仓库不再维护本地 `master` 分支，发布和汉化始终以 `zh-CN` 为准。
安装包发布、自有更新源和签名密钥的配置见
[`tools/localization/RELEASE.md`](tools/localization/RELEASE.md)。

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
