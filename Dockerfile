FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    # Playwright dependencies
    libglib2.0-0 \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libatspi2.0-0 \
    libdbus-1-3 \
    # Tor and network tools
    netcat-openbsd \
    curl \
    python3-socks \
    python3-stem \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Explicitly install scrapling package to ensure it's available
RUN pip install scrapling==0.2.99

# Install additional packages for Tor communication
RUN pip install stem requests[socks] pysocks

# Install NLTK data
RUN python -m nltk.downloader punkt
RUN python -m nltk.downloader punkt_tab
RUN python -m nltk.downloader stopwords

# Install Playwright browsers
RUN python -m playwright install --with-deps chromium

# Copy the rest of the application
COPY . .

# Set Docker environment flag
ENV RUNNING_IN_DOCKER=true

# Make the entrypoint script executable
RUN chmod +x docker-entrypoint.sh

# Set the entrypoint script
ENTRYPOINT ["./docker-entrypoint.sh"]

# Default command to run the scraper as a module
CMD ["python", "-m", "src.main"] 