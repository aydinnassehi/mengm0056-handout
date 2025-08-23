import os
import io
import json
import base64
import re
import time
import threading
import tempfile
import subprocess
from pathlib import Path

import requests
from flask import Flask, request, redirect, abort, jsonify, render_template_string

# -------- Configuration (env) --------
# GitHub repo where gh-pages hosts the PDFs
GH_OWNER = os.environ["GH_OWNER"]          # e.g. "your-org-or-user"
GH_REPO  = os.environ["GH_REPO"]           # e.g. "your-repo"
GH_TOKEN = os.environ["GH_TOKEN"]          # Fine-grained PAT: Contents RW + Pages RW
PAGES_BRANCH = os.environ.get("PAGES_BRANCH", "gh-pages")
PAGES_BASE   = os.environ["PAGES_BASE"]    # e.g. "https://your-org.github.io/your-repo"

# Build behaviour
SCENARIOS = [1, 2, 3, 4, 5]
PAGES_BUILD_TIMEOUT_S   = int(os.environ.get("PAGES_BUILD_TIMEOUT_S", "180"))
PAGES_PROPAGATE_TIMEOUT = int(os.environ.get("PAGES_PROPAGATE_TIMEOUT", "90"))
POLL_INTERVAL_S         = float(os.environ.get("POLL_INTERVAL_S", "1.2"))

app = Flask(__name__)

# -------- Minimal in-process status store (single worker) --------
STATUS = {}  # uuid -> dict
STATUS_LOCK = threading.Lock()

def set_status(uuid, **fields):
    with STATUS_LOCK:
        s = STATUS.get(uuid, {})
        s.update(fields)
        STATUS[uuid] = s

def get_status(uuid):
    with STATUS_LOCK:
        return dict(STATUS.get(uuid, {}))

# -------- GitHub helpers --------
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

# -------- GitHub Pages build/ready helpers --------
def trigger_pages_build():
    url = f"https://api.github.com/repos/{GH_OWNER}/{GH_REPO}/pages/builds"
    r = requests.post(url, headers=_gh_headers())
    if r.status_code not in (200, 201, 204):
        raise RuntimeError(f"Failed to trigger Pages build: {r.status_code} {r.text}")

def get_latest_pages_build():
    url = f"https://api.github.com/repos/{GH_OWNER}/{GH_REPO}/pages/builds/latest"
    r = requests.get(url, headers=_gh_headers())
    if r.status_code != 200:
        raise RuntimeError(f"Failed to fetch latest Pages build: {r.status_code} {r.text}")
    return r.json()  # includes 'status': 'built'|'building'|'errored'

def wait_for_pages_build(max_seconds=PAGES_BUILD_TIMEOUT_S, poll_every=3):
    deadline = time.time() + max_seconds
    last_status = None
    while time.time() < deadline:
        try:
            info = get_latest_pages_build()
            last_status = info.get("status")
            if last_status in ("built", "errored"):
                return last_status
        except Exception:
            pass
        time.sleep(poll_every)
    return last_status or "unknown"

def wait_for_url_200(url, max_seconds=PAGES_PROPAGATE_TIMEOUT, poll_every=3):
    deadline = time.time() + max_seconds
    while time.time() < deadline:
        try:
            r = requests.head(url, allow_redirects=True, timeout=5)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(poll_every)
    return False

# -------- Build + publish (runs in background thread) --------
def build_and_publish(uuid: str):
    try:
        total_steps = (len(SCENARIOS) * 3) + 4   # generate + compile + upload per scenario (x3), plus index upload + pages build + propagate + done
        step = 0
        set_status(uuid, stage="starting", step=step, total=total_steps, done=False, error=None)

        # If already live on Pages, finish immediately
        if uuid_folder_exists(uuid):
            set_status(uuid, stage="already_published", step=total_steps-1)
            set_status(uuid, done=True, pages_url=f"{PAGES_BASE}/{uuid}/")
            return

        with tempfile.TemporaryDirectory(prefix=f"{uuid}_") as tmp:
            tmpdir = Path(tmp)

            # Generate + compile each scenario
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

            # Upload PDFs and index to gh-pages/<uuid>/
            commit_msg = f"Add scenario PDFs for {uuid}"
            for s in SCENARIOS:
                step += 1; set_status(uuid, stage=f"upload_s{s}", step=step)
                upload_file(f"{uuid}/mengm0056_s{s}_handout.pdf", tmpdir / f"mengm0056_s{s}_handout.pdf", commit_msg)

            step += 1; set_status(uuid, stage="upload_index", step=step)
            upload_file(f"{uuid}/index.html", tmpdir / "index.html", commit_msg)

        # Trigger GitHub Pages build and wait until it is built
        step += 1; set_status(uuid, stage="trigger_pages_build", step=step)
        trigger_pages_build()

        step += 1; set_status(uuid, stage="pages_building", step=step)
        status = wait_for_pages_build(max_seconds=PAGES_BUILD_TIMEOUT_S, poll_every=3)
        if status == "errored":
            set_status(uuid, done=True, error="GitHub Pages build failed", pages_url=None)
            return

        # Optional: wait for CDN propagation so the first GET does not 404
        pages_url = f"{PAGES_BASE}/{uuid}/"
        step += 1; set_status(uuid, stage="pages_propagating", step=step, pages_url=pages_url)
        _ok = wait_for_url_200(pages_url, max_seconds=PAGES_PROPAGATE_TIMEOUT, poll_every=3)

        # Done
        set_status(uuid, stage="done", step=total_steps, done=True, pages_url=pages_url, error=None)

    except subprocess.CalledProcessError as e:
        set_status(uuid, done=True, error=f"Build error: {e}", pages_url=None)
    except Exception as e:
        set_status(uuid, done=True, error=f"Server error: {e}", pages_url=None)

