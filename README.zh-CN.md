# D2R Mobile · GitHub Actions 构建

[English](README.md) | **简体中文**

[![Build IPA](https://github.com/jiayx/d2r-mobile-build/actions/workflows/pack.yml/badge.svg)](https://github.com/jiayx/d2r-mobile-build/actions/workflows/pack.yml)

基于 [jhaizhou-ops/d2r-mobile](https://github.com/jhaizhou-ops/d2r-mobile) 的 **NO_XCODE** 方案，使用 GitHub Actions 构建未签名 IPA 和配套 Data 资源。可以从 Releases 下载，也可以按下方步骤自行构建。

## 下载与安装

进入 **[最新 Release](https://github.com/jiayx/d2r-mobile-build/releases/latest)**：IPA 从 **Assets 附件**下载，Data 从 Release 正文的**配套 Data**中直接点击下载链接。

| 文件 | 下载位置 | 用途 |
| --- | --- | --- |
| `D2RMobile-unsigned.ipa` | Assets 附件 | 约 126MB，用 Sideloadly 签名并安装 |
| `D2R-Mobile-Resources.zip.001`、`.002`、`.003` | 正文的配套 Data 链接 | 三个资源分卷，必须全部下载，总计约 5.42GB |
| `Resources-Parts-SHA256SUMS.txt`、`Resources-SHA256SUMS.txt` | 正文的配套 Data 链接 | 校验分卷与合并后的 ZIP |
| `RESOURCE-INSTALL.txt` | Assets 附件 | 分卷合并与资源导入说明 |

`Source code` 压缩包是构建脚本，不是安装包。

### 1. 安装 IPA

需要 **iOS 26 或以上**，以及 **A17 Pro 或更新芯片，或 M 系列 iPad**。此包不包含 A16 及更早设备所需的额外贴图包。

使用 Sideloadly 签名并安装 `D2RMobile-unsigned.ipa`，按系统提示完成信任设置。**IPA 需要配合下方 Data 资源使用。**

### 2. 合并并解压 Data

将三个分卷和两个校验文件放在同一目录。

macOS：在该目录打开终端，执行：

```sh
shasum -a 256 -c Resources-Parts-SHA256SUMS.txt
cat D2R-Mobile-Resources.zip.001 D2R-Mobile-Resources.zip.002 D2R-Mobile-Resources.zip.003 > D2R-Mobile-Resources.zip
shasum -a 256 -c Resources-SHA256SUMS.txt
```

Linux 可使用 `sha256sum -c` 替代 `shasum -a 256 -c`。

Windows：在该目录打开**命令提示符（cmd）**，执行：

```bat
copy /b D2R-Mobile-Resources.zip.001+D2R-Mobile-Resources.zip.002+D2R-Mobile-Resources.zip.003 D2R-Mobile-Resources.zip
```

解压合并后的 ZIP，得到 `D2R Mobile Resources` 文件夹，内含 **18 个 `.data` 文件，约 5.56GB**。

### 3. 导入 Data 并启动

用数据线连接 iPhone，在 **Finder → iPhone → 文件 → D2R Mobile** 中拖入整个 `D2R Mobile Resources` 文件夹；也可以放进手机的 **文件 → 我的 iPhone → D2R Mobile**。

打开应用，点击“重试”。首次启动需等待着色器编译完成，**iPhone 17 Pro Max 参考耗时约 6 分钟**，其他机型耗时不同。当前 v1.0.6 包尚未进行真机运行验证。

更新 IPA 时，配套资源版本不变就可以继续使用已有 Data。应用标识不变时，覆盖安装通常保留资源和存档；**卸载应用会删除它们**。

## 配套版本

| 项目 | 版本 |
| --- | --- |
| 上游 | v1.0.6 |
| Switch 更新 | `1.0.34.0` / `v2228224` |
| 游戏内部版本 | `3.3.94012` |
| 所需版本 | 包含「术士君临」资料片 |

## 自己运行构建

### 1. Fork 仓库

点击 **Fork** 创建自己的副本，打开 **Actions**，如有提示则启用工作流。请仅使用自己有权使用的游戏文件和密钥。

### 2. 配置输入

在自己的仓库进入 **Settings → Secrets and variables → Actions → New repository secret**，名称填写 **`GAME_INPUT_MANIFEST`**，完整粘贴以下 JSON。下载地址和 SHA256 已填好：

```json
{
  "kind": "packages",
  "files": [
    {
      "name": "game.torrent",
      "url": "https://gamegula.com/index.php?do=download&id=405",
      "sha256": "016f7c907deb1f4cd6098a7cd06823907a589ff2502aa2c8b341a89ccf984266",
      "select": [1, 2]
    }
  ],
  "key_archive": {
    "url": "https://drive.google.com/uc?export=download&id=147IsDRRJNF_VMT6Fj50glrnqAeb7oR_1",
    "sha256": "b73573af5eae6c9f7739ca9931cebf04774cf2ba9d6ee98f2f04c2dc88fca71c"
  }
}
```

种子中包含本体与更新包，`select: [1, 2]` 选择这两项；`key_archive` 是包含解包密钥的 ZIP。使用这份配置，无需另外填写 `PROD_KEYS` Secret。

### 3. 运行构建

进入 **Actions → Build D2R Mobile IPA → Run workflow**，选择 `main`，使用下表参数：

| 参数 | 填写内容 |
| --- | --- |
| `prepare_only` | `false`，不勾选 |
| `input_revision` | `game-3.3.94012-v1`；更换游戏文件或修改种子下载项时更换 |

**只需运行这一个工作流。** 它会构建 IPA、检查配套 Data，并自动发布 Release。已有相同 Data 时直接复用，不重新压缩或上传；没有配套资源或内容发生变化时，自动打包并发布 Data。

构建成功后，进入**自己仓库的 Releases**。正文提供配套 Data 分卷与校验文件的直接下载链接，即使这些文件保存在较早的 Release，也可以从当前页面直接下载。按上方步骤合并并导入。资源标识与手机上已有 Data 相同时，更新 IPA 无需重新下载 Data。

请保留配套 Data 所在的 Release 及其附件，确保下载链接持续可用。

Actions 运行摘要中也有 IPA 和 Data 的下载入口。IPA 构建附件内包含安装包、资源下载信息（`resources.json`）和导入说明，保留期为 **3 天**。
