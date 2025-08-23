import os
import io
import json
import base64
import re
import threading
import tempfile
import subprocess
from pathlib import Path
from flask import Flask, request, redirect, abort, jsonify, render_template_string
import requests

# --- Config via env ---
GH_OWNER = os.environ["GH_OWNER"]
GH_REPO  = os.environ["GH_REPO"]
GH_TOKEN = os.environ["GH_TOKEN"]
PAGES_BRANCH = os.environ.get("PAGES_BRANCH", "gh-pages")
PAGES_BASE = os.environ["PAGES_BASE"]  # e.g. https://<owner>.github.io/<repo>

SCENARIOS = [1, 2, 3, 4, 5]

app = Flask(__name__)

# --- Simple in-memory progress store ---
# NOTE: This lives in-process. Run a single worker (e.g. gunicorn -w 1) unless you add Redis.
STATUS = {}  # uuid -> dict(status)
STATUS_LOCK = threading.Lock()

def set_status(uuid, **fields):
    with STATUS_LOCK:
        s = STATUS.get(uuid, {})
        s.update(fields)
        STATUS[uuid] = s

def get_status(uuid):
    with STATUS_LOCK:
        return STATUS.get(uuid, {}).copy()

# --- GitHub helpers ---
def _gh_headers():
    return {
        "Authorization": f"Bearer {GH_TOKEN}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "mengm0056-pdf-uploader"
    }

def _gh_contents_url(path):
    return f"https://api.github.com/repos/{GH_OWNER}/{GH_REPO}/contents/{path}"

def gh_get(path):
    return requests.get(_gh_contents_url(path), headers=_gh_headers(), params={"ref": PAGES_BRANCH})

def gh_put(path, data_bytes, message, sha=None):
    content_b64 = base64.b64encode(data_bytes).decode("ascii")
    payload = {
        "message": message,
        "content": content_b64,
        "branch": PAGES_BRANCH,
        "committer": {"name": "PDF Bot", "email": "no-reply@example.com"}
    }
    if sha:
        payload["sha"] = sha
    r = requests.put(_gh_contents_url(path), headers=_gh_headers(), data=json.dumps(payload))
    if r.status_code not in (200, 201):
        raise RuntimeError(f"GitHub upload failed for {path}: {r.status_code} {r.text}")
    return r.json()

def upload_file(path_in_repo: str, local_path: Path, commit_msg: str):
    sha = None
    r = gh_get(path_in_repo)
    if r.status_code == 200:
        try:
            sha = r.json().get("sha")
        except Exception:
            sha = None
    with open(local_path, "rb") as f:
        gh_put(path_in_repo, f.read(), commit_msg, sha=sha)

def uuid_folder_exists(uuid: str) -> bool:
    return gh_get(f"{uuid}").status_code == 200

# --- Build logic with progress updates ---
def build_and_publish(uuid: str):
    """Runs in a background thread; updates STATUS[uuid]."""
    try:
        set_status(uuid, stage="starting", step=0, total= (len(SCENARIOS)*3 + 2), done=False, error=None)

        # If already published, nothing to do
        if uuid_folder_exists(uuid):
            set_status(uuid, stage="already_published", step=1)
            set_status(uuid, done=True, pages_url=f"{PAGES_BASE}/{uuid}/")
            return

        with tempfile.TemporaryDirectory(prefix=f"{uuid}_") as tmp:
            tmpdir = Path(tmp)
            step = 0

            # Generate & compile each scenario
            for s in SCENARIOS:
                step += 1; set_status(uuid, stage=f"generate_s{s}", step=step)
                tex_path = tmpdir / f"mengm0056_s{s}_handout.tex"
                with open(tex_path, "w", encoding="utf-8") as tex_out:
                    subprocess.run(["python", f"generate_s{s}_handout.py", "--uuid", uuid],
                                   stdout=tex_out, check=True)

                step += 1; set_status(uuid, stage=f"compile_s{s}", step=step)
                subprocess.run(
                    ["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error", tex_path.name],
                    cwd=str(tmpdir), check=True
                )

            # Write per-UUID index.html
            step += 1; set_status(uuid, stage="write_index", step=step)
            html = f"""<!doctype html>
<meta charset="utf-8">
<title>Scenario PDFs for {uuid}</title>
<h1>Scenario PDFs for {uuid}</h1>
<ul>
  {''.join([f'<li><a href="mengm0056_s{s}_handout.pdf">Scenario {s}</a></li>' for s in SCENARIOS])}
</ul>"""
            (tmpdir / "index.html").write_text(html, encoding="utf-8")

            # Upload everything to gh-pages/<uuid>/
            commit_msg = f"Add scenario PDFs for {uuid}"
            for s in SCENARIOS:
                step += 1; set_status(uuid, stage=f"upload_s{s}", step=step)
                upload_file(f"{uuid}/mengm0056_s{s}_handout.pdf", tmpdir / f"mengm0056_s{s}_handout.pdf", commit_msg)

            step += 1; set_status(uuid, stage="upload_index", step=step)
            upload_file(f"{uuid}/index.html", tmpdir / "index.html", commit_msg)

        set_status(uuid, stage="done", done=True, pages_url=f"{PAGES_BASE}/{uuid}/")

    except subprocess.CalledProcessError as e:
        set_status(uuid, done=True, error=f"Build error: {e}", pages_url=None)
    except Exception as e:
        set_status(uuid, done=True, error=f"Server error: {e}", pages_url=None)

