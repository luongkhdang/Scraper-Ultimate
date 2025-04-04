# Articles Database API

This API provides a safe interface to access the articles database from other projects.

## Features

- RESTful API for accessing article data
- Automatic connection pooling for efficient database access
- Pagination support for large result sets
- Error handling and proper HTTP status codes
- CORS support for web clients

## Setup

### Environment Variables

Create a `.env` file with the following variables:

```
DB_HOST=postgres
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=postgres
DB_NAME=news-db
API_HOST=0.0.0.0
API_PORT=8000
```

### Running with Docker Compose

The easiest way to run the API is with Docker Compose:

```bash
docker-compose -f docker-compose.api.yml up -d
```

This will start both the PostgreSQL database and the API server.

## API Endpoints

### Get API Status

```
GET /
```

Response:

```json
{
  "status": "ok",
  "message": "Article Database API is running",
  "timestamp": 1633456789.123
}
```

### Get Articles

```
GET /articles?status=ReadyForReview&page=1&limit=20
```

Parameters:

- `status` (optional): Article status to filter by (default: "ReadyForReview")
- `page` (optional): Page number for pagination (default: 1)
- `limit` (optional): Number of articles per page (default: 20, max: 100)

Response:

```json
{
  "articles": [
    {
      "id": 123,
      "url": "https://example.com/article",
      "domain": "example.com",
      "title": "Example Article",
      "content": "Article content...",
      "proceeding_status": "ReadyForReview",
      "pub_date": "2023-01-15T12:34:56",
      "created_at": "2023-01-15T12:34:56",
      "scraped_at": "2023-01-15T12:40:00"
    }
  ],
  "count": 1,
  "page": 1,
  "limit": 20,
  "total": 100
}
```

### Get Article by ID

```
GET /articles/{article_id}
```

Response:

```json
{
  "id": 123,
  "url": "https://example.com/article",
  "domain": "example.com",
  "title": "Example Article",
  "content": "Article content...",
  "proceeding_status": "ReadyForReview",
  "pub_date": "2023-01-15T12:34:56",
  "created_at": "2023-01-15T12:34:56",
  "scraped_at": "2023-01-15T12:40:00"
}
```

### Check URL Existence

```
GET /check-url?url=https://example.com/article
```

Response:

```json
{
  "exists": true
}
```

### Get Status Counts

```
GET /status/counts
```

Response:

```json
{
  "counts": {
    "ReadyForReview": 100,
    "Pending": 50,
    "FAILED": 10
  },
  "total": 160
}
```

### Get Failed Domains

```
GET /domains/failed
```

Response:

```json
{
  "domains": {
    "example.com": {
      "failed_count": 5,
      "error_messages": ["Connection timed out", "403 Forbidden"],
      "article_ids": [123, 456, 789]
    }
  },
  "count": 1
}
```

## Using the API from Another Project

See the `api_client_example.py` file for examples of how to consume this API from another project.

## Security Considerations

- The API is designed to be accessed from trusted services only
- For production use, consider adding authentication (JWT, API keys)
- Restrict CORS origins to trusted domains
- Use HTTPS in production
