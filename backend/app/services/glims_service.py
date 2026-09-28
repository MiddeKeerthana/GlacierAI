from pathlib import Path

import geopandas as gpd
import requests

from shapely.geometry import shape, mapping


# ==========================================================
# GLIMS CONFIGURATION
# ==========================================================

GLIMS_WFS_URL = "https://glims.org/geoserver/wfs"

GLIMS_LAYER = "GLIMS:GLIMS_Glacier_Outlines"


# ==========================================================
# PROJECT PATHS
# ==========================================================

PROJECT_DIR = Path(__file__).resolve().parents[3]

RGI_PATH = (
    PROJECT_DIR
    / "datasets"
    / "processed"
    / "global_rgi.gpkg"
)


# ==========================================================
# SEARCH CONFIGURATION
# ==========================================================

# Historical GLIMS outlines can extend beyond the
# current RGI polygon. Therefore we expand the RGI
# bounding box before querying GLIMS.
BBOX_PADDING_DEGREES = 0.20

GLIMS_REQUEST_LIMIT = 1000


# ==========================================================
# FETCH GLIMS OUTLINES
# ==========================================================

def get_glims_outlines(
    glacier_geometry,
    glims_id=None,
    limit=GLIMS_REQUEST_LIMIT,
):
    """
    Fetch historical GLIMS glacier outlines.

    The search area is intentionally larger than the
    current RGI polygon because historical GLIMS outlines
    can differ substantially from the current RGI boundary.

    If a GLIMS ID is available, it is used as the primary
    identity filter so neighboring glaciers are not returned.
    """

    if glacier_geometry is None:
        return []

    # ------------------------------------------------------
    # Validate geometry
    # ------------------------------------------------------

    if not glacier_geometry.is_valid:
        glacier_geometry = glacier_geometry.buffer(0)

    if glacier_geometry.is_empty:
        return []

    # ------------------------------------------------------
    # RGI bounding box
    # ------------------------------------------------------

    minx, miny, maxx, maxy = glacier_geometry.bounds

    # Expand the bounding box so historical outlines
    # outside the current RGI boundary can still be found.
    minx -= BBOX_PADDING_DEGREES
    miny -= BBOX_PADDING_DEGREES
    maxx += BBOX_PADDING_DEGREES
    maxy += BBOX_PADDING_DEGREES

    # ------------------------------------------------------
    # WFS request
    # ------------------------------------------------------

    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": GLIMS_LAYER,
        "outputFormat": "application/json",
        "srsName": "EPSG:4326",
        "bbox": (
            f"{minx},{miny},{maxx},{maxy},"
            "EPSG:4326"
        ),
        "count": limit,
    }

    # ------------------------------------------------------
    # Request GLIMS
    # ------------------------------------------------------

    response = requests.get(
        GLIMS_WFS_URL,
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    features = data.get(
        "features",
        [],
    )

    matched_features = []

    # ------------------------------------------------------
    # Process returned features
    # ------------------------------------------------------

    for feature in features:

        try:

            properties = feature.get(
                "properties",
                {},
            )

            feature_glims_id = properties.get(
                "glac_id"
            )

            # ------------------------------------------------
            # IMPORTANT:
            # Exact GLIMS ID matching prevents neighboring
            # glaciers from being included.
            # ------------------------------------------------

            if glims_id is not None:

                if (
                    str(feature_glims_id).strip()
                    != str(glims_id).strip()
                ):
                    continue

            # ------------------------------------------------
            # Geometry
            # ------------------------------------------------

            feature_geometry = feature.get(
                "geometry"
            )

            if not feature_geometry:
                continue

            glims_geometry = shape(
                feature_geometry
            )

            if glims_geometry.is_empty:
                continue

            # ------------------------------------------------
            # Historical outlines may not intersect the
            # current RGI boundary exactly.
            #
            # Therefore, when an exact GLIMS ID is known,
            # the GLIMS ID is considered the primary match.
            # ------------------------------------------------

            spatial_match = glims_geometry.intersects(
                glacier_geometry
            )

            # ------------------------------------------------
            # Date / year
            # ------------------------------------------------

            src_date = properties.get(
                "src_date"
            )

            year = None

            if src_date:

                try:

                    year = int(
                        str(src_date)[:4]
                    )

                except (
                    ValueError,
                    TypeError,
                ):

                    year = None

            # ------------------------------------------------
            # Store record
            # ------------------------------------------------

            matched_features.append(
                {
                    "id": feature.get(
                        "id"
                    ),

                    "glims_id": feature_glims_id,

                    "year": year,

                    "date": src_date,

                    "area_km2": properties.get(
                        "db_area"
                    ),

                    "analysis_id": properties.get(
                        "anlys_id"
                    ),

                    "submission_id": properties.get(
                        "subm_id"
                    ),

                    "status": properties.get(
                        "rec_status"
                    ),

                    "source": properties.get(
                        "chief_affl"
                    ),

                    "glacier_name": properties.get(
                        "glac_name"
                    ),

                    "spatial_match": spatial_match,

                    "geometry": mapping(
                        glims_geometry
                    ),
                }
            )

        except Exception as error:

            print(
                "Warning: Could not process "
                f"GLIMS feature: {error}"
            )

    # ------------------------------------------------------
    # Sort chronologically
    # ------------------------------------------------------

    matched_features.sort(
        key=lambda item: (
            item["year"] is None,
            (
                item["year"]
                if item["year"] is not None
                else 9999
            ),
        )
    )

    return matched_features


# ==========================================================
# GET RGI RECORD
# ==========================================================

def get_rgi_record(
    rgi_id,
):
    """
    Load an exact RGI glacier from
    global_rgi.gpkg.
    """

    if not RGI_PATH.exists():

        print(
            f"RGI file not found: {RGI_PATH}"
        )

        return None

    rgi = gpd.read_file(
        RGI_PATH
    )

    matches = rgi[
        rgi["rgi_id"]
        .astype(str)
        == str(rgi_id)
    ]

    if matches.empty:
        return None

    return matches.iloc[0]


# ==========================================================
# GET GLIMS FOR RGI GLACIER
# ==========================================================

def get_glims_for_rgi(
    rgi_id,
):
    """
    Get historical GLIMS outlines associated
    with an exact RGI glacier.
    """

    # ------------------------------------------------------
    # Find RGI record
    # ------------------------------------------------------

    record = get_rgi_record(
        rgi_id
    )

    if record is None:

        return {
            "success": False,
            "rgi_id": rgi_id,
            "message": "RGI glacier not found.",
            "features": [],
        }

    # ------------------------------------------------------
    # Get GLIMS ID
    # ------------------------------------------------------

    glims_id = record.get(
        "glims_id"
    )

    if (
        glims_id is None
        or str(glims_id).strip() == ""
    ):

        return {
            "success": False,
            "rgi_id": rgi_id,
            "message": (
                "No GLIMS ID associated "
                "with this RGI glacier."
            ),
            "features": [],
        }

    glims_id = str(
        glims_id
    ).strip()

    # ------------------------------------------------------
    # Get RGI geometry
    # ------------------------------------------------------

    geometry = record.get(
        "geometry"
    )

    if geometry is None:

        return {
            "success": False,
            "rgi_id": rgi_id,
            "glims_id": glims_id,
            "message": (
                "RGI glacier geometry "
                "is not available."
            ),
            "features": [],
        }

    # ------------------------------------------------------
    # Query GLIMS
    # ------------------------------------------------------

    try:

        features = get_glims_outlines(
            geometry,
            glims_id=glims_id,
        )

    except requests.RequestException as error:

        return {
            "success": False,
            "rgi_id": rgi_id,
            "glims_id": glims_id,
            "message": (
                f"GLIMS request failed: {error}"
            ),
            "features": [],
        }

    # ------------------------------------------------------
    # Return result
    # ------------------------------------------------------

    return {
        "success": True,
        "rgi_id": rgi_id,
        "glims_id": glims_id,
        "glims_layer": GLIMS_LAYER,
        "count": len(features),
        "historical_records": features,
    }