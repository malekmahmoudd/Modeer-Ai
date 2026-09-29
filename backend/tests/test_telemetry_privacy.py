"""The privacy default must apply in a fresh process, before ONNX imports."""

import os
import subprocess
import sys
from pathlib import Path


def test_app_disables_telemetry_before_native_import(tmp_path):
    env = os.environ.copy()
    env["ORT_DISABLE_TELEMETRY"] = "0"
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import os, sys; import app; "
                "assert 'onnxruntime' not in sys.modules; "
                "assert os.environ['ORT_DISABLE_TELEMETRY'] == '1'; "
                "import onnxruntime; "
                "assert os.environ['ORT_DISABLE_TELEMETRY'] == '1'"
            ),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
