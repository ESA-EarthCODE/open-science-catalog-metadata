import os
import json
import subprocess
import sys

# Add the current script's directory to sys.path to allow importing sibling modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datacite import DataCiteClient

def get_dois_from_file_at_commit(file_path: str, commit: str) -> set:
    """Extracts all DOIs (canonical and publications) from a file at a specific commit."""
    try:
        content = subprocess.check_output(
            ["git", "show", f"{commit}:{file_path}"],
            stderr=subprocess.DEVNULL
        ).decode("utf-8")
        data = json.loads(content)
        properties = data.get("properties", data)
        
        dois = set()
        
        # 1. Canonical DOI
        canonical = properties.get("sci:doi") or data.get("sci:doi")
        if canonical:
            dois.add(canonical)
            
        # 2. Versioned DOIs
        publications = properties.get("sci:publications", data.get("sci:publications", []))
        for p in publications:
            v_doi = p.get("doi")
            if v_doi:
                dois.add(v_doi)
                
        return dois
    except Exception:
        return set()

def main():
    try:
        client = DataCiteClient()
    except ValueError as e:
        print(f"Error: {e}")
        return

    base_ref = os.environ.get("BASE_REF")
    head_ref = os.environ.get("HEAD_REF")

    if not base_ref or not head_ref:
        print("BASE_REF or HEAD_REF environment variables are missing.")
        return

    print(f"Comparing PR branch ({head_ref}) against base branch ({base_ref})")

    try:
        diff_output = subprocess.check_output(
            ["git", "diff", "--name-only", f"{base_ref}...{head_ref}"],
            stderr=subprocess.DEVNULL
        ).decode("utf-8")
        
        changed_files = [f for f in diff_output.splitlines() if f.endswith("collection.json") or f.endswith("record.json")]
    except Exception as e:
        print(f"Failed to get git diff: {e}")
        return

    if not changed_files:
        print("No STAC Collections or OGC Records were modified in this PR. Nothing to clean up.")
        return

    deleted_count = 0
    prefix = os.environ.get("DATACITE_PREFIX")

    for file_path in changed_files:
        head_dois = get_dois_from_file_at_commit(file_path, head_ref)
        base_dois = get_dois_from_file_at_commit(file_path, base_ref)

        # Find new DOIs introduced in the PR branch
        new_dois = head_dois - base_dois

        if new_dois:
            for doi in new_dois:
                if prefix and not doi.startswith(prefix):
                    continue  # Skip foreign/external DOIs
                
                try:
                    state = client.get_doi_state(doi)
                    # We ONLY delete if it's a draft. (DataCite API also strictly enforces this)
                    if state == "draft":
                        print(f"Deleting dangling draft DOI {doi} for {file_path}")
                        try:
                            client.delete_doi(doi)
                            deleted_count += 1
                        except Exception as e:
                            print(f"Failed to delete DOI {doi}: {e}")
                    else:
                        print(f"DOI {doi} is in state '{state}', skipping deletion.")
                except Exception as e:
                    print(f"Failed to check state for DOI {doi}: {e}")
        else:
            print(f"No new DOIs detected for {file_path} in this PR.")

    print(f"Cleanup complete. Deleted {deleted_count} draft DOIs.")

if __name__ == "__main__":
    main()
