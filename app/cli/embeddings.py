#  cli/embeddings.py

import click

from app.services.backfill_service import (
    backfill_embeddings
)


@click.command()
@click.option(
    "--force",
    is_flag=True,
    help="Rebuild all embeddings"
)
def embeddings(force):

    result = backfill_embeddings(force)

    print(
        f"Updated {result['updated']} embeddings"
    )
