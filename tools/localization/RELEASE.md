# 简体中文版发布说明

本分支面向自用 x64 Windows：普通 `[build]` 构建只产生一个保留 1 天的 x64 便携版 Actions Artifact，Artifact 内直接是程序文件，不再套一层 ZIP；推送 tag 时不会上传 Artifact，而是直接创建 GitHub Release。x64 成品仍包含运行 WOW64 功能所必需的 `x86` 辅助目录，这不等于发布独立的 i386 版本。Release 包含：

- `systeminformer-build-release-setup.exe`：安装程序
- `systeminformer-build-win64-bin.zip`：供用户下载的 x64 便携版
- `systeminformer-build-bin.zip`：安装程序使用的 x64 安装载荷（保留 `amd64` 目录结构）
- `systeminformer-zh-CN-SHA256SUMS.txt`：发布文件校验和
- `systeminformer-update.json`：内置更新器读取的签名元数据

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

对应公钥已经嵌入 `plugins/Updater/verify.c`。工作流会先验证所需 Secret，再生成 `systeminformer-update.json`；缺少私钥时 tag 构建会失败，不会发布无法验证的更新。

## 可选：配置 Windows 代码签名证书

准备包含私钥的 PFX 后，配置以下 Secrets：

- `WINDOWS_CODESIGN_CERTIFICATE_B64`：PFX 文件的 Base64 内容
- `WINDOWS_CODESIGN_CERTIFICATE_PASSWORD`：PFX 密码

未配置时仍会发布安装包，但安装包没有受信任发布者签名，Windows 可能显示未知发布者或 SmartScreen 警告。

## 发布

确认工作区已提交、推送且构建成功后，为要发布的提交创建并推送 tag：

```powershell
git tag v4.0.26241.138-zh-cn.1
git push origin v4.0.26241.138-zh-cn.1
```

tag 工作流会重新构建汉化版本、可选地执行 Authenticode 签名、重新计算校验和、生成更新器签名元数据，最后创建 GitHub Release。不要在审核完成前推送发布 tag。
