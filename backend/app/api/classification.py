from pathlib import Path
import tempfile

from fastapi import APIRouter, UploadFile, File, HTTPException

from backend.services.glacier_classifier_service import (
    classify_glacier,
)


# ==========================================================
# ROUTER
# ==========================================================

router = APIRouter()


# ==========================================================
# ALLOWED IMAGE TYPES
# ==========================================================

ALLOWED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".tif",
    ".tiff",
}


# ==========================================================
# CLASSIFICATION ENDPOINT
# ==========================================================

@router.post("/predict")
async def predict_glacier_type(
    file: UploadFile = File(...)
):
    """
    Classify an uploaded glacier image.

    Returns:
        Glacier type
        Confidence
        Probability for each glacier type
    """

    # ------------------------------------------------------
    # Validate filename
    # ------------------------------------------------------

    if not file.filename:

        raise HTTPException(
            status_code=400,
            detail="No filename provided.",
        )

    extension = Path(
        file.filename
    ).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:

        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported image format. "
                "Use JPG, JPEG, PNG, TIF, or TIFF."
            ),
        )

    # ------------------------------------------------------
    # Read uploaded file
    # ------------------------------------------------------

    contents = await file.read()

    if not contents:

        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty.",
        )

    # ------------------------------------------------------
    # Temporary image file
    # ------------------------------------------------------

    temp_path = None

    try:

        with tempfile.NamedTemporaryFile(
            suffix=extension,
            delete=False,
        ) as temp_file:

            temp_file.write(contents)

            temp_path = Path(
                temp_file.name
            )

        # --------------------------------------------------
        # Run CNN classifier
        # --------------------------------------------------

        result = classify_glacier(
            temp_path
        )

        return {
            "success": True,
            "filename": file.filename,
            "classification": result,
        }

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Glacier classification failed: "
                f"{str(exc)}"
            ),
        )

    finally:

        # --------------------------------------------------
        # Delete temporary file
        # --------------------------------------------------

        if temp_path is not None:

            try:

                temp_path.unlink(
                    missing_ok=True
                )

            except Exception:
                pass