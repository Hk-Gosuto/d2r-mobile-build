# d2r-mobile build workflow

[English](README.md) | [简体中文](README.zh-CN.md)

Build two IPAs from [jhaizhou-ops/d2r-mobile](https://github.com/jhaizhou-ops/d2r-mobile) source using GitHub Actions and your own prepared input package. Each run defaults to the latest official upstream Release, compiles on macOS 26, and publishes to your private repository.

## 1. Prepare the input

Obtain a prepared package and its `Prepared-SHA256SUMS.txt`, with HTTPS download links for both files. Direct links and Google Drive file share links are supported.

The package contains the generated game payload, files required for native compilation, precompiled Metal shaders, and download information for the matching Data and Legacy Device Pack. See the [prepared package format and export guide](docs/PREPARED_INPUT.md).

For Google Drive, use file links in the form `https://drive.google.com/file/d/FILE_ID/view` and set access to **Anyone with the link → Viewer**. Signed direct links must remain valid throughout the download.

## 2. Create your build repository

1. Click [Use this template](https://github.com/jiayx/d2r-mobile-build/generate), choose **Create a new repository**, and select **Private**.
2. Copy this branch's [build entry workflow](.github/workflows/build.yml) to your `.github/workflows/build.yml`.
3. Open **Settings → Secrets and variables → Actions → New repository secret**. Create **`PREPARED_INPUT`** containing this JSON:

   ```json
   {
     "url": "https://your-storage.example/D2RMobile-Prepared.zip",
     "sha256_url": "https://your-storage.example/Prepared-SHA256SUMS.txt"
   }
   ```

`url` points to the prepared package; `sha256_url` points to its checksum file. Both links remain in your repository Secret.

## 3. Run the build

Open **Actions → Build IPA → Run workflow**. Leave `source_ref` empty to resolve and compile the latest official upstream Release tag.

- To test development code, set `source_ref` to `main`, another branch, a tag, or a commit.
- To build your changes, set `source_repository` to your fork and `source_ref` to its branch.
- For a private source repository, add a **`SOURCE_TOKEN`** Secret containing a fine-grained token with Contents read access to that source repository.

The workflow verifies the package against the selected source, then compiles the iOS 18 and iOS 26 IPAs in parallel. Completed downloads are cached before preparing the build and remain reusable after later failures.

## 4. Download and install

Device requirements: A14 / M1 or newer, with at least 6 GB of memory.

After a successful build, open your repository's **Releases**:

| File | Purpose |
|---|---|
| `D2RMobile-<version>-build.<run>.<attempt>.ipa` | iOS 26 and later |
| `D2RMobile-<version>-build.<run>.<attempt>-ios18.ipa` | iOS 18–25 |
| `SHA256SUMS.txt`, `build-report.json` | Checksums and build details |
| `RESOURCE-INSTALL.txt` | Resource installation instructions |

1. Sign and install the matching IPA using [Sideloadly](https://sideloadly.io/), [iloader](https://iloader.app/), [AltStore Classic](https://faq.altstore.io/altstore-classic/your-altstore), or [SideStore](https://sidestore.io/).
2. Download the matching Data using the Release description's links. Follow `RESOURCE-INSTALL.txt` to combine and extract it, then copy the `D2R Mobile Resources` folder into the app using Finder or Files.
3. **A14–A16 devices** also need the linked `Legacy-Device-Pack.zip`. Extract it and import the entire `Legacy Device Pack` folder beside the resource folder. A17 Pro and newer devices and M-series iPads use the standard Data.
4. Open the app and select the resource folder. Metal shaders are precompiled, so the app skips the first-launch batch shader compilation screen.

Data and Legacy download links come from the prepared package. Previously imported matching resources remain usable after an IPA update. Back up saves, keep the app identifier unchanged, and install over the existing app.

## Updates

Run **Build IPA** again with `source_ref` empty to use the maintained workflow's latest build logic and the latest official upstream Release.

Every run and rerun gets independent Release and file names, allowing repeated builds of the same upstream version. Prepared package caches are independent of the app version and remain reusable for ordinary runtime changes. If upstream changes game rewriting, asset generation, or shader generation rules, the workflow requests an updated prepared package. Update the links and checksum information in `PREPARED_INPUT` when replacing it.

### iCloud saves

The default sideload configuration uses local saves. Automatic iCloud sync requires a paid Apple Developer Program account, an iCloud-enabled App ID, and matching provisioning and signing. Exported saves can also be backed up or transferred manually through iCloud Drive.
