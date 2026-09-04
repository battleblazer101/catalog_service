# Catalog Service API

## 1. Overview

The Catalog Service exposes a REST API through **FastAPI**.

The service is responsible for:

* Managing configured media paths.
* Scanning configured storage locations.
* Cataloguing music, movies, TV and books.
* Generating embeddings during ingestion.
* Performing textual search.
* Performing semantic search.
* Providing catalog statistics.
* Providing individual catalog item access.
* Removing catalog entries that are no longer present on disk.
* Supporting local filesystem and SMB storage.

The HTTP entry point is:

```text
app/main.py
```

There is intentionally **no separate `api/catalog.py`**.

The external driver should communicate exclusively with the FastAPI application.

---

# 2. Service Base URL

The development/deployment configuration currently starts Uvicorn on:

```text
http://127.0.0.1:8000
```

The service itself should therefore be treated as having a configurable base URL:

```text
http://<catalog-service-host>:8000
```

For example:

```text
http://catalog-service:8000
```

The consuming driver should not hard-code `127.0.0.1` unless both applications are guaranteed to run in the same network namespace.

---

# 3. Basic Endpoints

## `GET /`

Returns basic service information.

### Response

```json
{
  "service": "catalog_service",
  "version": "1.0.0"
}
```

The actual version is taken from the application's configuration.

---

## `GET /health`

Health/readiness check.

### Response

```json
{
  "status": "healthy"
}
```

The driver can use this endpoint to determine whether the Catalog Service is reachable.

A successful HTTP response indicates that the FastAPI application is running.

---

# 4. App Path API

App paths define **where media is stored** and **what type of media is located there**.

Supported media types:

```text
music
movie
tv
book
```

An app path contains:

```text
id
name
path
media_type
description
enabled
created_at
updated_at
```

---

## `GET /catalog/paths`

List configured paths.

### Optional query parameters

```text
media_type
enabled_only
```

Example:

```text
GET /catalog/paths
```

or:

```text
GET /catalog/paths?media_type=music
```

or:

```text
GET /catalog/paths?media_type=movie&enabled_only=true
```

### Response

```json
{
  "count": 2,
  "paths": [
    {
      "id": 1,
      "name": "Music",
      "path": "/media/music",
      "media_type": "music",
      "description": "Main music library",
      "enabled": true,
      "created_at": "...",
      "updated_at": "..."
    },
    {
      "id": 2,
      "name": "Movies",
      "path": "/media/movies",
      "media_type": "movie",
      "description": "Movie library",
      "enabled": true,
      "created_at": "...",
      "updated_at": "..."
    }
  ]
}
```

---

## `GET /catalog/paths/{path_id}`

Retrieve one configured path.

Example:

```text
GET /catalog/paths/2
```

### Response

```json
{
  "id": 2,
  "name": "Movies",
  "path": "/media/movies",
  "media_type": "movie",
  "description": "Movie library",
  "enabled": true,
  "created_at": "...",
  "updated_at": "..."
}
```

### Errors

```text
404
```

if the path does not exist.

---

## `POST /catalog/paths`

Create a new media path.

### Request

```json
{
  "name": "Movies",
  "path": "/media/movies",
  "media_type": "movie",
  "description": "Main movie library",
  "enabled": true
}
```

### Response

HTTP:

```text
201 Created
```

```json
{
  "id": 2,
  "name": "Movies",
  "path": "/media/movies",
  "media_type": "movie",
  "description": "Main movie library",
  "enabled": true,
  "created_at": "...",
  "updated_at": "..."
}
```

### Supported media types

```text
music
movie
tv
book
```

An invalid media type produces:

```text
400 Bad Request
```

A duplicate filesystem path produces:

```text
409 Conflict
```

---

# 5. Updating Paths

## `PUT /catalog/paths/{path_id}`

Updates an existing configured path.

Example:

```text
PUT /catalog/paths/2
```

### Request

```json
{
  "name": "Movies",
  "path": "/media/movies",
  "media_type": "movie",
  "description": "Updated movie library",
  "enabled": true
}
```

All fields are optional.

For example, disabling a path:

```json
{
  "enabled": false
}
```

The path remains configured but will no longer participate in the normal global scan.

### Errors

```text
404
```

Path does not exist.

```text
400
```

Invalid media type.

```text
409
```

Filesystem path conflicts with another configured path.

---

# 6. Deleting Paths

## `DELETE /catalog/paths/{path_id}`

Removes the configuration entry.

Example:

```text
DELETE /catalog/paths/2
```

### Response

```json
{
  "deleted": true,
  "id": 2
}
```

Important distinction:

**Deleting an AppPath does not necessarily mean deleting the media catalog entries belonging to that path.**

Path configuration and catalog contents are separate concerns.

If we want automatic cleanup, that should be an explicit catalog operation rather than an implicit side effect of deleting configuration.

---

# 7. Scanning