# --- Endpoints ---

@app.get("/start")
def start():
    """Return a waiting room page and kick off background build if needed."""
    uuid = (request.args.get("uuid") or "").strip()
    if not uuid or not re.fullmatch(r"[0-9a-fA-F-]{16,}", uuid):
        abort(400, "Missing/invalid uuid")

    s = get_status(uuid)
    if not s or s.get("done") and not s.get("pages_url"):
        # Either first time or previous error -> reset
        set_status(uuid, stage="queued", step=0, total=(len(SCENARIOS)*3 + 2), done=False, error=None)
        threading.Thread(target=build_and_publish, args=(uuid,), daemon=True).start()

    # Simple waiting-room HTML with polling + progress bar
    page = """<!doctype html>
<meta charset="utf-8">
<title>Building PDFs…</title>
<style>
  body{font-family:system-ui,Segoe UI,Roboto,Arial;margin:2rem auto;max-width:720px;line-height:1.5}
  .bar{height:14px;background:#eee;border-radius:7px;overflow:hidden}
  .fill{height:100%;width:0%;}
  .fill.ok{background:#4caf50}
  .fill.err{background:#d32f2f}
  .muted{color:#666;font-size:.9rem}
  code{background:#f6f8fa;padding:.1rem .3rem;border-radius:4px}
</style>
<h1>Generating your scenario PDFs</h1>
<p class="muted">UUID: <code id="u"></code></p>
<div class="bar"><div id="fill" class="fill"></div></div>
<p id="stage" class="muted" style="margin:.5rem 0 1rem 0;">Starting…</p>
<p id="msg" class="muted"></p>
<script>
const uuid = new URLSearchParams(location.search).get('uuid');
document.getElementById('u').textContent = uuid;
const fill = document.getElementById('fill');
const stage = document.getElementById('stage');
const msg = document.getElementById('msg');

async function tick(){
  try{
    const r = await fetch(`/status?uuid=${encodeURIComponent(uuid)}&t=${Date.now()}`);
    const s = await r.json();
    if(s.error){
      fill.className='fill err';
      fill.style.width='100%';
      stage.textContent = 'Error';
      msg.textContent = s.error;
      return;
    }
    const total = s.total || 100;
    const pct = Math.max(0, Math.min(100, Math.round(100*(s.step||0)/total)));
    fill.className = 'fill ok';
    fill.style.width = pct + '%';
    stage.textContent = s.stage ? `Stage: ${s.stage} (${pct}%)` : 'Working…';
    if(s.done && s.pages_url){
      stage.textContent = 'Done - opening your PDFs…';
      setTimeout(()=>{ window.location.href = s.pages_url; }, 600);
      return;
    }
  }catch(e){
    // ignore transient errors; keep polling
  }
  setTimeout(tick, 1200);
}
tick();
</script>
"""
    return render_template_string(page)

@app.get("/status")
def status():
    uuid = (request.args.get("uuid") or "").strip()
    if not uuid:
        return jsonify({"error":"Missing uuid"}), 400
    s = get_status(uuid)
    if not s:
        # If nothing recorded yet, report queued
        s = {"stage":"queued","step":0,"total":(len(SCENARIOS)*3 + 2),"done":False}
    return jsonify(s)

# Keep your old /generate if you like, but the new flow uses /start
@app.get("/generate")
def generate_legacy():
    # For backwards compatibility: simply redirect to /start so users see progress
    uuid = (request.args.get("uuid") or "").strip()
    if not uuid:
        abort(400, "Missing uuid")
    return redirect(f"/start?uuid={uuid}", code=302)

@app.get("/")
def health():
    return "OK"
