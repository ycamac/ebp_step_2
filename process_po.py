"""
Process PO payloads through the ERP stub with retries and safe re-runs.

First we read the payloads from the JSON file.
Then we load the state from the JSON file to prevent sending the same payload twice.
Then we process the payloads through the ERP stub with retries and safe re-runs.
Then we save the state to the JSON file.

Due to the time constraints, I didn't add a summary of the payloads.

Usage:
    python3 process_po.py
"""
import json
import os
import sys
import time

from erp_stub import ERPError, post_to_erp
from payloads import load_payloads, payload_key, unique_payloads

INPUT_PATH = "po_payloads.json"
OUTPUT_PATH = "processed_state.json"
MAX_ATTEMPTS = 8
RETRYABLE_STATUSES = {429, 500}


def load_state(path):
    if not os.path.exists(path):
        return {"processed": {}, "failed": {}}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_state(path, state):
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def post_with_retry(payload):
    delay = 10.0
    last_error = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return post_to_erp(payload)
        except ERPError as exc:
            last_error = exc
            if exc.status not in RETRYABLE_STATUSES:
                raise
            if attempt == MAX_ATTEMPTS:
                break
            sleep_for = 2.0 if exc.status == 429 else delay
            time.sleep(sleep_for)
            if exc.status == 500:
                delay = min(delay * 2, 30.0)

    raise last_error


def process_payloads():
    payloads = load_payloads(INPUT_PATH)
    state = load_state(OUTPUT_PATH)
    unique = unique_payloads(payloads)
    had_failures = False

    for payload in unique:
        key = payload_key(payload)

        if key in state["processed"]:
            print(f"skip {key}: already processed")
            continue

        if key in state["failed"]:
            print(f"skip {key}: previously failed ({state['failed'][key]['error']})")
            continue

        try:
            result = post_with_retry(payload)
        except ERPError as exc:
            if exc.status == 400:
                state["failed"][key] = {
                    "error": str(exc),
                    "status": exc.status,
                    "payload": payload,
                }
                save_state(OUTPUT_PATH, state)
                had_failures = True
                print(f"fail {key}: {exc}")
            else:
                # 429/500: transient — do not save; next run will retry
                had_failures = True
                print(f"retry later {key}: {exc}")
            continue

        state["processed"][key] = {
            "erp_id": result.get("erp_id"),
            "status": result.get("status"),
            "payload": payload,
        }
        save_state(OUTPUT_PATH, state)
        print(f"ok   {key}: {result.get('erp_id')}")

    return had_failures


def main():
    return 1 if process_payloads() else 0


if __name__ == "__main__":
    sys.exit(main())
