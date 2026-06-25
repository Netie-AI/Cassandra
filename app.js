async function load() {
  try {
    const r = await fetch("/api/dashboard");
    if (!r.ok) { setEmpty("No data — click Run cycle"); return; }
    const d = await r.json();
    const s = d.score;
    document.getElementById("crs").textContent = s.crs;
    document.getElementById("band").textContent = s.band;
    document.getElementById("conf").textContent = `± ${s.band_halfwidth} · confidence ${(s.confidence * 100).toFixed(0)}%`;
    document.getElementById("asof").textContent = `as of ${s.asof}`;
    document.getElementById("f").textContent = s.fragility?.toFixed(3) ?? "—";
    document.getElementById("t").textContent = s.trigger?.toFixed(3) ?? "—";
    document.getElementById("phase").textContent = s.phase ?? "—";
    document.getElementById("mom").textContent = s.momentum_state ?? "—";

    const fac = s.factors || {};
    document.getElementById("factors").innerHTML = Object.entries(fac).map(([k, v]) =>
      `<div class="p-2 bg-slate-800 rounded" title="${k}"><div class="text-slate-500">${k}</div><div class="text-lg">${Number(v).toFixed(3)}</div></div>`
    ).join("");

    document.getElementById("metrics").innerHTML = (d.metrics || []).map(m =>
      `<tr class="border-t border-slate-800 hover:bg-slate-800" title="${m.note || ''}">
        <td class="p-1">${m.name}</td><td class="p-1">${m.factor}</td>
        <td class="p-1">${m.raw_value != null ? Number(m.raw_value).toFixed(4) : "MISSING"}</td>
        <td class="p-1 text-slate-500 truncate max-w-xs">${m.source}</td></tr>`
    ).join("");
  } catch (e) {
    setEmpty(String(e));
  }
}

function setEmpty(msg) {
  document.getElementById("crs").textContent = "—";
  document.getElementById("band").textContent = msg;
}

document.getElementById("runBtn").onclick = async () => {
  document.getElementById("runBtn").disabled = true;
  document.getElementById("runBtn").textContent = "Running…";
  await fetch("/api/run", { method: "POST" });
  await load();
  document.getElementById("runBtn").disabled = false;
  document.getElementById("runBtn").textContent = "Run cycle";
};

load();
