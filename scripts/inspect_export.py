"""Build a codebook from a Qualtrics CSV or an SPSS .sav file.

Qualtrics export tags like `Q4_1`, `BFI_Q17__` and `Q13.0` say nothing about what
was asked. The question text does, and it is sitting in the file already: row 2 of
a Qualtrics CSV, or the variable labels of a .sav. This script pulls it out and
writes a codebook so you can identify which columns belong to which measure.

It also groups consecutive columns into blocks and tries to recognise known
instruments from their wording, which is how you find out whether the survey
administered the measure you pre-registered.

Usage:
    python scripts/inspect_export.py                       # newest file in data/raw/
    python scripts/inspect_export.py --input path/to.sav
    python scripts/inspect_export.py --search "level of competence"
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

from common import OUTPUT_DIR, RAW_DIR, ensure_dirs

# Distinctive phrases from measures relevant to this project. Matching is on the
# question text, so a hit is strong evidence and a miss is worth investigating.
SIGNATURES: dict[str, dict] = {
    "NAQ-R (Negative Acts Questionnaire-Revised, 22 items)": {
        "phrases": [
            "below your level of competence",
            "ordered to do work",
            "gossip and rumours",
            "ignored or excluded",
            "persistent criticism",
            "opinions ignored",
            "shouted at",
            "spontaneous anger",
            "threats of violence",
            "intimidating behaviour",
            "excessive monitoring",
            "unmanageable workload",
            "practical jokes",
            "unreasonable deadlines",
            "withholding information",
            "hints or signals from others that you should quit",
        ],
        "expect": 22,
    },
    "BFI-2 (Big Five Inventory-2, 60 items)": {
        "phrases": [
            "is outgoing, sociable",
            "is compassionate",
            "tends to be disorganized",
            "tends to be disorganised",
            "is relaxed, handles stress well",
            "has few artistic interests",
            "i am someone who",
            "is fascinated by art",
            "worries a lot",
            "is full of energy",
        ],
        "expect": 60,
    },
    "Mini-IPIP6 Openness subscale (4 items)": {
        "phrases": [
            "vivid imagination",
            "not interested in abstract ideas",
            "do not have a good imagination",
            "difficulty understanding abstract ideas",
        ],
        "expect": 4,
    },
    "Demographics": {
        "phrases": [
            "what is your age",
            "how old are you",
            "your gender",
            "first language",
            "english your first",
            "employment status",
            "employed full",
        ],
        "expect": None,
    },
    "Attention / validity check": {
        "phrases": [
            "attention",
            "reading carefully",
            "please select",
            "to show you are",
        ],
        "expect": None,
    },
    "Consent": {
        "phrases": ["i consent", "consent to participate", "explanatory statement"],
        "expect": None,
    },
}

METADATA = {
    "StartDate", "EndDate", "Status", "IPAddress", "Progress", "Duration (in seconds)",
    "Finished", "RecordedDate", "ResponseId", "RecipientLastName", "RecipientFirstName",
    "RecipientEmail", "ExternalReference", "LocationLatitude", "LocationLongitude",
    "DistributionChannel", "UserLanguage",
}


def load_any(path: Path) -> tuple[pd.DataFrame, dict[str, str], dict]:
    """Return (data, name -> question text, extra info) for a .sav or Qualtrics CSV."""
    if path.suffix.lower() == ".sav":
        import pyreadstat

        data, meta = pyreadstat.read_sav(str(path), apply_value_formats=False)
        return data, dict(meta.column_names_to_labels), {"value_labels": meta.variable_value_labels}

    names = pd.read_csv(path, nrows=0).columns.tolist()
    second = pd.read_csv(path, skiprows=[0], nrows=1, header=None, dtype=str)
    labels = dict(zip(names, second.iloc[0].astype(str).tolist())) if not second.empty else {}

    skip = [1]
    third = pd.read_csv(path, skiprows=[0, 1], nrows=1, header=None, dtype=str)
    if not third.empty and third.iloc[0].astype(str).str.contains("ImportId").any():
        skip = [1, 2]
    data = pd.read_csv(path, skiprows=skip, low_memory=False)
    data.columns = names
    return data, labels, {"value_labels": {}}


def strip_prefix(name: str) -> str:
    """Reduce a Qualtrics export tag to its block prefix.

    `Q4_11` -> `Q4`, `BFI_Q17__` -> `BFI_Q`, `Part_A._3` -> `Part_A`, `Q13.0` -> `Q`.
    """
    base = re.sub(r"[._]+$", "", name)
    base = re.sub(r"\.\d+$", "", base)
    base = re.sub(r"[._]\d+$", "", base)
    base = re.sub(r"\d+$", "", base)
    return re.sub(r"[._]+$", "", base) or name


def detect_blocks(columns: list[str]) -> list[dict]:
    """Group consecutive non-metadata columns sharing a prefix."""
    blocks: list[dict] = []
    for position, name in enumerate(columns, start=1):
        if name in METADATA:
            continue
        prefix = strip_prefix(name)
        if blocks and blocks[-1]["prefix"] == prefix and blocks[-1]["end"] == position - 1:
            blocks[-1]["end"] = position
            blocks[-1]["columns"].append(name)
        else:
            blocks.append(
                {"prefix": prefix, "start": position, "end": position, "columns": [name]}
            )
    return blocks


def identify(labels: list[str]) -> list[str]:
    joined = " || ".join(str(x).lower() for x in labels)
    hits = []
    for instrument, spec in SIGNATURES.items():
        matched = [p for p in spec["phrases"] if p in joined]
        if matched:
            hits.append(f"{instrument} — matched {len(matched)} phrase(s): {matched[0]!r}")
    return hits


def summarise_values(series: pd.Series) -> str:
    values = series.dropna()
    if values.empty:
        return "all missing"
    unique = values.unique()
    if len(unique) <= 12 and not pd.api.types.is_float_dtype(values.dtype):
        return ", ".join(str(v) for v in sorted(unique, key=str)[:12])
    if pd.api.types.is_numeric_dtype(values):
        if len(unique) <= 12:
            return ", ".join(str(v) for v in sorted(unique)[:12])
        return f"numeric, {values.min():g} to {values.max():g}"
    return f"{len(unique)} distinct text values"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=None)
    parser.add_argument("--search", default=None, help="print columns whose text matches")
    args = parser.parse_args()

    ensure_dirs()
    if args.input:
        source = args.input
    else:
        candidates = sorted(
            list(RAW_DIR.glob("*.csv")) + list(RAW_DIR.glob("*.sav")),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            raise SystemExit(f"No .csv or .sav found in {RAW_DIR}/")
        source = candidates[0]

    data, labels, extra = load_any(source)
    columns = list(data.columns)

    if args.search:
        needle = args.search.lower()
        print(f"Columns whose name or question text contains {args.search!r}:\n")
        for position, name in enumerate(columns, start=1):
            text = str(labels.get(name, ""))
            if needle in name.lower() or needle in text.lower():
                print(f"  {position:>4}  {name:<24} {text[:100]}")
        return

    blocks = detect_blocks(columns)

    lines = [
        "# Codebook",
        "",
        f"Source: `{source.name}` — {len(columns)} variables, {len(data)} rows.",
        "",
        "## Blocks of consecutive variables",
        "",
        "Qualtrics export tags are grouped here by shared prefix, which usually "
        "corresponds to one question block or one instrument.",
        "",
    ]

    block_rows = []
    for block in blocks:
        texts = [labels.get(c, "") for c in block["columns"]]
        matches = identify(texts)
        block_rows.append(
            {
                "Rows": f"{block['start']}–{block['end']}"
                if block["end"] > block["start"]
                else str(block["start"]),
                "Prefix": block["prefix"],
                "n vars": len(block["columns"]),
                "Looks like": "; ".join(m.split(" — ")[0] for m in matches) or "—",
                "First question text": (str(texts[0])[:70] if texts else ""),
            }
        )
    lines += [pd.DataFrame(block_rows).to_markdown(index=False), ""]

    lines += ["## Instrument detection", ""]
    any_found = False
    for instrument, spec in SIGNATURES.items():
        found = [
            b for b in blocks if any(instrument in m for m in identify([labels.get(c, "") for c in b["columns"]]))
        ]
        if not found:
            lines.append(f"- **{instrument}**: not detected")
            continue
        any_found = True
        for block in found:
            note = ""
            if spec["expect"] and len(block["columns"]) != spec["expect"]:
                note = (
                    f" — **{len(block['columns'])} variables, but this measure has "
                    f"{spec['expect']} items.** Check whether the block is split or "
                    "includes extra columns."
                )
            lines.append(
                f"- **{instrument}**: rows {block['start']}–{block['end']} "
                f"(`{block['columns'][0]}` … `{block['columns'][-1]}`), "
                f"{len(block['columns'])} variables{note}"
            )
    if not any_found:
        lines.append("")
        lines.append(
            "> Nothing matched. If this came from a `.sav`, check the labels actually "
            "carry the question text; if from a CSV, confirm row 2 holds question text."
        )
    lines.append("")

    lines += [
        "## Every variable",
        "",
        "| # | Name | Question text | n valid | Values |",
        "|---|------|---------------|---------|--------|",
    ]
    for position, name in enumerate(columns, start=1):
        text = str(labels.get(name, "")).replace("|", "/").replace("\n", " ")[:120]
        lines.append(
            f"| {position} | `{name}` | {text} | {int(data[name].notna().sum())} | "
            f"{summarise_values(data[name]).replace('|', '/')} |"
        )
    lines.append("")

    value_labels = extra.get("value_labels") or {}
    if value_labels:
        lines += ["## Value labels", ""]
        for name, mapping in value_labels.items():
            pairs = ", ".join(f"{k} = {v}" for k, v in list(mapping.items())[:12])
            lines.append(f"- `{name}`: {pairs}")
        lines.append("")

    target = OUTPUT_DIR / "codebook.md"
    target.write_text("\n".join(lines) + "\n")

    print(f"Source: {source.name} — {len(columns)} variables, {len(data)} rows\n")
    print(pd.DataFrame(block_rows).to_string(index=False))
    print(f"\nWrote {target}")
    print("\nTo find a specific measure:")
    print('  python scripts/inspect_export.py --search "level of competence"')


if __name__ == "__main__":
    main()
