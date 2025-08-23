import os
import io
import base64
import json
import subprocess
import tempfile
from pathlib import Path
from flask import Flask, request, redirect, abort
import requests

# --- Configuration from environment ---
GH_OWNER = os.environ["GH_OWNER"]         # e.g. "your-org-or-user"
GH_REPO  = os.environ["GH_REPO"]          # e.g. "your-repo"
GH_TOKEN = os.environ["GH_TOKEN"]         # fine-grained PAT with Contents: Read & write
PAGES_BRANCH = os.environ.get("PAGES_BRANCH", "gh-pages")
PAGES_BASE = os.environ["PAGES_BASE"]     # e.g. "https://your-org.github.io/your-repo"

# --- Flask app ---
app = Flask(__name__)

SCENARIOS = [1, 2, 3, 4, 5]

def github_headers():
    return {
        "Authorization": f"Bearer {GH_TOKEN}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "mengm0056-pdf-uploader"
    }

def gh_contents_url(path):
    return f"https://api.github.com/repos/{GH_OWNER}/{GH_REPO}/contents/{path}"

def gh_get(path):
    r = requests.get(gh_contents_url(path), headers=github_headers(), params={"ref": PAGES_BRANCH})
    return r

def gh_put(path, data_bytes, message, sha=None):
    # Upload via GitHub Contents API (base64-encoded)
    content_b64 = base64.b64encode(data_bytes).decode("ascii")
    payload = {
        "message": message,
        "content": content_b64,
        "branch": PAGES_BRANCH,
        "committer": {"name": "PDF Bot", "email": "no-reply@example.com"}
    }
    if sha:
        payload["sha"] = sha
    r = requests.put(gh_contents_url(path), headers=github_headers(), data=json.dumps(payload))
    if r.status_code not in (200, 201):
        raise RuntimeError(f"GitHub upload failed for {path}: {r.status_code} {r.text}")
    return r.json()

def ensure_uuid_folder_exists(uuid: str) -> bool:
    """Return True if UUID folder already exists on gh-pages."""
    r = gh_get(f"{uuid}")
    return r.status_code == 200

def upload_file(path_in_repo: str, local_path: Path, commit_msg: str):
    # Check if file exists to get its sha (required for updates)
    sha = None
    r = gh_get(path_in_repo)
    if r.status_code == 200:
        sha = r.json().get("sha")
    with open(local_path, "rb") as f:
        gh_put(path_in_repo, f.read(), commit_msg, sha=sha)

def build_once(uuid: str, workdir: Path):
    """Generate LaTeX and compile PDFs into workdir."""
    for s in SCENARIOS:
        tex = workdir / f"mengm0056_s{s}_handout.tex"
        pdf = workdir / f"mengm0056_s{s}_handout.pdf"
        # Generate LaTeX
        with open(tex, "w", encoding="utf-8") as tex_out:
            subprocess.run(
                ["python", f"generate_s{s}_handout.py", "--uuid", uuid],
                stdout=tex_out, check=True
            )
        # Compile
        subprocess.run(
            ["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error", tex.name],
            cwd=str(workdir),
            check=True
        )

    # Create index.html for this UUID
    index_html = f"""<!doctype html>
<meta charset="utf-8">
<title>Scenario PDFs for {uuid}</title>
<h1>Scenario PDFs for {uuid}</h1>
<ul>
  {''.join([f'<li><a href="mengm0056_s{s}_handout.pdf">Scenario {s}</a></li>' for s in SCENARIOS])}
</ul>
"""
    (workdir / "index.html").write_text(index_html, encoding="utf-8")

@app.get("/generate")
def generate():
    uuid = (request.args.get("uuid") or "").strip()
    if not uuid:
        abort(400, "Missing uuid")

    # If already present on gh-pages, skip building and redirect immediately
    if ensure_uuid_folder_exists(uuid):
        return redirect(f"{PAGES_BASE}/{uuid}/", code=302)

    # Build PDFs in a temp dir
    with tempfile.TemporaryDirectory(prefix=f"{uuid}_") as tmp:
        tmpdir = Path(tmp)
        build_once(uuid, tmpdir)

        # Upload all PDFs and index.html under /<uuid>/ in gh-pages
        commit_msg = f"Add scenario PDFs for {uuid}"
        for s in SCENARIOS:
            upload_file(f"{uuid}/mengm0056_s{s}_handout.pdf", tmpdir / f"mengm0056_s{s}_handout.pdf", commit_msg)
        upload_file(f"{uuid}/index.html", tmpdir / "index.html", commit_msg)

    # Redirect to the permanent static URL
    return redirect(f"{PAGES_BASE}/{uuid}/", code=302)

@app.get("/")
def health():
    return "OK"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
