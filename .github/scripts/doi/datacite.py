import os
import json
import urllib.request
import urllib.error
import base64
from typing import Optional, Dict, Any, List

DATACITE_API_BASE_URL = os.getenv("DATACITE_API_URL", "https://api.test.datacite.org")
DATACITE_USER = os.getenv("DATACITE_USER")
DATACITE_PASSWORD = os.getenv("DATACITE_PASSWORD")
DATACITE_PREFIX = os.getenv("DATACITE_PREFIX")

class DataCiteError(Exception):
    """Custom exception for DataCite API errors, including the response body."""
    def __init__(self, code: int, body: str):
        self.code = code
        self.body = body
        super().__init__(f"DataCite API Error {code}: {body}")

class DataCiteClient:
    def __init__(self):
        if not all([DATACITE_USER, DATACITE_PASSWORD, DATACITE_PREFIX]):
            raise ValueError("Missing DataCite credentials or prefix env vars.")
        
        auth_str = f"{DATACITE_USER}:{DATACITE_PASSWORD}"
        self.auth_header = f"Basic {base64.b64encode(auth_str.encode()).decode()}"

    def _request(self, method: str, url: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        headers = {
            "Content-Type": "application/vnd.api+json",
            "Authorization": self.auth_header
        }
        
        json_data = json.dumps(data).encode("utf-8") if data else None
        req = urllib.request.Request(url, data=json_data, headers=headers, method=method)
        
        try:
            with urllib.request.urlopen(req) as response:
                if response.status == 204:
                    return {}
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            raise DataCiteError(e.code, error_body) from e

    def create_draft_doi(self, metadata: Dict[str, Any]) -> str:
        """Creates a Draft DOI and returns the DOI string."""
        url = f"{DATACITE_API_BASE_URL}/dois"
        payload = {
            "data": {
                "type": "dois",
                "attributes": {
                    "prefix": DATACITE_PREFIX,
                    "event": "draft",
                    **metadata
                }
            }
        }
        result = self._request("POST", url, payload)
        return result["data"]["attributes"]["doi"]

    def get_doi_state(self, doi: str) -> Optional[str]:
        """Returns the state of the DOI (draft, findable, registered) or None if not found."""
        url = f"{DATACITE_API_BASE_URL}/dois/{doi}"
        try:
            result = self._request("GET", url)
            return result["data"]["attributes"]["state"]
        except DataCiteError as e:
            if e.code == 404:
                return None
            raise

    def update_doi(self, doi: str, attributes: Dict[str, Any]) -> None:
        """Updates an existing DOI's attributes."""
        url = f"{DATACITE_API_BASE_URL}/dois/{doi}"
        payload = {
            "data": {
                "type": "dois",
                "attributes": attributes
            }
        }
        self._request("PUT", url, payload)

    def delete_doi(self, doi: str) -> None:
        """Deletes a draft DOI."""
        url = f"{DATACITE_API_BASE_URL}/dois/{doi}"
        self._request("DELETE", url)

    def publish_doi(self, doi: str, target_url: str) -> None:
        """Transitions a DOI from Draft to Findable state."""
        self.update_doi(doi, {"event": "publish", "url": target_url})

def map_stac_to_datacite(stac_item: Dict[str, Any], portal_ui_base_url: str, extra_related_identifiers: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Maps STAC or OGC Record metadata to DataCite attributes including recommended properties."""
    # OGC Records (often used for workflows) nest attributes in 'properties'
    properties = stac_item.get("properties", stac_item)
    stac_id = stac_item.get("id")
    
    # Extract from properties if available, fallback to top-level
    title = properties.get("title", stac_item.get("title", stac_id))
    description = properties.get("description", stac_item.get("description", ""))
    created_at = properties.get("created", stac_item.get("created"))
    updated_at = properties.get("updated", stac_item.get("updated"))
    publication_year = created_at[:4] if created_at else "2026"
    
    # Extract creators/publishers/contributors from providers
    providers = properties.get("providers", stac_item.get("providers", []))
    creators = []
    contributors = []
    publisher = "ESA EarthCODE"
    
    for provider in providers:
        name = provider.get("name")
        roles = provider.get("roles", [])
        # DataCite roles mapping
        if "producer" in roles:
            creators.append({"name": name})
        if "host" in roles:
            publisher = name
        if any(r in roles for r in ["licensor", "processor", "contributor"]):
            contributors.append({
                "name": name, 
                "contributorType": "DataCollector" if "processor" in roles else "Distributor"
            })

    if not creators:
        creators = [{"name": "ESA EarthCODE", "nameType": "Organizational"}]

    # Determine type and URL structure
    # OGC records might have type in properties
    raw_type = properties.get("osc:type", stac_item.get("osc:type", properties.get("type", "product")))
    stac_type = "workflow" if raw_type == "workflow" else "product"
    
    suffix = "/collection" if stac_type == "product" else "/record"
    path_segment = f"{stac_type}s"

    # Resource Type Mapping
    if stac_type == "product":
        resource_type_general = "Dataset"
        resource_type_name = "Dataset"
    else:
        # Detect specific workflow types
        app_type = properties.get("application:type", "").lower()
        if "jupyter-notebook" in app_type or "notebook" in app_type:
            resource_type_general = "ComputationalNotebook"
            resource_type_name = "Jupyter Notebook"
        else:
            resource_type_general = "Workflow"
            resource_type_name = "Workflow"

    # Subjects (Keywords)
    subjects = []
    keywords = properties.get("keywords", stac_item.get("keywords", []))
    for kw in keywords:
        subjects.append({"subject": kw})

    # Dates
    dates = []
    if created_at:
        dates.append({"date": created_at, "dateType": "Created"})
    if updated_at:
        dates.append({"date": updated_at, "dateType": "Updated"})
    
    # Geolocations
    geolocations = []
    extent = properties.get("extent", stac_item.get("extent", {}))
    spatial = extent.get("spatial", {})
    bboxes = spatial.get("bbox", [])
    if bboxes and isinstance(bboxes[0], list):
        for bbox in bboxes:
            if len(bbox) >= 4:
                geolocations.append({
                    "geoLocationBox": {
                        "westBoundLongitude": bbox[0],
                        "southBoundLatitude": bbox[1],
                        "eastBoundLongitude": bbox[2],
                        "northBoundLatitude": bbox[3]
                    }
                })

    # Related Identifiers (Links)
    related_identifiers = []
    if extra_related_identifiers:
        related_identifiers.extend(extra_related_identifiers)
    
    links = stac_item.get("links", []) # Links are usually top-level in both STAC and OGC
    for link in links:
        rel = link.get("rel")
        href = link.get("href")
        if rel in ["cite-as", "via", "derived_from", "git"] and href:
            # Try to detect if it's a DOI
            if "doi.org/" in href:
                doi_val = href.split("doi.org/")[-1]
                related_identifiers.append({
                    "relatedIdentifier": doi_val,
                    "relatedIdentifierType": "DOI",
                    "relationType": "IsDerivedFrom" if rel == "derived_from" else "IsDescribedBy"
                })
            elif href.startswith("http"):
                related_identifiers.append({
                    "relatedIdentifier": href,
                    "relatedIdentifierType": "URL",
                    "relationType": "IsDerivedFrom" if rel == "derived_from" else "IsDescribedBy"
                })

    attributes = {
        "titles": [{"title": title}],
        "creators": creators,
        "contributors": contributors,
        "publisher": publisher,
        "publicationYear": int(publication_year),
        "subjects": subjects,
        "dates": dates,
        "language": "en",
        "types": {
            "resourceTypeGeneral": resource_type_general,
            "resourceType": resource_type_name
        },
        "descriptions": [{"description": description, "descriptionType": "Abstract"}],
        "geoLocations": geolocations,
        "relatedIdentifiers": related_identifiers,
        "url": f"{portal_ui_base_url}/{path_segment}/{stac_id}{suffix}"
    }
    
    return attributes
