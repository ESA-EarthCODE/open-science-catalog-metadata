import os
import json
import glob
import sys
import re

# Add the current script's directory to sys.path to allow importing sibling modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datacite import DataCiteClient, map_stac_to_datacite
from check_changes import check_doi_need, check_pr_for_new_version_requests

SCIENTIFIC_EXTENSION_URL = "https://stac-extensions.github.io/scientific/v1.0.0/schema.json"
PORTAL_UI_BASE_URL = os.getenv("PORTAL_UI_BASE_URL", "https://opensciencedata.esa.int")

def surgical_update(file_path: str, doi: str, is_publication: bool = False):
    """Updates the STAC collection or OGC Record file using string manipulation to preserve formatting."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    scientific_ext = "https://stac-extensions.github.io/scientific/v1.0.0/schema.json"
    is_record = file_path.endswith("record.json")
    prefix = os.environ.get("DATACITE_PREFIX")

    if is_publication:
        # Append to sci:publications
        if '"sci:publications"' in content:
            # Check if this DOI is already there
            if f'"{doi}"' in content:
                print(f"DOI {doi} already exists in sci:publications for {file_path}")
                return

            # Append to existing sci:publications array
            pub_match = re.search(r'("sci:publications"\s*:\s*\[[^\]]*)', content, re.DOTALL)
            if pub_match:
                prefix_content = pub_match.group(1)
                # Determine indentation
                lines = prefix_content.split('\n')
                indent = "    "
                for line in reversed(lines):
                    if line.strip() and not line.strip().endswith('['):
                        m = re.match(r'^(\s*)', line)
                        if m:
                            indent = m.group(1)
                            break
                
                sep = "," if not prefix_content.strip().endswith("[") else ""
                new_pub = f'{sep}\n{indent}{{"doi": "{doi}"}}'
                content = content.replace(prefix_content, prefix_content + new_pub)
        else:
            # Create sci:publications array
            if is_record and '"properties"' in content:
                 match = re.search(r'("properties"\s*:\s*\{(\r?\n))(\s+)"', content)
                 if match:
                    block_prefix = match.group(1)
                    indent = match.group(3)
                    pub_entry = indent + f'"sci:publications": [\n{indent}{indent}{{"doi": "{doi}"}}\n{indent}],\n'
                    content = content.replace(block_prefix, block_prefix + pub_entry)
                 else:
                    match = re.search(r'^(\s+)"', content, re.MULTILINE)
                    indent = match.group(1) if match else "  "
                    pub_entry = f'{indent}"sci:publications": [\n{indent}{indent}{{"doi": "{doi}"}}\n{indent}],\n'
                    content = re.sub(r'^(\s*)\{(\r?\n)', r'\g<1>{\g<2>' + pub_entry, content)
            else:
                match = re.search(r'^(\s+)"', content, re.MULTILINE)
                indent = match.group(1) if match else "  "
                pub_entry = f'{indent}"sci:publications": [\n{indent}{indent}{{"doi": "{doi}"}}\n{indent}],\n'
                content = re.sub(r'^(\s*)\{(\r?\n)', r'\g<1>{\g<2>' + pub_entry, content)
    else:
        # Update/Insert sci:doi (Canonical)
        # 1. Handle Foreign DOI Migration (Existing logic)
        if prefix and '"sci:doi"' in content:
            doi_match = re.search(r'"sci:doi"\s*:\s*"([^"]+)"', content)
            if doi_match:
                existing_val = doi_match.group(1)
                if not existing_val.startswith(prefix):
                    print(f"Migrating foreign DOI {existing_val} to sci:publications")
                    sanitized_val = existing_val.replace("https://doi.org/", "").replace("http://doi.org/", "")
                    if f'"{sanitized_val}"' not in content or '"sci:publications"' not in content:
                        if '"sci:publications"' in content:
                            pub_match = re.search(r'("sci:publications"\s*:\s*\[[^\]]*)', content, re.DOTALL)
                            if pub_match:
                                prefix_content = pub_match.group(1)
                                lines = prefix_content.split('\n')
                                indent = "    "
                                for line in reversed(lines):
                                    if line.strip() and not line.strip().endswith('['):
                                        m = re.match(r'^(\s*)', line)
                                        if m:
                                            indent = m.group(1)
                                            break
                                sep = "," if not prefix_content.strip().endswith("[") else ""
                                new_pub = f'{sep}\n{indent}{{"doi": "{sanitized_val}"}}'
                                content = content.replace(prefix_content, prefix_content + new_pub)
                        else:
                            match = re.search(r'^(\s+)"', content, re.MULTILINE)
                            indent = match.group(1) if match else "  "
                            pub_entry = f'{indent}"sci:publications": [\n{indent}{indent}{{"doi": "{sanitized_val}"}}\n{indent}],\n'
                            content = re.sub(r'^(\s*)\{(\r?\n)', r'\g<1>{\g<2>' + pub_entry, content)

        if '"sci:doi"' in content:
            content = re.sub(r'("sci:doi"\s*:\s*")[^"]+(")', r'\g<1>' + doi + r'\g<2>', content)
        else:
            if is_record and '"properties"' in content:
                match = re.search(r'("properties"\s*:\s*\{(\r?\n))(\s+)"', content)
                if match:
                    prefix_block = match.group(1)
                    indent = match.group(3)
                    content = content.replace(prefix_block, prefix_block + indent + f'"sci:doi": "{doi}",\n')
                else:
                    match = re.search(r'^(\s+)"', content, re.MULTILINE)
                    indent = match.group(1) if match else "  "
                    content = re.sub(r'^(\s*)\{(\r?\n)', r'\g<1>{\g<2>' + indent + f'"sci:doi": "{doi}",\n', content)
            else:
                match = re.search(r'^(\s+)"', content, re.MULTILINE)
                indent = match.group(1) if match else "  "
                content = re.sub(r'^(\s*)\{(\r?\n)', r'\g<1>{\g<2>' + indent + f'"sci:doi": "{doi}",\n', content)

    # Update Extensions (Existing logic)
    ext_key = "conformsTo" if is_record else "stac_extensions"
    if scientific_ext not in content:
        if f'"{ext_key}"' in content:
            match = re.search(rf'("{ext_key}"\s*:\s*\[[^\]]*)', content, re.DOTALL)
            if match:
                prefix_block = match.group(1).rstrip()
                lines = prefix_block.split('\n')
                item_indent = "    "
                for line in reversed(lines):
                    if line.strip() and not line.strip().endswith('['):
                        m = re.match(r'^(\s*)', line)
                        if m:
                            item_indent = m.group(1)
                            break
                trailing_ws_match = re.search(r'(\s+)$', match.group(1))
                trailing_ws = trailing_ws_match.group(1) if trailing_ws_match else "\n  "
                if prefix_block.strip().endswith('['):
                    new_ext = f'\n{item_indent}"{scientific_ext}"'
                else:
                    new_ext = f',\n{item_indent}"{scientific_ext}"'
                content = content.replace(match.group(1), prefix_block + new_ext + trailing_ws)
        else:
            match = re.search(r'^(\s+)"', content, re.MULTILINE)
            indent = match.group(1) if match else "  "
            ext_entry = f'{indent}"{ext_key}": [\n{indent}{indent}"{scientific_ext}"\n{indent}],\n'
            content = re.sub(r'^(\s*)\{(\r?\n)', r'\g<1>{\g<2>' + ext_entry, content)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

def surgical_remove_publication(file_path: str, doi: str):
    """Surgically removes a DOI entry from sci:publications while preserving layout/formatting."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Escape the DOI for regex
    escaped_doi = re.escape(doi)

    # Pattern 1: match entry with a trailing comma
    pattern_trailing = rf'{{\s*"doi"\s*:\s*"{escaped_doi}"\s*}},\s*'
    content_new = re.sub(pattern_trailing, "", content)

    if content_new == content:
        # Pattern 2: match entry with a leading comma
        pattern_leading = rf',\s*{{\s*"doi"\s*:\s*"{escaped_doi}"\s*}}'
        content_new = re.sub(pattern_leading, "", content)

    if content_new == content:
        # Pattern 3: match entry with no commas (only item)
        pattern_only = rf'{{\s*"doi"\s*:\s*"{escaped_doi}"\s*}}'
        content_new = re.sub(pattern_only, "", content)

    if content_new != content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content_new)
        print(f"Surgically removed DOI {doi} from sci:publications in {file_path}")
    else:
        print(f"Warning: Could not find DOI {doi} in sci:publications in {file_path}")

