from pathlib import Path
from datetime import datetime, timedelta, timezone

import json
import requests
import rasterio
import numpy as np
import re
from rasterio.features import rasterize
from shapely.geometry import mapping

from backend.app.services.sentinel_service import (
    get_access_token,
)

from backend.app.services.sentinel_catalog import (
    search_historical_sentinel2,
    select_best_observation_per_year,
)

from backend.app.services.sentinel_download import (
    get_utm_crs,
    get_crs_url,
    create_rgi_utm_bbox,
)

from backend.app.services.rgi_service import (
    find_glacier_by_name,
)

from backend.app.services.glims_service import (
    get_glims_for_rgi,
)

from backend.scripts.predict_geotiff import (
    predict_geotiff,
)


# ==========================================================
# PROJECT PATHS
# ==========================================================

PROJECT_ROOT = (
    Path(__file__).resolve().parents[2]
)

HISTORICAL_DIR = (
    PROJECT_ROOT
    / "datasets"
    / "historical"
)

SATELLITE_DIR = (
    HISTORICAL_DIR
    / "satellite"
)

PREDICTION_DIR = (
    HISTORICAL_DIR
    / "predictions"
)

SATELLITE_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

PREDICTION_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ==========================================================
# COPERNICUS PROCESS API
# ==========================================================

PROCESS_URL = (
    "https://sh.dataspace.copernicus.eu/"
    "process/v1"
)


# ==========================================================
# CONFIGURATION
# ==========================================================

PIXEL_SIZE = 12

DEFAULT_START_YEAR = 2023
DEFAULT_END_YEAR = 2026

DEFAULT_SEASON_START_MONTH = 6
DEFAULT_SEASON_START_DAY = 1

DEFAULT_SEASON_END_MONTH = 9
DEFAULT_SEASON_END_DAY = 30

DEFAULT_MAX_CLOUD_COVER = 30


# ==========================================================
# EVALSCRIPT
# ==========================================================
#
# IMPORTANT:
# We use TILE mosaicking so that Sentinel-2 scenes/tiles
# covering the requested AOI can be combined.
#
# dataMask is used to select valid pixels.
#
# Reflectance is multiplied by 10000 before storing as UINT16.
#
# ==========================================================

EVALSCRIPT = """
//VERSION=3

function setup() {

    return {

        input: [
            {
                bands: [
                    "B04",
                    "B03",
                    "B02",
                    "dataMask"
                ],
                units: "REFLECTANCE"
            }
        ],

        mosaicking: "TILE",

        output: {
            id: "default",
            bands: 3,
            sampleType: "UINT16"
        }

    };

}


function evaluatePixel(samples) {

    // Look through all available Sentinel-2 tiles.
    // Return the first valid pixel.

    for (var i = 0; i < samples.length; i++) {

        if (samples[i].dataMask == 1) {

            return [

                samples[i].B04 * 10000,
                samples[i].B03 * 10000,
                samples[i].B02 * 10000

            ];

        }

    }

    // No valid satellite observation
    return [0, 0, 0];

}
"""


# ==========================================================
# DOWNLOAD ONE HISTORICAL IMAGE
# ==========================================================

