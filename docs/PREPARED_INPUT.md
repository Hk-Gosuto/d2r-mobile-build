# Prepared package

[English](PREPARED_INPUT.md) | [简体中文](PREPARED_INPUT.zh-CN.md)

Supply an HTTPS link to a ZIP, tar.gz, or tar.xz package in the `PREPARED_INPUT` Secret’s `ios` object. The required files are shown below; one enclosing directory is supported.

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

| File | Contents |
|---|---|
| `prepared.json` | Format `d2r-mobile-prepared`, schema `1`, game versions, program checksums, payload metadata and each file’s size and SHA-256. `producer.source_commit` identifies the source used to generate the package. |
| `source-payload.zip` | Generated game program, interface resources, overlays and binary iOS Metal libraries under `Payload/DmIOS.app/`. |
| `shader-chain.lock` | Shader toolchain fingerprints. |
| `resource-manifest.json` | Names, sizes and checksums of the 18 Data files for this game resource version, shared by iOS and macOS. |
| `generated/` | Headers and native artwork source required for compilation. |

The build checks package integrity, game programs, resource metadata, and shader consistency. It compares generation dependencies with `producer.source_commit` in the selected source repository. Native runtime changes can reuse the package; changes to generation rules require a matching updated package.

The workflow downloads this package and compiles the selected source into two IPAs. Download Data and the Legacy Device Pack separately from your resource provider, then follow the [installation instructions](../README.md#download-and-use-on-ios).
