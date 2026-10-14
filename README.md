# d2r-mobile build workflow

[English](README.md) | [简体中文](README.zh-CN.md)

Build your own IPA and Data from [jhaizhou-ops/d2r-mobile](https://github.com/jhaizhou-ops/d2r-mobile) source using GitHub Actions. Supply one HTTPS archive containing your own prepared ExeFS/RomFS. The workflow downloads and caches it, compiles both iOS variants, and saves the results in your private repository's Releases.

## 1. Prepare the input archive

Supported game: **3.3.94012**, Switch update **1.0.34.0**, including the required expansion. Use the complete, decrypted ExeFS and RomFS with the base game and update already combined. See the upstream [game-file requirements](https://github.com/jhaizhou-ops/d2r-mobile/blob/main/docs/GAME_FILES.md).

Create a **ZIP, tar.gz, or tar.xz** containing:

```text
ExeFS/
  main
  sdk
  subsdk0
RomFS/
  data/
    build_manifest.psv
    ...complete game resources...
```

A single enclosing folder is also supported.

Upload the archive to your own storage and obtain an **HTTPS URL that directly downloads the file**. For signed URLs, set an expiry that covers the entire download.

Calculate the archive's SHA-256:

```sh
# macOS
shasum -a 256 game-input.zip
# Linux
sha256sum game-input.zip
```

Windows PowerShell:

```powershell
(Get-FileHash .\game-input.zip -Algorithm SHA256).Hash
```

## 2. Create your build repository

1. Select [Use this template](https://github.com/jiayx/d2r-mobile-build/generate), choose **Create a new repository**, and set its visibility to **Private**.
2. Open **Settings → Secrets and variables → Actions → New repository secret**. Create a secret named **`GAME_ARCHIVE`**, with this JSON as its value (replace `url` with your direct download URL and `sha256` with the checksum calculated above):

   ```json
   {
     "url": "https://your-storage.example/game-input.zip",
     "sha256": "YOUR_ARCHIVE_SHA256"
   }
   ```

## 3. Run the build

In your repository, open **Actions → Build IPA and Data → Run workflow**. Leave `source_ref` empty to automatically build the latest official upstream Release.

To test the latest development code, set `source_ref` to `main`. You can also enter another branch, tag, or commit, or set `source_repository` to your public fork. Choose a source revision compatible with your game input.

The first build includes Legacy texture conversion and takes longer. Subsequent builds reuse existing resources.

## 4. Download and install

After a successful run, open **Releases in your own repository**. The latest app Release contains:

| File | Use |
|---|---|
| `D2RMobile-<version>.ipa` | iOS 26 and later |
| `D2RMobile-<version>-ios18.ipa` | iOS 18–25 |
| `SHA256SUMS.txt`, `build-report.json` | Checksums and build details |

Filenames use the source tag; builds after a tag also include the source commit. Sources without a version tag use the commit. The Release description links to your matching Data and Legacy Device Pack.

1. Sign and install the matching IPA using [Sideloadly](https://sideloadly.io/), [iloader](https://iloader.app/), [AltStore Classic](https://faq.altstore.io/altstore-classic/your-altstore), or [SideStore](https://sidestore.io/).
2. Download all three `D2R-Mobile-Resources.zip.001`–`.003` parts from your linked Data Release. Follow `RESOURCE-INSTALL.txt` to join them, extract the ZIP, and copy the `D2R Mobile Resources` folder into the app using Finder or Files.
3. **A16 and earlier devices** also need the linked `Legacy-Device-Pack.zip`. Extract it and import the entire `Legacy Device Pack` folder beside the resource folder. A17 Pro and newer devices and M-series iPads use the standard Data.
4. Open the app and import/select the resource folder. Initial shader compilation takes several minutes; approximately 6 minutes is a reference for iPhone 17 Pro Max.

When updating, keep the same app identifier, back up your saves, and install the new IPA over the existing app.

## Updates and reuse

Run **Build IPA and Data** again with `source_ref` empty to build the latest official upstream Release using this project's latest build tools. Keep your existing `GAME_ARCHIVE` configuration when using the same input files.

- The original archive is cached **before extraction**; retries reuse completed downloads.
- When Data contents match, the Release links to your existing Data. Keep using the resources already imported on your phone.
- Matching Legacy conversion inputs and settings reuse your existing Legacy pack.
- Retain older Data and Legacy Releases referenced by your app Releases.
- Keep the original archive; update the URL and checksum in `GAME_ARCHIVE` when replacing the input.

Build tooling is licensed under [MIT](LICENSE). Upstream and third-party code retain their respective licenses.
