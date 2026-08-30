# 简体中文版发布说明

本分支面向自用 x64 Windows：普通 `[build]` 构建只产生一个保留 1 天的 x64 便携版 Actions Artifact，Artifact 内直接是程序文件，不再套一层 ZIP；手动运行发布工作流时不会上传 Artifact，而是创建 GitHub Release。x64 成品仍包含运行 WOW64 功能所必需的 `x86` 辅助目录，这不等于发布独立的 i386 版本。Release 包含：

- `systeminformer-build-release-setup.exe`：安装程序
- `systeminformer-build-win64-bin.zip`：供用户下载的 x64 便携版
- `systeminformer-zh-CN-SHA256SUMS.txt`：发布文件校验和
- `systeminformer-update.json`：内置更新器读取的签名元数据

构建过程仍会在 runner 内生成 `systeminformer-build-bin.zip`，将其嵌入安装程序后不再作为
Release 资产公开；普通安装和更新都不需要用户单独下载该内部载荷。

上游 `CustomBuildTool` 在非官方构建环境中默认使用 `0.0` 作为主次版本。工作流会拉取官方
版本 Tag，从当前提交可达的最高版本自动解析 `BUILD_MAJORVERSION` 和 `BUILD_MINORVERSION`，
因此上游从 4.0 切换到新的主版本或次版本后不需要手改 CI。后两段继续使用本次构建的
UTC 日期和时间生成；这既保留上游的主次版本，又保证只有汉化发生变化时也能产生一个更高、
可供已安装版本识别的更新版本。

安装版通过内置更新器下载并验证新的安装程序。便携版只提示新版本并打开 Release 页面，更新时应手动下载新的 ZIP 后覆盖。

## 两类签名

Windows Authenticode 与内置更新器签名是两套独立机制：

1. Authenticode 用于向 Windows 标明发布者。不能复用官方证书或私钥；需要购买或申请自己的代码签名证书。即便签名有效，新的证书和下载文件仍可能在积累信誉前触发 SmartScreen。
2. 更新器使用本 fork 自己的 ECDSA P-256 密钥验证安装包，防止 GitHub Release 或更新元数据被替换。发布 tag 前必须配置该私钥。

## 配置更新器签名

审核期间生成的私钥位于本地仓库的 `.git/zh-cn-update-signing-private.pem`，不会被 Git 跟踪。请先离线备份；丢失后，已发布客户端无法验证由新密钥签署的后续更新。

将其以 Base64 形式写入仓库 Secret，避免在终端输出私钥：

```powershell
$keyBytes = [IO.File]::ReadAllBytes('.git\zh-cn-update-signing-private.pem')
$keyBase64 = [Convert]::ToBase64String($keyBytes)
$keyBase64 | gh secret set UPDATE_SIGNING_PRIVATE_KEY_B64 --repo AnLifeX/systeminformer
$keyBase64 = $null
```

对应公钥已经嵌入 `plugins/Updater/verify.c`。工作流会先验证所需 Secret，再生成 `systeminformer-update.json`；缺少私钥时发布构建会失败，不会发布无法验证的更新。

## 可选：配置 Windows 代码签名证书

准备包含私钥的 PFX 后，配置以下 Secrets：

- `WINDOWS_CODESIGN_CERTIFICATE_B64`：PFX 文件的 Base64 内容
- `WINDOWS_CODESIGN_CERTIFICATE_PASSWORD`：PFX 密码

未配置时仍会发布安装包，但安装包没有受信任发布者签名，Windows 可能显示未知发布者或 SmartScreen 警告。

## 发布

确认改动已提交并推送到 `zh-CN`，且分支上的轻量检查成功后：

1. 打开仓库 Actions 中的 `zh-CN build`；
2. 选择 `Run workflow`，分支使用 `zh-CN`；
3. 工作流再次执行完整汉化检查，成功后才启动 Windows 发布构建。

不需要手工创建 Tag。工作流从安装程序读取实际四段版本号，并创建例如
`zh-cn-v4.0.26242.1512` 的 Tag。旧的 `zh-cn-v0.1.x` 仅是历史汉化发行序号，不影响已安装
程序使用四段版本号比较更新。

发布过程会拒绝覆盖既有 Release，并将本次四段版本与当前 `latest` 的更新元数据逐段比较；
只有严格更新的版本才会继续。随后它会可选执行 Authenticode 签名、重新计算校验和、生成
更新器签名元数据，将四个文件先上传到草稿 Release，重新下载并核对文件集合、SHA-256、版本、
提交、下载地址、长度、哈希和更新器签名长度，全部通过后才把草稿公开。任何一步失败都不会
把未验证的 Release 暴露给更新器；本次运行创建的未公开草稿会被清理，修复问题后重新运行即可。

因此汉化文本、规则或测试有改动时不必等待上游发布新版本：提交并推送改动，等轻量检查通过，
再手动运行一次 `zh-CN build` 即可向已安装版本发布更新。每日上游检查仍只做检查，不会替你
自动发布。
