System Informer 简体中文便携版
================================

这是由 Gaq152/systeminformer 的 zh-CN 分支自动编译的非官方汉化版本。
程序核心代码、驱动和插件来自 System Informer 官方仓库；此构建没有官方数字签名，
Windows SmartScreen 可能提示未知发布者。

开始使用
--------

64 位 Windows 请运行 SystemInformer.exe。本压缩包是便携构建，不需要安装，
也不要直接覆盖已经安装的官方版或其他第三方版本。

如果本机已经安装 System Informer，首次仅检查汉化界面时，可在当前目录打开
PowerShell 并运行：

    .\SystemInformer.exe -newinstance -nosettings -nokph -noplugins

这些参数会启动独立实例、不读取或保存正式版配置、不加载内核驱动，也不加载插件。

设置位置
--------

默认设置通常保存在：

    %APPDATA%\SystemInformer

如果希望把设置保存在程序目录，可在 SystemInformer.exe 旁边创建空文件：

    SystemInformer.exe.settings.xml

卸载本便携版
------------

1. 在 System Informer 中选择“系统 -> 退出”，确保托盘图标也消失。
2. 如果曾把它设为默认任务管理器，先在“系统 -> 选项 -> 常规”中点击
   “恢复默认...”。
3. 删除整个解压目录。
4. 如果测试时加载过驱动且文件无法删除，重启 Windows 后再删除。

如果程序已经被删除，但 Ctrl+Shift+Esc 仍试图打开旧版 System Informer，
请阅读仓库 README.md 中“卸载与恢复 Windows 任务管理器”一节，不要随意删除
整段注册表路径。

在线文件分析提示
----------------

OnlineChecks 插件可能在首次启动时询问是否启用 Hybrid-Analysis。启用后会查询文件
哈希，未知文件还可能被上传进行完整分析。不需要该功能时，请进入配置并关闭扫描、
自动扫描和自动提交，或使用 -noplugins 启动。

项目地址
--------

汉化分支：
https://github.com/Gaq152/systeminformer/tree/zh-CN

官方项目：
https://github.com/winsiderss/systeminformer

许可证：MIT（参见 LICENSE.txt）
