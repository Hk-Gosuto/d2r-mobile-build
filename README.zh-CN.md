# d2r-mobile 构建工作流

[English](README.md) | [简体中文](README.zh-CN.md)

使用 GitHub Actions，从 [jhaizhou-ops/d2r-mobile](https://github.com/jhaizhou-ops/d2r-mobile) 源码构建自己的 IPA 和 Data。提供一份包含自有 ExeFS/RomFS 的 HTTPS 压缩包直链，工作流会下载并缓存输入、编译两种 iOS 版本，并将结果保存到你自己的私有仓库 Release。

本仓库提供构建工具和模板，不提供游戏文件、解密密钥或可下载的游戏构建产物。请只使用你有权使用的输入文件。

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

允许外面再套一层文件夹。只有手机使用的 18 个 Data 文件不能构建 IPA。不要把密钥或凭证放进压缩包。

把压缩包放到自己的存储服务，取得 **HTTPS 直接下载地址**。支持带有效期的签名直链，下载完成前地址必须有效。浏览器分享页、Google Drive 文件夹链接、登录页和 HTML 确认页都不是直链。Google Drive 需要能直接返回压缩包、无需交互登录的授权下载地址；工作流不会代为登录 Google 或获取游戏文件。

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
2. 打开 **Settings → Secrets and variables → Actions → New repository secret**。只创建一个名为 **`GAME_ARCHIVE`** 的 Secret，内容填写以下 JSON，将 `url` 换成自己的压缩包直链，`sha256` 换成上一步计算的校验值：

   ```json
   {
     "url": "https://your-storage.example/game-input.zip",
     "sha256": "YOUR_ARCHIVE_SHA256"
   }
   ```

   `sha256` 为 64 位十六进制校验值，用于验证下载的压缩包。

3. 如果组织限制了 Actions 的使用，需要允许调用本仓库的可复用工作流及其依赖的 Action。

构建不需要 `prod.keys`、Apple ID、签名证书或付费苹果开发者账号，签名在安装时另外完成。

## 3. 执行构建

在自己的仓库打开 **Actions → Build IPA and Data → Run workflow**。保持源码参数默认，即构建当前支持的上游正式版本。

测试其他源码时，`source_repository` 填上游仓库或自己的公开 Fork，`source_ref` 填分支、标签或提交。所选源码仍须兼容支持的游戏输入。构建报告会记录实际使用的源码和工具提交。

原生 App 使用 **macOS 26、iOS SDK 26.4 及以上**编译。两份 IPA 都从源码构建，不依赖上游预编译壳。构建时间因缓存而异，首次 Legacy 贴图转换可能明显慢于后续构建。

## 4. 下载和安装

构建成功后，打开**自己仓库的 Releases**。最新 App Release 包含：

| 文件 | 用途 |
|---|---|
| `D2RMobile-<版本>.ipa` | iOS 26 及以上 |
| `D2RMobile-<版本>-ios18.ipa` | iOS 18–25 |
| `SHA256SUMS.txt`、`build-report.json` | 校验值与构建详情 |

自定义源码构建会在文件名中加入源码提交。Release 正文提供配套 Data 与 Legacy Device Pack 的下载链接；内容没变时，会引用自己仓库里之前生成的资源 Release。

1. 使用 [Sideloadly](https://sideloadly.io/)、[iloader](https://iloader.app/)、[AltStore Classic](https://faq.altstore.io/altstore-classic/your-altstore) 或 [SideStore](https://sidestore.io/) 签名安装对应 IPA。
2. 从正文链接的 Data Release 下载全部三个 `D2R-Mobile-Resources.zip.001`–`.003` 分卷，按 `RESOURCE-INSTALL.txt` 合并、解压，再通过 Finder 或“文件”App 将 `D2R Mobile Resources` 文件夹导入应用。
3. **A16 及更早设备**还需下载正文链接的 `Legacy-Device-Pack.zip`，解压后将整个 `Legacy Device Pack` 文件夹与资源文件夹并排导入。A17 Pro 及更新芯片和 M 系列 iPad 无需这个补充包。
4. 打开应用并导入或选择资源文件夹。首次编译着色器需要数分钟，iPhone 17 Pro Max 可参考约 6 分钟。

IPA 未签名。自动校验不能替代真机测试。更新时保持应用标识一致，并提前备份存档；卸载应用会删除本地资源和存档。

## 更新与复用

构建入口调用本项目 `main` 上集中维护的工作流。下次发起构建时会使用当前工具和支持版本，不需要手动复制新脚本，自己的 Secret 保持不变。入口参数若有变化，会在这里说明。

- 原始压缩包下载完成后会**先缓存，再解压**。缓存仍有效时，解压或编译失败重试不用重新下载。
- 构建会检查游戏程序和资源，拒绝不兼容或缺失的输入。
- 相同 Data 直接复用自己仓库中的 Release，不再重复下载、压缩、分卷和上传。手机已导入的相同 Data 也不用重复导入。
- 相同 Legacy 包从自己仓库的 Release 恢复，不重新转换或上传。
- GitHub 可能自动淘汰缓存，请保留原始压缩包。更换输入时更新 `GAME_ARCHIVE` 中的地址和校验值。
- 请保留仍被 App Release 引用的旧 Data 和 Legacy Release。这些资源位于自己的私有仓库，不依赖本项目 Release 下载。

模板中附带工具源码供查看，但实际构建使用中央工作流固定提交的工具。个人源码修改放在所选的源码 Fork 中。

构建工具使用 [MIT 许可证](LICENSE)。上游及第三方代码保留各自许可证，这些许可证不授予游戏内容的使用或分发权利。
