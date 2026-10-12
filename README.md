# D2R Mobile 私有远端构建

GitHub Actions 在临时云端机器上完成 NO_XCODE 打包，输出未签名 IPA。源代码仓库不保存游戏文件、主机密钥或 IPA。

固定配套：上游 v1.0（46578a2b）、v1.0 壳包、Switch 1.0.34.0/v2228224（内部版本 3.3.94012）、SPIRV-Cross 1.4.357.0。版本和哈希登记在 build-config.json。

## 单独导出手机游戏资源

运行 Actions 的 **Export D2R Mobile resources**，沿用已有的 `input_revision`。它只恢复原始下载和解包工具缓存，重新解包、验证版本，导出手机需要的 18 个 `.data` 文件；不会重新下载游戏或编译 IPA。缓存缺失时会停止，避免意外重复下载。

产物 `D2R-Mobile-Resources.zip` 内含 `D2R Mobile Resources/data/`、逐文件 SHA256 和中文导入说明。资源合计 5,561,224,037 字节，导出后逐个读取 ZIP 中的文件并核对大小和 SHA256。下载解压后，把整个 `D2R Mobile Resources` 文件夹通过 Finder → iPhone → 文件 → D2R Mobile 拷入应用，打开应用点击重试。正常覆盖安装且应用标识不变时通常保留资源；卸载会删除资源和存档。

Actions artifact 保留 3 天；成功构建也会自动上传到下述私有 Release，Release 附件不受 artifact 保留期影响。源码仓库不提交游戏资源，IPA 不包含这 18 个大文件。

## 自动发布 Release

IPA 构建和资源导出成功后会自动发布对应附件，不需要另外点发布按钮或填写版本号。Release 标签由游戏版本、上游提交和 `input_revision` 自动生成；同一配套版本的两个工作流更新同一个 Release。第一次只有一种产物时暂存为草稿，IPA 和资源附件齐全后自动发布。`prepare_only` 不发布。

资源 ZIP 自动分成 3 个小于 2GiB 的分卷，并附上 `Resources-Parts-SHA256SUMS.txt`、原始 ZIP 校验值和 `RESOURCE-INSTALL.txt`。下载所有分卷后按说明合并、校验，再解压导入手机。同版本后续构建更新对应附件；如果更换游戏输入，修改 `input_revision`，避免混用资源。发布前校验版本和本地产物 SHA256，上传后核对附件大小及 GitHub 返回的 SHA256（如有）。

引入发布流程的提交会自动从已有成功构建恢复 IPA 和资源包，完成首次发布，不重新下载游戏或编译。源仓库必须保持私有，发布步骤才会运行。

## 提供远端输入

在这个私有仓库 Settings → Secrets and variables → Actions 设置 `GAME_INPUT_MANIFEST`。下载地址必须能直接返回文件；带验证码的页面或网盘展示页不能直接用于无人值守构建。临时签名地址可用，缓存失效后需要更新。

方案 A：已解密的游戏目录压缩包，不需要密钥：

```json
{
  "kind": "prepared",
  "files": [
    {"name": "game.zip", "url": "https://你的私有存储/game.zip", "sha256": "可选的64位SHA256"}
  ]
}
```

压缩包中需要一个完整的 `ExeFS/`、`RomFS/` 目录对。RomFS 必须来自本体与指定更新的合并结果；程序必须是原版未修改文件。删除示例中的 sha256 字段，或填真实的完整哈希。

方案 B：本体与更新的 NSP/XCI（可分别打包或合并在同一个包），还需要设置 `PROD_KEYS` secret，内容为你自己主机导出的 prod.keys 全文：

```json
{
  "kind": "packages",
  "files": [
    {"name": "base.nsp", "url": "https://你的私有存储/base.nsp"},
    {"name": "update.nsp", "url": "https://你的私有存储/update.nsp"}
  ]
}
```

支持 zip/rar/7z 包装及 `.part1.rar`、`.part2.rar` 形式的 RAR 分卷，所有分卷都需登记。NSZ 目前不支持；请提供 NSP/XCI 或已解密目录。DLC 包不参与此脚本的提取。程序先按三个 SHA256 核对版本，再按上游清单核对 18 个资源档案的字节数。

也支持可直接获取的 `.torrent` 元数据文件。该项必须固定 `sha256`，并用 `select: [1, 2]` 这样的数组明确指定要下载的包序号；可用 `aria2c --show-files` 查看序号。下载完整后立刻保存原始包缓存，然后才读取密钥、解包和校验游戏版本。下载不完整不保存缓存。种子连通性可通过单独的 Probe remote game source 工作流测试。

