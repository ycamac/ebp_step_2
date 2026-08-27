"""
PO payload utilities to load and deduplicate payloads.
"""

import json


def payload_key(payload):
    po_number = payload.get("po_number", "")
    if po_number:
        return po_number
    return f"_invalid:{payload.get('supplier', '')}:{payload.get('confirmed_at', '')}"


def load_payloads(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("Expected a JSON array of PO payloads")
    return data


def unique_payloads(payloads):
    seen = set()
    unique = []
    for payload in payloads:
        key = payload_key(payload)
        if key in seen:
            continue
        seen.add(key)
        unique.append(payload)
    return unique
