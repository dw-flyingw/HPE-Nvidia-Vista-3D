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

# Install frontend dependencies from pyproject.toml
# Extract dependencies and install them
COPY pyproject.toml ./
RUN pip install --no-cache-dir \
    streamlit>=1.32.0 \
    extra-streamlit-components>=0.1.81 \
    requests>=2.31.0 \
    beautifulsoup4>=4.12.3 \
    fastapi>=0.104.0 \
    uvicorn>=0.24.0 \
    pandas>=2.0.0 \
    numpy>=2.0.0 \
    scipy>=1.11.0 \
    plotly>=5.0.0 \
    nibabel>=5.1.0 \
    nilearn>=0.10.0 \
    scikit-image>=0.21.0 \
    tqdm>=4.66.0 \
    jinja2>=3.1.0 \
    python-dotenv>=1.0.0
# Note: dcm2niix is installed as a system package above
COPY utils/ ./utils/
COPY assets/ ./assets/
COPY conf/ ./conf/
COPY app.py ./app.py
CMD ["/usr/local/bin/streamlit", "run", "/app/app.py", "--server.port=8501", "--server.address=0.0.0.0"]


