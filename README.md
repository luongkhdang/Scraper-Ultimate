# News Scraper Ultimate

A powerful news scraper that extracts articles from various news websites and stores them in a PostgreSQL database.

## Features

- Extracts article URLs from news website homepages
- Scrapes full article content using Newspaper3k
- Extracts metadata like authors, publish date, and keywords
- Stores articles in a PostgreSQL database
- Parallel processing for faster scraping
- Proxy rotation to avoid IP blocking
- Handles errors gracefully
- Docker support for easy deployment

## Requirements

- Python 3.7+
- PostgreSQL (or Docker)
- Docker and Docker Compose (optional)

## Installation

### Option 1: Using Docker (Recommended)

1. Clone this repository:

```bash
git clone https://github.com/yourusername/Scraper-Ultimate.git
cd Scraper-Ultimate
```

2. Start the application with Docker Compose:

```bash
docker-compose up -d
```

This will:

- Start a PostgreSQL container
- Build and start the scraper container
- Mount the local directory to the container for easy development

### Option 2: Manual Installation

1. Clone this repository:

```bash
git clone https://github.com/yourusername/Scraper-Ultimate.git
cd Scraper-Ultimate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Set up PostgreSQL:

```bash
# Create the PostgreSQL database
createdb news-db
```

4. Configure environment variables:

```bash
# Copy the example .env file
cp .env.example .env
# Edit .env with your settings
```

## Configuration

The application can be configured using environment variables:

- `DB_NAME`: Database name (default: news-db)
- `DB_USER`: Database user (default: postgres)
- `DB_PASSWORD`: Database password (default: postgres)
- `DB_HOST`: Database host (default: localhost)
- `DB_PORT`: Database port (default: 5432)
- `MAX_ARTICLES_PER_WEBSITE`: Maximum number of articles to scrape per website (default: 5)
- `PARALLEL_WORKERS`: Number of parallel workers (default: 3)
- `USE_PROXIES`: Whether to use proxy rotation (default: true)

## Usage

1. Add website URLs to scrape in `sources/websites.md`, one URL per line.

2. Run the scraper:

With Docker:

```bash
docker-compose up
```

Without Docker:

```bash
python src/main.py
```

## Proxy Rotation

The scraper automatically generates a list of proxies from multiple sources and rotates through them during scraping to avoid IP blocking. This helps with:

- Avoiding rate limiting from news websites
- Bypassing simple anti-scraping measures
- Distributing requests across multiple IPs

You can disable proxy rotation by setting `USE_PROXIES=false` in your `.env` file.

## Docker Commands

- Start the application: `docker-compose up -d`
- Stop the application: `docker-compose down`
- View logs: `docker-compose logs -f scraper`
- Access PostgreSQL: `docker exec -it news-db psql -U postgres -d news-db`

## Database Schema

The articles are stored in the `articles` table with the following schema:

- `id`: Serial primary key
- `url`: Unique URL of the article
- `title`: Article title
- `text`: Full article text
- `summary`: Auto-generated summary
- `keywords`: Extracted keywords (JSONB)
- `authors`: List of authors (JSONB)
- `published_date`: Publication date
- `top_image`: URL of the article's main image
- `scraped_at`: Timestamp when the article was scraped
- `created_at`: Timestamp when the record was created

## License

MIT
