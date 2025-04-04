FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY src/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire application
COPY . .

# Fix potential import issues by making the PYTHONPATH include the project root
ENV PYTHONPATH=/app

# Expose API port
EXPOSE 8000

# Run the API server
CMD ["python", "src/api/api_client.py"] 