def download_historical_image(
    observation,
    geometry,
    latitude,
    longitude,
    output_dir,
    glacier_slug,
):
    """
    Download the exact Sentinel-2 observation selected by the catalog.

    The catalog chooses the best observation for the year.
    The Process API is then restricted to a small time window around
    that exact observation datetime.
    """

    datetime_string = observation.get("datetime")
    scene_id = observation.get("id")
    cloud_cover = observation.get("cloud_cover")

    if not datetime_string:
        raise RuntimeError("Selected historical observation has no datetime.")

    if not scene_id:
        raise RuntimeError("Selected historical observation has no scene ID.")

    observation_datetime = datetime.fromisoformat(
        datetime_string.replace("Z", "+00:00")
    )

    year = observation_datetime.year

    print()
    print("==========================================")
    print(f" DOWNLOADING HISTORICAL SENTINEL-2 - {year}")
    print("==========================================")
    print()
    print("Scene ID              :", scene_id)
    print("Observation datetime  :", datetime_string)
    print("Catalog cloud         :", cloud_cover, "%")

    # Restrict Process API to the selected catalog observation.
    start_datetime = observation_datetime - timedelta(minutes=2)
    end_datetime = observation_datetime + timedelta(minutes=2)

    target_crs = get_utm_crs(latitude, longitude)

    print("Target CRS            :", target_crs)

    bbox = create_rgi_utm_bbox(
        geometry=geometry,
        target_crs=target_crs,
    )

    print("AOI source            : RGI 7.0 glacier bbox")
    print("UTM BBOX              :", bbox)

    token = get_access_token()

    selected_cloud = (
        float(cloud_cover)
        if cloud_cover is not None
        else DEFAULT_MAX_CLOUD_COVER
    )

    payload = {
        "input": {
            "bounds": {
                "bbox": bbox,
                "properties": {
                    "crs": get_crs_url(target_crs)
                },
            },
            "data": [
                {
                    "type": "sentinel-2-l2a",
                    "dataFilter": {
                        "timeRange": {
                            "from": start_datetime.strftime(
                                "%Y-%m-%dT%H:%M:%SZ"
                            ),
                            "to": end_datetime.strftime(
                                "%Y-%m-%dT%H:%M:%SZ"
                            ),
                        },
                        "mosaickingOrder": "leastCC",
                        "maxCloudCoverage": selected_cloud,
                    },
                    "processing": {
                        "upsampling": "BILINEAR",
                        "downsampling": "BILINEAR",
                    },
                }
            ],
        },
        "output": {
            "resx": PIXEL_SIZE,
            "resy": PIXEL_SIZE,
            "responses": [
                {
                    "identifier": "default",
                    "format": {
                        "type": "image/tiff"
                    },
                }
            ],
        },
        "evalscript": EVALSCRIPT,
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "image/tiff",
    }

    print()
    print("Requesting selected historical Sentinel-2 image...")

    response = requests.post(
        PROCESS_URL,
        json=payload,
        headers=headers,
        timeout=180,
    )

    if response.status_code != 200:
        raise RuntimeError(
            "Historical Sentinel-2 request failed "
            f"(HTTP {response.status_code}):\n"
            f"{response.text}"
        )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = (
        output_dir
        / f"{glacier_slug}_{year}.tif"
    )

    with open(output_path, "wb") as file:
        file.write(response.content)

    if len(response.content) == 0:
        raise RuntimeError(
            "Historical Sentinel-2 response was empty."
        )

    print()
    print("Download successful!")
    print("File:", output_path)
    print("Size:", len(response.content), "bytes")

    return {
        "path": output_path,
        "scene_id": scene_id,
        "datetime": datetime_string,
        "cloud_cover": cloud_cover,
        "year": year,
    }


# ==========================================================
# APPLY RGI POLYGON TO PREDICTION
# ==========================================================

def apply_rgi_polygon(
    mask_path,
    geometry,
    output_path,
):

    print()
    print(
        "Applying RGI glacier polygon..."
    )

    with rasterio.open(
        mask_path
    ) as src:

        mask = src.read(1)

        transform = src.transform

        crs = src.crs

        height = src.height

        width = src.width

        profile = src.profile.copy()

    # ------------------------------------------------------
    # Convert RGI geometry from EPSG:4326
    # to image CRS
    # ------------------------------------------------------

    from rasterio.warp import transform_geom

    transformed_geometry = transform_geom(
        "EPSG:4326",
        crs,
        geometry,
    )

    # ------------------------------------------------------
    # Rasterize RGI polygon
    # ------------------------------------------------------

    rgi_mask = rasterize(

        [
            (
                transformed_geometry,
                1
            )
        ],

        out_shape=(
            height,
            width,
        ),

        transform=transform,

        fill=0,

        dtype=np.uint8,

    )

    # ------------------------------------------------------
    # Clip AI prediction to RGI glacier
    # ------------------------------------------------------

    clipped_mask = (
        mask
        * rgi_mask
    ).astype(
        np.uint8
    )

    # ------------------------------------------------------
    # Save clipped mask
    # ------------------------------------------------------

    profile.update(
        dtype=rasterio.uint8,
        count=1,
        nodata=0,
    )

    with rasterio.open(
        output_path,
        "w",
        **profile,
    ) as dst:

        dst.write(
            clipped_mask,
            1,
        )

    # ------------------------------------------------------
    # Area calculation
    # ------------------------------------------------------

    glacier_pixels = int(
        np.count_nonzero(
            clipped_mask
        )
    )

    pixel_width = abs(
        transform.a
    )

    pixel_height = abs(
        transform.e
    )

    pixel_area_m2 = (
        pixel_width
        * pixel_height
    )

    area_m2 = (
        glacier_pixels
        * pixel_area_m2
    )

    area_km2 = (
        area_m2
        / 1_000_000
    )

    return {

        "glacier_pixels":
            glacier_pixels,

        "pixel_area_m2":
            pixel_area_m2,

        "area_m2":
            area_m2,

        "area_km2":
            area_km2,

        "mask_path":
            str(output_path),

    }


