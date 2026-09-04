# Catalog Service

Catalog Service is a standalone media catalog and indexing service.

It provides a single FastAPI HTTP API for managing media library paths,
scanning media, storing normalized catalog records, generating embeddings,
and performing both lexical and semantic search.

The service is designed to be consumed by other applications through its
HTTP API. Consumers do not need direct access to the catalog database,
filesystem, SMB shares, scanners, embedding models, or vector index.

---

## Version

**v1.0.0**

---

## Features

- FastAPI-based HTTP API
- Single application access point through `app/main.py`
- Media path management
- Local filesystem support
- SMB/CIFS network share support
- Recursive media scanning
- Music metadata extraction using Mutagen
- Movie filename parsing
- TV series, season, and episode parsing
- Book metadata extraction
- Normalized catalog records
- Automatic embedding generation during ingestion
- Embedding backfill support
- Lexical catalog search
- Semantic search
- FAISS-based vector search
- Catalog statistics
- Catalog cleanup for stale media
- SQLAlchemy database persistence
- Alembic database migrations
- Docker/deployment-friendly startup

---

# Architecture

The service is intentionally structured around a single HTTP entry point:

```text
                    Other Applications
                           │
                           │ HTTP
                           ▼
                    ┌─────────────┐
                    │  FastAPI    │
                    │ app/main.py │
                    └──────┬──────┘
                           │
             ┌─────────────┼─────────────┐
             │             │             │
             ▼             ▼             ▼
        App Paths      Scanning       Search
             │             │             │
             │       ┌─────┴─────┐   ┌───┴────────┐
             │       │           │   │            │
             ▼       ▼           ▼   ▼            ▼
          Database  Music      Movies Lexical   Semantic
                    TV         Books   Search    Search
                                      │            │
                                      │            ▼
                                      │          Embeddings
                                      │            │
                                      │            ▼
                                      │          FAISS
                                      │
                                      ▼
                                   Database
````

The service owns all catalog internals.

External applications communicate with the service through HTTP and should
not access these internals directly.

---

# API Access

The only application access point is:

```text
app/main.py
```

The service exposes a FastAPI application.

There is intentionally no separate `api/catalog.py` layer.

A deployed instance is normally available at:

```text
http://<host>:8000
```

The actual host and port are deployment-specific.

---

# API

## Service

### `GET /`

Returns service information.

Example response:

```json
{
  "service": "catalog_service",
  "version": "1.0.0"
}
```

---

### `GET /health`

Health check.

Example response:

```json
{
  "status": "healthy"
}
```

This endpoint can be used by another application, reverse proxy, container
runtime, or monitoring system to verify that the service is running.

---

# App Paths

App paths define the storage locations that should be scanned.

Supported media types:

```text
music
movie
tv
book
```

---

## List paths

```http
GET /catalog/paths
```

Optional parameters:

```text
media_type
enabled_only
```

Example:

```http
GET /catalog/paths?media_type=movie&enabled_only=true
```

---

## Get a path

```http
GET /catalog/paths/{path_id}
```

---

## Create a path

```http
POST /catalog/paths
```

Example:

```json
{
  "name": "Movies",
  "path": "/media/movies",
  "media_type": "movie",
  "description": "Main movie library",
  "enabled": true
}
```

---

## Update a path

```http
PUT /catalog/paths/{path_id}
```

Example:

```json
{
  "enabled": false
}
```

All update fields are optional.

---

## Delete a path

```http
DELETE /catalog/paths/{path_id}
```

Example response:

```json
{
  "deleted": true,
  "id": 1
}
```

Deleting a configured path does not implicitly delete catalog items.

Path configuration and catalog data are separate concerns.

---

# Scanning

Scanning discovers media files from configured storage locations.

The scanner layer is storage-provider agnostic.

Supported storage:

```text
Local filesystem
SMB/CIFS
```

Supported media:

```text
Music
Movies
TV
Books
```

---

## Scan all enabled paths

```http
POST /catalog/scan
```

Optional:

```text
media_type
```

Example:

```http
POST /catalog/scan?media_type=music
```

Without a media type, all enabled paths are scanned.

Example response:

```json
{
  "media_type": "music",
  "paths_scanned": 1,
  "scanned": 1250,
  "inserted": 42,
  "results": [
    {
      "path_id": 1,
      "name": "Music",
      "path": "/media/music",
      "media_type": "music",
      "scanned": 1250,
      "inserted": 42
    }
  ]
}
```

`scanned` represents files discovered by the scanner.

`inserted` represents new catalog records created.

Running the same scan repeatedly is therefore expected to produce zero
new inserts once the catalog is up to date.

---

## Scan one configured path

```http
POST /catalog/scan/paths/{path_id}
```

This explicitly scans one configured path.

---

## Media-specific scans

Music:

```http
POST /catalog/scan/music
```

Movies:

```http
POST /catalog/scan/movies
```

TV:

```http
POST /catalog/scan/tv
```

Books:

```http
POST /catalog/scan/books
```

These are convenience endpoints for clients that want to trigger a scan for
a specific media type.

---

# Catalog Items

Catalog items are normalized records representing discovered media.

A catalog item contains information such as:

```text
id
media_type
title
creator
collection
genre
year
path
metadata
```

Internal embedding fields are owned by the Catalog Service and should not
be required by API consumers.

---

## List catalog items

```http
GET /catalog/items
```

Optional parameters include:

```text
media_type
limit
offset
```

Example:

```http
GET /catalog/items?media_type=movie&limit=100&offset=0
```

---

## Get a catalog item

```http
GET /catalog/items/{item_id}
```

Example response:

```json
{
  "id": 123,
  "media_type": "movie",
  "title": "The Matrix",
  "creator": "Unknown",
  "collection": "Unknown",
  "genre": "Unknown",
  "year": 1999,
  "path": "/media/movies/The.Matrix.1999.1080p.mkv",
  "metadata": {
    "media_format": "mkv",
    "source_filename": "The.Matrix.1999.1080p.mkv"
  }
}
```

---

# Search

Catalog Service provides two different search mechanisms.

## Lexical search

```http
GET /catalog/search?query=matrix
```

Lexical search is database-backed and gives higher weight to matches in:

```text
title       3.0
creator     2.0
collection  1.5
```

It is suitable for exact or near-exact searches such as:

```text
matrix
beatles
breaking bad
tolkien
```

---

## Semantic search

```http
GET /catalog/search/semantic?query=movies about artificial intelligence
```

Semantic search converts the query into an embedding and searches the
catalog's vector index.

It is intended for natural-language queries such as:

```text
movies about artificial intelligence

