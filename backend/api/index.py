"""Vercel Python serverless entrypoint for the FastAPI backend.

Vercel mounts the ASGI application exported as ``app``. The bundle root is
``executors[1]`` of this file; chdir there so the settings' project-relative
paths (analytical dataset, local trace file) resolve inside the deployment.
"""

import os
from pathlib import Path

os.chdir(Path(__file__).resolve().parents[1])

from sales_intelligence.main import app  # noqa: E402