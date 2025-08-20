# Use the official Apify SDK base image for Python
FROM apify/actor-python:3.11

# Set working directory
WORKDIR /usr/src/app

# Copy requirements and install dependencies first (for better caching)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . ./

# Create non-root user for security
RUN groupadd -r apify && useradd -r -g apify apify
RUN chown -R apify:apify /usr/src/app
USER apify

# Set environment variables
ENV PYTHONPATH=/usr/src/app
ENV PYTHONUNBUFFERED=1

# Set the command to run the actor
CMD python3 -m src.main
