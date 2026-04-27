"""Parse registry.yaml and merge with auto-discovery results."""

import os
import yaml


def load_registry(app_dir):
    """Return parsed registry dict or empty structure on failure."""
    path = os.path.join(app_dir, "registry.yaml")
    try:
        with open(path, "r") as f:
            data = yaml.safe_load(f) or {}
        return data, None
    except (yaml.YAMLError, OSError) as e:
        return {"projects": [], "links": []}, str(e)


def merge_projects(registry_projects, discovered_projects):
    """Merge: registry wins by id. Discovered entries get a 'discovered' badge."""
    reg_by_id = {p["id"]: p for p in registry_projects}
    merged = list(registry_projects)
    for dp in discovered_projects:
        if dp["id"] not in reg_by_id:
            dp["discovered"] = True
            merged.append(dp)
    return merged
