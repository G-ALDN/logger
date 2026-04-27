# Use a lightweight Python image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy your requirements and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your python script
COPY logger.py .

# Run the script when the container starts
CMD ["uvicorn", "logger:app", "--host", "0.0.0.0", "--port", "8000"]