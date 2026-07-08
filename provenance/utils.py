import argparse
import json
from pathlib import Path


CONFIG_DIR = Path(__file__).resolve().parent


def _load_json_config(filename: str) -> dict:
    with (CONFIG_DIR / filename).open(encoding="utf-8") as config_file:
        return json.load(config_file)


def configure_semantic_benchmark_rohub() -> None:
    """Load this repository's annotation settings into semantic-benchmark."""
    import semantic_benchmark.rohub as rohub

    rohub.configure_repository_settings(
        annotation_config=_load_json_config("annotation_config.json"),
    )


def parse_bool(value):
    if isinstance(value, bool):
        return value

    normalized_value = value.lower()
    if normalized_value == "true":
        return True
    if normalized_value == "false":
        return False
    raise argparse.ArgumentTypeError("Expected 'true' or 'false'.")
