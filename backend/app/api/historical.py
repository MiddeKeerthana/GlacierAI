from pathlib import Path
import json
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.scripts.historical_analysis import (
    run_historical_analysis,
)

from backend.scripts.change_analysis import (
    run_change_analysis,
)

from backend.scripts.future_prediction import (
    generate_future_prediction,
)

from backend.app.services.rgi_service import (
    find_glacier_by_name,
)

from backend.app.services.glims_service import (
    get_glims_for_rgi,
)


router = APIRouter(
    tags=["Historical Analysis"],
)


# ==========================================================
# PROJECT PATHS
# ==========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[3]

HISTORICAL_DIR = (
    PROJECT_ROOT
    / "datasets"
    / "historical"
)


# ==========================================================
# REQUEST MODEL
# ==========================================================

class HistoricalAnalysisRequest(BaseModel):
    name: str
    rgi_id: Optional[str] = None
    start_year: int = 2023
    end_year: int = 2026


# ==========================================================
# GLACIER IDENTITY
# ==========================================================

def resolve_glacier_identity(
    name: Optional[str] = None,
    rgi_id: Optional[str] = None,
):
    """
    Resolve the glacier using RGI ID first.

    This prevents two glaciers with similar names from
    being mixed up.
    """

    if rgi_id:
        glacier = find_glacier_by_name(rgi_id)

        if glacier:
            return glacier

    if name:
        glacier = find_glacier_by_name(name)

        if glacier:
            return glacier

    return None


# ==========================================================
# HISTORICAL FILE HELPERS
# ==========================================================

def historical_file_for(
    glacier_name: str,
    rgi_id: Optional[str] = None,
) -> Path:

    if rgi_id:
        # Preserve the standard hyphenated RGI folder name.
        rgi_slug = rgi_id.strip().lower()

        rgi_file = (
            HISTORICAL_DIR
            / rgi_slug
            / "historical_results.json"
        )

        if rgi_file.exists():
            return rgi_file

    name_slug = (
        glacier_name
        .strip()
        .lower()
        .replace(" ", "_")
    )

    return (
        HISTORICAL_DIR
        / name_slug
        / "historical_results.json"
    )


def prediction_file_for(
    glacier_name: str,
    rgi_id: Optional[str] = None,
) -> Path:

    if rgi_id:
        # Preserve the standard hyphenated RGI folder name.
        # Return this path even before future_prediction.json exists,
        # because the predictor creates it in this folder.
        rgi_slug = rgi_id.strip().lower()

        return (
            HISTORICAL_DIR
            / rgi_slug
            / "future_prediction.json"
        )

    name_slug = (
        glacier_name
        .strip()
        .lower()
        .replace(" ", "_")
    )

    return (
        HISTORICAL_DIR
        / name_slug
        / "future_prediction.json"
    )


# ==========================================================
# RUN HISTORICAL ANALYSIS
# ==========================================================

@router.post("/historical/analyze")
def analyze_historical(
    request: HistoricalAnalysisRequest,
):

    glacier = resolve_glacier_identity(
        name=request.name,
        rgi_id=request.rgi_id,
    )

    if not glacier:
        raise HTTPException(
            status_code=404,
            detail="Glacier could not be resolved from the supplied name/RGI ID.",
        )

    resolved_rgi_id = (
        glacier.get("rgi_id")
        if isinstance(glacier, dict)
        else request.rgi_id
    )

    glacier_name = (
        glacier.get("name")
        or glacier.get("rgi_name")
        or request.name
        if isinstance(glacier, dict)
        else request.name
    )

    # ------------------------------------------------------
    # HISTORICAL ANALYSIS
    # ------------------------------------------------------

    try:

        result = run_historical_analysis(
            glacier_name=glacier_name,
            rgi_id=resolved_rgi_id,
            start_year=request.start_year,
            end_year=request.end_year,
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=f"Historical analysis failed: {error}",
        )

    # ------------------------------------------------------
    # GLIMS HISTORICAL REFERENCE
    # ------------------------------------------------------

    glims_reference = None

    if resolved_rgi_id:
        try:
            glims_reference = get_glims_for_rgi(resolved_rgi_id)
        except Exception as error:
            print(
                "GLIMS reference could not be loaded:",
                error,
            )

    # ------------------------------------------------------
    # CHANGE ANALYSIS
    # ------------------------------------------------------

    change_result = None

    try:

        change_result = run_change_analysis(
            glacier_name=glacier_name,
            rgi_id=resolved_rgi_id,
        )

    except Exception as error:

        print(
            "Change analysis could not be generated:",
            error,
        )

    # ------------------------------------------------------
    # FUTURE PREDICTION
    # ------------------------------------------------------

    prediction_result = None

    try:

        prediction_result = generate_future_prediction(
            glacier_name=glacier_name,
            rgi_id=resolved_rgi_id,
        )

        print(
            "Future prediction generated:",
            prediction_result.get("json_path")
            if isinstance(prediction_result, dict)
            else prediction_result,
        )

    except Exception as error:

        print(
            "Future prediction could not be generated:",
            error,
        )

    return {
        "status": "success",
        "glacier": glacier_name,
        "rgi_id": resolved_rgi_id,
        "start_year": request.start_year,
        "end_year": request.end_year,
        "data": result,
        "glims_reference": glims_reference,
        "change_analysis": change_result,
        "prediction": (
            prediction_result.get("data")
            if isinstance(prediction_result, dict)
            else None
        ),
        "prediction_generated": (
            isinstance(prediction_result, dict)
            and "data" in prediction_result
        ),
    }


