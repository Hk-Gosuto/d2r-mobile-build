# d2r-mobile build workflow

[English](README.md) | [简体中文](README.zh-CN.md)

Build IPAs from [d2r-mobile](https://github.com/jhaizhou-ops/d2r-mobile) source using your prepared package and GitHub Actions. Each run defaults to the latest official upstream Release, compiles iOS 18 and iOS 26 variants in parallel on macOS 26, and publishes to your private repository.

## Configure

1. Click [Use this template](https://github.com/jiayx/d2r-mobile-build/generate) and create a **Private** repository.
2. Use [D2RMobile-Prepared.zip](https://drive.google.com/file/d/1bjroriGTb2UwD48Pz1bGWZEJ5QDpAqbd/view) (141 MB) as the build input. Copy the configuration below into the Secret.
3. Under **Settings → Secrets and variables → Actions**, add a **`PREPARED_INPUT`** Secret:

   ```json
   {
     "url": "https://drive.google.com/file/d/1bjroriGTb2UwD48Pz1bGWZEJ5QDpAqbd/view",
     "sha256": "c3f45f4880a5738a69b09ee91881e5efc68cdc0cd2bc510be1147904834c2f38"
   }
   ```

The workflow downloads the prepared package directly from Google Drive. See the [prepared package format](docs/PREPARED_INPUT.md).

## Files to prepare

| Package | Download size | Purpose |
|---|---|---|
| `D2RMobile-Prepared.zip` | 141 MB | Input to GitHub Actions for building both IPAs |
| `D2R-Mobile-Resources.zip.001`, `.002`, `.003` | 5.42 GB total | Data required on every supported device; contains the `D2R Mobile Resources` folder with 18 `.data` files |
| `Legacy-Device-Pack.zip` | 1.02 GB | Additional textures for A14–A16 devices; contains the `Legacy Device Pack` folder |

The IPA workflow downloads only the prepared package. Download matching Data and Legacy archives from your resource provider’s storage, then follow [Download and use](#download-and-use) to import them after installing the IPA.

## Build

Open **Actions → Build IPA → Run workflow**:

- Run with the defaults to compile the latest official upstream Release.
- To test development code, set `source_ref` to `main`, another branch, a tag, or a commit.
- To test your changes, set `source_repository` to your fork and `source_ref` to its branch. For private source repositories, add a **`SOURCE_TOKEN`** Secret with Contents read access to that repository.

The build entry automatically uses the latest build logic maintained by this project. The workflow downloads and verifies the prepared package, checks source compatibility, then compiles and packages both IPAs. Completed downloads and native compiler modules are cached for later builds. Repeated builds and reruns of the same upstream version each receive independent Release and file names.

## Download and use

After the build, download from your repository’s **Releases**:

| File | Purpose |
|---|---|
| `D2RMobile-<version>-build.<run>.<attempt>.ipa` | iOS 26 and later |
| `D2RMobile-<version>-build.<run>.<attempt>-ios18.ipa` | iOS 18–25 |
| `SHA256SUMS.txt`, `build-report.json` | Checksums and build details |

1. Sign and install the IPA with [Sideloadly](https://sideloadly.io/), [iloader](https://iloader.app/), [AltStore Classic](https://faq.altstore.io/altstore-classic/your-altstore), or [SideStore](https://sidestore.io/).
2. Download matching Data from your resource provider’s storage. For split archives, download all `.001`, `.002`, and `.003` parts and open `.001` with an extractor supporting split archives. Import the extracted `D2R Mobile Resources` folder into the app using Finder or Files.
3. A14–A16 devices also need `Legacy-Device-Pack.zip` from your storage provider. Extract it and import the entire `Legacy Device Pack` folder beside the resource folder. A17 Pro and newer devices and M-series iPads use the standard Data.
4. Open the app and select the resource folder. The prepared package includes precompiled Metal shaders.

Device requirements: A14 / M1 or newer, with at least 6 GB of memory.

## Update the IPA

Run **Build IPA** again to build the latest official upstream Release. Back up saves, keep the app identifier unchanged, and install over the existing app. Previously imported matching Data and Legacy resources remain reusable.

Ordinary native code changes can reuse the prepared package. If the workflow reports incompatible generation rules, obtain a newer prepared package and update `PREPARED_INPUT`.