upbeat music for a party

books about space exploration

crime dramas set in New York
```

The caller does not need to know which embedding model or vector index is
being used.

Those are implementation details of the Catalog Service.

---

# Embeddings

Embeddings are generated automatically when new catalog items are inserted.

The embedding input is based on the item's searchable metadata:

```text
title
creator
collection
genre
```

The service stores:

```text
embedding
embedding_model
embedding_created_at
```

for internally managing semantic search.

Existing catalog items can be processed using the embedding backfill service.

---

# Vector Search

Semantic search is implemented internally using an embedding model and
vector indexing.

The current architecture separates vector functionality into:

```text
app/services/embedding_service.py
app/services/faiss_service.py
app/services/semantic_search_service.py
```

This keeps the API independent from the specific vector-search
implementation.

A future implementation can replace or modify the vector index without
requiring consumers to change their driver.

---

# Catalog Cleanup

Media can be removed or moved after it has been scanned.

The catalog therefore supports explicit cleanup of stale records.

```http
POST /catalog/cleanup
```

An optional media type can be supplied:

```http
POST /catalog/cleanup?media_type=movie
```

Cleanup is intentionally separate from scanning.

Scanning discovers media.

Cleanup removes catalog records that no longer correspond to existing
media.

---

# Statistics

```http
GET /catalog/stats
```

Example:

```json
{
  "total_items": 10000,
  "music_items": 5000,
  "movie_items": 2000,
  "tv_items": 1500,
  "book_items": 1500,
  "embedded_items": 10000,
  "missing_embeddings": 0,
  "embedding_coverage": 100.0
}
```

Statistics can be used for monitoring and administration.

---

# Storage

The storage layer is abstracted through:

```text
StorageProvider
```

This allows scanners to operate without knowing whether files are stored
locally or on an SMB share.

## Local filesystem

Examples:

```text
/media/music
/var/lib/media/movies
```

## SMB

SMB URLs:

```text
smb://server/share/music
```

UNC paths:

```text
\\server\share\music
```

SMB authentication is supplied separately from the filesystem path.

Credentials should never be embedded in catalog paths.

---

# Media Scanners

Each media type has a dedicated scanner.

```text
app/scanners/music.py
app/scanners/movies.py
app/scanners/tv.py
app/scanners/books.py
```

All scanners return the common `CatalogItem` structure.

The catalog ingestion layer therefore does not need to know how metadata
was discovered.

---

## Music

Music metadata is read using Mutagen.

Supported formats include:

```text
MP3
FLAC
M4A
WAV
OGG
```

Embedded metadata is preferred.

The filename is used as a fallback title when no title tag is available.

---

## Movies

Movie metadata is currently derived primarily from filenames.

The scanner handles common filename conventions including:

```text
The.Matrix.1999.1080p.WEB-DL.x264.mkv
TheMatrix1999WEB-DL.mkv
```

Technical release information is removed from the normalized title.

The original filename is retained in metadata.

---

## TV

The TV scanner supports common conventions including:

```text
S01E01
s01e01
1x01
Season 1 Episode 1
```

It also supports season directories such as:

```text
Season 01
Season.01
Season-01
S01
Specials
```

The series directory is used as the primary source of series metadata.

---

## Books

Books are normalized into the common catalog structure while preserving
book-specific metadata.

---

# Database

Catalog Service uses SQLAlchemy for database access.

Database schema changes are managed with Alembic.

The service should run migrations before starting the application.

The deployment startup process currently performs:

```bash
alembic upgrade head
```

before starting Uvicorn.

---

# Configuration

The service uses environment variables for deployment-specific settings.

The database URL is configured through:

```text
CATALOG_DATABASE_URL
```

Example:

```text
CATALOG_DATABASE_URL=sqlite:////var/lib/catalog_service/catalog.db
```

The embedding model cache is configured through:

```text
HF_HOME
```

The deployment startup script uses:

```text
/var/lib/catalog_service/model-cache
```

for the model cache.

---

# Running Locally

Create a virtual environment:

```bash
python3 -m venv .venv
```

Activate it:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run database migrations:

```bash
alembic upgrade head
```

Start the service:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The API is then available at:

```text
http://127.0.0.1:8000
```

FastAPI's interactive documentation is available at:

```text
http://127.0.0.1:8000/docs
```

OpenAPI schema:

```text
http://127.0.0.1:8000/openapi.json
```

---

# Production Startup

The supplied `start.sh` script performs the required startup sequence:

```text
1. Change to application directory
2. Configure Python environment
3. Configure model cache
4. Configure database
5. Run Alembic migrations
6. Start Uvicorn
```

The application is started using:

```bash
./start.sh
```

---

# Driver Integration

Other applications should communicate with Catalog Service through its
HTTP API.

A driver should treat Catalog Service as an independent service and should
not import its Python modules.

For example:

```text
Other Application
        │
        │ HTTP
        ▼
