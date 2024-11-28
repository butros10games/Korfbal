FROM python:3.13-slim

# Install dependencies
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /kwt_daphne

# Install Python dependencies
COPY /requirements/daphne.txt /kwt_daphne/
RUN pip install --no-cache-dir -r daphne.txt

# Copy application files
COPY /apps/ /kwt_daphne/apps/
COPY /korfbal/ /kwt_daphne/korfbal/
COPY /manage.py /kwt_daphne/

# Expose the Daphne port
EXPOSE 8001

# Run Daphne server
CMD ["daphne", "-p", "8001", "-b", "0.0.0.0", "korfbal.asgi:application"]