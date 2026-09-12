"""
Download benchmark resources from a RoHub research object.

The module authenticates with RoHub, loads a research object by UUID, selects
the semantic benchmark resource by name from the RO's resource listing, and
downloads it to a filename provided by the user.
"""

import argparse
import logging
from semantic_benchmark.rohub import download_benchmark_resources, validate_uuid

LOG_FORMAT = "%(levelname)s:%(name)s:%(message)s"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Download benchmark resources from a RoHub research object."
    )
    parser.add_argument(
        "--identifier",
        type=validate_uuid,
        required=True,
        help="UUID identifier of the RoHub research object.",
    )
    parser.add_argument(
        "--username",
        type=str,
        required=True,
        help="Username for RoHub.",
    )
    parser.add_argument(
        "--password",
        type=str,
        required=True,
        help="Password for RoHub.",
    )
    parser.add_argument(
        "--semantic-resource-filename",
        type=str,
        required=True,
        help="Output filename for the semantic benchmark resource.",
    )
    parser.add_argument(
        "--use-production-rohub",
        action="store_true",
        default=False,
        help="Use production RoHub instead of the development instance.",
    )
    return parser.parse_args(argv)


def run(args) -> dict[str, str]:
    return download_benchmark_resources(
        identifier=args.identifier,
        username=args.username,
        password=args.password,
        semantic_resource_filename=args.semantic_resource_filename,
        use_production_rohub=args.use_production_rohub,
    )


def main():
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
    args = parse_args()
    run(args)


if __name__ == "__main__":
    main()
