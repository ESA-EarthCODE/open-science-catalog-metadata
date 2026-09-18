# DOI Assignment System

This directory contains the logic and automation for assigning [DataCite](https://datacite.org/) DOIs to STAC Collections (Products and Workflows) within the Open Science Catalog.

## Logic & Architecture

The system supports a **Canonical DOI** for the root endpoint and **Versioned DOIs** for specific snapshots. It follows a **Research -> Strategy -> Execution** lifecycle, implemented via an automated Pull Request workflow and a versioned deployment process.

### 1. Detection & Automation Phase
The system identifies the need for a new Canonical DOI or a metadata update.

- **Canonical DOI:** A STAC Collection (`products/**/collection.json`) or OGC Record (`workflows/**/record.json`) lacks the `sci:doi` property. This DOI points to the root endpoint (e.g., `/products/4dmed-2d-alt/collection`). When a new Canonical DOI is generated, an initial Versioned DOI (v1) is also automatically generated to ensure a stable snapshot exists from day one.
- **Versioned DOI:** A new DOI version is only created if explicitly requested by a Data Steward, or automatically when a new Canonical DOI is created for the first time.
- **Requesting a New Version:** To generate a new DOI version for an existing product, the system automatically injects a dynamic checklist into the Pull Request body listing the modified STAC Collections or Workflows. The Data Steward must check the box next to the specific file they want to version:
    - `- [x] Request new DOI version for \`products/polaris/collection.json\``
- **Significant Change & Metadata Updates:**
    - If changes are detected in fields like `title`, `description`, `keywords`, `providers`, `extent`, or `links`, but **no new version is requested**, the system will **update the metadata** of the existing Canonical DOI and the latest versioned DOI on DataCite.
    - If a new version **is** requested, the system generates a new Draft DOI and adds it to the `sci:publications` array.

### 2. Intelligent DOI Management
- **Canonical Storage:** The Canonical DOI is stored in the `sci:doi` field.
- **Version Storage:** Versioned DOIs are stored in the `sci:publications` array as objects: `{"doi": "10.xxxx/version-doi"}`.
- **Draft Updates:** If a DOI is still in a `draft` state (e.g., during PR review), the system updates its metadata instead of creating a new one.
- **DataCite Relationships:** 
    - The **Canonical DOI** is automatically updated to include `HasVersion` relationships pointing to all published versions.
    - Each **Versioned DOI** includes an `IsVersionOf` relationship pointing back to the Canonical DOI.
- **Foreign DOI Migration:** If an item has an existing `sci:doi` from an external source, it is moved to `sci:publications`, and a new local Canonical DOI is assigned to `sci:doi`.

### 3. Publication Phase
When a PR is merged into `main`:
1. The system identifies new/modified DOIs in `sci:doi` and `sci:publications`.
2. Draft DOIs are transitioned to `Findable` (Published).
3. **Target URLs**:
    - Canonical DOI -> `/products/{id}/collection`
    - Version DOI -> `/products/{id}/collection_v{n}`
4. A Git tag (`product-<id>-v{n}`) is created for the new version.

### 4. Versioned GitHub Pages Deployment
On every push to `main`, the system builds a versioned static site in the `dist/` directory:
- **Canonical File (`collection.json`)**: Contains links to all versions (`has-version`), the latest versioned snapshot (`latest-version`), and the DataCite history (`version-history`).
- **Versioned Files (`collection_vN.json`)**: Contain links to the canonical root (`is-version-of`), predecessor/successor versions, and DataCite metadata.
- **Recursive Item Versioning:** Associated local STAC Items are snapshotted at the corresponding tag and linked from the versioned collection.

## DataCite Metadata Mapping

The system automatically extracts provider information from your STAC/OGC metadata to populate DataCite fields. This logic relies on the STAC Provider `roles` array:

- **Creator (Mandatory, 1+):** Extracted from any provider with the `producer` role. 
  - *Fallback:* If no producer is found, it defaults to `"ESA EarthCODE"` (mapped with `nameType: "Organizational"`).
- **Publisher (Mandatory, exactly 1):** Extracted from the provider with the `host` role. 
  - *Conflict Resolution:* If multiple providers have the `host` role, the **last** one listed in the file is used, as DataCite strictly requires a single publisher.
  - *Fallback:* If no host is found, it defaults to `"ESA EarthCODE"`.
- **Contributor (Optional):** Extracted from providers with `licensor`, `processor`, or `contributor` roles.
  - *Note:* `processor` providers are mapped as `DataCollector`, while `licensor` or `contributor` providers are mapped as `Distributor`.

## Components (Location: `.github/scripts/doi/`)

- `datacite.py`: Low-level wrapper for DataCite REST API. Supports state detection, updates, and deletions.
- `check_changes.py`: Git-based change detection logic.
- `generate_drafts.py`: Main script for the detection phase; updates local files and manages draft DOIs.
- `publish_dois.py`: Main script for the publication phase; finalizes DOIs on DataCite.
- `build_pages.py`: Build script for the versioned GitHub Pages deployment.
- `cleanup_drafts.py`: Target script for deleting abandoned drafts when a PR is closed.

## Configuration (GitHub Secrets & Variables)

The following configurations must be set in the GitHub repository for the workflows to function correctly:

### Secrets
| Secret | Description | Required |
| :--- | :--- | :--- |
| `DATACITE_USER` | DataCite Repository Account ID (e.g., `MYORG.REPO`) | **Yes** |
| `DATACITE_PASSWORD` | DataCite Repository Password | **Yes** |
| `DATACITE_PREFIX` | Assigned DOI Prefix (e.g., `10.xxxx`) | **Yes** |
| `DATACITE_API_URL` | DataCite API Base URL (Defaults to `https://api.test.datacite.org`) | No |
| `BOT_PAT` | Personal Access Token used to auto-commit DOIs back to PRs (handling forks) and to create the Scheduled/Manual Audit PRs so that CI validation workflows are triggered. | No* |

*\*Highly recommended for a smooth contributor experience.*

### Variables
| Variable | Description | Default |
| :--- | :--- | :--- |
| `PORTAL_UI_BASE_URL` | Base URL for the Open Science Catalog UI. Used to construct the DOI target URL. | `https://opensciencedata.esa.int` |

## Metadata Overrides & Manual Control

- **Skip DOI:** To prevent an item from receiving a DOI, add `"osc:skip_doi": true` to its `collection.json` or `record.json`.
- **Manual Reverts (The "Veto"):** If the automated PR proposes a DOI update that is not desired (e.g., a false positive or an insignificant change):
    1.  Manually edit the PR branch and revert the `sci:doi` field to its previous value (or remove it if it was new).
    2.  The publication workflow (`publish_dois.py`) only publishes DOIs that are present and modified in the merge commit. Reverting the field ensures no DOI action is taken.
    3.  **Baseline Note:** Since the historical baseline is driven by **Git Tags** (`<stac_type>-<id>-v*`), a vetoed item will be flagged again by the next audit if the significant changes remain. To stop future audits from flagging the item, you must either revert the significant changes, accept the DOI, or use `osc:skip_doi`.
- **Version Tags as Baselines:** The baseline for change detection only advances when a new version tag is created. This happens automatically when a new DOI is published. If you need to "approve" a metadata state as the new baseline *without* updating the DOI, you would need to manually create and push a new version tag for that item.
- **Persistent State:** For untagged legacy items, the system defaults to a **Permissive Baseline**, treating the current repository state as the initial validated version.