# ==========================================================
# GET HISTORICAL DATA
# ==========================================================

@router.get("/historical")
def get_historical(
    glacier: Optional[str] = None,
    rgi_id: Optional[str] = None,
):

    if not glacier and not rgi_id:
        raise HTTPException(
            status_code=400,
            detail="Provide glacier or rgi_id.",
        )

    resolved = resolve_glacier_identity(
        name=glacier,
        rgi_id=rgi_id,
    )

    if not resolved:
        raise HTTPException(
            status_code=404,
            detail="Glacier not found.",
        )

    resolved_name = (
        resolved.get("name")
        or resolved.get("rgi_name")
        or glacier
        or rgi_id
    )

    resolved_rgi_id = (
        resolved.get("rgi_id")
        or rgi_id
    )

    file_path = historical_file_for(
        resolved_name,
        resolved_rgi_id,
    )

    # ------------------------------------------------------
    # GLIMS HISTORICAL REFERENCE
    #
    # GLIMS is independent of the locally processed
    # Sentinel-2/U-Net historical results. Therefore, return
    # GLIMS data even when the local historical JSON does not
    # exist yet.
    # ------------------------------------------------------

    glims_reference = None

    if resolved_rgi_id:
        try:
            glims_reference = get_glims_for_rgi(resolved_rgi_id)
        except Exception as error:
            print(
                "GLIMS reference could not be loaded:",
                error,
            )

    # ------------------------------------------------------
    # LOCAL AI HISTORICAL DATA
    # ------------------------------------------------------

    if not file_path.exists():

        return {
            "status": "glims_only" if glims_reference else "no_data",
            "glacier": resolved_name,
            "rgi_id": resolved_rgi_id,
            "data": [],
            "glims_reference": glims_reference,
            "message": (
                "No local Sentinel-2/U-Net historical observations "
                "have been processed for this glacier yet. "
                "GLIMS historical reference data is available."
                if glims_reference
                else
                "No historical observations have been processed for "
                "this glacier yet. Run /api/historical/analyze to "
                "generate historical data."
            ),
        }

    try:

        import json

        with open(
            file_path,
            "r",
            encoding="utf-8",
        ) as file:

            data = json.load(file)

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=f"Could not read historical data: {error}",
        )

    return {
        "status": "success",
        "glacier": resolved_name,
        "rgi_id": resolved_rgi_id,
        "data": data,
        "glims_reference": glims_reference,
    }


# ==========================================================
# CHANGE ANALYSIS
# ==========================================================

