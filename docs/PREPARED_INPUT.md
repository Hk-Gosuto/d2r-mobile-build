# Prepared package / 预处理包

[English](../README.md) | [简体中文](../README.zh-CN.md)

Supply an HTTPS link to a ZIP, tar.gz, or tar.xz package in the `PREPARED_INPUT` Secret. The required files are shown below; one enclosing directory is supported.

在 `PREPARED_INPUT` Secret 中填写 ZIP、tar.gz 或 tar.xz 预处理包的 HTTPS 链接。必需文件如下，允许外面再套一层文件夹。

```text
prepared.json
source-payload.zip
shader-chain.lock
resource-manifest.json
generated/
  host/dm_vault_tab.h
  host/dm_hud_exp.h
  host/dm_bright_levels.inc
  ios/Sources/dm_touch_native_art.c
```

| File / 文件 | Contents / 内容 |
|---|---|
| `prepared.json` | Format `d2r-mobile-prepared`, schema `1`, game versions, program checksums, payload metadata and each file’s size and SHA-256. `producer.source_commit` identifies the source used to generate the package. / 格式标识、版本号 `1`、游戏版本、程序校验值、payload 元数据及各文件大小和 SHA-256。`producer.source_commit` 标识生成此包时的源码提交。 |
| `source-payload.zip` | Generated game program, interface resources, overlays and binary iOS Metal libraries under `Payload/DmIOS.app/`. / `Payload/DmIOS.app/` 下已生成的游戏程序、界面素材、覆盖层和二进制 iOS Metal 着色器。 |
| `shader-chain.lock` | Shader toolchain fingerprints. / 着色器工具链指纹。 |
| `resource-manifest.json` | Names, sizes and checksums of the matching phone Data files. / 配套手机 Data 文件的名称、大小和校验值。 |
| `generated/` | Headers and native artwork source required for compilation. / 原生编译所需的头文件和界面素材源码。 |

The build checks package integrity, game programs, resource metadata, and shader consistency. It compares generation dependencies with `producer.source_commit` in the selected source repository. Native runtime changes can reuse the package; changes to generation rules require a matching updated package.

构建会检查包完整性、游戏程序、资源元数据和着色器的一致性，并在所选源码仓库中对照 `producer.source_commit` 检查生成依赖。原生运行时代码修改可复用此包；生成规则变化时需使用配套的新包。

The workflow downloads this package and compiles the selected source into two IPAs. Download Data and the Legacy Device Pack separately from your resource provider, then follow the [installation instructions](../README.md#download-and-use).

工作流下载此包，并将所选源码编译成两份 IPA。Data 和 Legacy Device Pack 从资源提供者的网盘另行下载，导入方式见[安装说明](../README.zh-CN.md#下载和使用)。
