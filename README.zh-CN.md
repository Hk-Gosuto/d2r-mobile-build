# d2r-mobile 构建工作流

[English](README.md) | [简体中文](README.zh-CN.md)

使用 GitHub Actions，从 [jhaizhou-ops/d2r-mobile](https://github.com/jhaizhou-ops/d2r-mobile) 源码构建自己的 IPA 和 Data。提供一份包含自有 ExeFS/RomFS 的 HTTPS 压缩包直链，工作流会下载并缓存输入、编译两种 iOS 版本，并将结果保存到你自己的私有仓库 Release。

## 1. 准备输入压缩包

支持的游戏版本：**3.3.94012**，Switch 更新 **1.0.34.0**，包含所需资料片。需要已经解密、合并本体与更新的完整 ExeFS 和 RomFS，具体要求见上游的[游戏文件说明](https://github.com/jhaizhou-ops/d2r-mobile/blob/main/docs/GAME_FILES.zh-CN.md)。

打成一个 **ZIP、tar.gz 或 tar.xz**，目录如下：

```text
ExeFS/
  main
  sdk
  subsdk0
RomFS/
  data/
    build_manifest.psv
    ...完整游戏资源...
```

允许外面再套一层文件夹。

把压缩包上传到自己的存储服务，取得能直接下载文件的 **HTTPS 直链**。使用签名直链时，将有效期设为覆盖整个下载过程。

计算压缩包的 SHA-256：

```sh
# macOS
shasum -a 256 game-input.zip
# Linux
sha256sum game-input.zip
```

Windows PowerShell：

```powershell
(Get-FileHash .\game-input.zip -Algorithm SHA256).Hash
```

## 2. 创建自己的构建仓库

1. 点击 [Use this template](https://github.com/jiayx/d2r-mobile-build/generate)，选择 **Create a new repository**，可见性选 **Private**。
2. 打开 **Settings → Secrets and variables → Actions → New repository secret**。创建一个名为 **`GAME_ARCHIVE`** 的 Secret，内容填写以下 JSON，将 `url` 换成自己的压缩包直链，`sha256` 换成上一步计算的校验值：

   ```json
   {
     "url": "https://your-storage.example/game-input.zip",
     "sha256": "YOUR_ARCHIVE_SHA256"
   }
   ```

## 3. 执行构建

在自己的仓库打开 **Actions → Build IPA and Data → Run workflow**。保持源码参数默认，即构建当前支持的上游正式版本。

测试其他源码时，`source_repository` 填上游仓库或自己的公开 Fork，`source_ref` 填分支、标签或提交。选择与游戏输入版本匹配的源码。

首次构建包含 Legacy 贴图转换，耗时较长；后续构建会复用已有资源。

## 4. 下载和安装

构建成功后，打开**自己仓库的 Releases**。最新 App Release 包含：

| 文件 | 用途 |
|---|---|
| `D2RMobile-<版本>.ipa` | iOS 26 及以上 |
| `D2RMobile-<版本>-ios18.ipa` | iOS 18–25 |
| `SHA256SUMS.txt`、`build-report.json` | 校验值与构建详情 |

自定义源码构建会在文件名中加入源码提交。Release 正文提供配套 Data 与 Legacy Device Pack 的下载链接。

1. 使用 [Sideloadly](https://sideloadly.io/)、[iloader](https://iloader.app/)、[AltStore Classic](https://faq.altstore.io/altstore-classic/your-altstore) 或 [SideStore](https://sidestore.io/) 签名安装对应 IPA。
2. 从正文链接的 Data Release 下载全部三个 `D2R-Mobile-Resources.zip.001`–`.003` 分卷，按 `RESOURCE-INSTALL.txt` 合并、解压，再通过 Finder 或“文件”App 将 `D2R Mobile Resources` 文件夹导入应用。
3. **A16 及更早设备**还需下载正文链接的 `Legacy-Device-Pack.zip`，解压后将整个 `Legacy Device Pack` 文件夹与资源文件夹并排导入。A17 Pro 及更新芯片和 M 系列 iPad 使用标准 Data 即可。
4. 打开应用并导入或选择资源文件夹。首次编译着色器需要数分钟，iPhone 17 Pro Max 可参考约 6 分钟。

更新时保持应用标识一致，提前备份存档，再覆盖安装新版 IPA。

## 更新与复用

后续在自己的仓库再次运行 **Build IPA and Data**，即可使用本项目 `main` 上更新后的构建工具和支持版本。输入文件保持相同时，沿用已有的 `GAME_ARCHIVE` 配置。

- 原始压缩包**先缓存，再解压**，重试时复用已完成的下载。
- Data 内容相同时，Release 直接引用已有的 Data。手机上已导入的资源继续使用。
- Legacy 转换输入和设置相同时，恢复已有的 Legacy 包。
- 保留仍被 App Release 引用的旧 Data 和 Legacy Release。
- 保留原始压缩包；更换输入时，更新 `GAME_ARCHIVE` 中的地址和校验值。

构建工具使用 [MIT 许可证](LICENSE)。上游及第三方代码保留各自许可证。