Scanning is the mechanism that discovers files and inserts them into the catalog.

The scanner layer handles:

```text
music
movie
tv
book
```

and storage is abstracted behind:

```text
StorageProvider
```

Therefore the API does not need to expose whether a path is local or SMB.

---

# 8. Scan All Enabled Paths

## `POST /catalog/scan`

Scans all enabled configured paths.

Optional:

```text
media_type
```

Example:

```text
POST /catalog/scan
```

Scans:

```text
music
movie
tv
book
```

Example:

```text
POST /catalog/scan?media_type=music
```

Only enabled music paths are scanned.

### Response

```json
{
  "media_type": "music",
  "paths_scanned": 2,
  "scanned": 1250,
  "inserted": 42,
  "results": [
    {
      "path_id": 1,
      "name": "Music",
      "path": "/media/music",
      "media_type": "music",
      "scanned": 1000,
      "inserted": 20
    },
    {
      "path_id": 5,
      "name": "More Music",
      "path": "/media/music2",
      "media_type": "music",
      "scanned": 250,
      "inserted": 22
    }
  ]
}
```

The important distinction is:

```text
scanned
```

means files discovered by the scanner.

```text
inserted
```

means new catalog records created.

A subsequent scan may therefore produce:

```json
{
  "scanned": 1250,
  "inserted": 0
}
```

which is expected.

---

# 9. Scan One Path

## `POST /catalog/scan/paths/{path_id}`

Scans one configured path regardless of whether it is enabled.

Example:

```text
POST /catalog/scan/paths/5
```

### Response

```json
{
  "path_id": 5,
  "name": "Movies",
  "path": "/media/movies",
  "media_type": "movie",
  "scanned": 500,
  "inserted": 17
}
```

This endpoint is useful for the driver when an administrator explicitly requests a rescan of one library.

---

# 10. Media-Specific Scan Endpoints

Convenience endpoints are also exposed.

## Music

```text
POST /catalog/scan/music
```

Equivalent to:

```text
POST /catalog/scan?media_type=music
```

---

## Movies

```text
POST /catalog/scan/movies
```

Equivalent to:

```text
POST /catalog/scan?media_type=movie
```

---

## TV

```text
POST /catalog/scan/tv
```

Equivalent to:

```text
POST /catalog/scan?media_type=tv
```

---

## Books

```text
POST /catalog/scan/books
```

Equivalent to:

```text
POST /catalog/scan?media_type=book
```

These are primarily convenience endpoints for consumers that want an obvious media-specific operation.

---

# 11. Catalog Items

The underlying catalog consists of `MediaItem` records.

Conceptually each item contains:

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
embedding
embedding_model
embedding_created_at
created_at
updated_at
```

The `embedding` and embedding implementation details should generally **not be exposed directly to the external driver**.

The driver should treat the Catalog Service as the owner of semantic indexing.

---

# 12. Get Catalog Item

## `GET /catalog/items/{item_id}`

Returns one catalog item.

Example:

```text
GET /catalog/items/123
```

### Response

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

The exact metadata contents depend on the scanner.

---

# 13. List Catalog Items

## `GET /catalog/items`

Lists catalog items.

The API should support filtering by media type.

Example:

```text
GET /catalog/items
```

or:

```text
GET /catalog/items?media_type=movie
```

The driver can therefore retrieve:

```text
all movies
all music
all TV
all books
```

without knowing anything about the underlying database.

Pagination should be supported for this endpoint once the catalog becomes large.

A practical interface is:

```text
limit
offset
media_type
```

For example:

```text
GET /catalog/items?media_type=movie&limit=100&offset=0
```

---

# 14. Text Search

## `GET /catalog/search`

Performs traditional database-backed text search.

Example:

```text
GET /catalog/search?query=matrix
```

### Response

```json
{
  "query": "matrix",
  "count": 2,
  "results": [
    {
      "id": 123,
      "media_type": "movie",
      "title": "The Matrix",
      "creator": "Unknown",
      "collection": "Unknown",
      "genre": "Unknown",
      "year": 1999,
      "score": 3.0
    }
  ]
}
```

The current lexical scoring gives greater weight to:

```text
title       3.0
creator     2.0
collection  1.5
```

This endpoint does **not** require embeddings.

That distinction is important.

---

# 15. Semantic Search

## `GET /catalog/search/semantic`

Performs embedding-based semantic search.

Example:

```text
GET /catalog/search/semantic?query=movies%20about%20artificial%20intelligence
```

The service:

1. Receives the natural-language query.
2. Generates an embedding using the configured embedding model.
3. Searches the catalog's vector index.
4. Returns the closest catalog items.

The driver therefore does not need to know anything about:

```text
SentenceTransformer
FAISS
vector dimensions
embedding serialization
model names
```

Those are internal implementation details.

### Conceptual response

```json
{
  "query": "movies about artificial intelligence",
  "count": 5,
  "results": [
    {
      "id": 123,
      "media_type": "movie",
      "title": "The Matrix",
      "creator": "Unknown",
      "collection": "Unknown",
      "genre": "Unknown",
      "year": 1999,
      "score": 0.81
    }
  ]
}
```

The score represents semantic similarity rather than the lexical score used by `/catalog/search`.

---

# 16. Why There Are Two Search APIs

The driver should understand these as two different capabilities.

### Lexical search

```text
GET /catalog/search
```

Best for:

```text
"matrix"
"beatles"
"breaking bad"
"tolkien"
```

It is deterministic and database-backed.

### Semantic search

```text
GET /catalog/search/semantic
```

Best for:

```text
"movies involving artificial intelligence"

