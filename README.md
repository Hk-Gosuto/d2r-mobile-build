# d2r-mobile build workflow

[English](README.md) | [简体中文](README.zh-CN.md)

Build your own IPA and Data from [jhaizhou-ops/d2r-mobile](https://github.com/jhaizhou-ops/d2r-mobile) source using GitHub Actions. Supply an archive containing your prepared ExeFS/RomFS and its SHA256SUMS file, using HTTPS download URLs or Google Drive file share links. The workflow downloads and caches the archive, compiles both iOS variants from source on macOS 26, and saves the results in your private repository's Releases. No prebuilt upstream IPA is required.

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

Create a checksum file alongside the archive:

```sh
# macOS
shasum -a 256 game-input.zip > SHA256SUMS.txt
# Linux
sha256sum game-input.zip > SHA256SUMS.txt
```

Windows PowerShell:

```powershell
$hash = (Get-FileHash .\game-input.zip -Algorithm SHA256).Hash
"$hash  game-input.zip" | Set-Content -Encoding ascii SHA256SUMS.txt
```

Upload **both files** to your storage. Each URL must be downloadable without signing in. Google Drive's **Anyone with the link → Viewer** file links are supported, including large ZIP files; use file links, not folder links. For signed HTTPS URLs, set an expiry that covers the entire download. The checksum file must contain exactly one archive checksum.

## 2. Create your build repository

1. Select [Use this template](https://github.com/jiayx/d2r-mobile-build/generate), choose **Create a new repository**, and set its visibility to **Private**.
2. Copy the [build entry workflow](.github/workflows/build.yml) from this page into `.github/workflows/build.yml` in your private repository, replacing an older entry if present. It calls the maintained source-build workflow, so you do not need to copy updated build scripts for each app version.
3. Open **Settings → Secrets and variables → Actions → New repository secret**. Create a secret named **`GAME_ARCHIVE`**, with this JSON as its value. Replace `url` with the ZIP link and `sha256_url` with the link to `SHA256SUMS.txt`:

   ```json
   {
     "url": "https://your-storage.example/game-input.zip",
     "sha256_url": "https://your-storage.example/SHA256SUMS.txt"
   }
   ```

Google Drive links can be pasted in the form `https://drive.google.com/file/d/FILE_ID/view`; no Google account authorization is needed in Actions. Store the two links in your private repository's secret.

## 3. Run the build

In your repository, open **Actions → Build IPA and Data → Run workflow**. Leave `source_ref` empty to automatically build the latest official upstream Release.

To test the latest development code, set `source_ref` to `main`. You can also enter another branch, tag, or commit, or set `source_repository` to your public fork. Choose a source revision compatible with your game input.

For a private source repository, add a `SOURCE_TOKEN` repository secret containing a fine-grained token with read-only Contents access to that source repository. Set `source_repository` to its `owner/repository` and `source_ref` to the branch or tag to build.

The first build includes Legacy texture conversion on two parallel Linux workers. Data is prepared in parallel with the IPA build path. Subsequent builds reuse existing resources and matching generated payloads.

## 4. Download and install

Hardware requirements: A14 / M1 or later, with at least 6 GB of RAM.

After a successful run, open **Releases in your own repository**. The latest app Release contains:

| File | Use |
|---|---|
| `D2RMobile-<version>.ipa` | iOS 26 and later |
| `D2RMobile-<version>-ios18.ipa` | iOS 18–25 |
| `SHA256SUMS.txt`, `build-report.json` | Checksums and build details |

Filenames use the source tag; builds after a tag also include the source commit. Sources without a version tag use the commit. The Release description links to your matching Data and Legacy Device Pack.

The app's version follows the upstream source version. Every run and rerun gets its own Release and IPA filenames, for example `v1.0.14-build.7.1` and `v1.0.14-build.7.2`; `7.2` identifies workflow run 7, attempt 2. Rebuild the same upstream version to get a separate download while keeping earlier builds. Multiple runs queue and execute one at a time.

1. Sign and install the matching IPA using [Sideloadly](https://sideloadly.io/), [iloader](https://iloader.app/), [AltStore Classic](https://faq.altstore.io/altstore-classic/your-altstore), or [SideStore](https://sidestore.io/).
2. Download all three `D2R-Mobile-Resources.zip.001`–`.003` parts from your linked Data Release. Follow `RESOURCE-INSTALL.txt` to join them, extract the ZIP, and copy the `D2R Mobile Resources` folder into the app using Finder or Files.
3. **A14–A16 devices** also need the linked `Legacy-Device-Pack.zip`. Extract it and import the entire `Legacy Device Pack` folder beside the resource folder. A17 Pro and newer devices and M-series iPads use the standard Data.
4. Open the app and import/select the resource folder. Initial shader compilation takes several minutes; approximately 6 minutes is a reference for iPhone 17 Pro Max.

When updating, keep the same app identifier, back up your saves, and install the new IPA over the existing app.

### iCloud saves

The upstream source includes iCloud save synchronization. These unsigned packages use the ordinary sideloading configuration and do not provision iCloud; free Apple ID signing supports local saves only. Automatic iCloud sync requires a paid Apple Developer Program account, an App ID with iCloud enabled, and a matching provisioning profile and signature. Enabling the in-game iCloud switch alone cannot grant those permissions. You can back up or transfer exported saves using iCloud Drive manually.

## Updates and reuse

Run **Build IPA and Data** again with `source_ref` empty to build the latest official upstream Release using this project's latest build tools. Keep your existing `GAME_ARCHIVE` configuration when using the same input files.

Each new run automatically uses the maintained shared workflow's latest build logic. You do not need to sync the template or copy updated scripts.

- The checksum file determines the original archive's cache key. The verified archive is cached **before extraction**, independently of the app version; completed downloads survive later extraction or compilation failures.
- Unchanged archive checksums reuse the verified input manifest. Matching payloads then build without restoring or extracting the large archive.
- Drive downloads retry transient failures and resume partial transfers within a running job. A stopped or failed download is not treated as a completed cache entry.
- Rewritten game code, generated interface assets, build tools and shaders have separate caches keyed by their relevant inputs. Changes to the app runtime alone do not invalidate unchanged game rewriting or shader outputs.
- Matching prebuilt SPIRV-Cross, zlib-ng and shader translator tools are downloaded and verified automatically. If a matching package is unavailable, the workflow compiles it from source. No additional configuration is needed.
- When Data contents match, the Release links to your existing Data. Keep using the resources already imported on your phone.
- Matching Legacy conversion inputs and settings reuse your existing Legacy pack.
- Legacy reuse downloads only its verified index and descriptor; the phone's texture archive stays in its existing Release.
- Completed generation stages are cached immediately. Both iOS variants compile in parallel on macOS 26.
- Retain older Data and Legacy Releases referenced by your app Releases.
- GitHub can evict caches; retain your source archive. Keep the ZIP and checksum links in `GAME_ARCHIVE` current when replacing input files.

Build tooling is licensed under [MIT](LICENSE). Upstream and third-party code retain their respective licenses.
