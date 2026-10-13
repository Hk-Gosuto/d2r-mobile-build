# D2R Mobile · GitHub Actions Builds and Automatic Releases

**English** | [简体中文](README.zh-CN.md)

[![Build IPA](https://github.com/jiayx/d2r-mobile-build/actions/workflows/pack.yml/badge.svg)](https://github.com/jiayx/d2r-mobile-build/actions/workflows/pack.yml)
[![Export resources](https://github.com/jiayx/d2r-mobile-build/actions/workflows/resources.yml/badge.svg)](https://github.com/jiayx/d2r-mobile-build/actions/workflows/resources.yml)

Build an unsigned IPA, export matching game resources, and publish them automatically to GitHub Releases using the **NO_XCODE** approach from [jhaizhou-ops/d2r-mobile](https://github.com/jhaizhou-ops/d2r-mobile). Builds run on Ubuntu runners in GitHub Actions.

This repository contains build scripts and pinned version settings. IPA and resource files are stored as Release assets and Actions artifacts. Console keys and download inputs are configured through Actions Secrets and are not committed to Git.

## Download and install

Open the **[latest Release](https://github.com/jiayx/d2r-mobile-build/releases/latest)** and download these files from Assets:

| Asset | Purpose |
| --- | --- |
| `D2RMobile-unsigned.ipa` | About 126 MB; sign and install with Sideloadly |
| `D2R-Mobile-Resources.zip.001`, `.002`, `.003` | Three parts of the resource ZIP; download all three, totaling about 5.42 GB |
| `Resources-Parts-SHA256SUMS.txt` | Verify the three ZIP parts |
| `Resources-SHA256SUMS.txt` | Verify the combined ZIP |
| `RESOURCE-INSTALL.txt` | Instructions for combining the parts and importing resources |
| `build-report.json`, `resources-report.json`, `SHA256SUMS.txt` | Version information, file sizes, and SHA256 checksums |

The `Source code` archives that GitHub adds automatically contain the build scripts.

### 1. Install the IPA

Your phone needs **iOS 26 or later**. This build targets devices with BC texture support (A17 Pro and later, or M-series iPads). The additional Legacy Device Pack required for A16 and earlier is not included. Sign and install the IPA with Sideloadly, then complete the trust setup prompted by iOS.

**The IPA contains the game program, converted shaders, and other generated content. Large resources such as maps, models, and audio must be imported separately.** Installing only the IPA is not enough to play.

### 2. Combine the resource parts

Place all three parts and both `Resources-…SHA256SUMS.txt` files in the same directory.

On macOS, open a terminal in that directory and run:

```sh
shasum -a 256 -c Resources-Parts-SHA256SUMS.txt
cat D2R-Mobile-Resources.zip.001 D2R-Mobile-Resources.zip.002 D2R-Mobile-Resources.zip.003 > D2R-Mobile-Resources.zip
shasum -a 256 -c Resources-SHA256SUMS.txt
```

On Linux, use `sha256sum -c` in place of `shasum -a 256 -c` above.

On Windows, open **Command Prompt (cmd)** in the directory containing the parts and run:

```bat
copy /b D2R-Mobile-Resources.zip.001+D2R-Mobile-Resources.zip.002+D2R-Mobile-Resources.zip.003 D2R-Mobile-Resources.zip
```

The combined ZIP is about 5.42 GB. Extract it to get a `D2R Mobile Resources` folder containing 18 `.data` files, totaling **5,561,224,037 bytes (about 5.56 GB)**. If you keep the parts, the combined ZIP, and the extracted files, allow disk space for each copy.

### 3. Import resources to your phone

Connect your iPhone by cable. In **Finder → iPhone → Files → D2R Mobile**, drag in the entire `D2R Mobile Resources` folder. Alternatively, place the folder in **Files → On My iPhone → D2R Mobile** on the phone.

Return to the app and tap **Retry**. On the first launch, the phone compiles shaders; wait for it to finish. The time required depends on the device. Installing over an existing installation with the same app identifier usually preserves resources. Uninstalling the app deletes its resources and saves.

**Initial shader compilation reference: about 6 minutes on iPhone 17 Pro Max.** Compilation time varies by device. The current v1.0.6 package has not yet been verified on a physical device.

## Pinned versions

| Component | Current setting |
| --- | --- |
| Upstream | v1.0.6, commit `2eb5758771f110cd53082b999d88d242766610da` |
| iOS shell | Upstream v1.0.6 `D2RMobile-shell.ipa` |
| Switch update | `1.0.34.0` / `v2228224` |
| Internal game version | `3.3.94012` |
| Required edition | Diablo II: Resurrected with Reign of the Warlock |
| SPIRV-Cross | `1.4.357.0` |

Hashes and tool commits are pinned in [build-config.json](build-config.json). Do not mix other game versions or upstream shell packages. The 18 exported resource archives come directly from the RomFS after merging the base game and update; packaging does not modify their contents. File names and sizes are checked against the upstream list, and each file's SHA256 is verified before and after ZIP compression.

## Run your own build

Forks do not inherit this repository's Actions Secrets. Use game files and console keys that you legally possess and are authorized to use. Upstream requires the Reign of the Warlock expansion.

Open **Settings → Secrets and variables → Actions → New repository secret**, name it **`GAME_INPUT_MANIFEST`**, and paste the complete configuration below. The actual download URLs and SHA256 values are already filled in; no replacements are needed:

```json
{
  "kind": "packages",
  "files": [
    {
      "name": "game.torrent",
      "url": "https://gamegula.com/index.php?do=download&id=405",
      "sha256": "016f7c907deb1f4cd6098a7cd06823907a589ff2502aa2c8b341a89ccf984266",
      "select": [
        1,
        2
      ]
    }
  ],
  "key_archive": {
    "url": "https://drive.google.com/uc?export=download&id=147IsDRRJNF_VMT6Fj50glrnqAeb7oR_1",
    "sha256": "b73573af5eae6c9f7739ca9931cebf04774cf2ba9d6ee98f2f04c2dc88fca71c"
  }
}
```

This is the input configuration used for the builds:

- `files[0].url` downloads the **torrent metadata** from GameGula; its `sha256` verifies the `.torrent` file, not the game packages.
- `select: [1, 2]` downloads the **base NSP and `1.0.34.0` (`v2228224`) update NSP** from that torrent. There is no separate update download URL in this configuration.
- `key_archive` downloads a **ZIP containing `prod.keys`** from Google Drive and verifies the ZIP's SHA256. It provides the extraction keys; it is not the update package. The ZIP is read temporarily and deleted, without being cached or included in outputs.

With this configuration, no separate `PROD_KEYS` Secret is needed. Actions downloads and extracts the inputs automatically and reuses complete original downloads from the cache when available. Keep the JSON in the Secret; do not commit game packages or key contents to Git.

### Workflows

| Workflow | Purpose |
| --- | --- |
| **Build D2R Mobile IPA** | Prepare game inputs, generate and validate an IPA, and automatically upload it to the Release |
| **Export D2R Mobile resources** | Extract again from the existing raw download cache, export 18 resource archives, and automatically upload resource parts to the Release |
| **Probe remote game source** | Read torrent inputs from the Secret and briefly test connectivity for a selected package; does not produce complete game files |
| **Check PNG encoder compatibility** | Inspect an unexpired PNG diagnostic artifact for troubleshooting |

Run **Build D2R Mobile IPA** first, then **Export D2R Mobile resources**. Resource export requires the raw download and extraction tool caches to exist. If a required cache is missing, it stops rather than downloading the game again.

Build inputs:

- `prepare_only=false`: build the complete IPA.
- `prepare_only=true`: validate the toolchain and warm caches only; no IPA or Release is produced.
- `input_revision`: use the same value in both workflows. Change it when replacing input files to distinguish caches and Releases.

Start builds with **Run workflow** in Actions. **Release publishing happens automatically after successful builds; no separate publishing task or manually entered tag is needed.**

## Automatic releases and outputs

Release tags are generated from the game version, upstream commit, and `input_revision`. Both workflows update the same Release for matching versions. When only one type of output is available initially, the Release remains a draft. It is published automatically once the IPA, all three resource parts, and accompanying files are present. Later builds of the same version update the corresponding assets; changing the version or input revision creates a separate Release.

Each GitHub Release asset must be smaller than 2 GiB, so the resource ZIP is split into parts of at most 1,900,000,000 bytes. Local SHA256 checks run before upload; asset sizes and the SHA256 returned by GitHub are checked afterward.

Actions artifacts are retained for **3 days**. The IPA artifact contains the IPA and build report. The resource artifact contains the **complete resource ZIP** and report, so no part combining is required. Release assets are independent of the Actions artifact retention period.

## Public repository and input visibility

This repository is public. **Other people can access Releases, Actions logs, and build outputs.** Downloading Actions artifacts requires a GitHub login and read access to the repository. [GitHub documentation](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/download-workflow-artifacts)

Making the repository public does not expose Actions Secret values to visitors. Pull request workflows from forks also do not receive the original repository's Secrets by default. Do not put actual download credentials or key contents in the README, commits, logs, or artifacts. [GitHub Secrets documentation](https://docs.github.com/en/code-security/reference/secret-security/secret-types)

**Actions caches are not private file storage.** GitHub states that people who can open pull requests may be able to read caches from the base branch. This project's caches include raw game packages and generated content, but not console keys or the original input Secret text. If input files must remain private, build in a separate private repository or controlled storage environment instead of using this public repository's caches. [GitHub caching documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching)

The current workflows are started manually. They do not run build steps with Secrets or Release write access for external pull requests.

## Caching and validation

- **Tool cache:** SPIRV-Cross, hactool, and the upstream shell package.
- **Raw download cache:** complete game inputs and a size / SHA256 manifest. It is saved immediately after successful downloads, before reading keys and extracting files, so later extraction or compilation failures do not require another download.
- **Generated cache:** the rewritten game program, shader conversion tools and results, and UI assets.
- **PNG compression backend and Python dependency caches:** pinned versions to keep generated content consistent.

The raw download cache is independent of keys and extraction scripts. Changing the extraction process or replacing keys does not invalidate it. Generated caches are distinguished by tools, configuration, and input revision. Keys are written only to a temporary directory and deleted after extraction; they are not included in caches or assets.

GitHub caches have storage limits and eviction rules; they are not permanent backups. Before cloud extraction, the workflow removes unrelated preinstalled SDKs from the temporary runner and checks for at least 28 GiB of free space. It does not modify your local computer.

The public upstream source does not include the recorded startup prefetch table `bootlist.tsv`. The official v1.0.6 shell does not require it. The rewriting step removes stale prefetch files from build outputs. This workflow copies the verified shell byte for byte and rejects an unexpected prefetch requirement or stale prefetch files in the final IPA. Build reports record `startup_prefetch: false` and the shell's shader chain identifier; this startup optimization is not enabled.
