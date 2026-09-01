"""Download the survey responses from Qualtrics into data/raw/.

Requires two environment variables (never hard-code these into the repo):

    QUALTRICS_API_TOKEN   Account Settings -> Qualtrics IDs -> API -> Generate Token
    QUALTRICS_DATA_CENTER optional; otherwise taken from config/study.yaml

Usage:
    python scripts/fetch_qualtrics.py
    python scripts/fetch_qualtrics.py --labels          # choice text instead of numbers
    python scripts/fetch_qualtrics.py --format spss     # .sav for SPSS/jamovi

If the API route is blocked for your account, export manually from the Qualtrics
UI instead and drop the CSV into data/raw/ — every later script reads from there
and does not care how the file arrived.
"""

from __future__ import annotations

import argparse
import io
import os
import sys
import time
import zipfile
from datetime import datetime

import requests

from common import RAW_DIR, ensure_dirs, load_config

POLL_SECONDS = 2
POLL_TIMEOUT_SECONDS = 600


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", default="csv", choices=["csv", "tsv", "spss"])
    parser.add_argument(
        "--labels",
        action="store_true",
        help="export choice text rather than numeric codes (numeric is the default "
        "because the analysis scripts expect numbers)",
    )
    parser.add_argument(
        "--include-incomplete",
        action="store_true",
        help="include responses still in progress; they are screened out later anyway",
    )
    return parser


def start_export(base: str, headers: dict, survey_id: str, payload: dict) -> str:
    resp = requests.post(
        f"{base}/surveys/{survey_id}/export-responses", json=payload, headers=headers, timeout=60
    )
    if resp.status_code == 401:
        sys.exit("Qualtrics rejected the API token (401). Check QUALTRICS_API_TOKEN.")
    if resp.status_code == 404:
        sys.exit(f"Survey {survey_id} not found (404). Check survey_id in config/study.yaml.")
    resp.raise_for_status()
    return resp.json()["result"]["progressId"]


def await_export(base: str, headers: dict, survey_id: str, progress_id: str) -> str:
    deadline = time.time() + POLL_TIMEOUT_SECONDS
    while time.time() < deadline:
        resp = requests.get(
            f"{base}/surveys/{survey_id}/export-responses/{progress_id}", headers=headers, timeout=60
        )
        resp.raise_for_status()
        result = resp.json()["result"]
        status = result["status"]
        if status == "complete":
            return result["fileId"]
        if status == "failed":
            sys.exit("Qualtrics reported the export failed.")
        print(f"  ... {result.get('percentComplete', 0):.0f}% complete", flush=True)
        time.sleep(POLL_SECONDS)
    sys.exit("Timed out waiting for the Qualtrics export.")


def main() -> None:
    args = build_parser().parse_args()
    config = load_config()
    ensure_dirs()

    token = os.environ.get("QUALTRICS_API_TOKEN")
    if not token:
        sys.exit(
            "QUALTRICS_API_TOKEN is not set.\n"
            "  export QUALTRICS_API_TOKEN='...'   (see docs/psy4414/qualtrics-export-guide.md)"
        )

    data_center = os.environ.get("QUALTRICS_DATA_CENTER") or config["qualtrics"]["data_center"]
    survey_id = config["qualtrics"]["survey_id"]
    if "REPLACE_ME" in survey_id:
        sys.exit("Set qualtrics.survey_id in config/study.yaml first.")

    base = f"https://{data_center}.qualtrics.com/API/v3"
    headers = {"X-API-TOKEN": token, "Content-Type": "application/json"}

    payload: dict = {
        "format": args.format,
        "useLabels": bool(args.labels),
        "seenUnansweredRecode": -99,
        "compress": True,
    }
    if not args.include_incomplete:
        payload["exportResponsesInProgress"] = False

    print(f"Requesting {args.format} export for {survey_id} from {data_center} ...")
    progress_id = start_export(base, headers, survey_id, payload)
    file_id = await_export(base, headers, survey_id, progress_id)

    resp = requests.get(
        f"{base}/surveys/{survey_id}/export-responses/{file_id}/file", headers=headers, timeout=300
    )
    resp.raise_for_status()

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    written = []
    with zipfile.ZipFile(io.BytesIO(resp.content)) as archive:
        for member in archive.namelist():
            suffix = member.rsplit(".", 1)[-1]
            target = RAW_DIR / f"qualtrics-export-{stamp}.{suffix}"
            target.write_bytes(archive.read(member))
            written.append(target)

    for path in written:
        print(f"Saved {path.relative_to(path.parents[2])} ({path.stat().st_size:,} bytes)")
    print("\nThese files are git-ignored. Next: python scripts/prepare_data.py")


if __name__ == "__main__":
    main()
