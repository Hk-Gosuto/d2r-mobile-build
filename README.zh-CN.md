# d2r-mobile 构建工作流

[English](README.md) | [简体中文](README.zh-CN.md)

在 GitHub Actions 中从 [d2r-mobile](https://github.com/jhaizhou-ops/d2r-mobile) 源码构建 IPA。默认选择上游最新正式 Release，在 macOS 26 上并行编译 iOS 18 和 iOS 26 两份 IPA，发布到自己的私有仓库。

## 构建

1. 点击 [Use this template](https://github.com/jiayx/d2r-mobile-build/generate)，创建 **Private** 仓库。
2. 在 **Settings → Secrets and variables → Actions** 添加 Secret **`PREPARED_INPUT`**，将以下 JSON 粘贴为它的值：

   ```json
   {
     "url": "https://drive.google.com/file/d/1bjroriGTb2UwD48Pz1bGWZEJ5QDpAqbd/view",
     "sha256": "c3f45f4880a5738a69b09ee91881e5efc68cdc0cd2bc510be1147904834c2f38"
   }
   ```

3. 打开 **Actions → Build IPA → Run workflow**。

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

从 [Data + Legacy 共享目录](https://drive.google.com/drive/folders/1lfjUghi54ohyDxYEtNuEjtGUZyGovaIA)下载手机运行所需的资源：

| 压缩包 | 下载大小 | 用途 |
|---|---|---|
| `D2R-Mobile-Resources.zip.001`、`.002`、`.003` | 合计 5.42 GB | 所有支持设备均需导入的 Data，解压后为包含 18 个 `.data` 文件的 `D2R Mobile Resources` 文件夹 |
| `Legacy-Device-Pack.zip` | 1.02 GB | A14–A16 设备需要的补充贴图，解压后为 `Legacy Device Pack` 文件夹 |

1. 使用 [Sideloadly](https://sideloadly.io/)、[iloader](https://iloader.app/)、[AltStore Classic](https://faq.altstore.io/altstore-classic/your-altstore) 或 [SideStore](https://sidestore.io/) 签名安装 IPA。
2. 从上方共享目录下载配套 Data。分卷形式需下载全部 `.001`、`.002`、`.003`，用支持分卷的解压工具打开 `.001`，将解压得到的 `D2R Mobile Resources` 文件夹通过 Finder 或“文件”App 导入应用。
3. A14–A16 设备另从同一共享目录下载 `Legacy-Device-Pack.zip`，解压后将整个 `Legacy Device Pack` 文件夹与资源文件夹并排导入。A17 Pro 及更新芯片、M 系列 iPad 使用标准 Data。
4. 打开应用并选择资源文件夹。预处理包已包含预编译 Metal 着色器。

设备要求：A14 / M1 及更新芯片，至少 6 GB 内存。

## 更新 IPA

再次运行 **Build IPA** 即可构建上游最新正式 Release。更新 IPA 时备份存档，保持应用标识一致并覆盖安装，已导入的相同 Data 和 Legacy 可继续使用。

普通原生代码更新可复用预处理包；工作流提示生成规则不兼容时，取得新版预处理包并更新 `PREPARED_INPUT`。
