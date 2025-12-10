#!/usr/bin/env python3
"""Extract aircraft entries that contain lat/lon coordinates."""

import argparse
import json
import sys
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "aircraft_json",
        nargs="?",
        default="workdir/aircraft.json",
        help="Path to aircraft.json (default: workdir/aircraft.json)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="extractedEntries/entries.json",
        help="Optional output file (defaults to stdout)",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON with indentation",
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help="Append timestamped entries per ICAO into the output (preserve history)",
    )
    return parser.parse_args()


def load_aircraft(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        sys.exit(f"Input file not found: {path}")
    except json.JSONDecodeError as exc:
        sys.exit(f"Failed to parse JSON ({path}): {exc}")


def filter_with_coordinates(aircraft: dict) -> dict:
    result = {}
    for icao, entry in aircraft.items():
        if "lat" in entry and "lon" in entry:
            result[icao] = entry
    return result


def current_timestamp_ms() -> int:
    return time.time_ns() // 1_000_000


def positions_differ(left: dict | None, right: dict) -> bool:
    if left is None:
        return True
    return left.get("lat") != right.get("lat") or left.get("lon") != right.get("lon")


def load_existing_output(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
            if isinstance(data, dict):
                return data
            sys.exit(f"Output file {path} does not contain a JSON object")
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as exc:
        sys.exit(f"Failed to parse existing output ({path}): {exc}")


def dump_result(data: dict, dest: Path | None, pretty: bool) -> None:
    kwargs = {"ensure_ascii": False}
    if pretty:
        kwargs.update({"indent": 2, "sort_keys": True})
    else:
        kwargs.update({"separators": (",", ":")})

    if dest:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, **kwargs)
            handle.write("\n")
    else:
        json.dump(data, sys.stdout, **kwargs)
        sys.stdout.write("\n")


def main() -> None:
    args = parse_args()
    aircraft_path = Path(args.aircraft_json)
    output_path = Path(args.output) if args.output else None

    aircraft = load_aircraft(aircraft_path)
    filtered = filter_with_coordinates(aircraft)
    if output_path:
        # ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if args.history:
            # Load existing history (icao -> [ {"ts":..., "entry": {...}}, ... ])
            try:
                with output_path.open("r", encoding="utf-8") as fh:
                    existing_raw = json.load(fh)
            except FileNotFoundError:
                existing_raw = {}

            if not isinstance(existing_raw, dict):
                sys.exit(f"Existing output {output_path} is not a JSON object")

            existing = {}
            # normalize legacy single-entry values to history lists
            for k, v in existing_raw.items():
                if isinstance(v, list):
                    existing[k] = v
                elif isinstance(v, dict):
                    existing[k] = [{"ts": current_timestamp_ms(), "entry": v}]
                else:
                    existing[k] = []

            updated = dict(existing)
            for icao, entry in filtered.items():
                last_list = updated.get(icao, [])
                if last_list:
                    last_entry = last_list[-1].get("entry")
                else:
                    last_entry = None

                if positions_differ(last_entry, entry):
                    # append new timestamped entry
                    rec = {"ts": current_timestamp_ms(), "entry": entry}
                    updated.setdefault(icao, []).append(rec)

            dump_result(updated, output_path, args.pretty)
        else:
            existing = load_existing_output(output_path)
            updated = dict(existing)
            for icao, entry in filtered.items():
                if positions_differ(existing.get(icao), entry):
                    updated[icao] = entry
            dump_result(updated, output_path, args.pretty)
    else:
        dump_result(filtered, None, args.pretty)


if __name__ == "__main__":
    main()