def main():
    try:
        client = DataCiteClient()
    except ValueError as e:
        print(f"Error: {e}")
        return

    event_name = os.environ.get("GITHUB_EVENT_NAME")
    changed_files_env = os.environ.get("CHANGED_FILES")
    
    if event_name == "pull_request_target":
        if not changed_files_env or not changed_files_env.strip():
            print("No relevant STAC Collections or OGC Records were modified in this PR. Skipping DOI generation.")
            return
        files = [f for f in changed_files_env.strip().split() if f]
        print(f"Running audit on modified files only: {files}")
    else:
        print(f"Running full repository audit (Event: {event_name})...")
        files = glob.glob("products/**/collection.json", recursive=True) + \
                glob.glob("workflows/**/record.json", recursive=True)

    summary = []
    requested_versions = check_pr_for_new_version_requests()
    prefix = os.environ.get("DATACITE_PREFIX")

    for file_path in files:
        with open(file_path, 'r', encoding='utf-8') as f:
            stac_item = json.load(f)
        
        properties = stac_item.get("properties", stac_item)
        canonical_doi = properties.get("sci:doi") or stac_item.get("sci:doi")
        
        # 1. Canonical DOI Logic
        is_new_canonical = False
        if not canonical_doi or (prefix and not canonical_doi.startswith(prefix)):
            print(f"Generating Canonical DOI for {file_path}")
            metadata = map_stac_to_datacite(stac_item, PORTAL_UI_BASE_URL)
            try:
                new_canonical = client.create_draft_doi(metadata)
                surgical_update(file_path, new_canonical, is_publication=False)
                summary.append(f"- {file_path}: Created Canonical DOI {new_canonical}")
                canonical_doi = new_canonical
                is_new_canonical = True
            except Exception as e:
                print(f"Failed to create canonical DOI for {file_path}: {e}")
                summary.append(f"- {file_path}: FAILED to create Canonical DOI ({e})")
                continue
        else:
            # Update existing Canonical DOI metadata
            print(f"Updating metadata for Canonical DOI {canonical_doi}")
            metadata = map_stac_to_datacite(stac_item, PORTAL_UI_BASE_URL)
            try:
                client.update_doi(canonical_doi, metadata)
                summary.append(f"- {file_path}: Updated Canonical DOI metadata ({canonical_doi})")
            except Exception as e:
                print(f"Failed to update Canonical DOI {canonical_doi}: {e}")

        # Determine if the canonical DOI is brand new in this PR
        is_new_canonical_in_pr = False
        base_ref = os.environ.get("BASE_REF")
        if base_ref and event_name == "pull_request_target":
            try:
                import subprocess
                content_base = subprocess.check_output(
                    ["git", "show", f"{base_ref}:{file_path}"],
                    stderr=subprocess.DEVNULL
                ).decode("utf-8")
                data_base = json.loads(content_base)
                props_base = data_base.get("properties", data_base)
                base_doi = props_base.get("sci:doi") or data_base.get("sci:doi")
                is_new_canonical_in_pr = not base_doi or (prefix and not base_doi.startswith(prefix))
            except Exception:
                is_new_canonical_in_pr = True

        # 2. Versioned DOI Logic
        is_version_requested = file_path in requested_versions
        publications = properties.get("sci:publications", stac_item.get("sci:publications", []))
        our_versions = [p.get("doi") for p in publications if p.get("doi") and (not prefix or p.get("doi").startswith(prefix))]
        
        latest_v_doi = our_versions[-1] if our_versions else None
        latest_v_state = None
        if latest_v_doi:
            try:
                latest_v_state = client.get_doi_state(latest_v_doi)
            except Exception as e:
                print(f"Failed to check state for Version DOI {latest_v_doi}: {e}")

        if is_version_requested or is_new_canonical or is_new_canonical_in_pr:
            if is_new_canonical_in_pr:
                reason = "Initial version for new Canonical DOI in this PR"
            elif is_new_canonical:
                reason = "Initial version for new Canonical DOI"
            else:
                reason = "New version requested"
            
            # If the latest version DOI is already a draft, reuse it and update its metadata
            if latest_v_doi and latest_v_state == "draft":
                print(f"{reason} for {file_path}, but a Draft Version DOI ({latest_v_doi}) already exists. Reusing it.")
                metadata = map_stac_to_datacite(stac_item, PORTAL_UI_BASE_URL)
                if canonical_doi:
                    metadata["relatedIdentifiers"] = [{
                        "relatedIdentifier": canonical_doi,
                        "relatedIdentifierType": "DOI",
                        "relationType": "IsVersionOf"
                    }]
                try:
                    client.update_doi(latest_v_doi, metadata)
                    summary.append(f"- {file_path}: Reused and updated Draft Version DOI metadata ({latest_v_doi})")
                except Exception as e:
                    print(f"Failed to update existing Draft Version DOI {latest_v_doi}: {e}")
                    summary.append(f"- {file_path}: FAILED to update Draft Version DOI ({e})")
            else:
                # Generate a brand new Draft Version DOI
                print(f"{reason} for {file_path}. Generating Draft Version DOI.")
                metadata = map_stac_to_datacite(stac_item, PORTAL_UI_BASE_URL)
                if canonical_doi:
                    metadata["relatedIdentifiers"] = [{
                        "relatedIdentifier": canonical_doi,
                        "relatedIdentifierType": "DOI",
                        "relationType": "IsVersionOf"
                    }]

                try:
                    new_version_doi = client.create_draft_doi(metadata)
                    surgical_update(file_path, new_version_doi, is_publication=True)
                    summary.append(f"- {file_path}: Created Draft Version DOI {new_version_doi}")
                except Exception as e:
                    print(f"Failed to create version DOI for {file_path}: {e}")
                    summary.append(f"- {file_path}: FAILED to create Version DOI ({e})")
        else:
            # No version requested and it is not a new canonical.
            # If there is a draft version DOI in our publications, we must remove it (Unticked state)
            if latest_v_doi and latest_v_state == "draft":
                print(f"No version requested for {file_path}, but a Draft Version DOI ({latest_v_doi}) exists. Deleting draft and removing from publications.")
                try:
                    client.delete_doi(latest_v_doi)
                    surgical_remove_publication(file_path, latest_v_doi)
                    summary.append(f"- {file_path}: Deleted unticked Draft Version DOI ({latest_v_doi})")
                except Exception as e:
                    print(f"Failed to delete/remove unticked Draft Version DOI {latest_v_doi}: {e}")
                    summary.append(f"- {file_path}: FAILED to delete/remove unticked Draft Version DOI ({e})")
            else:
                # No draft exists, or latest version is already published.
                if latest_v_doi:
                    print(f"No version requested for {file_path}, and latest version ({latest_v_doi}) is already {latest_v_state or 'published'}. Skipping.")

    if summary:
        print("\nDOI Generation Summary:")
        print("\n".join(summary))
        # Optional: write summary to a file for GitHub Action to read
        with open("doi_summary.md", "w") as f:
            f.write("## DOI Generation Summary\n\n")
            f.write("\n".join(summary))
    else:
        print("No DOI actions performed.")

if __name__ == "__main__":
    main()
