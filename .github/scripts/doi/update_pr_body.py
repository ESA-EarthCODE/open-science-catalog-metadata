import os
import json
import urllib.request
import urllib.error
import re

def main():
    event_name = os.environ.get("GITHUB_EVENT_NAME")
    if event_name != "pull_request_target":
        return
    
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    changed_files_env = os.environ.get("CHANGED_FILES", "")
    changed_files = [f for f in changed_files_env.strip().split() if f]
    
    if not changed_files:
        return

    if not event_path or not os.path.exists(event_path):
        print("GITHUB_EVENT_PATH not found.")
        return

    with open(event_path, 'r') as f:
        event_data = json.load(f)
    
    pr = event_data.get("pull_request")
    if not pr:
        return
    
    pr_body = pr.get("body") or ""
    pr_url = pr.get("url")
    token = os.environ.get("GITHUB_TOKEN")
    
    if not token:
        print("No GITHUB_TOKEN available, skipping PR body update.")
        return

    # Parse existing checkboxes to preserve state
    existing_states = {}
    for match in re.finditer(r"-\s*\[([ xX])\]\s*Request new DOI version for `([^`]+)`", pr_body):
        state = match.group(1).lower() == 'x'
        filepath = match.group(2)
        existing_states[filepath] = state
    
    import subprocess
    base_ref = os.environ.get("BASE_REF")
    prefix = os.environ.get("DATACITE_PREFIX")

    version_files = []
    auto_v1_files = []

    for f in changed_files:
        has_base_doi = False
        if base_ref:
            try:
                content_base = subprocess.check_output(
                    ["git", "show", f"{base_ref}:{f}"],
                    stderr=subprocess.DEVNULL
                ).decode("utf-8")
                data_base = json.loads(content_base)
                props_base = data_base.get("properties", data_base)
                base_doi = props_base.get("sci:doi") or data_base.get("sci:doi")
                if base_doi and (not prefix or base_doi.startswith(prefix)):
                    has_base_doi = True
            except Exception:
                pass

        if has_base_doi:
            version_files.append(f)
        else:
            auto_v1_files.append(f)

    # Generate new checklist
    checklist_lines = [
        "<!-- DOI_CHECKLIST_START -->",
        "### 🏷️ DOI Versioning",
        "Select the files you want to generate a new DOI version for. (Otherwise, only the metadata of the Canonical DOI will be updated).",
        ""
    ]
    if version_files:
        for f in version_files:
            mark = "x" if existing_states.get(f) else " "
            checklist_lines.append(f"- [{mark}] Request new DOI version for `{f}`")
    else:
        checklist_lines.append("_No existing datasets modified that require manual versioning._")

    if auto_v1_files:
        checklist_lines.append("")
        checklist_lines.append("ℹ️ **New Datasets/Workflows (Initial v1 DOI automatically assigned):**")
        for f in auto_v1_files:
            checklist_lines.append(f"- `{f}`")

    checklist_lines.append("<!-- DOI_CHECKLIST_END -->")
    new_checklist_str = "\n".join(checklist_lines)

    # Replace or append
    if "<!-- DOI_CHECKLIST_START -->" in pr_body and "<!-- DOI_CHECKLIST_END -->" in pr_body:
        new_body = re.sub(
            r"<!-- DOI_CHECKLIST_START -->.*<!-- DOI_CHECKLIST_END -->",
            new_checklist_str,
            pr_body,
            flags=re.DOTALL
        )
    else:
        new_body = pr_body + "\n\n" + new_checklist_str
    
    if new_body.strip() == pr_body.strip():
        print("PR body is already up to date.")
        return
    
    # Update PR via GitHub API
    req = urllib.request.Request(pr_url, method="PATCH", data=json.dumps({"body": new_body}).encode("utf-8"), headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json"
    })
    
    try:
        with urllib.request.urlopen(req) as response:
            print("Successfully updated PR body with dynamic DOI checklist.")
    except urllib.error.HTTPError as e:
        print(f"Failed to update PR body: {e.read().decode('utf-8')}")

if __name__ == "__main__":
    main()
