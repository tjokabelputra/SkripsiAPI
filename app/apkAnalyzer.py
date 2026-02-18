import csv
from androguard.core.apk import APK
from app.core.constants import FEATURE_CSV

# Load Filter
def load_feature_whitelist(csv_path=FEATURE_CSV):
    whitelist = set()
    with open(csv_path, 'r', encoding="utf-8") as f:
        read = csv.reader(f)
        for row in read:
            whitelist.add(row[0])
    return whitelist

FEATURE_WHITELIST = load_feature_whitelist()
PERMISSION_WHITELIST = {x for x in FEATURE_WHITELIST if x.startswith("Permission::")}
INTENT_WHITELIST = {x for x in FEATURE_WHITELIST if x.startswith("Intent::")}

def analyze_apk(apk_path):
    apk = APK(apk_path)

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

    # Result
    return {
        "permissions": permissions,
        "intents": intents,
    }