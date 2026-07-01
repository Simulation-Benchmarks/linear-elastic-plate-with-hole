"""
RoHub Provenance Upload Module

This module handles the upload of research object provenance data to RoHub,
a platform for research object management and sharing. It processes RO-Crate
metadata artifacts and manages the complete upload workflow including:
- Authentication with RoHub
- Deletion of existing research objects with the same title
- Upload of new research objects from zip files
- Polling for upload completion
- Adding semantic annotations to uploaded objects

The module supports both production and development environments of RoHub.
"""

import argparse

from rohub_provenance import upload_provenance_rocrate
from utils import parse_bool


def parse_args():
    """
    Parse command-line arguments for RoHub provenance upload.

    Returns:
        argparse.Namespace: Parsed command-line arguments containing:
            - provenance_folderpath (str): Path to the zip file containing 
                                          provenance data (RO-Crate)
            - username (str): RoHub authentication username
            - password (str): RoHub authentication password
    """
    parser = argparse.ArgumentParser(
        description="Upload benchmark provenance RO-Crates to RoHub."
    )
    parser.add_argument(
        "--provenance_folderpath",
        type=str,
        required=True,
        help="Path to the folder containing provenance data",
    )
    parser.add_argument(
        "--benchmark-name",
        type=str,
        required=True,
        help="Name of the benchmark to be uploaded",
    )
    parser.add_argument(
        "--username",
        type=str,
        required=True,
        help="Username for RoHub",
    )
    parser.add_argument(
        "--password",
        type=str,
        required=True,
        help="Password for RoHub",
    )
    parser.add_argument(
        "--rocrate-title",
        type=str,
        required=True,
        help="Title of the RO-Crate to be uploaded",
    )
    parser.add_argument(
        "--code-repository-url",
        type=str,
        default=None,
        help="Full GitHub branch URL to annotate as schema.org/codeRepository",
    )
    parser.add_argument(
        "--used-software-url",
        type=str,
        default=None,
        help="Software identifier URL to annotate as prov:used",
    )
    parser.add_argument(
        "--use-production-rohub",
        type=parse_bool,
        default=False,
        help="Use production RoHub instead of the development instance (true/false)",
    )
    return parser.parse_args()


def run(args):
    """
    Execute the complete RoHub upload workflow.

    This function delegates the RoHub-specific operations to
    rohub_provenance.upload_provenance_rocrate:
    1. Configure and authenticate with RoHub
    2. Delete existing research objects with the same RO-Crate title
    3. Upload the new research object from the specified zip file
    4. Poll the upload job status until completion or timeout
    5. Add semantic annotations to the successfully uploaded object

    Args:
        args (argparse.Namespace): Parsed command-line arguments containing:
            - provenance_folderpath: Path to the provenance zip file
            - username: RoHub username
            - password: RoHub password

    Raises:
        Exception: If authentication fails
        Exception: If upload fails
        Exception: If deletion of an existing RO fails

    Configuration:
        USE_PRODUCTION_ROHUB (bool): When True, uses RoHub production server.
                                     Set to False for development environment.

        Timeout Settings:
            - Upload timeout: 5 minutes (300 seconds)
            - Poll interval: 10 seconds between status checks
    Annotations:
        The function adds a predefined annotation linking the research object
        to the NFDI4Ing Model Validation Platform benchmark.
    """
    upload_provenance_rocrate(
        provenance_folderpath=args.provenance_folderpath,
        benchmark_name=args.benchmark_name,
        username=args.username,
        password=args.password,
        rocrate_title=args.rocrate_title,
        code_repository_url=args.code_repository_url,
        used_software_url=args.used_software_url,
        use_production_rohub=args.use_production_rohub,
    )


def main():
    """
    Main entry point for the RoHub provenance upload script.

    Parses command-line arguments and initiates the upload workflow to RoHub.
    This function is called when the script is executed directly.

    Usage:
        python upload_provenance.py \
            --provenance_folderpath /path/to/ro-crate.zip \
            --username user@example.com \
            --password your_password

    Note:
        - Ensure the provenance file is a valid zip containing RO-Crate metadata
        - Valid RoHub credentials are required for authentication
        - The script deletes existing research objects with the same title
        - Upload process may take up to 5 minutes

    Exits:
        The script will exit with a non-zero status code if authentication
        or upload fails, or if required arguments are not provided.
    """
    args = parse_args()
    run(args)


if __name__ == "__main__":
    main()
