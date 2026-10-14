# d2r-mobile build workflow

[English](README.md) | [简体中文](README.zh-CN.md)

Build your own IPA and Data from [jhaizhou-ops/d2r-mobile](https://github.com/jhaizhou-ops/d2r-mobile) source using GitHub Actions. Supply one HTTPS archive containing your own prepared ExeFS/RomFS. The workflow downloads and caches it, compiles both iOS variants, and saves the results in your private repository's Releases.

This repository provides build tools and a template. It does not provide game files, decryption keys, or downloadable game builds. Use only inputs you have the right to use.

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

A single enclosing folder is also supported. The phone's 18 Data archives alone are insufficient to build an IPA. Do not include keys or credentials in the archive.

Store the archive on your own storage and obtain an **HTTPS direct download URL**. Signed URLs are supported; keep the URL valid until the download finishes. A browser sharing page, Google Drive folder link, login page, or HTML confirmation page is not a direct download. For Google Drive, use an authorized direct download URL that returns the archive without an interactive login. This workflow does not perform Google login or obtain game files for you.

If you want to fill in the optional `sha256`, calculate it with:

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
2. Open **Settings → Secrets and variables → Actions → New repository secret**. Create one secret named **`GAME_ARCHIVE`**, with this JSON as its value (replace `url` with your direct download URL):

   ```json
   {
     "url": "https://your-storage.example/game-input.zip",
     "sha256": ""
   }
   ```

   `url` is required. `sha256` is optional: leave it empty, set it to `null`, or omit it to skip the input archive's SHA-256 comparison. When supplied, it must contain 64 hexadecimal characters. Archive extraction, game-version checks, and output verification still run.

3. If your organization restricts Actions, allow this repository's reusable workflow and the actions it calls.

No `prod.keys`, Apple ID, signing certificate, or paid Apple developer account is needed for the build. Signing happens separately when installing.

## 3. Run the build

In your repository, open **Actions → Build IPA and Data → Run workflow**. Leave the source fields unchanged to build the supported release.

To test another source revision, set `source_repository` to the upstream repository or a public fork, and `source_ref` to a branch, tag, or commit. A source revision must remain compatible with the supported game input. The build records the exact source and tools commits.

The native app is compiled on **macOS 26 with iOS SDK 26.4 or newer**. Both variants are built from source; no prebuilt upstream shell is required. Build time varies; the first Legacy texture conversion can take substantially longer than subsequent builds.

## 4. Download and install

After a successful run, open **Releases in your own repository**. The latest app Release contains:

| File | Use |
|---|---|
| `D2RMobile-<version>.ipa` | iOS 26 and later |
| `D2RMobile-<version>-ios18.ipa` | iOS 18–25 |
| `SHA256SUMS.txt`, `build-report.json` | Checksums and build details |

Custom source builds include the source commit in the filename. The Release description links to your matching Data and Legacy Device Pack. Those files may be stored in an earlier Release in your repository when their contents are unchanged.

1. Sign and install the matching IPA using [Sideloadly](https://sideloadly.io/), [iloader](https://iloader.app/), [AltStore Classic](https://faq.altstore.io/altstore-classic/your-altstore), or [SideStore](https://sidestore.io/).
2. Download all three `D2R-Mobile-Resources.zip.001`–`.003` parts from your linked Data Release. Follow `RESOURCE-INSTALL.txt` to join them, extract the ZIP, and copy the `D2R Mobile Resources` folder into the app using Finder or Files.
3. **A16 and earlier devices** also need the linked `Legacy-Device-Pack.zip`. Extract it and import the entire `Legacy Device Pack` folder beside the resource folder. A17 Pro and newer devices and M-series iPads do not need this additional pack.
4. Open the app and import/select the resource folder. Initial shader compilation takes several minutes; approximately 6 minutes is a reference for iPhone 17 Pro Max.

The IPA is unsigned. Automated verification does not replace testing on your device. Keep the app identifier consistent when updating, and back up your saves before installing. Uninstalling the app deletes its local resources and saves.

## Updates and reuse

Your build entry calls the centrally maintained workflow on `main`. A newly started run uses its current tools and supported release; you do not need to copy updated scripts into your repository. Your `GAME_ARCHIVE` secret remains in your repository. Interface changes, if any, are documented here.

- The completed original archive is cached **before extraction**, so extraction or compilation failures do not require another download while the cache is available.
- Game program and resource checks reject incompatible or incomplete input.
- Matching Data is reused from your own Releases without downloading, compressing, splitting, or uploading it again. Existing phone Data can remain when its contents are unchanged.
- Matching Legacy packs are restored from your own Releases without converting or uploading them again.
- GitHub can evict caches. Keep your source archive available. Update `GAME_ARCHIVE` when replacing the input. With `sha256` set, renewing the URL for an identical file retains the same cache. Without `sha256`, the full URL identifies the cache: changing the URL creates a new cache; replacing the file at the same URL requires clearing its input cache under **Actions → Caches**.
- Retain older Data and Legacy Releases referenced by your app Releases. They are private to your repository and do not depend on downloads from this project's Releases.

The template includes the tool source for reference, but the build executes the tools from the central workflow's exact commit. Personal source modifications belong in the selected source fork.

Build tooling is licensed under [MIT](LICENSE). Upstream and third-party code retain their respective licenses; these licenses do not grant rights to game content.
