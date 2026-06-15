"""
Download benchmark resources from a RoHub research object.

The module authenticates with RoHub, loads a research object by UUID, selects a
resource by its RoHub type, and downloads it to a filename provided by the user.
"""

import argparse
import logging
from uuid import UUID
import rohub
from rohub_provenance import login_to_rohub
from utils import parse_bool

SOFTWARE_SOURCE_CODE_TYPE = "Software source code"
ANNOTATION_COLLECTION_TYPE = "Annotation Collection"

LOG_FORMAT = "%(levelname)s:%(name)s:%(message)s"
LOGGER = logging.getLogger(__name__)


def validate_uuid(value: str) -> str:
    """Validate a command-line UUID while preserving its original string form."""
    try:
        UUID(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Expected a UUID identifier, got: {value}"
        ) from exc
    return value


def _select_resource_identifier(resources, resource_type: str) -> str:
    """Return the single resource identifier matching the requested RoHub type."""
    required_columns = {"identifier", "type"}
    missing_columns = required_columns.difference(resources.columns)
    if missing_columns:
        raise ValueError(
            "Resource list is missing required columns: "
            + ", ".join(sorted(missing_columns))
        )

    matching_resources = resources.loc[
        resources["type"] == resource_type, "identifier"
    ].dropna()

    if matching_resources.empty:
        raise ValueError(f"No resource found with type: {resource_type}")

    if len(matching_resources) > 1:
        raise ValueError(
            f"Expected one resource with type '{resource_type}', "
            f"found {len(matching_resources)}."
        )

    return str(matching_resources.iloc[0])


def _download_benchmark_resource(
    identifier: str,
    resource_filename: str,
    resource_type: str,
) -> str:
    """Load a research object and download its resource of the given type."""
    research_object = rohub.ros_load(identifier)
    resources = research_object.list_resources()
    resource_identifier = _select_resource_identifier(resources, resource_type)

    LOGGER.info(
        "Downloading %s resource %s to %s",
        resource_type,
        resource_identifier,
        resource_filename,
    )
    rohub.resource_download(resource_identifier, resource_filename)
    return resource_identifier


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
    if not args.zip_resource_filename and not args.semantic_resource_filename:
        raise ValueError(
            "Provide --zip-resource-filename, --semantic-resource-filename, or both."
        )
    login_to_rohub(
        username=args.username,
        password=args.password,
        use_production_rohub=args.use_production_rohub
    )
    
    downloaded_resources = {}

    if args.zip_resource_filename:
        downloaded_resources[SOFTWARE_SOURCE_CODE_TYPE] = (
            _download_benchmark_resource(
                identifier=args.identifier,
                resource_filename=args.zip_resource_filename,
                resource_type=SOFTWARE_SOURCE_CODE_TYPE,
            )
        )

    if args.semantic_resource_filename:
        downloaded_resources[ANNOTATION_COLLECTION_TYPE] = (
            _download_benchmark_resource(
                identifier=args.identifier,
                resource_filename=args.semantic_resource_filename,
                resource_type=ANNOTATION_COLLECTION_TYPE,
            )
        )

    return downloaded_resources


def main():
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
    args = parse_args()
    run(args)


if __name__ == "__main__":
    main()
