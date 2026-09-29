import os
import json
import glob
import subprocess
import shutil
from typing import List, Dict, Any, Optional, Tuple

def get_tags_for_item(stac_id: str, stac_type: str) -> List[Tuple[int, str, str]]:
    """Returns a list of (version, tag_name, commit_sha) for an item, sorted by version."""
    try:
        tag_prefix = f"{stac_type}-{stac_id}"
        output = subprocess.check_output(
            ["git", "tag", "-l", f"{tag_prefix}-v*"],
            stderr=subprocess.DEVNULL
        ).decode("utf-8").splitlines()
        
        tag_list = []
        for t in output:
            import re
            match = re.match(rf"^{re.escape(tag_prefix)}-v(\d+)$", t)
            if match:
                try:
                    v = int(match.group(1))
                    # Get commit SHA of the tag
                    commit = subprocess.check_output(
                        ["git", "rev-list", "-n", "1", t],
                        stderr=subprocess.DEVNULL
                    ).decode("utf-8").strip()
                    tag_list.append((v, t, commit))
                except (ValueError, subprocess.CalledProcessError):
                    continue
        
        return sorted(tag_list)
    except Exception:
        return []

def get_file_at_commit(file_path: str, commit_hash: str) -> Optional[Dict[str, Any]]:
    """Returns the JSON content of a file at a specific commit."""
    try:
        content = subprocess.check_output(
            ["git", "show", f"{commit_hash}:{file_path}"],
            stderr=subprocess.DEVNULL
        ).decode("utf-8")
        return json.loads(content)
    except Exception as e:
        print(f"Warning: Could not load {file_path} at commit {commit_hash}: {e}")
        return None

def safe_load_json(file_path: str) -> Optional[Dict[str, Any]]:
    """Loads a JSON file with robust error handling."""
    if not os.path.exists(file_path):
        return None
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"ERROR: Failed to parse {file_path}: {e}")
        # Print a snippet of the file around the error for debugging
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                start = max(0, e.lineno - 3)
                end = min(len(lines), e.lineno + 2)
                print("Context:")
                for i in range(start, end):
                    prefix = ">>" if i + 1 == e.lineno else "  "
                    print(f"{prefix} {i+1}: {lines[i].strip()}")
        except Exception:
            pass
        return None
    except Exception as e:
        print(f"ERROR: Unexpected error reading {file_path}: {e}")
        return None

def is_local_path(href: str) -> bool:
    """Checks if a href is a local relative path (not a URL or absolute path)."""
    if not href:
        return False
    # Check for common protocols
    if any(href.startswith(p) for p in ["http://", "https://", "s3://", "ftp://"]):
        return False
    # If it starts with / it's absolute to the system, which we don't want to version
    if href.startswith("/"):
        return False
    return True

