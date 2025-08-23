FROM python:3.11-slim

# Install TeX Live and latexmk
RUN apt-get update && apt-get install -y --no-install-recommends \
    latexmk \
    texlive-latex-recommended \
    texlive-latex-extra \
    texlive-science \
    texlive-fonts-recommended \
    texlive-fonts-extra \
    && rm -rf /var/lib/apt/lists/*

# Set workdir
WORKDIR /app

# Copy requirements first
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . .

# Expose Flask port
EXPOSE 8000

# Run the Flask app
CMD ["gunicorn", "-b", "0.0.0.0:8000", "app:app"]
