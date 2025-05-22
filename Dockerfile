# Use an official lightweight Python image
FROM python:3.13-slim

# Set working directory inside the container
WORKDIR /app

# Copy project files into the container
COPY . /app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose Flask port
EXPOSE 8000

# Start Flask app
CMD ["python", "app.py"]
