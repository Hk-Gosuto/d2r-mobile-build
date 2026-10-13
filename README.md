# D2R Mobile · GitHub Actions Builds

**English** | [简体中文](README.zh-CN.md)

[![Build IPA](https://github.com/jiayx/d2r-mobile-build/actions/workflows/pack.yml/badge.svg)](https://github.com/jiayx/d2r-mobile-build/actions/workflows/pack.yml)

Build an unsigned IPA and matching Data resources with GitHub Actions, using the **NO_XCODE** approach from [jhaizhou-ops/d2r-mobile](https://github.com/jhaizhou-ops/d2r-mobile). Download a build from Releases or run your own build below.

## Download and install

Open the **[latest Release](https://github.com/jiayx/d2r-mobile-build/releases/latest)**. Download the IPA from its **Assets** and the Data files from the direct download links under **配套 Data** in the Release description:

| File | Where | Purpose |
| --- | --- | --- |
| `D2RMobile-unsigned.ipa` | Assets | iOS 26+; sign and install with Sideloadly |
| `D2RMobile-ios18-unsigned.ipa` | Assets | iOS 18–25, Metal 3 compatibility build |
| `Legacy-Device-Pack.zip` | Legacy Device Pack link in the Release description | Additional textures for A16 and earlier devices; about 1 GB |
| `D2R-Mobile-Resources.zip.001`, `.002`, `.003` | Data links in the Release description | Download all three resource parts, totaling about 5.42 GB |
| `Resources-Parts-SHA256SUMS.txt`, `Resources-SHA256SUMS.txt` | Data links in the Release description | Verify the parts and combined ZIP |
| `RESOURCE-INSTALL.txt` | Assets | Resource combining and import instructions |

The `Source code` archives are build scripts, not the installation package.

### 1. Install the IPA

Choose by system: **iOS 26+** uses `D2RMobile-unsigned.ipa`; **iOS 18–25** uses `D2RMobile-ios18-unsigned.ipa`. The compatibility build can also be tested on iOS 26+ when investigating graphics problems; it is not a confirmed fix for system crashes.

Both packages support **A17 Pro and newer chips, M-series iPads, and A16 and earlier chips with the matching Legacy Device Pack**. Older devices still need enough memory; support does not guarantee every model runs reliably.

Sign and install the selected IPA with Sideloadly, then complete the trust setup prompted by iOS. The two variants share an app identifier, so installing one replaces the other. **The IPA must be used with the Data resources below.**

### 2. Combine and extract Data

Place all three parts and both checksum files in the same directory.

On macOS, open a terminal in that directory and run:

```sh
shasum -a 256 -c Resources-Parts-SHA256SUMS.txt
cat D2R-Mobile-Resources.zip.001 D2R-Mobile-Resources.zip.002 D2R-Mobile-Resources.zip.003 > D2R-Mobile-Resources.zip
shasum -a 256 -c Resources-SHA256SUMS.txt
```

On Linux, use `sha256sum -c` instead of `shasum -a 256 -c`.

On Windows, open **Command Prompt (cmd)** in the directory and run:

```bat
copy /b D2R-Mobile-Resources.zip.001+D2R-Mobile-Resources.zip.002+D2R-Mobile-Resources.zip.003 D2R-Mobile-Resources.zip
```

Extract the combined ZIP to get a `D2R Mobile Resources` folder containing **18 `.data` files, about 5.56 GB**.

### 3. Import Data and launch

Connect your iPhone by cable. In **Finder → iPhone → Files → D2R Mobile**, drag in the entire `D2R Mobile Resources` folder. Alternatively, place the folder in **Files → On My iPhone → D2R Mobile** on the phone.

For **A16 and earlier devices**, also download `Legacy-Device-Pack.zip` from the link in this IPA Release. Extract it and copy the entire `Legacy Device Pack` folder beside `D2R Mobile Resources` inside the app. Use the pack linked by your IPA Release; both system variants share that pack. A17 Pro and newer devices and M-series iPads do not need it.

Open the app and tap **Retry**. On the first launch, wait for shader compilation to finish. The reference time is **about 6 minutes on iPhone 17 Pro Max**; other devices vary. The current v1.0.7 package has not yet been verified on a physical device.

When updating the IPA, reuse the existing Data if the matching resource version is unchanged. Installing over an existing installation with the same app identifier usually preserves resources and saves. **Uninstalling the app deletes them.**

## Matching versions

| Component | Version |
| --- | --- |
| Upstream | v1.0.7 |
| Switch update | `1.0.34.0` / `v2228224` |
| Internal game version | `3.3.94012` |
| Required edition | Includes Reign of the Warlock |

## Run your own build

### 1. Fork the repository

Click **Fork** to create your copy, then open **Actions** and enable workflows if prompted. Use game files and keys you are authorized to use.

### 2. Configure the input

In your repository, open **Settings → Secrets and variables → Actions → New repository secret**. Name it **`GAME_INPUT_MANIFEST`** and paste the complete JSON below. The download URLs and SHA256 values are already filled in:

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

The torrent contains the base game and update, selected by `select: [1, 2]`. `key_archive` is the ZIP containing extraction keys. No separate `PROD_KEYS` Secret is needed with this configuration.

### 3. Run the build

Open **Actions → Build D2R Mobile IPA → Run workflow**, select `main`, and use:

| Input | Setting |
| --- | --- |
| `prepare_only` | `false` — leave unchecked |
| `input_revision` | `game-3.3.94012-v1` — change when replacing game files or editing the torrent download entry |

**Run this workflow once.** It builds both IPA variants with legacy-device support and publishes the Release automatically. Existing Data is reused without recompressing or uploading it; missing or changed Data is packaged and published automatically. The matching Legacy Device Pack is also generated once and reused by later builds when its inputs and conversion settings match.

After success, open **Releases in your own repository**. The Release description provides direct links to the matching Data parts and checksums, even when those files are hosted in an earlier Release. Download and import them as described above. If the resource identifier matches the Data already on your phone, updating the IPA does not require downloading Data again.

Keep the Releases hosting the referenced Data and Legacy Device Pack, including their attachments so its download links remain available.

The Actions run summary also links to the IPA and Data. The IPA artifact contains both installation packages, resource download information (`resources.json` and `legacy-resources.json`), and import instructions, and is retained for **3 days**.
