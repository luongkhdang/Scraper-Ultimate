# News Scraper Ultimate

## Overview

This project is a robust web scraping application designed to extract and store news articles from various credible online sources. It utilizes a sophisticated multi-layered approach to fetch content efficiently while handling potential anti-scraping mechanisms. The extracted data is stored in a PostgreSQL database.

## Core Features & Scraping Techniques

The scraper employs several advanced techniques to ensure reliable content extraction:

- **Multi-Method Extraction:**
  - Uses `newspaper3k` for initial, fast content extraction.
  - Employs **Playwright** with a headless Chromium browser as a fallback to handle JavaScript-heavy sites, dynamic content loading, and complex DOM structures. Special handling is included for redirect chains (e.g., from aggregators like Google News).
- **Advanced Scraping Strategy:**
  - Integrates a **Special Strategy** module (`src/scraper/scraper_hooks/strategies/special_strategy.py`) specifically designed for sites with strong anti-bot protections.
  - Utilizes **StealthyFetcher** (via the `scrapling` library) as a final fallback, providing enhanced stealth capabilities against detection systems.
- **Anti-Detection Measures:**
  - **User-Agent Rotation:** Uses a diverse pool of realistic browser user agents.
  - **Realistic Headers:** Sends browser-like HTTP headers, including referrers.
  - **Randomized Delays:** Introduces variable delays between requests and actions to mimic human browsing patterns.
  - **Fingerprint Consistency:** Applies consistent browser fingerprint properties (screen size, platform, etc.) within scraping sessions to avoid detection.
  - **Tor Integration:** Leverages a Tor proxy service (configured via Docker Compose) for IP address rotation, enhancing anonymity and bypassing IP-based blocks. The Special Strategy module can trigger Tor circuit rotation when protection is detected.
  - **Behavior Simulation:** Simulates human-like interactions such as scrolling patterns within Playwright sessions.
  - **Consent/Overlay Handling:** Attempts to automatically handle cookie consent dialogs and dismiss overlay elements that might obstruct content.
- **Concurrency:** Uses Python's `ThreadPoolExecutor` to process multiple articles and sources concurrently, maximizing throughput.
- **Robust Error Handling & Retries:** Implements retry logic for failed extractions and handles various exceptions gracefully. Includes adaptive delays based on detection history.
- **Persistence:** Stores extracted article metadata and content in a PostgreSQL database.
- **Containerized Environment:** Fully containerized using Docker and Docker Compose for easy setup, dependency management, and deployment across different environments. Includes services for the scraper, database (PostgreSQL), database management (pgAdmin), and the Tor proxy.

## Technology Stack

- **Language:** Python 3.10
- **Core Libraries:**
  - `requests` / `httpx` (via `scrapling`): HTTP requests
  - `newspaper3k`: Basic article extraction
  - `BeautifulSoup4` / `lxml`: HTML parsing (dependencies for `newspaper3k`)
  - `Playwright`: Advanced browser automation and rendering
  - `scrapling` (with `StealthyFetcher`): Stealthy, browser-based fetching
  - `NLTK`: Text processing (used by `newspaper3k`)
- **Database:** PostgreSQL
- **Anonymization:** Tor Proxy
- **Containerization:** Docker, Docker Compose

## Setup and Running

The application is designed to be run using Docker Compose.

1.  **Prerequisites:**
    - Docker ([https://docs.docker.com/get-docker/](https://docs.docker.com/get-docker/))
    - Docker Compose ([https://docs.docker.com/compose/install/](https://docs.docker.com/compose/install/))
2.  **Configuration:**
    - Review `docker-compose.yml` for service configurations and exposed ports.
    - Environment variables (e.g., `TORPASSWORD`) can be set within `docker-compose.yml` or potentially via an external `.env` file (though one is not strictly required by default).
3.  **Build and Run:**
    ```bash
    docker-compose up --build -d
    ```
    This command builds the necessary Docker images (if not already built) and starts all the defined services (`postgres`, `pgadmin`, `tor`, `scraper`, `api`) in detached mode.
4.  **Accessing Services:**
    - **pgAdmin:** `http://localhost:5050`
    - **API:** `http://localhost:8000` (if running)
5.  **Operation:**
    - The `scraper` service will automatically start processing sources and extracting articles based on the entry point defined in the `Dockerfile` (`src.main`).
    - Logs can be viewed using `docker-compose logs scraper`.
6.  **Stopping:**
    ```bash
    docker-compose down
    ```
