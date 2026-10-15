# Prepared input package / 预处理包

[English README](../README.md) | [中文 README](../README.zh-CN.md)

The workflow accepts a ZIP, tar.gz, or tar.xz containing this layout, optionally inside one enclosing directory:

工作流接受 ZIP、tar.gz 或 tar.xz，目录如下；允许外面再套一层文件夹：

```text
prepared.json
source-payload.zip
shader-chain.lock
generated/
  host/dm_vault_tab.h
  host/dm_hud_exp.h
  host/dm_bright_levels.inc
  ios/Sources/dm_touch_native_art.c
resource-manifest.json
resources.json
legacy-resources.json
```

- `source-payload.zip`: generated game program, interface resources, overlays, and binary iOS Metal libraries. / 已生成的游戏程序、界面素材、覆盖层和二进制 iOS Metal 着色器。
- `shader-chain.lock`: tool fingerprints corresponding to the compiled shader chain. / 该着色器链对应的工具指纹。
- `generated/`: game-derived inputs used by the fresh native compilation. / 编译最新原生源码时使用的生成文件。
- `resource-manifest.json`: identities, sizes, and checksums of the required phone resources. / 手机资源的内容标识、大小和校验值。
- `resources.json`, `legacy-resources.json`: matching Data and Legacy download descriptors. Their links can point to HTTPS storage or Google Drive and must be accessible to the package's users. / 配套 Data 与 Legacy 下载描述，可指向 HTTPS 存储或 Google Drive，使用者需有权下载。
- `prepared.json`: schema, producer provenance, per-file checksums, and generation compatibility fingerprints. / 格式、生成来源、各文件校验值和生成规则的兼容性指纹。

Data and Legacy archives stay at the described download locations. The prepared package carries their metadata; builds reuse those links in the new IPA Release. Native runtime sources come from the selected upstream checkout on every run.

Data 和 Legacy 大文件保留在描述文件指向的下载位置。预处理包携带其元数据，新 IPA Release 沿用这些链接；每次构建的原生运行时代码来自当次选择的上游源码。

## Export / 导出

In a private producer workflow, after payload generation and Metal precompilation have completed, run from the build workspace root:

在自己的私有生成工作流中，游戏 payload 和 Metal 预编译完成后，在构建工作区根目录执行：

```sh
python scripts/source/prepared.py export
```

The exporter reads `outputs/source-payload.zip`, `outputs/source-input-report.json`, resource descriptors in `outputs/`, and the generated files and shader lock in `upstream/dm`. It verifies them together, then writes:

导出工具读取 `outputs/source-payload.zip`、`outputs/source-input-report.json`、`outputs/` 中的资源描述，以及 `upstream/dm` 中的生成文件和着色器锁文件；完成一致性校验后生成：

```text
outputs/D2RMobile-Prepared.zip
outputs/Prepared-SHA256SUMS.txt
```

Upload these two files to your storage and use their links in `PREPARED_INPUT`. Resource download locations can be adjusted in the descriptors before exporting; the exporter validates their identities and file checksums.

将这两个文件存到自己的存储空间，把链接填入 `PREPARED_INPUT`。导出前可在描述文件中调整资源下载地址；导出工具会校验资源身份和文件校验信息。

## Compatibility / 兼容性

The package records the game program checksums, resource identities, game product, shader chain, and generation dependencies. Runtime-only changes can reuse it. A change to a tracked generation rule requires a newly generated package. App version, source commit, build number, and Release names are resolved afresh by the consuming workflow.

预处理包记录游戏程序校验值、资源身份、游戏产品标识、着色器链和生成依赖。只改运行时代码时可继续复用；被跟踪的生成规则发生变化时需更新包。App 版本、源码提交、构建编号和 Release 名称由使用者当次运行重新确定。
