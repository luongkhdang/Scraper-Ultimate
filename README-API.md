# Article Database API

This API provides a safe interface for other projects to access the article database without directly connecting to PostgreSQL.

## Getting Started

The API service is now integrated into your Docker setup. You can start it along with your other services using:

```bash
docker-compose up -d
```

## API Endpoints

The API is accessible at http://localhost:8000/ and provides the following endpoints:

### Root Endpoint

- `GET /`: Get API status and version

### Articles Endpoints

- `GET /articles`: Get articles with filters and pagination
  - Query params: `status`, `page`, `limit`
- `GET /articles/{article_id}`: Get a specific article by ID

### Status Endpoints

- `GET /status/counts`: Get counts of articles by status
- `GET /domains/failed`: Get domains with failed article processing
- `GET /check-url?url=...`: Check if a URL exists in the database

## Using the API from Another Project

To access this API from another Docker project:

1. Add your API service to the same network as your other project by adding to your other project's docker-compose.yml:

```yaml
networks:
  external:
    name: scraper-ultimate_app_network
```

2. Then you can access the API using the service name:

```python
import requests

API_BASE_URL = "http://news-api:8000"

def get_articles(status="ReadyForReview", page=1, limit=20):
    response = requests.get(
        f"{API_BASE_URL}/articles",
        params={"status": status, "page": page, "limit": limit}
    )
    return response.json()
```

3. For non-Docker projects, use `http://localhost:8000` as the base URL

## Swagger Documentation

Interactive API documentation is available at:

- http://localhost:8000/docs
- http://localhost:8000/redoc

## Benefits of Using the API

- **Security**: No direct database access required
- **Stability**: Database changes won't break client applications
- **Abstraction**: Clients don't need to know database schema details
- **Maintenance**: Easier to update database logic without affecting clients
