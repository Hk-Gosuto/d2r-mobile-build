# D2R Mobile 私有远端构建

GitHub Actions 在临时云端机器上完成 NO_XCODE 打包，输出未签名 IPA。源代码仓库不保存游戏文件、主机密钥或 IPA。

固定配套：上游 v1.0（46578a2b）、v1.0 壳包、Switch 1.0.34.0/v2228224（内部版本 3.3.94012）、SPIRV-Cross 1.4.357.0。版本和哈希登记在 build-config.json。

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

密钥只写入 runner 临时目录，提取结束即删除，密钥和原始下载包不进入缓存。

## 运行

Actions → Build D2R Mobile IPA → Run workflow。

- `prepare_only=false`：真正下载、校验、打包并上传 IPA。
- `prepare_only=true`：只编译验证工具链并预热缓存，不代表 IPA 已完成。
- `input_revision`：通常保留默认值；替换资源文件时修改它，使资源及中间产物缓存同时失效。

成功后下载 `D2RMobile-unsigned-<运行号>` artifact，包含 IPA、SHA256SUMS.txt、build-report.json。产物保留 3 天。

## 缓存

1. `.tools`：固定版本的 SPIRV-Cross、hactool、官方壳包。
2. `.dm-work/data/.../Update`：校验通过的合并游戏文件。命中后跳过下载和解包；每次仍核对程序哈希及资源大小。
3. `.dm-work/build/cache`、`build/gfx`、`build/ios` 和生成素材：游戏程序改写、着色器提取、翻译器、着色器库及界面素材。
4. Python 下载由 setup-python 缓存。

缓存全部位于私有仓库的 Actions 存储，和 Git 提交历史无关。GitHub 缓存有配额和淘汰机制，不是永久网盘；被淘汰后工作流会重新下载。原始资源量较大，需关注仓库缓存额度。工作流先移除临时 runner 上用不到的 Android/Swift/Haskell SDK，并要求至少 28 GiB 空闲空间；不修改你的本地电脑。

生成缓存按上游/工具锁定配置、依赖版本、操作系统、输入修订号区分，避免混用不同版本。失败的打包不保存不完整生成缓存，但已验证的游戏资源提前保存，修复后不必重新下载。

Ubuntu 是此自动化选择的构建平台。上游文档声明 Linux 做包尚未验证；只有实际运行成功且通过 IPA 校验，才证明本工作流的 Linux 做包路径已验证。工具链预热成功不足以证明完整游戏构建成功。
