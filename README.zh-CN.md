# d2r-mobile 构建工作流

[English](README.md) | [简体中文](README.zh-CN.md)

使用 GitHub Actions 和自己的预处理包，从 [jhaizhou-ops/d2r-mobile](https://github.com/jhaizhou-ops/d2r-mobile) 源码构建两份 IPA。默认选择上游最新正式 Release，在 macOS 26 上编译，并发布到自己的私有仓库。

## 1. 准备输入

准备预处理包及配套的 `Prepared-SHA256SUMS.txt`，取得两个文件的 HTTPS 下载链接。支持直链和 Google Drive 文件分享链接。

预处理包包含已生成的游戏 payload、原生编译所需文件、预编译 Metal 着色器，以及配套 Data / Legacy Device Pack 的下载信息。包的结构和导出方式见[预处理包说明](docs/PREPARED_INPUT.md)。

Google Drive 使用 `https://drive.google.com/file/d/文件ID/view` 形式的文件分享链接，将文件设为「知道链接的任何人 → 查看者」。签名直链的有效期需覆盖下载过程。

## 2. 创建构建仓库

1. 点击 [Use this template](https://github.com/jiayx/d2r-mobile-build/generate)，选择 **Create a new repository**，可见性选 **Private**。
2. 将本页的[构建入口工作流](.github/workflows/build.yml)复制到自己的 `.github/workflows/build.yml`。
3. 打开 **Settings → Secrets and variables → Actions → New repository secret**，创建 **`PREPARED_INPUT`**，填写以下 JSON：

   ```json
   {
     "url": "https://your-storage.example/D2RMobile-Prepared.zip",
     "sha256_url": "https://your-storage.example/Prepared-SHA256SUMS.txt"
   }
   ```

`url` 是预处理包链接，`sha256_url` 是校验文件链接。两个链接保存在自己的仓库 Secret 中。

## 3. 执行构建

打开 **Actions → Build IPA → Run workflow**。`source_ref` 留空，自动获取上游最新正式 Release 的标签并编译。

- 测试最新开发代码：`source_ref` 填 `main`，也可以填写其他分支、标签或提交。
- 构建自己的修改：`source_repository` 填自己的 Fork，`source_ref` 填对应分支。
- 使用私有源码仓库：添加 **`SOURCE_TOKEN`** Secret，填写对该源码仓库具有 Contents 只读权限的细粒度令牌。

工作流校验预处理包与所选源码的兼容性，再并行编译 iOS 18 和 iOS 26 两份 IPA。下载完成后先缓存，后续失败可复用已完成的下载。

## 4. 下载和安装

设备要求：A14 / M1 及更新芯片，至少 6 GB 内存。

构建成功后，打开自己仓库的 **Releases**：

| 文件 | 用途 |
|---|---|
| `D2RMobile-<版本>-build.<运行编号>.<尝试次数>.ipa` | iOS 26 及以上 |
| `D2RMobile-<版本>-build.<运行编号>.<尝试次数>-ios18.ipa` | iOS 18–25 |
| `SHA256SUMS.txt`、`build-report.json` | 校验值与构建详情 |
| `RESOURCE-INSTALL.txt` | 配套资源安装说明 |

1. 使用 [Sideloadly](https://sideloadly.io/)、[iloader](https://iloader.app/)、[AltStore Classic](https://faq.altstore.io/altstore-classic/your-altstore) 或 [SideStore](https://sidestore.io/) 签名安装对应 IPA。
2. 从 Release 正文的链接下载配套 Data，按 `RESOURCE-INSTALL.txt` 合并、解压，将 `D2R Mobile Resources` 文件夹通过 Finder 或“文件”App 导入应用。
3. **A14–A16 设备**还需下载正文链接的 `Legacy-Device-Pack.zip`，解压后将整个 `Legacy Device Pack` 文件夹与资源文件夹并排导入。A17 Pro 及更新芯片和 M 系列 iPad 使用标准 Data。
4. 打开应用并选择资源文件夹。Metal 着色器已预编译，首次启动无需等待批量着色器编译。

Data 和 Legacy 的下载链接沿用预处理包内的信息。已导入相同资源时，更新 IPA 后继续使用原资源。更新前备份存档，保持应用标识一致并覆盖安装。

## 更新

再次运行 **Build IPA**，`source_ref` 留空，即使用维护中的最新构建逻辑和上游最新正式 Release。

每次运行及重跑使用独立的 Release 和文件名，支持同一上游版本反复构建。预处理包的缓存与 App 版本无关，普通运行时代码更新可继续复用；上游改变游戏改写、素材或着色器生成规则时，工作流会提示更新预处理包。替换输入后更新 `PREPARED_INPUT` 中的链接和校验信息。

### iCloud 存档

默认侧载配置使用本地存档。iCloud 自动同步需要付费 Apple Developer Program 账号、已开启 iCloud 的 App ID，以及匹配的描述文件和签名。导出的存档也可通过 iCloud 云盘手动备份或传输。
