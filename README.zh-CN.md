# D2R Mobile · GitHub Actions 构建模板

[English](README.md) | **简体中文**

**[基于此模板创建自己的仓库](https://github.com/jiayx/d2r-mobile-build/generate)**

基于 [jhaizhou-ops/d2r-mobile](https://github.com/jhaizhou-ops/d2r-mobile) 的 **NO_XCODE** 方案，在自己的 GitHub 仓库中构建未签名 IPA 和配套游戏资源。构建在 GitHub Actions 的 Ubuntu runner 上运行，产物自动发布到运行工作流的仓库。

请基于模板创建**私有仓库**，提供自己合法持有且有权处理的游戏文件与主机密钥。模板创建会复制源码文件，不继承 Secrets、Release、Actions 附件或缓存。模板不提供游戏下载来源或密钥。

## 1. 创建私有仓库

1. 点击 **Use this template → Create a new repository**，或使用上面的创建链接。
2. **Owner** 选择自己的账号，**Repository name** 自行填写，选择 **Private**。无需勾选 **Include all branches**，默认分支即可。
3. 点击 **Create repository from template**，之后的操作都在**新建的仓库**中进行。
4. 打开 **Actions**，如果 GitHub 提示启用工作流，按提示启用。账号或组织策略需要允许工作流使用的 Actions。私有仓库运行会使用你账号的 Actions 额度或计费设置。

无需修改脚本中的仓库账号、壳包地址、源码提交或工具版本。发布脚本自动识别当前仓库，使用 GitHub 自动提供的 `GITHUB_TOKEN`，无需另外配置个人访问令牌。工作流已声明 `contents: write`，仍受组织策略约束。

## 2. 配置游戏输入

在新仓库打开 **Settings → Secrets and variables → Actions → New repository secret**。添加的是 **Secrets**，不是 Variables：

| Secret 名称 | 是否必需 | 填写内容 |
| --- | --- | --- |
| `GAME_INPUT_MANIFEST` | 必需 | 以下两种 JSON 清单任选一种，将地址替换为自己的文件直链 |
| `PROD_KEYS` | `packages` 需要 | 自己的 `prod.keys` 文件**完整文本内容**，不是文件路径；`prepared` 无需配置 |

两种输入**选择一种**即可，均需符合[固定配套版本](#固定配套版本)。上游要求包含「术士君临」资料片，不含资料片的版本不支持、也未验证。

### 方案 A：`packages`，本体与更新包

将 `GAME_INPUT_MANIFEST` 设置为：

```json
{
  "kind": "packages",
  "files": [
    {"name": "base.nsp", "url": "https://example.com/your-base.nsp"},
    {"name": "update.nsp", "url": "https://example.com/your-update.nsp"}
  ]
}
```

替换两个地址，提供本体和 **Switch `1.0.34.0`（`v2228224`）更新包**，同时添加 `PROD_KEYS` Secret。`packages` 是输入类型，不代表只有一个地址：`files` 可以包含多个下载项。如果一个 ZIP/7z/RAR 已同时包含本体与更新，只填写一个下载项即可，例如 `{"name": "game.zip", "url": "https://example.com/your-game.zip"}`。支持 NSP/XCI 和 RAR 分卷，不支持 NSZ。DLC 包不参与此脚本的提取。

### 方案 B：`prepared`，已解密的 ExeFS 与 RomFS

将 `GAME_INPUT_MANIFEST` 设置为：

```json
{
  "kind": "prepared",
  "files": [
    {"name": "game.zip", "url": "https://example.com/your-game.zip"}
  ]
}
```

压缩包内必须包含唯一一组同级 `ExeFS/` 和 `RomFS/` 目录，已经解密并合并指定更新，对应内部版本 **`3.3.94012`**。不能将 NSP/XCI 改名后当作此类输入。此方案不需要 `PROD_KEYS`。`packages` 流程已完整验证；`prepared` 已有实现，但尚未用独立输入压缩包做完整流程验证。

### 下载地址与清单字段

| 字段 | 含义 |
| --- | --- |
| `kind` | `packages` 或 `prepared` |
| `files` | 要下载的文件列表，至少一项 |
| `files[].name` | 唯一的本地文件名，保留正确扩展名；只能使用字母、数字、`.`、`_`、`-`，且不能以 `.` 开头 |
| `files[].url` | 直接返回文件的 HTTPS 地址；可以使用自己私有存储的签名下载链接 |
| `files[].sha256` | 普通文件可省略；填写时应为该下载文件实际的 64 位十六进制 SHA256 |

GitHub runner 无法读取你电脑上的路径。需要把自己的输入放在 GitHub Actions 可访问的存储中，并保证下载结束前链接有效。本地路径、浏览器登录页、验证码页面和网盘展示页不能使用。不要把游戏包或密钥提交到 Git，也不要将真实地址写进公开教程。含凭据的下载地址只放入 Secret；修改清单中的地址也会改变缓存身份。

需要校验下载完整性时，在每个下载项加入 `sha256`。macOS 使用 `shasum -a 256 文件名`，Linux 使用 `sha256sum 文件名` 获取。计算的是下载压缩包本身的哈希，不是解压后的内容。

高级 `.torrent` 输入需要元数据文件的 SHA256，以及明确的包序号，例如 `select: [1, 2]`。仅使用自己有权下载和处理的输入。

## 3. 先构建 IPA，再导出资源

在新仓库进入 **Actions → Build D2R Mobile IPA → Run workflow**，选择 `main`，参数如下：

| 工作流参数 | 正常构建填写 | 何时修改 |
| --- | --- | --- |
| `prepare_only` | `false`，不勾选 | `true` 仅检查工具并预热工具缓存，不下载游戏输入、不构建 IPA、不发布 Release |
| `input_revision` | `game-3.3.94012-v1` | 更换文件或修改下载项时更换；允许 1～64 个字母、数字、`.`、`_`、`-` |

等待 IPA 工作流**成功**后，再运行 **Actions → Export D2R Mobile resources → Run workflow**，选择 `main`，填写**相同的 `input_revision`**。资源工作流复用 IPA 构建保存的原始下载和工具缓存。若所需缓存已被淘汰，先重新运行完整 IPA 构建以补齐缓存，再重试资源导出。

两个工作流成功后，配套 Release 自动发布到**自己的仓库**。首次只有 IPA 时暂存为草稿，等待资源齐全。无需手动打标签、创建 Release 或配置发布令牌。私有仓库的 Release 仅对有仓库访问权限的人开放。

下载已缓存但解包失败时，修正密钥或解包问题，保留原 `input_revision` 重跑即可复用下载。如果修改了清单中的 `kind` 或 `files`，则两个工作流都使用新的修订号，避免复用不同输入。

另外提供 **Probe remote game source**（种子连通性）与 **Check PNG encoder compatibility**（尚未过期的 PNG 诊断附件）用于排错，正常构建无需运行。

## 固定配套版本

| 项目 | 当前配置 |
| --- | --- |
| 上游 | v1.0.1，提交 `ea86e79688f9339319de3e2c52c69b8b13e30e9e` |
| iOS 壳包 | 上游 v1.0.1 `D2RMobile-shell.ipa` |
| Switch 更新 | `1.0.34.0` / `v2228224` |
| 游戏内部版本 | `3.3.94012` |
| 所需版本 | 《暗黑破坏神 II：狱火重生》含「术士君临」资料片 |
| SPIRV-Cross | `1.4.357.0` |

哈希和工具提交固定在 [build-config.json](build-config.json)。不要混用其他游戏版本或其他上游壳包。导出的 18 个资源档案直接来自合并本体与更新后的 RomFS，打包时不修改内容；文件名和大小按上游清单检查，压缩前后逐文件核对 SHA256。

## 安装自己的构建产物

两个工作流成功后，进入**你自己仓库的 Releases**，在 Assets 中下载：

| 附件 | 用途 |
| --- | --- |
| `D2RMobile-unsigned.ipa` | 约 126MB，用 Sideloadly 签名并安装 |
| `D2R-Mobile-Resources.zip.001`、`.002`、`.003` | 配套资源 ZIP 的三个分卷，必须全部下载，总计约 5.42GB |
| `Resources-Parts-SHA256SUMS.txt` | 检查三个分卷是否完整 |
| `Resources-SHA256SUMS.txt` | 检查合并后的 ZIP |
| `RESOURCE-INSTALL.txt` | 分卷合并和资源导入说明 |
| `build-report.json`、`resources-report.json`、`SHA256SUMS.txt` | 版本、逐文件大小与 SHA256 等校验信息 |

GitHub 自动附带的 `Source code` 压缩包是构建脚本源码。

### 1. 安装 IPA

手机需要 **iOS 26 或以上**。用 Sideloadly 签名并安装 IPA，按系统提示完成信任设置。

**IPA 内包含游戏程序和转换后的着色器等生成内容，地图、模型、音频等大资源需要另外导入。** 只有 IPA 还不能直接游玩。

### 2. 合并资源分卷

将三个分卷和两个 `Resources-…SHA256SUMS.txt` 文件放在同一目录。

macOS：在该目录打开终端，执行：

```sh
shasum -a 256 -c Resources-Parts-SHA256SUMS.txt
cat D2R-Mobile-Resources.zip.001 D2R-Mobile-Resources.zip.002 D2R-Mobile-Resources.zip.003 > D2R-Mobile-Resources.zip
shasum -a 256 -c Resources-SHA256SUMS.txt
```

Linux 可使用 `sha256sum -c` 替代上面的 `shasum -a 256 -c`。

Windows：在分卷所在目录打开**命令提示符（cmd）**，执行：

```bat
copy /b D2R-Mobile-Resources.zip.001+D2R-Mobile-Resources.zip.002+D2R-Mobile-Resources.zip.003 D2R-Mobile-Resources.zip
```

合并后的完整 ZIP 约 5.42GB，解压后得到 `D2R Mobile Resources` 文件夹，里面有 18 个 `.data` 文件，合计 **5,561,224,037 字节（约 5.56GB）**。保留分卷、合并 ZIP 和解压文件时，需要分别为它们留出空间。

### 3. 导入手机

用数据线连接 iPhone，在 **Finder → iPhone → 文件 → D2R Mobile** 中拖入整个 `D2R Mobile Resources` 文件夹；也可以放进手机的 **文件 → 我的 iPhone → D2R Mobile**。

回到应用点击“重试”。首次启动会在手机上编译着色器，等待进度完成，耗时取决于机型。正常覆盖安装且应用标识不变时通常保留资源；卸载应用会删除资源和存档。

**本仓库产物已在 iPhone 17 Pro Max 上通过真机运行验证**，首次着色器编译约 **6 分钟**，其他机型耗时取决于设备。

## 自动发布与产物

Release 标签由游戏版本、上游提交和 `input_revision` 自动生成。同一配套版本的两个工作流更新同一个 Release；首次只有一种产物时暂存草稿，IPA、三个资源分卷及配套文件齐全后自动发布。后续同版本构建更新相应附件，版本或输入修订号变化时创建另一份 Release。

GitHub 每个 Release 附件必须小于 2GiB，因此资源 ZIP 按每卷最多 1,900,000,000 字节拆分。上传前检查本地产物 SHA256，上传后检查附件大小及 GitHub 返回的 SHA256。

Actions artifact 保留 **3 天**：IPA artifact 内有 IPA 和构建报告，资源 artifact 内是**完整资源 ZIP**和报告，不需要合并分卷。Release 附件不受 Actions artifact 的保留期影响。

## 可见性与使用权利

包含自己输入和构建产物的仓库应保持**私有**。Actions 会缓存原始游戏下载和生成内容，IPA 与资源也会上传为构建附件和 Release 附件。不要把公开仓库的缓存当作私有存储。[GitHub 缓存访问说明](https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching)

本模板仓库公开且有公开的 Release 附件。启用模板不会删除已有 Release、构建附件或缓存，也不会改变它们的访问权限。基于模板新建的仓库不继承这些内容。[GitHub 模板说明](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-repository-from-a-template)

私有构建和模板功能不授予游戏内容的使用许可，也不能保证合法。请仅使用有权使用的文件和密钥；复制、修改、绕过技术措施与分发产物可能分别受到法律限制。未经授权不要转发游戏内容。[GitHub DMCA 政策](https://docs.github.com/en/site-policy/content-removal-policies/dmca-takedown-policy)

## 缓存与校验

- **工具缓存**：SPIRV-Cross、hactool 和上游壳包。
- **原始下载缓存**：完整游戏输入和大小 / SHA256 清单，下载成功后立即保存，再读取密钥并解包。后续解包或编译失败仍可复用。
- **生成缓存**：改写后的游戏程序、着色器转换工具与结果、界面素材。
- **PNG 压缩后端和 Python 依赖缓存**：固定版本，避免生成内容变化。

原始下载缓存独立于密钥与解包脚本；修改解包流程或更换密钥不会使其失效。生成缓存按工具、配置和输入修订号区分。密钥仅写入临时目录，提取结束后删除，不进入缓存或附件。

GitHub 缓存有容量和淘汰机制，不是永久备份。云端解包前会清理临时 runner 上无关的预装 SDK，并检查至少 28GiB 空闲空间；不修改本地电脑。

公开上游源码缺少录制的启动预取表 `bootlist.tsv`。官方 v1.0.1 壳不要求该文件，改写步骤会清理构建产物中的预取文件残留。本流程逐字节复制已校验的官方壳；若清单要求预取文件，或最终 IPA 残留旧预取文件，则停止构建。构建报告记录 `startup_prefetch: false` 和壳的着色器链标识，未启用这项启动加速优化。
