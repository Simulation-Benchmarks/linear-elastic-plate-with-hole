import argparse


def parse_bool(value):
    if isinstance(value, bool):
        return value

    normalized_value = value.lower()
    if normalized_value == "true":
        return True
    if normalized_value == "false":
        return False
    raise argparse.ArgumentTypeError("Expected 'true' or 'false'.")
