"""Application-wide privacy defaults, set before native libraries initialize."""

import os

# ONNX Runtime's API opt-out happens after import and may miss its initial
# event. Disable the native uploader before any app module can import it.
# This is a privacy requirement, not an optional deployment preference.
os.environ["ORT_DISABLE_TELEMETRY"] = "1"
