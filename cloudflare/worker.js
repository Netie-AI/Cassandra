/**
 * Cloudflare Worker — KV score publish + geo + public GET.
 * Deploy: see docs/CLOUDFLARE_WORKER.md
 */
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const cors = {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, PUT, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type, X-Secret",
    };

    if (request.method === "OPTIONS") {
      return new Response(null, { headers: cors });
    }

    if (url.pathname === "/api/geo") {
      const country = request.cf?.country || "US";
      return Response.json({ country }, { headers: cors });
    }

    if (url.pathname === "/api/latest" && request.method === "GET") {
      const raw = await env.SCORE_KV.get("latest");
      if (!raw) {
        return new Response(JSON.stringify({ error: "No score published yet" }), {
          status: 404,
          headers: { ...cors, "Content-Type": "application/json" },
        });
      }
      return new Response(raw, {
        headers: { ...cors, "Content-Type": "application/json" },
      });
    }

    if (url.pathname === "/api/score" && request.method === "PUT") {
      if (request.headers.get("X-Secret") !== env.KV_SECRET) {
        return new Response("Unauthorized", { status: 401 });
      }
      const body = await request.text();
      await env.SCORE_KV.put("latest", body);
      return Response.json({ ok: true }, { headers: cors });
    }

    return new Response("Not found", { status: 404 });
  },
};
