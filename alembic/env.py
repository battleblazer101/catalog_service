from logging.config import fileConfig

import os

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

from app.database.database import Base
from app.models.media import MediaItem


config = context.config


# ------------------------------------------------------------
# Database URL
# ------------------------------------------------------------

database_url = os.getenv(
    "CATALOG_DATABASE_URL"
)

if database_url:
    config.set_main_option(
        "sqlalchemy.url",
        database_url,
    )


# ------------------------------------------------------------
# Metadata
# ------------------------------------------------------------

target_metadata = Base.metadata


# ------------------------------------------------------------
# Offline migrations
# ------------------------------------------------------------

def run_migrations_offline() -> None:

    url = config.get_main_option(
        "sqlalchemy.url"
    )

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={
            "paramstyle": "named"
        },
    )

    with context.begin_transaction():

        context.run_migrations()


# ------------------------------------------------------------
# Online migrations
# ------------------------------------------------------------

def run_migrations_online() -> None:

    connectable = engine_from_config(
        config.get_section(
            config.config_ini_section,
            {}
        ),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():

            context.run_migrations()


if context.is_offline_mode():

    run_migrations_offline()

else:

    run_migrations_online()
