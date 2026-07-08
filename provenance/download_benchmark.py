"""
Download benchmark resources from a RoHub research object.

The module authenticates with RoHub, loads a research object by UUID, selects a
resource by its RoHub type, and downloads it to a filename provided by the user.
"""

import argparse
import logging
from semantic_benchmark.rohub import download_benchmark_resources, validate_uuid
from utils import configure_semantic_benchmark_rohub, parse_bool

configure_semantic_benchmark_rohub()

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
        "--zip-resource-filename",
        type=str,
        default=None,
        help="Output filename for the Software source code resource.",
    )
    parser.add_argument(
        "--semantic-resource-filename",
        type=str,
        default=None,
        help="Output filename for the Annotation Collection resource.",
    )
    parser.add_argument(
        "--use-production-rohub",
        type=parse_bool,
        default=False,
        help="Use production RoHub instead of the development instance (true/false).",
    )
    return parser.parse_args(argv)


def run(args) -> dict[str, str]:
    return download_benchmark_resources(
        identifier=args.identifier,
        username=args.username,
        password=args.password,
        zip_resource_filename=args.zip_resource_filename,
        semantic_resource_filename=args.semantic_resource_filename,
        use_production_rohub=args.use_production_rohub,
    )


def main():
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
    args = parse_args()
    run(args)


if __name__ == "__main__":
    main()