密钥只写入 runner 临时目录，提取结束即删除，密钥不进入缓存。原始下载包单独缓存，解包失败后仍可复用。

如果已明确授权使用某个远端密钥归档，也可在输入清单中设置 `key_archive: {"url": "https://.../keys.zip", "sha256": "归档的完整SHA256"}`，不设置 `PROD_KEYS`。归档先校验哈希与格式，读取后立即删除；NSP 内的普通票据仅用于当前解包，并在结束后删除。此项不会把密钥归档缓存或提交到 Git。

## 运行

Actions → Build D2R Mobile IPA → Run workflow。

- `prepare_only=false`：真正下载、校验、打包并上传 IPA。
- `prepare_only=true`：只编译验证工具链并预热缓存，不代表 IPA 已完成。
- `input_revision`：通常保留默认值；替换资源文件时修改它，使资源及中间产物缓存同时失效。

成功后下载 `D2RMobile-unsigned-<运行号>` artifact，包含 IPA、SHA256SUMS.txt、build-report.json。产物保留 3 天。

## 缓存

1. `.tools`：固定版本的 SPIRV-Cross、hactool、官方壳包。
2. `.game-downloads`：完整下载的本体、更新包或资源压缩包，以及校验清单。独立步骤在解包前保存，并确认缓存已经存在；后续密钥、解包或编译失败都不影响它。恢复时核对文件大小与 SHA256，跳过远端下载后重新解包。为节省配额，新流程不再同时保存一份解包后的大资源缓存；已有的旧版合并资源缓存仍可恢复使用。
3. `.dm-work/build/cache`、`build/gfx`、`build/ios` 和生成素材：游戏程序改写、着色器提取、翻译器、着色器库及界面素材。
4. Python 下载由 setup-python 缓存。

缓存全部位于私有仓库的 Actions 存储，和 Git 提交历史无关。GitHub 缓存有配额和淘汰机制，不是永久网盘；被淘汰后工作流会重新下载。原始资源量较大，需关注仓库缓存额度。工作流先移除临时 runner 上用不到的 Android/Swift/Haskell SDK，并要求至少 28 GiB 空闲空间；不修改你的本地电脑。

生成缓存按上游/工具锁定配置、依赖版本、操作系统、输入修订号区分，避免混用不同版本。原始下载缓存按操作系统与输入修订号区分，独立于密钥及解包脚本；修复解包或更换密钥不会使下载缓存失效。失败的打包不保存不完整生成缓存，但下载完整的原始包已经提前保存，修复后不必重新下载。

复用已由 [第二次成功构建 38251016443](https://github.com/jiayx/d2r-mobile-build/actions/runs/38251016443) 实测：原始下载缓存与完整生成缓存均命中；游戏程序改写、162 个着色器包提取、翻译器编译及全部着色器翻译均显示“已有，跳过”。IPA 生成与校验步骤从首次约 7 分 54 秒降为约 1 分 5 秒；完整流程仍需恢复缓存和重新解包。两次成功构建后，9,060,449,631 字节的原始下载缓存和 333,420,059 字节的生成缓存都仍存在。

Ubuntu 是此自动化选择的构建平台。完整 NO_XCODE 做包已在 [运行 38249053001](https://github.com/jiayx/d2r-mobile-build/actions/runs/38249053001) 成功，产物为 `D2RMobile-unsigned-15`。程序原件、PNG、着色器源码摘要、完整包清单及 ZIP CRC 都通过校验；尚未做手机上的运行测试。工具链预热成功本身不足以证明完整游戏构建成功。

Pillow 固定为上游使用的 12.1.1，PNG 生成进程显式加载固定提交、校验源码 SHA256 的 zlib-ng 2.3.2。小样本云端检查已验证该组合能复现上游冻结的 PNG 字节哈希；系统 zlib 编码的像素相同，但压缩字节不同。打包前先检查所有原始技能图集与生成 PNG 的哈希，保留上游严格校验；若不匹配，单独上传一个小型 PNG 兼容性诊断样本。

上游公开源码不包含录制的启动预取表 `bootlist.tsv`，其运行时明确支持缺表时跳过预取；发布壳的清单却把它列为必需项。本流程校验原始壳 SHA256 后生成一份临时壳，只从内容清单移除该可选表，保留每个其他文件的原始字节和全部其他必需项。最终包也核对这份修正后的清单。不会伪造空表（运行时会拒绝空表）。`build-report.json` 中明确标记 `startup_prefetch: false`，没有这项启动加速优化。
