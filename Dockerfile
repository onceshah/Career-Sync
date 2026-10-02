FROM python:3.12-slim

# Set environment variables for Python optimization and safety
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_HOME=/app

WORKDIR $APP_HOME

# Install base build dependencies for native packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements and install python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && python -m spacy download en_core_web_sm \
    && apt-get purge -y --auto-remove build-essential \
    && rm -rf /root/.cache/pip

# Copy the rest of the application
COPY . .

# Default CLI command (Dry-Run mode: no Gmail credentials required in-container)
CMD ["python", "main.py", "--limit", "5"]
