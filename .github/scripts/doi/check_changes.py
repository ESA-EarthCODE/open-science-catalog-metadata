import json
import subprocess
import os
from typing import Dict, Any, Optional, Tuple

def get_file_at_commit(file_path: str, commit_hash: str) -> Optional[Dict[str, Any]]:
    """Returns the JSON content of a file at a specific commit."""
    try:
        content = subprocess.check_output(
            ["git", "show", f"{commit_hash}:{file_path}"],
            stderr=subprocess.DEVNULL
        ).decode("utf-8")
        return json.loads(content)
    except Exception:
        return None

def get_last_doi_change_commit(file_path: str) -> Optional[str]:
    """Finds the last commit hash where 'sci:doi' was modified in the file."""
    try:
        # -G looks for differences that have added or removed a match for the regex
        output = subprocess.check_output(
            ["git", "log", "-G", '"sci:doi"', "--format=%H", "-n", "1", "--", file_path],
            stderr=subprocess.DEVNULL
        ).decode("utf-8").strip()
        return output if output else None
    except Exception:
        return None

def get_last_version_tag_commit(stac_id: str, stac_type: str) -> Optional[str]:
    """Finds the commit hash of the latest version tag (<stac_type>-<stac_id>-v*)."""
    import re
    try:
        tag_prefix = f"{stac_type}-{stac_id}"
        # Get all tags for this ID, sorted by version number descending
        output = subprocess.check_output(
            ["git", "tag", "-l", f"{tag_prefix}-v*"],
            stderr=subprocess.DEVNULL
        ).decode("utf-8").splitlines()
            
        if not output:
            return None
            
        # Parse versions and sort
        tag_versions = []
        for t in output:
            match = re.match(rf"^{re.escape(tag_prefix)}-v(\d+)$", t)
            if match:
                try:
                    v = int(match.group(1))
                    tag_versions.append((v, t))
                except ValueError:
                    continue
        
        if not tag_versions:
            return None
            
        latest_tag = sorted(tag_versions, reverse=True)[0][1]
        
        # Get commit SHA of the tag
        commit = subprocess.check_output(
            ["git", "rev-list", "-n", "1", latest_tag],
            stderr=subprocess.DEVNULL
        ).decode("utf-8").strip()
        
        return commit
    except Exception:
        return None

def is_significant_change(current: Dict[str, Any], historical: Dict[str, Any]) -> bool:
    """
    Checks if metadata fields relevant to DataCite have changed.
    Includes title, description, keywords, providers, extent, and links.
    """
    # Handle OGC Record structure where most fields are in properties
    curr_props = current.get("properties", current)
    hist_props = historical.get("properties", historical)

    # Fields that might be in 'properties' (Workflows) or top-level (Products)
    fields_to_check = ["title", "description", "keywords", "providers", "extent"]
    
    for field in fields_to_check:
        if curr_props.get(field) != hist_props.get(field):
            return True
    
    # Check Links (typically top-level in both, but we check both just in case)
    if current.get("links") != historical.get("links"):
        return True
    
    if curr_props.get("links") != hist_props.get("links"):
        return True
        
    return False

def check_pr_for_new_version_requests() -> set:
    """Checks the PR body for file-specific checkboxes requesting a new DOI version."""
    import re
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path or not os.path.exists(event_path):
        return set()
    
    try:
        with open(event_path, 'r') as f:
            event_data = json.load(f)
            pr_body = event_data.get("pull_request", {}).get("body", "")
            if not pr_body:
                return set()
            
            # Find all ticked checkboxes matching our pattern
            matches = re.findall(r"-\s*\[[xX]\]\s*Request new DOI version for `([^`]+)`", pr_body)
            return set(matches)
    except Exception as e:
        print(f"Warning: Could not check PR body: {e}")
        return set()

def check_doi_need(file_path: str, requested_files: Optional[set] = None) -> Tuple[bool, Optional[str]]:
    """
    Checks if a file needs a new DOI.
    Returns (needs_doi, reason).
    """
    if not os.path.exists(file_path):
        return False, None

    # Check for explicit version request first
    if requested_files is None:
        requested_files = check_pr_for_new_version_requests()
    if file_path in requested_files:
        return True, "Explicit version request via PR checkbox"

    with open(file_path, 'r') as f:
        try:
            current_data = json.load(f)
        except json.JSONDecodeError:
            return False, "Invalid JSON"

    # Support nested properties for OGC Records
    properties = current_data.get("properties", current_data)

    if properties.get("osc:skip_doi") is True or current_data.get("osc:skip_doi") is True:
        return False, "Skipped via osc:skip_doi"

    doi = properties.get("sci:doi") or current_data.get("sci:doi")
    if not doi:
        return True, "Missing sci:doi"

    # Check if it's a foreign DOI (not matching our prefix)
    prefix = os.environ.get("DATACITE_PREFIX")
    if prefix and not doi.startswith(prefix):
        return True, f"Foreign DOI detected ({doi})"

    # If DOI exists, check for significant changes since it was last set
    stac_id = properties.get("id", current_data.get("id"))
    raw_type = properties.get("osc:type", current_data.get("osc:type", properties.get("type", "product")))
    stac_type = "workflow" if raw_type == "workflow" else "product"
    
    # Tiered fallback to find the historical baseline:
    # 1. Latest official version tag (<stac_type>-<id>-v*)
    # 2. Last commit that modified the "sci:doi" string (for untagged existing DOIs)
    # 3. The very first commit of the file
    last_commit = get_last_version_tag_commit(stac_id, stac_type)
    if not last_commit:
        last_commit = get_last_doi_change_commit(file_path)
    
    if not last_commit:
        # Final fallback: Assume current state is the validated baseline
        # to avoid re-versioning legacy items that haven't been tagged yet.
        try:
            last_commit = subprocess.check_output(
                ["git", "log", "-n", "1", "--format=%H", "--", file_path]
            ).decode("utf-8").strip()
        except Exception:
            return False, "Could not determine file history"

    historical_data = get_file_at_commit(file_path, last_commit)
    if not historical_data:
        return False, "Could not retrieve historical data"

    if is_significant_change(current_data, historical_data):
        return True, f"Significant changes detected since {last_commit}"

    return False, None
