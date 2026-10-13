# D2R Mobile · GitHub Actions Builds

**English** | [简体中文](README.zh-CN.md)

[![Build IPA](https://github.com/jiayx/d2r-mobile-build/actions/workflows/pack.yml/badge.svg)](https://github.com/jiayx/d2r-mobile-build/actions/workflows/pack.yml)
[![Export resources](https://github.com/jiayx/d2r-mobile-build/actions/workflows/resources.yml/badge.svg)](https://github.com/jiayx/d2r-mobile-build/actions/workflows/resources.yml)

Build an unsigned IPA and matching Data resources with GitHub Actions, using the **NO_XCODE** approach from [jhaizhou-ops/d2r-mobile](https://github.com/jhaizhou-ops/d2r-mobile). Download a build from Releases or run your own build below.

## Download and install

Open the **[latest Release](https://github.com/jiayx/d2r-mobile-build/releases/latest)** and download:

| File | Purpose |
| --- | --- |
| `D2RMobile-unsigned.ipa` | About 126 MB; sign and install with Sideloadly |
| `D2R-Mobile-Resources.zip.001`, `.002`, `.003` | Download all three resource parts, totaling about 5.42 GB |
| `Resources-Parts-SHA256SUMS.txt`, `Resources-SHA256SUMS.txt` | Verify the parts and combined ZIP |
| `RESOURCE-INSTALL.txt` | Resource combining and import instructions |

The `Source code` archives are build scripts, not the installation package.

### 1. Install the IPA

Requires **iOS 26 or later**, with an **A17 Pro or newer chip, or an M-series iPad**. This package does not include the additional texture pack needed by A16 and earlier devices.

Sign and install `D2RMobile-unsigned.ipa` with Sideloadly, then complete the trust setup prompted by iOS. **The IPA must be used with the Data resources below.**

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

Open the app and tap **Retry**. On the first launch, wait for shader compilation to finish. The reference time is **about 6 minutes on iPhone 17 Pro Max**; other devices vary. The current v1.0.6 package has not yet been verified on a physical device.

When updating the IPA, reuse the existing Data if the matching resource version is unchanged. Installing over an existing installation with the same app identifier usually preserves resources and saves. **Uninstalling the app deletes them.**

## Matching versions

| Component | Version |
| --- | --- |
| Upstream | v1.0.6 |
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

### 3. Build the IPA and Data

1. Open **Actions → Build D2R Mobile IPA → Run workflow**, select `main`, and use the settings below.
2. Wait for success, then run **Export D2R Mobile resources** with the same `input_revision`.
3. After both succeed, download the files from **Releases in your own repository**. Publishing is automatic; the Release stays a draft until the IPA and Data are both ready.

| Input | Setting |
| --- | --- |
| `prepare_only` | `false` — leave unchecked |
| `input_revision` | `game-3.3.94012-v1` — use the same value in both workflows |

Change `input_revision` in both workflows if you replace the game files or edit the torrent download entry. If resource export reports a missing cache, rerun the IPA build first, then retry resource export.

You can also download outputs from each successful Actions run. These artifacts are retained for **3 days**; the resource artifact contains the **complete ZIP**, so part combining is not needed.
