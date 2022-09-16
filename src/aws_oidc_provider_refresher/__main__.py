from typing import Tuple

import click

from aws_oidc_provider_refresher.command import Command
from aws_oidc_provider_refresher.tag import Tag, TagType


@click.command()
@click.option(
    "--filter",
    "tags",
    type=TagType(),
    required=False,
    multiple=True,
    help="to select providers by in the format Name=Value.",
)
@click.option(
    "--max-thumbprints", type=click.IntRange(1, 5), default=5, help="in the list"
)
@click.option(
    "--dry-run/--force",
    "dry_run",
    default=True,
    is_flag=True,
    help="show what should happen or update the OIDC providers",
)
@click.option("--verbose", is_flag=True, default=False, help="output")
@click.pass_context
def main(
    ctx,
    dry_run: bool,
    verbose: bool,
    max_thumbprints: int,
    tags: Tuple[Tag],
):
    """
    updates the thumbprint list of Open ID connect providers.

    It only show you what would happen: you have to specify --force
    to perform the update.

    By default all OIDC provider thumbprints are updated. You can
    filter providers by tag.
    """
    Command(**ctx.params).run()


if __name__ == "__main__":
    main()