# ==========================================================
# PROCESS ONE HISTORICAL OBSERVATION
# ==========================================================

def process_observation(
    observation,
    geometry,
    latitude,
    longitude,
    glacier_slug,
    satellite_dir,
    prediction_dir,
):
    """
    Download one selected historical Sentinel-2 observation,
    run U-Net V3.1, clip the prediction to the RGI polygon,
    and calculate glacier area.
    """

    year = int(
        observation["year"]
    )

    download_info = download_historical_image(
        observation=observation,
        geometry=geometry,
        latitude=latitude,
        longitude=longitude,
        output_dir=satellite_dir,
        glacier_slug=glacier_slug,
    )

    image_path = download_info["path"]

    print()
    print("==========================================")
    print(f" RUNNING U-NET V3.1 - {year}")
    print("==========================================")

    prediction = predict_geotiff(
        image_path=image_path,
        output_stem=f"{glacier_slug}_{year}",
        rgi_geometry=geometry,
    )

    print()
    print(
        "Raw U-Net V3.1 area:",
        prediction["area_km2"],
        "km²",
    )

    clipped_mask_path = (
        prediction_dir
        / f"{glacier_slug}_{year}_rgi_mask.tif"
    )

    analysis = apply_rgi_polygon(
        mask_path=prediction["mask_path"],
        geometry=geometry,
        output_path=clipped_mask_path,
    )

    result = {
        "year": year,
        "date": observation.get("datetime"),
        "scene_id": observation.get("id"),
        "catalog_cloud_percent": observation.get("cloud_cover"),
        "area_km2": round(
            analysis["area_km2"],
            6,
        ),
        "area_m2": round(
            analysis["area_m2"],
            2,
        ),
        "glacier_pixels": analysis["glacier_pixels"],
        "mask_path": analysis["mask_path"],
        "satellite_path": str(image_path),
        "model": "U-Net V3.1",
        "rgi_polygon_applied": True,
    }

    print()
    print("==========================================")
    print(f" {year} ANALYSIS COMPLETE")
    print("==========================================")
    print("Date:", observation.get("datetime"))
    print("Scene:", observation.get("id"))
    print(
        "Cloud:",
        observation.get("cloud_cover"),
        "%",
    )
    print(
        "Glacier pixels:",
        analysis["glacier_pixels"],
    )
    print(
        "Estimated glacier area:",
        round(
            analysis["area_km2"],
            6,
        ),
        "km²",
    )

    return result


# ==========================================================
# GLIMS HISTORICAL REFERENCE
# ==========================================================

def get_glims_historical_reference(
    rgi_id,
):
    """
    Fetch historical GLIMS records for the
    exact RGI glacier.

    GLIMS is kept as an independent historical
    reference source and is not merged directly
    into the Sentinel-2/U-Net observations.
    """

    if not rgi_id:

        return {
            "status": "unavailable",
            "records": [],
        }

    try:

        glims_result = get_glims_for_rgi(
            rgi_id
        )

        if not glims_result.get(
            "success"
        ):

            return {
                "status": "unavailable",
                "records": [],
                "message": glims_result.get(
                    "message",
                    "GLIMS data unavailable.",
                ),
            }

        records = []

        for item in glims_result.get(
            "historical_records",
            [],
        ):

            records.append(
                {
                    "year": item.get("year"),
                    "date": item.get("date"),
                    "area_km2": item.get("area_km2"),
                    "glims_id": item.get("glims_id"),
                    "analysis_id": item.get("analysis_id"),
                    "submission_id": item.get("submission_id"),
                    "status": item.get("status"),
                    "source": item.get("source"),
                    "glacier_name": item.get(
                        "glacier_name"
                    ),
                }
            )

        return {
            "status": "available",
            "glims_id": glims_result.get(
                "glims_id"
            ),
            "records": records,
        }

    except Exception as error:

        print(
            "GLIMS historical reference failed:",
            error,
        )

        return {
            "status": "unavailable",
            "records": [],
            "message": str(error),
        }