"upbeat music for a party"

"books about space exploration"

"crime dramas set in New York"
```

The caller does not need to decide how embeddings work.

---

# 17. Catalog Cleanup

A catalog can become stale if files are deleted or moved after scanning.

The service therefore needs an explicit cleanup operation.

Conceptually:

```text
POST /catalog/cleanup
```

The service compares catalog paths against the configured storage locations and removes records that no longer exist.

A media-specific cleanup can optionally be supported:

```text
POST /catalog/cleanup?media_type=movie
```

The response should report:

```json
{
  "checked": 1500,
  "removed": 23
}
```

This operation should be separate from scanning.

Scanning answers:

> What new media exists?

Cleanup answers:

> What previously catalogued media no longer exists?

---

# 18. Statistics

## `GET /catalog/stats`

Returns catalog statistics.

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

This is useful to the driver for:

* diagnostics
* administrative UI
* monitoring
* determining whether indexing has completed
* detecting missing embeddings

---

# 19. Recommended Driver Interface

The external project should **not mirror every internal service class**.

Instead, its driver should expose a small, stable interface around the HTTP API.

Conceptually:

```python
class CatalogDriver:

    async def health(self):
        ...

    async def list_paths(
        self,
        media_type=None,
        enabled_only=False,
    ):
        ...

    async def create_path(
        self,
        name,
        path,
        media_type,
        description=None,
        enabled=True,
    ):
        ...

    async def update_path(
        self,
        path_id,
        **changes,
    ):
        ...

    async def delete_path(
        self,
        path_id,
    ):
        ...

    async def scan(
        self,
        media_type=None,
    ):
        ...

    async def scan_path(
        self,
        path_id,
    ):
        ...

    async def get_item(
        self,
        item_id,
    ):
        ...

    async def list_items(
        self,
        media_type=None,
        limit=100,
        offset=0,
    ):
        ...

    async def search(
        self,
        query,
    ):
        ...

    async def semantic_search(
        self,
        query,
    ):
        ...

    async def cleanup(
        self,
        media_type=None,
    ):
        ...

    async def stats(self):
        ...
```

This gives the other project a clean abstraction.

---

# 20. Important Architectural Boundary

The driver should **never need to access**:

```text
SQLAlchemy
MediaItem
AppPath
SentenceTransformer
FAISS
Mutagen
smbclient
StorageProvider
LocalStorageProvider
SMBStorageProvider
```

Those belong entirely inside Catalog Service.

The driver communicates with:

```text
FastAPI
    │
    ├── /health
    ├── /catalog/paths
    ├── /catalog/scan
    ├── /catalog/items
    ├── /catalog/search
    ├── /catalog/search/semantic
    ├── /catalog/cleanup
    └── /catalog/stats
```

That is the actual public contract.

---

# 21. Recommended API Surface

For the **first deployable version**, I would consider this the final public surface:

| Method   | Endpoint                   | Purpose               |
|----------|----------------------------|-----------------------|
| `GET`    | `/`                        | Service information   |
| `GET`    | `/health`                  | Health check          |
| `GET`    | `/catalog/paths`           | List configured paths |
| `GET`    | `/catalog/paths/{id}`      | Get path              |
| `POST`   | `/catalog/paths`           | Create path           |
| `PUT`    | `/catalog/paths/{id}`      | Update path           |
| `DELETE` | `/catalog/paths/{id}`      | Delete path           |
| `POST`   | `/catalog/scan`            | Scan enabled paths    |
| `POST`   | `/catalog/scan/paths/{id}` | Scan one path         |
| `POST`   | `/catalog/scan/music`      | Scan music            |
| `POST`   | `/catalog/scan/movies`     | Scan movies           |
| `POST`   | `/catalog/scan/tv`         | Scan TV               |
| `POST`   | `/catalog/scan/books`      | Scan books            |
| `GET`    | `/catalog/items`           | List catalog          |
| `GET`    | `/catalog/items/{id}`      | Get catalog item      |
| `GET`    | `/catalog/search`          | Lexical search        |
| `GET`    | `/catalog/search/semantic` | Semantic search       |
| `POST`   | `/catalog/cleanup`         | Remove stale items    |
| `GET`    | `/catalog/stats`           | Catalog statistics    |
