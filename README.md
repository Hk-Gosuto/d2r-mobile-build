# d2r-mobile build workflow

[English](README.md) | [简体中文](README.zh-CN.md)

Build iOS and macOS apps from [d2r-mobile](https://github.com/jhaizhou-ops/d2r-mobile) source with GitHub Actions. Each run defaults to the latest official upstream Release and publishes to your private repository.

## Build for iOS

1. Click [Use this template](https://github.com/jiayx/d2r-mobile-build/generate) and create a **Private** repository.
2. Under **Settings → Secrets and variables → Actions**, add a **`PREPARED_INPUT`** Secret and paste the following JSON as its value:

   ```json
   {
     "url": "https://drive.google.com/file/d/1bjroriGTb2UwD48Pz1bGWZEJ5QDpAqbd/view",
     "sha256": "c3f45f4880a5738a69b09ee91881e5efc68cdc0cd2bc510be1147904834c2f38"
   }
   ```

   The prepared package in this configuration is provided by a community contributor.

3. Open **Actions → Build IPA → Run workflow**. Building and publishing typically takes **2–3 minutes**.

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

Download the community-provided [game resources (Data and Legacy)](https://drive.google.com/drive/folders/1lfjUghi54ohyDxYEtNuEjtGUZyGovaIA):

| Package | Download size | Purpose |
|---|---|---|
| `D2R-Mobile-Resources.zip.001`, `.002`, `.003` | 5.42 GB total | Data required on every supported device; contains the `D2R Mobile Resources` folder with 18 `.data` files |
| `Legacy-Device-Pack.zip` | 1.02 GB | Additional textures for A14–A16 devices; contains the `Legacy Device Pack` folder |

1. Sign and install the IPA with [Sideloadly](https://sideloadly.io/), [iloader](https://iloader.app/), [AltStore Classic](https://faq.altstore.io/altstore-classic/your-altstore), or [SideStore](https://sidestore.io/), then open the app once.
2. Download matching Data from the link above. For split archives, download all `.001`, `.002`, and `.003` parts and open `.001` with an extractor supporting split archives. Copy the entire extracted `D2R Mobile Resources` folder to **Files → On My iPhone → D2R Mobile**. Alternatively, connect to a Mac and drag the folder into the app under **Finder → your iPhone → Files**.
3. A14–A16 devices also need `Legacy-Device-Pack.zip` from the same link. Extract it and import the entire `Legacy Device Pack` folder beside the resource folder. A17 Pro and newer devices and M-series iPads use the standard Data.
4. Return to the app after copying. If the resource prompt is still shown, tap **Retry**; the app automatically detects and loads the resources. The IPA includes precompiled Metal shaders.

Device requirements: A14 / M1 or newer, with at least 6 GB of memory.

## Update the IPA

Run **Build IPA** again to build the latest official upstream Release. Back up saves, keep the app identifier unchanged, and install over the existing app. Previously imported matching Data and Legacy resources remain reusable.

Ordinary native code changes can reuse the prepared package. If the workflow reports incompatible generation rules, obtain a newer prepared package and update `PREPARED_INPUT`.

## Build for macOS

1. In your private repository, add a **`MACOS_PREPARED_INPUT`** Secret containing the Mac prepared package’s download configuration:

   ```json
   {
     "url": "https://drive.google.com/file/d/1t7u-eYg876z6681pqgHP5n0JDbwypzs7/view",
     "sha256": "d961071ea06bffb12be37f4e79b2933186e59d2f1ead884e74b2ec9471b7a67f"
   }
   ```

   The prepared package in this configuration is provided by a community contributor.

2. Open **Actions → Build macOS → Run workflow**. Building and publishing typically takes **2–3 minutes**. The source selection fields work the same way as for iOS.

The workflow downloads and verifies the Mac prepared package, compiles the current native source for both system versions, and publishes the apps. Prepared downloads are cached for later builds. The package contains the rewritten game programs, Mac interface resources and precompiled macOS Metal libraries. See the [Mac prepared package format](docs/MACOS_PREPARED_INPUT.md).

Download from your repository’s **Releases**:

| File | Purpose |
|---|---|
| `D2RMobile-<version>-build.<run>.<attempt>-macos26.zip` | Apple silicon Macs running macOS 26 or later |
| `D2RMobile-<version>-build.<run>.<attempt>-macos15.zip` | Apple silicon Macs running macOS 15–25 |
| `Mac-SHA256SUMS.txt`, `macos-build-report.json` | Checksums and build details |

Extract the ZIP and move the app to **Applications**. Reuse the Data downloaded above:

1. In Finder, press **⌘⇧.** to show hidden files. Copy `build_manifest.psv` and `.build.config` from the included `Mac Resource Metadata/data` into `D2R Mobile Resources/data`.
2. On first launch, select the `D2R Mobile Resources` folder. The app remembers this location.

Keep the resources in that location when updating the app. The macOS 15 app uses its own save directory and can coexist with the macOS 26 app.

The apps are signed ad hoc. If macOS blocks the first launch, follow Apple’s [instructions for opening an app you trust](https://support.apple.com/102445).
