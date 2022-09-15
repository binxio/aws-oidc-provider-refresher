import os
from typing import Tuple

import click

from aws_oidc_provider_refresher.command import Command
from aws_oidc_provider_refresher.logger import log
from aws_oidc_provider_refresher.tag import Tag, TagType


@click.command(help="update thumbprint list of selected Open ID connect providers")
@click.option("--dry-run/--force", is_flag=True, default=True, help="do not change anything")
@click.option("--verbose", is_flag=True, default=False, help="output")
@click.option(
    "--append", is_flag=True, default=False, help="new fingerprint to the list"
)
@click.option("--max-fingerprints", type=int, default=0, help="in the thumbprint list")
@click.option(
    "--tag",
    "tags",
    type=TagType(),
    required=False,
    multiple=True,
    help="to filter providers by in the format Name=Value.",
)
@click.pass_context
def main(
    ctx,
    dry_run: bool,
    append: bool,
    verbose: bool,
    max_fingerprints: int,
    tags: Tuple[Tag],
):
    Command(**ctx.params).run()


if __name__ == "__main__":
    main()
