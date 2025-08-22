export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: cors() });
    }
    if (url.pathname !== "/dispatch" || request.method !== "POST") {
      return new Response(JSON.stringify({ error: "Not found" }), {
        status: 404, headers: json()
      });
    }

    let body;
    try { body = await request.json(); } catch { body = {}; }
    const uuid = String(body.uuid || "").trim();

    if (!/^[0-9a-fA-F-]{16,}$/.test(uuid)) {
      return new Response(JSON.stringify({ error: "Invalid UUID" }), {
        status: 400, headers: json()
      });
    }

    const owner = env.GH_OWNER;
    const repo  = env.GH_REPO;
    const wf    = env.GH_WORKFLOW; // e.g. build-pdfs.yml
    const ref   = env.GH_REF || "main";

    const gh = await fetch(`https://api.github.com/repos/${owner}/${repo}/actions/workflows/${wf}/dispatches`, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${env.GH_TOKEN}`,
        "Accept": "application/vnd.github+json",
        "User-Agent": "uuid-pdf-dispatcher"
      },
      body: JSON.stringify({ ref, inputs: { uuid } })
    });

    if (gh.status !== 204) {
      const detail = await gh.text();
      return new Response(JSON.stringify({ error: "GitHub dispatch failed", detail }), {
        status: 502, headers: json()
      });
    }

    const base = `https://${owner}.github.io/${repo}/${uuid}/`;
    return new Response(JSON.stringify({ ok: true, uuid, url: base }), {
      status: 202, headers: json()
    });
  }
};

function cors() {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
  };
}
function json() {
  return { ...cors(), "Content-Type": "application/json; charset=utf-8" };
}
