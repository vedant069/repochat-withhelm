# Use the official Python 3.10 slim image as the base
FROM python:3.10-slim

# Install system dependencies including git and curl
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory to /app
WORKDIR /app

# Copy the requirements file and install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code to the container
COPY . /app/

# Expose port 5000 to allow external access
EXPOSE 5000

# Ensure the file exists and run the application
# Define the default command to run the correct application file
CMD ["python3", "full.py"]

