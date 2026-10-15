# d2r-mobile 构建工作流

[English](README.md) | [简体中文](README.zh-CN.md)

在 GitHub Actions 中从 [d2r-mobile](https://github.com/jhaizhou-ops/d2r-mobile) 源码构建 iOS 和 macOS 应用。默认选择上游最新正式 Release，发布到自己的私有仓库。

## 构建 iOS

1. 点击 [Use this template](https://github.com/jiayx/d2r-mobile-build/generate)，创建 **Private** 仓库。
2. 在 **Settings → Secrets and variables → Actions** 添加 Secret **`PREPARED_INPUT`**，将以下 JSON 粘贴为它的值：

   ```json
   {
     "url": "https://drive.google.com/file/d/1bjroriGTb2UwD48Pz1bGWZEJ5QDpAqbd/view",
     "sha256": "c3f45f4880a5738a69b09ee91881e5efc68cdc0cd2bc510be1147904834c2f38"
   }
   ```

   配置中的预处理包由热心网友提供。

3. 打开 **Actions → Build IPA → Run workflow**。预计 **2–3 分钟**完成打包并发布。

- 默认直接运行，自动编译上游最新正式 Release。
- 测试开发代码：`source_ref` 填 `main`、其他分支、标签或提交。
- 测试自己的修改：`source_repository` 填自己的 Fork，`source_ref` 填对应分支。私有源码仓库另配置 **`SOURCE_TOKEN`** Secret，授予该源码仓库 Contents 只读权限。

构建入口自动使用本项目维护的最新构建逻辑。工作流下载并校验预处理包，检查源码兼容性，再编译、打包两份 IPA。下载完成的预处理包和原生编译模块会缓存，供后续构建复用。同一上游版本支持多次构建及重跑，每次使用独立的 Release 和文件名。

## 下载和使用

构建完成后，在自己仓库的 **Releases** 下载：

| 文件 | 用途 |
|---|---|
| `D2RMobile-<版本>-build.<运行编号>.<尝试次数>.ipa` | iOS 26 及以上 |
| `D2RMobile-<版本>-build.<运行编号>.<尝试次数>-ios18.ipa` | iOS 18–25 |
| `SHA256SUMS.txt`、`build-report.json` | 校验值与构建详情 |

下载热心网友提供的[配套游戏资源（Data 和 Legacy）](https://drive.google.com/drive/folders/1lfjUghi54ohyDxYEtNuEjtGUZyGovaIA)：

| 压缩包 | 下载大小 | 用途 |
|---|---|---|
| `D2R-Mobile-Resources.zip.001`、`.002`、`.003` | 合计 5.42 GB | 所有支持设备均需导入的 Data，解压后为包含 18 个 `.data` 文件的 `D2R Mobile Resources` 文件夹 |
| `Legacy-Device-Pack.zip` | 1.02 GB | A14–A16 设备需要的补充贴图，解压后为 `Legacy Device Pack` 文件夹 |

1. 使用 [Sideloadly](https://sideloadly.io/)、[iloader](https://iloader.app/)、[AltStore Classic](https://faq.altstore.io/altstore-classic/your-altstore) 或 [SideStore](https://sidestore.io/) 签名安装 IPA，安装后先打开一次应用。
2. 从上方链接下载配套 Data。分卷形式需下载全部 `.001`、`.002`、`.003`，用支持分卷的解压工具打开 `.001`，将解压得到的整个 `D2R Mobile Resources` 文件夹拷到“文件”App →“我的 iPhone”→“D2R Mobile”；也可连接 Mac，在 Finder → 手机 →“文件”中拖入该应用。
3. A14–A16 设备另从同一链接下载 `Legacy-Device-Pack.zip`，解压后将整个 `Legacy Device Pack` 文件夹与资源文件夹并排导入。A17 Pro 及更新芯片、M 系列 iPad 使用标准 Data。
4. 拷贝完成后回到应用，若停在资源提示页，点击“重试”，应用会自动检测并加载资源。IPA 已包含预编译 Metal 着色器。

设备要求：A14 / M1 及更新芯片，至少 6 GB 内存。

## 更新 IPA

再次运行 **Build IPA** 即可构建上游最新正式 Release。更新 IPA 时备份存档，保持应用标识一致并覆盖安装，已导入的相同 Data 和 Legacy 可继续使用。

普通原生代码更新可复用预处理包；工作流提示生成规则不兼容时，取得新版预处理包并更新 `PREPARED_INPUT`。

## 构建 macOS

1. 在自己的私有仓库添加 Secret **`MACOS_PREPARED_INPUT`**，填入 Mac 预处理包的下载配置：

   ```json
   {
     "url": "https://drive.google.com/file/d/1t7u-eYg876z6681pqgHP5n0JDbwypzs7/view",
     "sha256": "d961071ea06bffb12be37f4e79b2933186e59d2f1ead884e74b2ec9471b7a67f"
   }
   ```

   此配置中的预处理包由热心网友提供。

2. 打开 **Actions → Build macOS → Run workflow**。构建和发布通常需要 **2–3 分钟**。源码选择参数与 iOS 构建相同。

工作流下载并校验 Mac 预处理包，从当前源码编译两种系统版本的原生程序，并发布应用。下载完成的包会缓存，供后续构建复用。包内包含改写后的游戏程序、Mac 界面资源和预编译 macOS Metal 着色器，结构见[Mac 预处理包格式](docs/MACOS_PREPARED_INPUT.zh-CN.md)。

在自己仓库的 **Releases** 下载：

| 文件 | 用途 |
|---|---|
| `D2RMobile-<版本>-build.<运行编号>.<尝试次数>-macos26.zip` | macOS 26 及以上的 Apple 芯片 Mac |
| `D2RMobile-<版本>-build.<运行编号>.<尝试次数>-macos15.zip` | macOS 15–25 的 Apple 芯片 Mac |
| `Mac-SHA256SUMS.txt`、`macos-build-report.json` | 校验值与构建详情 |

解压 ZIP，将应用移到“应用程序”。游戏资源可复用上方下载的 Data：

1. 在 Finder 按 **⌘⇧.** 显示隐藏文件，将 ZIP 附带的 `Mac Resource Metadata/data` 中的 `build_manifest.psv` 和 `.build.config` 复制到 `D2R Mobile Resources/data`。
2. 首次启动应用，选择 `D2R Mobile Resources` 文件夹；应用会记住这个位置。

更新应用时保持资源位置不变即可。macOS 15 版使用独立存档目录，可与 macOS 26 版并存。

应用使用本机临时签名。首次打开若被系统拦截，按 Apple 的[打开可信应用说明](https://support.apple.com/102445)操作。
