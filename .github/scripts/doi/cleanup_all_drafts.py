import os
import sys
import json
import urllib.request
import urllib.error

# Add the current script's directory to sys.path to allow importing sibling modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datacite import DataCiteClient, DATACITE_API_BASE_URL, DATACITE_USER

def main():
    try:
        client = DataCiteClient()
    except ValueError as e:
        print(f"Error: {e}")
        return

    # Check that we have the repository user
    if not DATACITE_USER:
        print("DATACITE_USER environment variable is missing.")
        return

    client_id = DATACITE_USER.lower()
    print(f"Fetching all draft DOIs for client repository: {client_id}")

    # Build request URL for DataCite API
    # We filter by client-id and draft state
    url = f"{DATACITE_API_BASE_URL}/dois?client-id={client_id}&state=draft&page[size]=100"
    
    draft_dois = []
    
    # Simple pagination loop
    current_url = url
    headers = {
        "Authorization": client.auth_header,
        "Accept": "application/vnd.api+json"
    }

    while current_url:
        req = urllib.request.Request(current_url, headers=headers)
        try:
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode("utf-8"))
                
                # Extract DOIs from data
                data = result.get("data", [])
                for item in data:
                    doi = item.get("attributes", {}).get("doi")
                    if doi:
                        draft_dois.append(doi)
                
                # Check for next page
                links = result.get("links", {})
                current_url = links.get("next")
        except Exception as e:
            print(f"Failed to fetch draft DOIs from {current_url}: {e}")
            break

    if not draft_dois:
        print("No draft DOIs found in this DataCite repository account.")
        return

    print(f"Found {len(draft_dois)} draft DOIs. Starting deletion...")

    deleted_count = 0
    for doi in draft_dois:
        try:
            print(f"Deleting Draft DOI: {doi}")
            client.delete_doi(doi)
            deleted_count += 1
        except Exception as e:
            print(f"Failed to delete DOI {doi}: {e}")

    print(f"\nCleanup complete. Successfully deleted {deleted_count} out of {len(draft_dois)} draft DOIs.")

if __name__ == "__main__":
    main()