def build_versioned_files(file_path: str, dist_dir: str):
    """Extracts historical versions based on Git tags and writes them to dist."""
    # Load current file to get ID
    current_data = safe_load_json(file_path)
    if not current_data:
        return
    
    properties = current_data.get("properties", current_data)
    stac_id = properties.get("id", current_data.get("id"))
    if not stac_id:
        return
        
    raw_type = properties.get("osc:type", current_data.get("osc:type", properties.get("type", "product")))
    stac_type = "workflow" if raw_type == "workflow" else "product"

    tags = get_tags_for_item(stac_id, stac_type)
    num_versions = len(tags)
    latest_v_num = tags[-1][0] if tags else 0
    
    if not tags:
        print(f"No tags found for {stac_id}, skipping history.")
        # We still want to copy the latest version though
        copy_latest(file_path, dist_dir, current_data, 0, 0, None)
        return

    target_subdir = os.path.dirname(os.path.join(dist_dir, file_path))
    os.makedirs(target_subdir, exist_ok=True)
    filename = os.path.basename(file_path) # e.g., collection.json
    base_name, ext = os.path.splitext(filename)

    for i, (v_num, tag_name, commit_sha) in enumerate(tags):
        data = get_file_at_commit(file_path, commit_sha)
        if not data:
            continue
        
        # Version and link STAC Items if they exist
        data = version_items(data, file_path, commit_sha, v_num, target_subdir, latest_v_num)
        
        v_filename = f"{base_name}_v{v_num}{ext}"
        
        # Swap DOIs for versioned files:
        # Versioned DOI goes to sci:doi, Canonical DOI goes to sci:publications
        props = data.get("properties", data)
        canonical_doi = props.get("sci:doi") or data.get("sci:doi")
        publications = props.get("sci:publications", data.get("sci:publications", []))
        
        # Find the DOI corresponding to this version number
        # We assume the N-th publication matching our prefix corresponds to version vN.
        # We can extract the prefix dynamically from the canonical_doi itself.
        prefix = None
        if canonical_doi and "/" in canonical_doi:
            prefix = canonical_doi.split("/")[0]

        our_versions = [p.get("doi") for p in publications if p.get("doi") and (not prefix or p.get("doi").startswith(prefix))]

        version_doi = None
        if our_versions and len(our_versions) >= v_num:
             version_doi = our_versions[v_num - 1]
        
        if version_doi and canonical_doi:
            if "properties" in data:
                data["properties"]["sci:doi"] = version_doi
                data["properties"]["sci:publications"] = [{"doi": canonical_doi}]
            else:
                data["sci:doi"] = version_doi
                data["sci:publications"] = [{"doi": canonical_doi}]

        # Inject navigation links
        links = data.get("links", [])
        
        # Canonical link
        links.append({"rel": "is-version-of", "href": f"{base_name}{ext}", "type": "application/json", "title": "Canonical version"})

        # Version history link (DataCite JSON variant for the Canonical DOI)
        if canonical_doi:
            api_base = os.getenv("DATACITE_API_URL", "https://api.test.datacite.org")
            datacite_json_url = f"{api_base}/dois/application/vnd.datacite.datacite+json/{canonical_doi}"
            links.append({"rel": "version-history", "href": datacite_json_url, "type": "application/vnd.datacite.datacite+json", "title": "Version History (DataCite JSON)"})

        # Latest version link should point to the actual latest versioned file
        if v_num < latest_v_num:
            links.append({"rel": "latest-version", "href": f"{base_name}_v{latest_v_num}{ext}", "type": "application/json", "title": "Latest version"})
        
        if i > 0:
            prev_v_num = tags[i-1][0]
            links.append({"rel": "predecessor-version", "href": f"{base_name}_v{prev_v_num}{ext}", "type": "application/json", "title": "Predecessor"})
        if i < num_versions - 1:
            next_v_num = tags[i+1][0]
            links.append({"rel": "successor-version", "href": f"{base_name}_v{next_v_num}{ext}", "type": "application/json", "title": "Successor"})

        data["links"] = links

        # Set the explicit version property to match the tag number
        data["version"] = str(v_num)

        # Ensure the Version Extension is in stac_extensions
        version_ext_url = "https://stac-extensions.github.io/version/v1.2.0/schema.json"
        if "stac_extensions" in data:
            if version_ext_url not in data["stac_extensions"]:
                data["stac_extensions"].append(version_ext_url)
        else:
            data["stac_extensions"] = [version_ext_url]

        with open(os.path.join(target_subdir, f"{base_name}_v{v_num}{ext}"), 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    # Copy latest
    prev_v_num = tags[-2][0] if num_versions > 1 else None
    copy_latest(file_path, dist_dir, current_data, num_versions, latest_v_num, prev_v_num)

def version_items(collection_data: Dict[str, Any], collection_path: str, commit_sha: str, v_num: int, target_subdir: str, latest_v_num: int) -> Dict[str, Any]:
    """Finds 'item' links, versions the items at the commit_sha, and updates links."""
    links = collection_data.get("links", [])
    new_links = []
    
    collection_dir = os.path.dirname(collection_path)
    
    for link in links:
        if link.get("rel") == "item":
            item_href = link.get("href")
            
            # ONLY version items that are local relative paths
            if is_local_path(item_href):
                # Resolve relative path
                item_path = os.path.normpath(os.path.join(collection_dir, item_href))
                
                item_data = get_file_at_commit(item_path, commit_sha)
                if item_data:
                    # Save versioned item
                    item_basename = os.path.basename(item_path)
                    item_name, item_ext = os.path.splitext(item_basename)
                    v_item_name = f"{item_name}_v{v_num}{item_ext}"
                    
                    # Inject navigation into item too
                    item_links = item_data.get("links", [])
                    if v_num < latest_v_num:
                        item_links.append({"rel": "latest-version", "href": f"{item_name}_v{latest_v_num}{item_ext}", "type": "application/json", "title": "Latest version"})
                    item_data["links"] = item_links

                    with open(os.path.join(target_subdir, v_item_name), 'w', encoding='utf-8') as f:
                        json.dump(item_data, f, indent=2)
                    
                    # Update collection link to point to versioned item
                    link["href"] = v_item_name
        
        new_links.append(link)
    
    collection_data["links"] = new_links
    return collection_data

def copy_latest(file_path: str, dist_dir: str, data: Dict[str, Any], num_versions: int, latest_v_num: int, prev_v_num: Optional[int]):
    """Copies the latest version of the collection and its items to dist."""
    target_subdir = os.path.dirname(os.path.join(dist_dir, file_path))
    os.makedirs(target_subdir, exist_ok=True)
    filename = os.path.basename(file_path)
    base_name, ext = os.path.splitext(filename)

    # Process items for the latest version too
    links = data.get("links", [])
    collection_dir = os.path.dirname(file_path)
    for link in links:
        if link.get("rel") == "item":
            item_href = link.get("href")
            if is_local_path(item_href):
                item_path = os.path.normpath(os.path.join(collection_dir, item_href))
                if os.path.exists(item_path):
                    shutil.copy(item_path, os.path.join(target_subdir, os.path.basename(item_path)))

    # Inject navigation links into the latest version
    # Point to the actual latest versioned file
    links.append({"rel": "latest-version", "href": f"{base_name}_v{latest_v_num}{ext}", "type": "application/json", "title": "Latest version"})

    # Point to all versions
    props = data.get("properties", data)
    stac_id = props.get("id", data.get("id"))
    raw_type = props.get("osc:type", data.get("osc:type", props.get("type", "product")))
    stac_type = "workflow" if raw_type == "workflow" else "product"

    tags = get_tags_for_item(stac_id, stac_type)
    for v_num, _, _ in tags:
         links.append({"rel": "has-version", "href": f"{base_name}_v{v_num}{ext}", "type": "application/json", "title": f"Version {v_num}"})

    # Version history link (DataCite JSON variant for the Canonical DOI)
    canonical_doi = props.get("sci:doi") or data.get("sci:doi")
    if canonical_doi:
        api_base = os.getenv("DATACITE_API_URL", "https://api.test.datacite.org")
        datacite_json_url = f"{api_base}/dois/application/vnd.datacite.datacite+json/{canonical_doi}"
        links.append({"rel": "version-history", "href": datacite_json_url, "type": "application/vnd.datacite.datacite+json", "title": "Version History (DataCite JSON)"})
    
    data["links"] = links
    
    # Remove the version property from the canonical file
    if "version" in data:
        del data["version"]

    # Ensure the Version Extension is in stac_extensions
    version_ext_url = "https://stac-extensions.github.io/version/v1.2.0/schema.json"
    if "stac_extensions" in data:
        if version_ext_url not in data["stac_extensions"]:
            data["stac_extensions"].append(version_ext_url)
    else:
        data["stac_extensions"] = [version_ext_url]
    
    with open(os.path.join(target_subdir, filename), 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

def copy_directory(src_dir: str, dest_dir: str):
    """Copies an entire directory if it exists."""
    if os.path.exists(src_dir):
        shutil.copytree(src_dir, os.path.join(dest_dir, src_dir), dirs_exist_ok=True)

def copy_file(src_file: str, dest_dir: str):
    """Copies a file if it exists, creating parent directories if needed."""
    if os.path.exists(src_file):
        dest_file = os.path.join(dest_dir, src_file)
        os.makedirs(os.path.dirname(dest_file), exist_ok=True)
        shutil.copy(src_file, dest_file)

def main():
    dist_dir = "dist"
    if os.path.exists(dist_dir):
        shutil.rmtree(dist_dir)
    os.makedirs(dist_dir)

    # 1. Copy root files
    if os.path.exists("catalog.json"):
        shutil.copy("catalog.json", os.path.join(dist_dir, "catalog.json"))

    # 2. Copy supplementary directories
    for d in ["eo-missions", "experiments", "projects", "themes", "variables"]:
        copy_directory(d, dist_dir)
        
    # 3. Copy intermediate catalog files for products and workflows
    copy_file("products/catalog.json", dist_dir)
    copy_file("workflows/catalog.json", dist_dir)

    # 4. Version and build the main collections/records
    files = glob.glob("products/**/collection.json", recursive=True) + \
            glob.glob("workflows/**/record.json", recursive=True)

    for file_path in files:
        print(f"Processing versioned tags for {file_path}...")
        build_versioned_files(file_path, dist_dir)

    print(f"Build complete. Files in {dist_dir}/")

if __name__ == "__main__":
    main()
