from datetime import datetime

def iso_now() -> str:
    return datetime.utcnow().isoformat() + "Z"