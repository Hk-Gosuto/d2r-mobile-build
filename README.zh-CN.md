# d2r-mobile 构建工作流

[English](README.md) | [简体中文](README.zh-CN.md)

使用 GitHub Actions，从 [jhaizhou-ops/d2r-mobile](https://github.com/jhaizhou-ops/d2r-mobile) 源码构建自己的 IPA 和 Data。提供包含自有 ExeFS/RomFS 的压缩包及 SHA256SUMS 校验文件，支持 HTTPS 直链或 Google Drive 文件分享链接。工作流下载并缓存输入，在 macOS 26 上从源码编译两种 iOS 版本，将结果保存到你自己的私有仓库 Release，无需上游预先发布 IPA。

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

在压缩包旁生成校验文件：

```sh
# macOS
shasum -a 256 game-input.zip > SHA256SUMS.txt
# Linux
sha256sum game-input.zip > SHA256SUMS.txt
```

Windows PowerShell：

```powershell
$hash = (Get-FileHash .\game-input.zip -Algorithm SHA256).Hash
"$hash  game-input.zip" | Set-Content -Encoding ascii SHA256SUMS.txt
```

将**压缩包和校验文件**都上传到自己的存储服务，取得无需登录即可下载的链接。Google Drive 选择「知道链接的任何人 → 查看者」后，可直接使用文件分享链接，大 ZIP 的下载确认页会自动处理；不要使用文件夹链接。使用签名 HTTPS 直链时，有效期需覆盖整个下载过程。校验文件只能包含这一份压缩包的校验值。

## 2. 创建自己的构建仓库

1. 点击 [Use this template](https://github.com/jiayx/d2r-mobile-build/generate)，选择 **Create a new repository**，可见性选 **Private**。
2. 将本页的[构建入口工作流](.github/workflows/build.yml)复制到自己私有仓库的 `.github/workflows/build.yml`，已有旧入口时替换它。入口调用维护中的源码构建工作流，后续 App 版本更新无需重复复制构建脚本。
3. 打开 **Settings → Secrets and variables → Actions → New repository secret**。创建一个名为 **`GAME_ARCHIVE`** 的 Secret，填写以下 JSON：`url` 是 ZIP 的链接，`sha256_url` 是 `SHA256SUMS.txt` 的链接：

   ```json
   {
     "url": "https://your-storage.example/game-input.zip",
     "sha256_url": "https://your-storage.example/SHA256SUMS.txt"
   }
   ```

Google Drive 链接直接使用 `https://drive.google.com/file/d/文件ID/view` 的形式即可，Actions 无需登录 Google 账号。两个链接保存在自己的私有仓库 Secret 中。

## 3. 执行构建

在自己的仓库打开 **Actions → Build IPA and Data → Run workflow**。`source_ref` 留空，即自动获取并构建上游最新正式 Release。

测试最新开发代码时，`source_ref` 填 `main`；也可以填其他分支、标签或提交。构建自己的修改时，`source_repository` 填自己的公开 Fork。选择与游戏输入版本匹配的源码。

首次构建包含 Legacy 贴图转换，耗时较长；后续构建会复用已有资源。

## 4. 下载和安装

构建成功后，打开**自己仓库的 Releases**。最新 App Release 包含：

| 文件 | 用途 |
|---|---|
| `D2RMobile-<版本>.ipa` | iOS 26 及以上 |
| `D2RMobile-<版本>-ios18.ipa` | iOS 18–25 |
| `SHA256SUMS.txt`、`build-report.json` | 校验值与构建详情 |

文件名使用源码标签；标签之后的构建会附带源码提交，没有版本标签时使用提交。Release 正文提供配套 Data 与 Legacy Device Pack 的下载链接。

1. 使用 [Sideloadly](https://sideloadly.io/)、[iloader](https://iloader.app/)、[AltStore Classic](https://faq.altstore.io/altstore-classic/your-altstore) 或 [SideStore](https://sidestore.io/) 签名安装对应 IPA。
2. 从正文链接的 Data Release 下载全部三个 `D2R-Mobile-Resources.zip.001`–`.003` 分卷，按 `RESOURCE-INSTALL.txt` 合并、解压，再通过 Finder 或“文件”App 将 `D2R Mobile Resources` 文件夹导入应用。
3. **A16 及更早设备**还需下载正文链接的 `Legacy-Device-Pack.zip`，解压后将整个 `Legacy Device Pack` 文件夹与资源文件夹并排导入。A17 Pro 及更新芯片和 M 系列 iPad 使用标准 Data 即可。
4. 打开应用并导入或选择资源文件夹。首次编译着色器需要数分钟，iPhone 17 Pro Max 可参考约 6 分钟。

更新时保持应用标识一致，提前备份存档，再覆盖安装新版 IPA。

### iCloud 存档

上游源码包含 iCloud 存档同步。这些未签名包使用普通侧载配置，不配置 iCloud 权限；免费 Apple ID 签名只支持本地存档。自动同步需要付费 Apple Developer Program 账号、已开启 iCloud 的 App ID，以及匹配的描述文件和签名，游戏内打开 iCloud 开关不能代替签名权限。导出的存档可以通过 iCloud 云盘手动备份或传输。

## 更新与复用

后续在自己的仓库再次运行 **Build IPA and Data**，将 `source_ref` 留空，即可使用最新构建工具打包上游最新正式 Release。输入文件保持相同时，沿用已有的 `GAME_ARCHIVE` 配置。

- 根据校验文件确定原始压缩包的缓存键，与 App 版本无关；验证下载后**先缓存，再解压**，后续解压或编译失败不会丢掉已完成的下载。
- Drive 下载遇到临时网络故障会重试，并在当前任务中续传；中断或失败的下载不会被当成完整缓存。
- 游戏程序改写、界面素材、构建工具和着色器分开缓存，按各自相关输入计算缓存键；只修改 App 运行时代码时，不会让未变的改写产物和着色器缓存失效。
- Data 内容相同时，Release 直接引用已有的 Data。手机上已导入的资源继续使用。
- Legacy 转换输入和设置相同时，恢复已有的 Legacy 包。
- 保留仍被 App Release 引用的旧 Data 和 Legacy Release。
- GitHub 可能清理缓存，请保留原始压缩包；更换输入时，保持 `GAME_ARCHIVE` 中 ZIP 和校验文件的链接有效。

构建工具使用 [MIT 许可证](LICENSE)。上游及第三方代码保留各自许可证。
