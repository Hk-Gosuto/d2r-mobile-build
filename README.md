# D2R Mobile · GitHub Actions Build Template

**English** | [简体中文](README.zh-CN.md)

**[Create your own repository from this template](https://github.com/jiayx/d2r-mobile-build/generate)**

Build an unsigned IPA and matching game resources in your own GitHub repository using the **NO_XCODE** approach from [jhaizhou-ops/d2r-mobile](https://github.com/jhaizhou-ops/d2r-mobile). Builds run on Ubuntu runners in GitHub Actions and automatically publish a Release in the repository running the workflows.

Create a **private repository** from this template and supply game files and console keys that you lawfully possess and are authorized to process. Template creation copies the source files; Secrets, Releases, Actions artifacts, and caches are not inherited. No game download source or key is supplied by the template.

## 1. Create a private repository

1. Click **Use this template → Create a new repository**, or use the link above.
2. Choose your account as **Owner**, enter a **Repository name** of your choice, and select **Private**. Keep **Include all branches** unchecked; the default branch is sufficient.
3. Click **Create repository from template**. Continue in **the newly created repository**, not this public template.
4. Open **Actions** and enable workflows if GitHub prompts you. Account or organization policies must allow the actions used by the workflows. Private repository runs use your account's Actions allowance or billing settings.

There is no need to edit the repository owner, shell URL, source commit, or tool versions. Release publishing uses the current repository and the automatically supplied `GITHUB_TOKEN`; a personal access token is not required. The workflows declare `contents: write`, subject to your organization policies.

## 2. Configure your inputs

Open **Settings → Secrets and variables → Actions → New repository secret** in your new repository. Add **Secrets**, not Variables:

| Secret | Required | Value |
| --- | --- | --- |
| `GAME_INPUT_MANIFEST` | Yes | One of the JSON manifests below, with your own direct download URLs |
| `PROD_KEYS` | For `packages` | The complete text contents of your own `prod.keys` file, not a file path; omit for `prepared` |

Choose **one** input type. Both must match the [pinned versions](#pinned-versions). The upstream requires the Reign of the Warlock expansion; the edition without it is not supported or verified.

### Option A: `packages` — base game and update packages

Set `GAME_INPUT_MANIFEST` to:

```json
{
  "kind": "packages",
  "files": [
    {"name": "base.nsp", "url": "https://example.com/your-base.nsp"},
    {"name": "update.nsp", "url": "https://example.com/your-update.nsp"}
  ]
}
```

Replace both URLs with your own. Supply the base game and **Switch update `1.0.34.0` (`v2228224`)**, and add the `PROD_KEYS` Secret. `packages` is an input type, not a single URL: `files` can list multiple downloads. If one ZIP/7z/RAR contains both packages, use one entry instead, such as `{"name": "game.zip", "url": "https://example.com/your-game.zip"}`. NSP/XCI and multipart RAR are supported; NSZ is not supported. DLC packages are not extracted by this script.

### Option B: `prepared` — decrypted ExeFS and RomFS

Set `GAME_INPUT_MANIFEST` to:

```json
{
  "kind": "prepared",
  "files": [
    {"name": "game.zip", "url": "https://example.com/your-game.zip"}
  ]
}
```

The archive must contain exactly one pair of sibling `ExeFS/` and `RomFS/` directories, already decrypted with the specified update merged. It must match internal version **`3.3.94012`**. Do not rename NSP/XCI packages to use this option. No `PROD_KEYS` Secret is needed. The `packages` path has been verified end to end; `prepared` is implemented but has not been verified end to end with a separate input archive.

### Download and manifest fields

| Field | Meaning |
| --- | --- |
| `kind` | `packages` or `prepared` |
| `files` | A nonempty list of files to download |
| `files[].name` | Unique local filename with the correct extension; use only letters, numbers, `.`, `_`, and `-`, without a leading `.` |
| `files[].url` | An HTTPS URL returning the actual file; a signed URL for your own private storage can be used |
| `files[].sha256` | Optional for ordinary files: the actual 64-character hexadecimal SHA256 of that downloaded file |

GitHub runners cannot read paths on your computer. Put your own inputs in storage reachable from GitHub Actions and keep URLs valid until downloading finishes. Local paths, browser login pages, CAPTCHA pages, and file-hosting landing pages do not work. Do not upload game packages or keys as Git commits or put real URLs in public documentation. Store credential-bearing URLs only in the Secret; changing a URL in the manifest also changes its cache identity.

For integrity checks, add a `sha256` field to each entry. On macOS, obtain it with `shasum -a 256 filename`; on Linux, use `sha256sum filename`. Hash the downloaded archive itself, not its extracted contents.

Advanced `.torrent` inputs require the metadata file's SHA256 and explicit package indices, for example `select: [1, 2]`. Only use inputs you are authorized to download and process.

## 3. Build the IPA, then export resources

In your new repository, open **Actions → Build D2R Mobile IPA → Run workflow**, select `main`, and use:

| Workflow input | Normal setting | When to change it |
| --- | --- | --- |
| `prepare_only` | `false` (unchecked) | `true` only checks tools and warms tool caches; it does not download game inputs, build an IPA, or publish a Release |
| `input_revision` | `game-3.3.94012-v1` | Change when replacing files or editing download entries; 1–64 letters, numbers, `.`, `_`, or `-` |

Wait for the IPA workflow to **succeed**. Then run **Actions → Export D2R Mobile resources → Run workflow** on `main`, with the **same `input_revision`**. This workflow reuses the original download and tool caches from the IPA build. If a required cache has been evicted, rerun the full IPA workflow to populate it, then retry resource export.

Once both workflows succeed, the matching Release is automatically published in **your own repository**. The first workflow leaves a draft while waiting for resources. No manual tag, release creation, or publishing token is needed. Private repository Releases are accessible only to people with repository access.

For an extraction failure after downloads were cached, fix the keys or extraction problem and rerun with the same `input_revision` to reuse the downloads. If you change `kind` or `files` in the manifest, use a new revision in both workflows to avoid reusing different inputs.

Optional diagnostics are available as **Probe remote game source** (torrent connectivity) and **Check PNG encoder compatibility** (an unexpired PNG diagnostic artifact). Neither is required for a normal build.

## Pinned versions

| Component | Current setting |
| --- | --- |
| Upstream | v1.0.1, commit `ea86e79688f9339319de3e2c52c69b8b13e30e9e` |
| iOS shell | Upstream v1.0.1 `D2RMobile-shell.ipa` |
| Switch update | `1.0.34.0` / `v2228224` |
| Internal game version | `3.3.94012` |
| Required edition | Diablo II: Resurrected with Reign of the Warlock |
| SPIRV-Cross | `1.4.357.0` |

Hashes and tool commits are pinned in [build-config.json](build-config.json). Do not mix other game versions or upstream shell packages. The 18 exported resource archives come directly from the RomFS after merging the base game and update; packaging does not modify their contents. File names and sizes are checked against the upstream list, and each file's SHA256 is verified before and after ZIP compression.

## Install your build

In **your own repository**, open **Releases** after both workflows succeed and download these files from Assets:

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

Your phone needs **iOS 26 or later**. Sign and install the IPA with Sideloadly, then complete the trust setup prompted by iOS.

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

**Tested on iPhone 17 Pro Max.** Initial shader compilation takes about **6 minutes** on this device. Compilation time varies by device.

## Automatic releases and outputs

Release tags are generated from the game version, upstream commit, and `input_revision`. Both workflows update the same Release for matching versions. When only one type of output is available initially, the Release remains a draft. It is published automatically once the IPA, all three resource parts, and accompanying files are present. Later builds of the same version update the corresponding assets; changing the version or input revision creates a separate Release.

Each GitHub Release asset must be smaller than 2 GiB, so the resource ZIP is split into parts of at most 1,900,000,000 bytes. Local SHA256 checks run before upload; asset sizes and the SHA256 returned by GitHub are checked afterward.

Actions artifacts are retained for **3 days**. The IPA artifact contains the IPA and build report. The resource artifact contains the **complete resource ZIP** and report, so no part combining is required. Release assets are independent of the Actions artifact retention period.

## Visibility and rights

Keep the repository containing your inputs and builds **private**. Its raw game downloads and generated content are cached by Actions, and IPA/resources are uploaded as artifacts and Release assets. Never use a public repository cache as private storage. [GitHub cache access documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching)

This template repository is public and has public Release assets. Enabling template mode does not remove existing Releases, artifacts, or caches, or change their access. New repositories created from the template do not inherit them. [GitHub template documentation](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-repository-from-a-template)

A private build and a template do not grant a license to game content or guarantee legal compliance. Use only files and keys you are authorized to use; copying, modifying, circumventing protection, and distributing outputs may have separate legal restrictions. Do not redistribute game content without permission. [GitHub DMCA policy](https://docs.github.com/en/site-policy/content-removal-policies/dmca-takedown-policy)

## Caching and validation

- **Tool cache:** SPIRV-Cross, hactool, and the upstream shell package.
- **Raw download cache:** complete game inputs and a size / SHA256 manifest. It is saved immediately after successful downloads, before reading keys and extracting files, so later extraction or compilation failures do not require another download.
- **Generated cache:** the rewritten game program, shader conversion tools and results, and UI assets.
- **PNG compression backend and Python dependency caches:** pinned versions to keep generated content consistent.

The raw download cache is independent of keys and extraction scripts. Changing the extraction process or replacing keys does not invalidate it. Generated caches are distinguished by tools, configuration, and input revision. Keys are written only to a temporary directory and deleted after extraction; they are not included in caches or assets.

GitHub caches have storage limits and eviction rules; they are not permanent backups. Before cloud extraction, the workflow removes unrelated preinstalled SDKs from the temporary runner and checks for at least 28 GiB of free space. It does not modify your local computer.

The public upstream source does not include the recorded startup prefetch table `bootlist.tsv`. The official v1.0.1 shell does not require it. The rewriting step removes stale prefetch files from build outputs. This workflow copies the verified shell byte for byte and rejects an unexpected prefetch requirement or stale prefetch files in the final IPA. Build reports record `startup_prefetch: false` and the shell's shader chain identifier; this startup optimization is not enabled.
