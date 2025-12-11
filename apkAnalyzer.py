import csv
from androguard.misc import AnalyzeAPK

# Load Filter
def load_feature_whitelist(csv_path="features/cols.csv"):
    whitelist = set()
    with open(csv_path, 'r', encoding="utf-8") as f:
        read = csv.reader(f)
        for row in read:
            whitelist.add(row[0])
    return whitelist

FEATURE_WHITELIST = load_feature_whitelist()
API_WHITELIST = {x for x in FEATURE_WHITELIST if x.startswith("APICall::")}
PERMISSION_WHITELIST = {x for x in FEATURE_WHITELIST if x.startswith("Permission::")}
INTENT_WHITELIST = {x for x in FEATURE_WHITELIST if x.startswith("Intent::")}

# API Call Formatter
def normalize_apicall(class_name, method_name):
    class_name = class_name.rstrip(";")
    class_name = class_name.replace(".", "/")
    return f"APICall::{class_name}.{method_name}()"


def analyze_apk(apk_path):
    apk, dex, analysis = AnalyzeAPK(apk_path)

    # API Levels
    min_sdk = apk.get_min_sdk_version()
    target_sdk = apk.get_target_sdk_version()

    #Permissions
    raw_permissions = apk.get_permissions() or []
    permissions = []

    for perm in raw_permissions:
        key = f"Permission::{perm.split('.')[-1]}"
        if key in PERMISSION_WHITELIST:
            permissions.append(key)

    permissions.sort()

    #Intent
    intents = set()
    receivers = apk.get_receivers()
    for receiver in receivers:
        filters = apk.get_intent_filters("receiver", receiver)

        for category, actions in filters.items():
            for action in actions:

                # action can be string or dict
                if isinstance(action, str):
                    name = action.split(".")[-1].upper()
                elif isinstance(action, dict):
                    vals = list(action.values())
                    name = vals[0].split(".")[-1].upper() if vals else None
                else:
                    name = None

                if not name:
                    continue

                feature_key = f"Intent::{name}"
                if feature_key in INTENT_WHITELIST:
                    intents.add(feature_key)

    intents = sorted(list(intents))

    #API Calls
    api_calls = set()
    for method in analysis.get_methods():
        for _, call, _ in method.get_xref_to():
            class_name = call.class_name
            method_name = call.name

            if not class_name.startswith("Landroid/"):
                continue

            formatted = normalize_apicall(class_name, method_name)

            if formatted in API_WHITELIST:
                api_calls.add(formatted)

    api_calls = sorted(list(api_calls))

    # Result
    return {
        "min_sdk": min_sdk,
        "target_sdk": target_sdk,
        "permissions": permissions,
        "intents": intents,
        "api_calls": api_calls
    }