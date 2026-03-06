# Use official Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy project code
COPY . /app

# Upgrade pip and install dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Expose port for FastAPI
EXPOSE 8080

# Start FastAPI app
CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8080"]--host", "0.0.0.0", "--port", "8000"]