FROM python:3.11-slim

WORKDIR /app

# Install dependencies strictly
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the backend
COPY . .

# Expose the API port (HuggingFace Spaces expects 7860)
EXPOSE 7860

# Boot the FastAPI uvicorn engine
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
