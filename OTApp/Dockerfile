# Use a modern python base
FROM python:3.12-slim

# 1. Set the working directory to /app
WORKDIR /app/OTApp

# 2. Add /app to the PYTHONPATH so 'python -m' can find 'OTApp'
ENV PYTHONPATH="/app"

# 3. Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Create the logs folder and set permissions
RUN mkdir -p /app/logs && chmod 777 /app/logs

# 4. Copy your entire project folder into /app
COPY . .

# 5. Use 'python3' and module dots (no .py)
CMD ["python3", "-m", "Orchestrator.Orchestrator"]