# ==========================================================
# RUN HISTORICAL ANALYSIS FOR ANY GLACIER
# ==========================================================

def run_historical_analysis(
    glacier_name,
    rgi_id=None,
    start_year=DEFAULT_START_YEAR,
    end_year=DEFAULT_END_YEAR,
    season_start_month=DEFAULT_SEASON_START_MONTH,
    season_start_day=DEFAULT_SEASON_START_DAY,
    season_end_month=DEFAULT_SEASON_END_MONTH,
    season_end_day=DEFAULT_SEASON_END_DAY,
    max_cloud_cover=DEFAULT_MAX_CLOUD_COVER,
):
    """
    Run the complete historical Sentinel-2 + U-Net V3.1 pipeline
    for any glacier found in the global RGI 7.0 inventory.
    """

    print()
    print("==========================================")
    print(" GLACIERAI - HISTORICAL GLACIER ANALYSIS")
    print("==========================================")
    print()
    print("Requested glacier:", glacier_name)
    print("Years:", start_year, "-", end_year)
    print()

    # ------------------------------------------------------
    # Resolve the exact RGI glacier
    # ------------------------------------------------------
    # Prefer the exact RGI ID when supplied. This is important
    # because multiple RGI polygons can share the same name.

    if rgi_id:
        rgi_glacier = find_glacier_by_name(rgi_id)
    else:
        rgi_glacier = find_glacier_by_name(glacier_name)

    if rgi_glacier is None:
        raise RuntimeError(
            f'Glacier "{glacier_name}" was not found in RGI 7.0.'
        )

    rgi_id = rgi_glacier["rgi_id"]
    rgi_name = rgi_glacier["name"]
    latitude = float(rgi_glacier["latitude"])
    longitude = float(rgi_glacier["longitude"])
    rgi_area_km2 = rgi_glacier.get("area_km2")

    geometry = mapping(
        rgi_glacier["geometry"]
    )

    glacier_slug = re.sub(
        r"[^a-z0-9]+",
        "_",
        rgi_name.lower(),
    ).strip("_")

    # Use the exact RGI ID as the storage key for on-demand
    # global analysis. This prevents same-named glaciers from
    # overwriting each other. The API falls back to legacy
    # name-based folders for existing processed datasets.
    if rgi_id:
        glacier_slug = rgi_id.strip().lower().replace(" ", "_")

    glacier_dir = (
        HISTORICAL_DIR
        / glacier_slug
    )

    satellite_dir = (
        glacier_dir
        / "satellite"
    )

    prediction_dir = (
        glacier_dir
        / "predictions"
    )

    satellite_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    prediction_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("RGI ID:", rgi_id)
    print("RGI name:", rgi_name)
    print("Latitude:", latitude)
    print("Longitude:", longitude)
    print("RGI area:", rgi_area_km2, "km²")
    print("Output directory:", glacier_dir)

    # ------------------------------------------------------
    # Search real Sentinel-2 observations
    # ------------------------------------------------------

    print()
    print("Searching Sentinel-2 historical observations...")

    observations = search_historical_sentinel2(
        latitude=latitude,
        longitude=longitude,
        start_year=start_year,
        end_year=end_year,
        season_start_month=season_start_month,
        season_start_day=season_start_day,
        season_end_month=season_end_month,
        season_end_day=season_end_day,
        max_cloud_cover=max_cloud_cover,
    )

    selected_observations = (
        select_best_observation_per_year(
            observations
        )
    )

    print()
    print(
        "Selected historical observations:",
        len(selected_observations),
    )

    if not selected_observations:

        glims_reference = (
            get_glims_historical_reference(
                rgi_id
            )
        )

        result_payload = {
            "status": "no_observations",

            "glacier": {
                "name": rgi_name,
                "rgi_id": rgi_id,
                "latitude": latitude,
                "longitude": longitude,
                "rgi_area_km2": rgi_area_km2,
            },

            "observations": [],

            "glims_reference": glims_reference,
        }

        results_file = (
            glacier_dir
            / "historical_results.json"
        )

        with open(
            results_file,
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                result_payload,
                file,
                indent=4,
            )

        print(
            "No suitable Sentinel-2 observations were found."
        )
        print(
            "Results saved to:",
            results_file,
        )

        return result_payload

    # ------------------------------------------------------
    # Process one best observation per year
    # ------------------------------------------------------

    results = []

    for observation in selected_observations:

        year = observation.get(
            "year"
        )

        try:

            result = process_observation(
                observation=observation,
                geometry=geometry,
                latitude=latitude,
                longitude=longitude,
                glacier_slug=glacier_slug,
                satellite_dir=satellite_dir,
                prediction_dir=prediction_dir,
            )

            results.append(
                result
            )

        except Exception as error:

            print()
            print(
                "ERROR processing",
                year,
            )
            print(error)

            results.append({
                "year": year,
                "date": observation.get(
                    "datetime"
                ),
                "scene_id": observation.get(
                    "id"
                ),
                "catalog_cloud_percent":
                    observation.get(
                        "cloud_cover"
                    ),
                "error": str(error),
            })

    # ------------------------------------------------------
    # Save structured historical results
    # ------------------------------------------------------

    successful_results = [
        item
        for item in results
        if "area_km2" in item
    ]

    # ------------------------------------------------------
    # GLIMS HISTORICAL REFERENCE
    # ------------------------------------------------------

    print()
    print(
        "Fetching GLIMS historical reference..."
    )

    glims_reference = (
        get_glims_historical_reference(
            rgi_id
        )
    )

    print(
        "GLIMS status:",
        glims_reference.get(
            "status"
        ),
    )

    print(
        "GLIMS records:",
        len(
            glims_reference.get(
                "records",
                [],
            )
        ),
    )

    result_payload = {
        "status": (
            "completed"
            if successful_results
            else "failed"
        ),
        "glacier": {
            "name": rgi_name,
            "rgi_id": rgi_id,
            "latitude": latitude,
            "longitude": longitude,
            "rgi_area_km2": rgi_area_km2,
        },
        "historical_config": {
            "start_year": start_year,
            "end_year": end_year,
            "season": {
                "start": (
                    f"{season_start_month:02d}-"
                    f"{season_start_day:02d}"
                ),
                "end": (
                    f"{season_end_month:02d}-"
                    f"{season_end_day:02d}"
                ),
            },
            "max_cloud_cover": max_cloud_cover,
        },
        "model": "U-Net V3.1",

        "observations": results,

        "glims_reference": glims_reference,
    }

    results_file = (
        glacier_dir
        / "historical_results.json"
    )

    with open(
        results_file,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            result_payload,
            file,
            indent=4,
        )

    # ------------------------------------------------------
    # Summary
    # ------------------------------------------------------

    print()
    print("==========================================")
    print(" HISTORICAL GLACIER ANALYSIS SUMMARY")
    print("==========================================")
    print()

    for result in results:

        if "area_km2" in result:

            print(
                f'{result["year"]} | '
                f'{result["date"]} | '
                f'Area: '
                f'{result["area_km2"]} km²'
            )

        else:

            print(
                f'{result["year"]} | '
                f'FAILED | '
                f'{result.get("error")}'
            )

    print()
    print("Successful observations:", len(successful_results))
    print("Results saved to:")
    print(results_file)
    print()
    print("Historical analysis finished.")

    return result_payload


# ==========================================================
# MAIN
# ==========================================================

def main():

    # Change this to test another RGI glacier.
    glacier_name = "McCall Glacier"

    run_historical_analysis(
        glacier_name=glacier_name,
        start_year=2023,
        end_year=2026,
        season_start_month=6,
        season_start_day=1,
        season_end_month=9,
        season_end_day=30,
        max_cloud_cover=30,
    )


# ==========================================================
# MAIN
# ==========================================================
# RUN
# ==========================================================

if __name__ == "__main__":
    main()
