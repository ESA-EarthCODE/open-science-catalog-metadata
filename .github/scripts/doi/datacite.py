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

def map_license_to_datacite_rights(license_str: Optional[str], links: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Maps STAC license strings and license links to standard DataCite rightsList objects."""
    # Find any link with rel="license"
    license_link = None
    for link in links:
        if link.get("rel") == "license" and link.get("href"):
            license_link = link
            break

    # Standardize lookup for the license string
    lic_key = license_str.strip().upper() if license_str else ""
    
    # Official SPDX definitions
    spdx_mapping = {
        "CC-BY-4.0": {
            "rights": "Creative Commons Attribution 4.0 International",
            "rightsUri": "https://creativecommons.org/licenses/by/4.0/legalcode",
            "rightsIdentifier": "cc-by-4.0"
        },
        "CC-BY-SA-4.0": {
            "rights": "Creative Commons Attribution-ShareAlike 4.0 International",
            "rightsUri": "https://creativecommons.org/licenses/by-sa/4.0/legalcode",
            "rightsIdentifier": "cc-by-sa-4.0"
        },
        "CC-BY-NC-4.0": {
            "rights": "Creative Commons Attribution-NonCommercial 4.0 International",
            "rightsUri": "https://creativecommons.org/licenses/by-nc/4.0/legalcode",
            "rightsIdentifier": "cc-by-nc-4.0"
        },
        "CC-BY-NC-SA-4.0": {
            "rights": "Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International",
            "rightsUri": "https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode",
            "rightsIdentifier": "cc-by-nc-sa-4.0"
        },
        "CC0-1.0": {
            "rights": "Creative Commons Zero v1.0 Universal",
            "rightsUri": "https://creativecommons.org/publicdomain/zero/1.0/legalcode",
            "rightsIdentifier": "cc0-1.0"
        },
        "MIT": {
            "rights": "MIT License",
            "rightsUri": "https://opensource.org/licenses/MIT",
            "rightsIdentifier": "mit"
        },
        "APACHE-2.0": {
            "rights": "Apache License 2.0",
            "rightsUri": "https://www.apache.org/licenses/LICENSE-2.0",
            "rightsIdentifier": "apache-2.0"
        },
        "LGPL-3.0-ONLY": {
            "rights": "GNU Lesser General Public License v3.0 only",
            "rightsUri": "https://www.gnu.org/licenses/lgpl-3.0.html",
            "rightsIdentifier": "lgpl-3.0-only"
        },
        "OGL-UK-3.0": {
            "rights": "Open Government Licence v3.0",
            "rightsUri": "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/",
            "rightsIdentifier": "ogl-uk-3.0"
        },
        "PROPRIETARY": {
            "rights": "Proprietary",
            "rightsUri": None,
            "rightsIdentifier": "proprietary"
        },
        "VARIOUS": {
            "rights": "Various",
            "rightsUri": None,
            "rightsIdentifier": "various"
        }
    }
    
    # 1. If we have a license link, try to map or use it directly
    if license_link:
        href = license_link.get("href")
        title = license_link.get("title")
        
        # Check if the href points to one of our standard SPDX licenses
        mapped = None
        for spdx_info in spdx_mapping.values():
            if spdx_info.get("rightsUri") and spdx_info["rightsUri"] in href:
                mapped = spdx_info
                break
                
        if mapped:
            return [{
                "rights": mapped["rights"],
                "rightsUri": mapped["rightsUri"],
                "rightsIdentifier": mapped["rightsIdentifier"],
                "rightsIdentifierScheme": "SPDX",
                "schemeUri": "https://spdx.org/licenses/"
            }]
        else:
            # Custom/proprietary license with direct link (e.g. Aviso License)
            rights_name = title or license_str or "License"
            rights_id = license_str.lower() if license_str else "proprietary"
            return [{
                "rights": rights_name,
                "rightsUri": href,
                "rightsIdentifier": rights_id,
                "rightsIdentifierScheme": "SPDX",
                "schemeUri": "https://spdx.org/licenses/"
            }]

    # 2. No link found, map purely by license_str
    if not license_str:
        return []

    mapped = spdx_mapping.get(lic_key)
    if not mapped:
        # Fallback to loose matching (without dashes, dots, or underscores)
        clean_key = lic_key.replace("-", "").replace(".", "").replace("_", "")
        clean_mapping = {k.replace("-", "").replace(".", "").replace("_", ""): v for k, v in spdx_mapping.items()}
        mapped = clean_mapping.get(clean_key)
        
    if mapped:
        rights_item = {
            "rights": mapped["rights"],
            "rightsIdentifier": mapped["rightsIdentifier"],
            "rightsIdentifierScheme": "SPDX",
            "schemeUri": "https://spdx.org/licenses/"
        }
        if mapped["rightsUri"]:
            rights_item["rightsUri"] = mapped["rightsUri"]
        return [rights_item]
    else:
        # Fallback for custom or unlisted licenses
        return [{
            "rights": license_str,
            "rightsIdentifier": license_str.lower(),
            "rightsIdentifierScheme": "SPDX",
            "schemeUri": "https://spdx.org/licenses/"
        }]

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
    license_str = properties.get("license", stac_item.get("license"))
    
    # Extract creators/publishers/contributors from providers
    providers = properties.get("providers", stac_item.get("providers", []))
    creators = []
    contributors = []
    publisher = "EarthCODE"
    
    for provider in providers:
        name = provider.get("name")
        if name == "ESA EarthCODE":
            name = "EarthCODE"
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
        creators = [{"name": "EarthCODE", "nameType": "Organizational"}]

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
        "rightsList": map_license_to_datacite_rights(license_str, links),
        "relatedIdentifiers": related_identifiers,
        "url": f"{portal_ui_base_url}/{path_segment}/{stac_id}{suffix}"
    }
    
    return attributes
