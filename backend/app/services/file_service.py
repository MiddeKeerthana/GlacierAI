import os
import shutil
import rasterio


UPLOAD_FOLDER = "uploads"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def save_uploaded_file(file):

    file_path = os.path.join(UPLOAD_FOLDER, file.filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return file_path


def extract_metadata(file_path):

    with rasterio.open(file_path) as src:

        metadata = {
            "filename": os.path.basename(file_path),
            "width": src.width,
            "height": src.height,
            "bands": src.count,
            "crs": str(src.crs),
            "driver": src.driver
        }

    return metadata