@router.get("/historical/change-analysis")
def get_change_analysis(
    glacier: Optional[str] = None,
    rgi_id: Optional[str] = None,
):

    if not glacier and not rgi_id:
        raise HTTPException(
            status_code=400,
            detail="Provide glacier or rgi_id.",
        )

    resolved = resolve_glacier_identity(
        name=glacier,
        rgi_id=rgi_id,
    )

    if not resolved:
        raise HTTPException(
            status_code=404,
            detail="Glacier not found.",
        )

    resolved_name = (
        resolved.get("name")
        or resolved.get("rgi_name")
        or glacier
        or rgi_id
    )

    resolved_rgi_id = (
        resolved.get("rgi_id")
        or rgi_id
    )

    # Change analysis requires processed historical observations.
    historical_path = historical_file_for(
        resolved_name,
        resolved_rgi_id,
    )

    if not historical_path.exists():
        return {
            "status": "no_data",
            "glacier": resolved_name,
            "rgi_id": resolved_rgi_id,
            "data": [],
            "message": (
                "Historical change analysis is not available yet because "
                "no historical observations have been processed for this glacier."
            ),
        }

    try:

        result = run_change_analysis(
            glacier_name=resolved_name,
            rgi_id=resolved_rgi_id,
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=f"Change analysis failed: {error}",
        )

    return {
        "status": "success",
        "glacier": resolved_name,
        "rgi_id": resolved_rgi_id,
        "data": result,
    }


# ==========================================================
# FUTURE PREDICTION
# ==========================================================

@router.get("/prediction")
def get_prediction(
    glacier: Optional[str] = None,
    rgi_id: Optional[str] = None,
):

    if not glacier and not rgi_id:
        raise HTTPException(
            status_code=400,
            detail="Provide glacier or rgi_id.",
        )

    resolved = resolve_glacier_identity(
        name=glacier,
        rgi_id=rgi_id,
    )

    if not resolved:
        raise HTTPException(
            status_code=404,
            detail="Glacier not found.",
        )

    resolved_name = (
        resolved.get("name")
        or resolved.get("rgi_name")
        or glacier
        or rgi_id
    )

    resolved_rgi_id = (
        resolved.get("rgi_id")
        or rgi_id
    )

    file_path = prediction_file_for(
        resolved_name,
        resolved_rgi_id,
    )

    # ------------------------------------------------------
    # Historical data is required before future prediction.
    # ------------------------------------------------------

    historical_path = historical_file_for(
        resolved_name,
        resolved_rgi_id,
    )

    if not historical_path.exists():
        return {
            "status": "no_data",
            "glacier": resolved_name,
            "rgi_id": resolved_rgi_id,
            "data": [],
            "message": (
                "Future prediction is not available yet because "
                "historical observations have not been processed for this glacier."
            ),
        }

    # ------------------------------------------------------
    # Generate prediction when missing OR stale/empty
    # ------------------------------------------------------

    needs_generation = not file_path.exists()

    if file_path.exists():
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                existing_prediction = json.load(file)

            existing_data = (
                existing_prediction.get("data")
                if isinstance(existing_prediction, dict)
                else None
            )
            if existing_data is None and isinstance(existing_prediction, dict):
                existing_data = existing_prediction

            existing_predictions = (
                existing_data.get("predictions", [])
                if isinstance(existing_data, dict)
                else []
            )
            existing_status = (
                existing_data.get("status")
                if isinstance(existing_data, dict)
                else None
            )

            # Regenerate old INSUFFICIENT_VALIDATION / empty prediction
            # files using the current predictor.
            if existing_status != "success" or not existing_predictions:
                needs_generation = True

        except Exception:
            needs_generation = True

    if needs_generation:

        try:
            generated = generate_future_prediction(
                glacier_name=resolved_name,
                rgi_id=resolved_rgi_id,
            )

            if isinstance(generated, dict):
                return {
                    "status": "success",
                    "glacier": resolved_name,
                    "rgi_id": resolved_rgi_id,
                    "data": generated.get("data"),
                }

        except Exception as error:
            raise HTTPException(
                status_code=500,
                detail=f"Future prediction failed: {error}",
            )

    # ------------------------------------------------------
    # Read existing prediction
    # ------------------------------------------------------

    if not file_path.exists():

        return {
            "status": "no_data",
            "glacier": resolved_name,
            "rgi_id": resolved_rgi_id,
            "data": [],
            "message": (
                "Future prediction has not been generated yet. "
                "Run historical analysis first."
            ),
        }

    try:

        import json

        with open(
            file_path,
            "r",
            encoding="utf-8",
        ) as file:

            data = json.load(file)

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=f"Could not read prediction data: {error}",
        )

    return {
        "status": "success",
        "glacier": resolved_name,
        "rgi_id": resolved_rgi_id,
        "data": data,
    }