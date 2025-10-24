FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_THEME_BASE=dark

# System deps for plotly, medical imaging, and 3D processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    dcm2niix \
    libgomp1 \
    libgl1 \
    libglib2.0-0 \
  && rm -rf /var/lib/apt/lists/*

# uv is causing an 'exec format error', so we are removing it and using pip directly.

# Install only frontend deps
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["/usr/local/bin/streamlit", "run", "/app/app.py", "--server.port=8501", "--server.address=0.0.0.0"]


