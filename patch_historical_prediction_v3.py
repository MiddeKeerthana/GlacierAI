from pathlib import Path
import re

TARGET = (
    Path(__file__).resolve().parent
    / "backend"
    / "app"
    / "api"
    / "historical.py"
)

if not TARGET.exists():
    raise SystemExit(
        f"Could not find: {TARGET}\n"
        "Run this script from the GlacierAI project root."
    )

source = TARGET.read_text(encoding="utf-8")

# ------------------------------------------------------------
# 1. Add the future-prediction import once.
# ------------------------------------------------------------

IMPORT_BLOCK = """from backend.scripts.future_prediction import (
    generate_future_prediction,
)
"""

if "from backend.scripts.future_prediction import" not in source:
    # Put it after the historical-analysis import block.
    marker = "from backend.scripts.historical_analysis import (\n    run_historical_analysis,\n)\n"

    if marker in source:
        source = source.replace(
            marker,
            marker + "\n" + IMPORT_BLOCK,
            1,
        )
    else:
        # Fallback: insert before the first local service import.
        fallback = "from backend.app.services.rgi_service import"
        if fallback in source:
            source = source.replace(
                fallback,
                IMPORT_BLOCK + "\n" + fallback,
                1,
            )
        else:
            raise SystemExit(
                "Could not locate a safe import position in historical.py."
            )

# ------------------------------------------------------------
# 2. Locate the actual POST /historical/analyze function.
# ------------------------------------------------------------

function_match = re.search(
    r'(@router\.post\("/historical/analyze"\)\s*'
    r'def analyze_historical\(\s*'
    r'request:\s*HistoricalAnalysisRequest\s*'
    r'\):)',
    source,
)

if not function_match:
    raise SystemExit(
        "Could not locate @router.post('/historical/analyze') "
        "in the current historical.py."
    )

function_start = function_match.start()

# Find the next top-level route/comment after the function.
next_section = re.search(
    r'\n(?=(?:# ={10,}|@router\.|def [A-Za-z_]))',
    source[function_match.end():],
)

if next_section:
    function_end = function_match.end() + next_section.start()
else:
    function_end = len(source)

function_block = source[function_start:function_end]

# ------------------------------------------------------------
# 3. Find the run_historical_analysis(...) call.
# ------------------------------------------------------------

run_match = re.search(
    r'(?ms)^        result\s*=\s*run_historical_analysis\(\n.*?^        \)\n',
    function_block,
)

if not run_match:
    raise SystemExit(
        "Found the historical endpoint, but could not locate "
        "its run_historical_analysis(...) call."
    )

# Do not insert twice.
if "generate_future_prediction(" not in function_block:
    prediction_call = """
        # --------------------------------------------------
        # GENERATE FUTURE AREA PREDICTION
        # --------------------------------------------------
        #
        # Historical analysis has just produced the selected
        # glacier's historical_results.json. Generate the
        # matching RGI-specific future_prediction.json now so
        # the existing /api/prediction endpoint and frontend
        # can display it immediately.
        # --------------------------------------------------

        prediction_result = None

        try:
            prediction_result = generate_future_prediction(
                glacier_name=glacier_name,
                rgi_id=resolved_rgi_id,
            )

            print(
                "Future prediction generated:",
                prediction_result["json_path"],
            )

        except Exception as prediction_error:
            # Historical analysis itself is still successful.
            # Prediction is reported as unavailable rather than
            # making a successful historical run fail.
            print(
                "Future prediction could not be generated:",
                prediction_error,
            )

"""
    insert_at = run_match.end()
    function_block = (
        function_block[:insert_at]
        + prediction_call
        + function_block[insert_at:]
    )

    source = (
        source[:function_start]
        + function_block
        + source[function_end:]
    )

elif "generate_future_prediction(" in function_block:
    print("Future prediction integration is already present.")
    print(f"Checked: {TARGET}")
    raise SystemExit(0)

# ------------------------------------------------------------
# 4. Syntax-check and save.
# ------------------------------------------------------------

compile(source, str(TARGET), "exec")
TARGET.write_text(source, encoding="utf-8")

print("GlacierAI historical API patched successfully.")
print(f"Updated: {TARGET}")
print("Future prediction will now run after successful historical analysis.")
