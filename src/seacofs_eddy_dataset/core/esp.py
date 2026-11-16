from __future__ import annotations

import importlib
import sys
from collections.abc import Callable
from pathlib import Path

from seacofs_eddy_dataset.config import PipelineConfig


def load_doppio_functions(config: PipelineConfig) -> tuple[Callable, Callable]:
    """Load the external ESP DOPPIO routines used by the pipeline."""
    esp_path = config.raw.get("paths", {}).get("esp_root")
    if esp_path:
        path = str(Path(esp_path).expanduser())
        if path not in sys.path:
            sys.path.insert(0, path)

    try:
        functions = importlib.import_module("functions")
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "Could not import ESP `functions.py`. Set `paths.esp_root` "
            "in the pipeline config to the directory containing it."
        ) from exc

    return functions.doppio, functions.out_core_param_fit