# -------- HTTP endpoints --------
WAITING_ROOM_HTML = """<!doctype html>
<meta charset="utf-8">
<title>Building PDFs…</title>
<style>
  body{font-family:system-ui,Segoe UI,Roboto,Arial;margin:2rem auto;max-width:720px;line-height:1.5}
  .bar{height:14px;background:#eee;border-radius:7px;overflow:hidden;margin:.5rem 0 1rem 0}
  .fill{height:100%;width:0%;}
  .fill.ok{background:#4caf50}
  .fill.err{background:#d32f2f}
  .muted{color:#666;font-size:.9rem}
  code{background:#f6f8fa;padding:.1rem .3rem;border-radius:4px}
</style>
<h1>Generating your scenario PDFs</h1>
<p class="muted">UUID: <code id="u"></code></p>
<div class="bar"><div id="fill" class="fill"></div></div>
<p id="stage" class="muted">Starting…</p>
<p id="msg" class="muted"></p>
<script>
const uuid = new URLSearchParams(location.search).get('uuid');
document.getElementById('u').textContent = uuid;
const fill = document.getElementById('fill');
const stage = document.getElementById('stage');
const msg = document.getElementById('msg');
const friendly = {
  trigger_pages_build: "Triggering GitHub Pages build…",
  pages_building: "GitHub Pages is building your site…",
  pages_propagating: "Publishing complete; waiting for it to go live…"
};

async function tick(){
  try{
    const r = await fetch(`/status?uuid=${encodeURIComponent(uuid)}&t=${Date.now()}`);
    const s = await r.json();
    if(s.error){
      fill.className='fill err'; fill.style.width='100%';
      stage.textContent = 'Error';
      msg.textContent = s.error;
      return;
    }
    const total = s.total || 100;
    const pct = Math.max(0, Math.min(100, Math.round(100*(s.step||0)/total)));
    fill.className = 'fill ok';
    fill.style.width = pct + '%';
    const label = friendly[s.stage] || (s.stage ? `Stage: ${s.stage}` : 'Working…');
    stage.textContent = `${label} (${pct}%)`;
    if(s.done && s.pages_url){
      stage.textContent = 'Done - opening your PDFs…';
      setTimeout(()=>{ window.location.href = s.pages_url; }, 600);
      return;
    }
  }catch(e){ /* ignore; keep polling */ }
  setTimeout(tick, %(poll)s);
}
tick();
</script>
""".replace("%(poll)s", str(int(POLL_INTERVAL_S*1000)))

@app.get("/start")
def start():
    uuid = (request.args.get("uuid") or "").strip()
    if not uuid or not re.fullmatch(r"[0-9a-fA-F-]{16,}", uuid):
        abort(400, "Missing/invalid uuid")

    s = get_status(uuid)
    # If first time or previous error, (re)kick the build
    if not s or (s.get("done") and not s.get("pages_url")):
        total_steps = (len(SCENARIOS) * 3) + 4
        set_status(uuid, stage="queued", step=0, total=total_steps, done=False, error=None)
        threading.Thread(target=build_and_publish, args=(uuid,), daemon=True).start()

    return render_template_string(WAITING_ROOM_HTML)

@app.get("/status")
def status():
    uuid = (request.args.get("uuid") or "").strip()
    if not uuid:
        return jsonify({"error":"Missing uuid"}), 400
    s = get_status(uuid)
    if not s:
        s = {"stage":"queued","step":0,"total":(len(SCENARIOS)*3 + 4),"done":False}
    return jsonify(s)

# Backwards compatibility: /generate just sends to /start so users see progress
@app.get("/generate")
def generate_legacy():
    uuid = (request.args.get("uuid") or "").strip()
    if not uuid:
        abort(400, "Missing uuid")
    return redirect(f"/start?uuid={uuid}", code=302)

@app.get("/")
def health():
    return "OK"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