CatalogDriver
        │
        │ HTTP
        ▼
Catalog Service
        │
        ├── Database
        ├── Filesystems
        ├── SMB
        ├── Scanners
        ├── Embeddings
        └── Vector index
```

This separation allows the Catalog Service to be deployed independently.

The consuming application only needs to know the service URL and API
contract.

---

# Recommended Driver Operations

A consumer driver should expose a small abstraction such as:

```python
health()

list_paths()

create_path()

update_path()

delete_path()

scan()

scan_path()

list_items()

get_item()

search()

semantic_search()

cleanup()

stats()
```

The driver should translate these operations into HTTP requests.

The implementation details of the Catalog Service should remain hidden
from the consuming application.

---

# Idempotency

Catalog ingestion is designed to be safe to repeat.

When scanning a file, the catalog checks whether the path already exists.

Existing paths are skipped during normal ingestion.

Therefore:

```text
scan
scan
scan
```

does not create duplicate catalog records for the same path.

This makes scheduled or manually triggered rescans safe.

---

# Error Handling

The API uses normal HTTP status codes.

Common responses include:

```text
200 OK
201 Created
400 Bad Request
404 Not Found
409 Conflict
500 Internal Server Error
```

Examples:

### Invalid media type

```text
400 Bad Request
```

### Unknown path ID

```text
404 Not Found
```

### Duplicate filesystem path

```text
409 Conflict
```

The driver should treat HTTP status codes as the primary error contract.

---

# Deployment Considerations

The Catalog Service is intended to run as a standalone service.

Recommended deployment components:

```text
Catalog Service
    │
    ├── Application
    ├── Database
    ├── Model cache
    └── Access to media storage
```

The service requires access to the configured media paths.

For SMB libraries, the service must also have network connectivity to the
SMB server and valid credentials where required.

---

# Project Structure

```text
app/
├── main.py
│
├── config.py
│
├── database/
│   └── database.py
│
├── models/
│   ├── app_path.py
│   └── media.py
│
├── scanners/
│   ├── books.py
│   ├── movies.py
│   ├── music.py
│   ├── tv.py
│   └── types/
│       ├── __init__.py
│       └── catalog_item.py
│
├── services/
│   ├── app_path_service.py
│   ├── backfill_service.py
│   ├── catalog_service.py
│   ├── embedding_service.py
│   ├── faiss_service.py
│   ├── search_service.py
│   └── semantic_search_service.py
│
└── storage/
    ├── __init__.py
    ├── base.py
    ├── factory.py
    ├── local.py
    └── smb.py
```

---

# Design Principles

## Single HTTP access point

All external access goes through:

```text
app/main.py
```

There is no separate catalog API module.

## Storage abstraction

Scanners do not depend directly on local filesystem or SMB APIs.

## Scanner abstraction

Every media scanner produces the same normalized catalog contract.

## Database ownership

The Catalog Service owns its database.

Consumers should not query the database directly.

## Search abstraction

Consumers request lexical or semantic searches without needing to know how
those searches are implemented.

## Deployment independence

The service can be deployed independently of the applications consuming it.

---

# v1.0.0 Scope

Version 1.0.0 establishes the first usable Catalog Service boundary.

It provides:

* Media path management
* Local and SMB storage
* Music scanning
* Movie scanning
* TV scanning
* Book scanning
* Catalog persistence
* Embedding generation
* Embedding backfill
* Lexical search
* Semantic search
* Vector indexing
* Catalog item retrieval
* Catalog cleanup
* Catalog statistics
* FastAPI HTTP access
* Alembic database migration support

The primary objective of v1.0.0 is to provide a stable service that other
applications can consume through a dedicated driver.

---

# License

Add the project license here.

---

---
