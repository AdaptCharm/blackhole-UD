# Use the official Python image from the Docker Hub
FROM python:3.11-slim

# Set the environment variable to enable buffered output
ENV PYTHONUNBUFFERED=1

# Install rclone
RUN apt-get update && apt-get install -y rclone

# Set the working directory in the container
WORKDIR /app

# Copy the requirements.txt file into the container
COPY requirements.txt .

# Install the required packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code into the container
COPY . .

# Command to run your script
CMD ["python", "blackhole-ud.py"]
