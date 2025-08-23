FROM python:3.11-slim
ENV FLASK_APP=app.py
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
EXPOSE 10000

# Run the Flask app
CMD ["flask", "run", "--host=0.0.0.0", "--port=10000"]


