# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your backend code
COPY . .

# Expose the FastAPI port (e.g., 8000)
EXPOSE 8000

# Run your backend
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
