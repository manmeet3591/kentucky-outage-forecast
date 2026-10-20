/* Kenya power outage & restoration forecast dashboard */
(() => {
  const SRC = {
    analysis: { label: "Hindcast (ERA5)", short: "Hindcast", c: "--s1" },
    lead1: { label: "Forecast 1 day ahead", short: "1 day ahead", c: "--s2" },
    lead2: { label: "2 days ahead", short: "2 days ahead", c: "--s3" },
    lead3: { label: "3 days ahead", short: "3 days ahead", c: "--s4" },
  };
  const BINS = [0.005, 0.01, 0.02, 0.05, 0.1, 0.2]; // outage share thresholds -> 7 classes
  const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const RAMP = () => ["--b0", "--b1", "--b2", "--b3", "--b4", "--b5", "--b6"].map(css);
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const pct = (v, d = 1) => (v == null ? "–" : (v * 100).toFixed(v < 0.1 && d ? d : 0) + "%");
  const num = v => (v == null ? "–" : Math.round(v).toLocaleString());
  const big = v => (v >= 1e6 ? (v / 1e6).toFixed(2) + "M" : v >= 1e4 ? Math.round(v / 1e3) + "k" : num(v));
  const DOW = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"], MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const tfmt = (iso, long = true) => {
    const d = new Date(iso + ":00Z");
    const day = `${d.getUTCDate()} ${MON[d.getUTCMonth()]}`;
    return long ? `${DOW[d.getUTCDay()]} ${day} ${iso.slice(11, 16)} EAT` : day;
  };

  const state = { src: "analysis", t: 0, sel: null, playing: null };
  let D, map, countyLayer, hospLayer;

  const outAt = (src, name, t) => D.series[src][name].out[t];
  const pop = name => D.pop[name];

  function colorFor(v) {
    const r = RAMP();
    let i = 0;
    while (i < BINS.length && v >= BINS[i]) i++;
    return v < 0.001 ? css("--nodata") : r[i];
  }

  // ---------------- charts ----------------
  function lineChart(el, { times, series, now, yfmt, events = [], onPick, ymax }) {
    const W = el.clientWidth || 600, H = el.clientHeight || 150, m = { l: 44, r: 10, t: 8, b: 20 };
    const iw = W - m.l - m.r, ih = H - m.t - m.b, n = times.length;
    const max = ymax ?? Math.max(1e-9, ...series.flatMap(s => s.values)) * 1.1;
    const x = i => m.l + (i / (n - 1)) * iw, y = v => m.t + ih - (v / max) * ih;
    const ticks = 4, yt = Array.from({ length: ticks + 1 }, (_, k) => (max / ticks) * k);
    const days = times.map((t, i) => [t, i]).filter(([t]) => t.endsWith("T00:00"));
    const every = Math.ceil(days.length / Math.max(2, Math.floor(iw / 70)));
    let svg = `<svg viewBox="0 0 ${W} ${H}" role="img">`;
    yt.forEach(v => svg += `<line class="gl" x1="${m.l}" x2="${W - m.r}" y1="${y(v)}" y2="${y(v)}"/><text x="${m.l - 6}" y="${y(v) + 4}" text-anchor="end">${yfmt(v)}</text>`);
    days.forEach(([t, i], k) => k % every === 0 && (svg += `<text x="${x(i)}" y="${H - 4}" text-anchor="middle">${tfmt(t, false)}</text>`));
    events.forEach(e => { const i = times.findIndex(t => t.startsWith(e.date)); if (i >= 0) svg += `<line class="ev" x1="${x(i)}" x2="${x(i)}" y1="${m.t}" y2="${m.t + ih}"><title>${esc(e.text)}</title></line>`; });
    svg += `<line class="ax" x1="${m.l}" x2="${W - m.r}" y1="${m.t + ih}" y2="${m.t + ih}"/>`;
    series.forEach(s => {
      svg += `<polyline class="ln" style="stroke:${s.color};stroke-width:${s.w || 2}" points="${s.values.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ")}"/>`;
    });
    if (now != null) svg += `<line class="now" x1="${x(now)}" x2="${x(now)}" y1="${m.t}" y2="${m.t + ih}"/>`;
    svg += `<line class="xh" x1="0" x2="0" y1="${m.t}" y2="${m.t + ih}" visibility="hidden"/>`;
    series.forEach((s, k) => svg += `<circle class="hd" data-k="${k}" r="4" fill="${s.color}" stroke="${css("--surface")}" stroke-width="2" visibility="hidden"/>`);
    svg += `<rect x="${m.l}" y="0" width="${iw}" height="${H}" fill="transparent" style="cursor:crosshair"/></svg><div class="tip hidden"></div>`;
    el.innerHTML = svg;
    const s = el.querySelector("svg"), rect = s.querySelector("rect"), xh = s.querySelector(".xh"), tip = el.querySelector(".tip");
    const idx = e => { const r = s.getBoundingClientRect(); return Math.max(0, Math.min(n - 1, Math.round(((e.clientX - r.left) * (W / r.width) - m.l) / iw * (n - 1)))); };
    rect.addEventListener("mousemove", e => {
      const i = idx(e);
      xh.setAttribute("x1", x(i)); xh.setAttribute("x2", x(i)); xh.setAttribute("visibility", "visible");
      s.querySelectorAll(".hd").forEach(c => { const v = series[c.dataset.k].values[i]; c.setAttribute("cx", x(i)); c.setAttribute("cy", y(v)); c.setAttribute("visibility", "visible"); });
      const ev = events.find(ev => times[i].startsWith(ev.date));
      tip.innerHTML = `<b>${tfmt(times[i])}</b>` + series.map(sr => `<div class="row"><i style="background:${sr.color}"></i><span>${esc(sr.name)}</span><span>${yfmt(sr.values[i], true)}</span></div>`).join("") + (ev ? `<div style="color:var(--ink-2);margin-top:3px">${esc(ev.text)}</div>` : "");
      tip.classList.remove("hidden");
      const r = s.getBoundingClientRect(), px = (x(i) / W) * r.width;
      tip.style.left = Math.min(px + 12, r.width - tip.offsetWidth - 4) + "px"; tip.style.top = "4px";
    });
    rect.addEventListener("mouseleave", () => { xh.setAttribute("visibility", "hidden"); s.querySelectorAll(".hd").forEach(c => c.setAttribute("visibility", "hidden")); tip.classList.add("hidden"); });
    if (onPick) rect.addEventListener("click", e => onPick(idx(e)));
  }

  function barChart(el, { times, values, now, color, yfmt }) {
    const W = el.clientWidth || 300, H = el.clientHeight || 100, m = { l: 44, r: 10, t: 6, b: 18 };
    const iw = W - m.l - m.r, ih = H - m.t - m.b, n = values.length, max = Math.max(1, ...values) * 1.1;
    const bw = Math.max(1, iw / n - 0.5);
    const y = v => m.t + ih - (v / max) * ih;
    let svg = `<svg viewBox="0 0 ${W} ${H}">`;
    [0, max / 2, max].forEach(v => svg += `<line class="gl" x1="${m.l}" x2="${W - m.r}" y1="${y(v)}" y2="${y(v)}"/><text x="${m.l - 6}" y="${y(v) + 4}" text-anchor="end">${yfmt(v)}</text>`);
    values.forEach((v, i) => v > 0 && (svg += `<rect x="${m.l + (i / n) * iw}" y="${y(v)}" width="${bw}" height="${m.t + ih - y(v)}" fill="${color}" rx="${bw > 4 ? 2 : 0}"><title>${tfmt(times[i])}: ${yfmt(v, true)}</title></rect>`));
    svg += `<line class="ax" x1="${m.l}" x2="${W - m.r}" y1="${m.t + ih}" y2="${m.t + ih}"/>`;
    if (now != null) svg += `<line class="now" x1="${m.l + (now / (n - 1)) * iw}" x2="${m.l + (now / (n - 1)) * iw}" y1="${m.t}" y2="${m.t + ih}"/>`;
    el.innerHTML = svg + "</svg>";
  }

  // ---------------- map ----------------
  function initMap() {
    map = L.map("map", { preferCanvas: true, zoomSnap: 0.25 });
    const dark = matchMedia("(prefers-color-scheme: dark)").matches;
    const esri = s => `https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/${s}/MapServer/tile/{z}/{y}/{x}`;
    L.tileLayer(esri(dark ? "World_Dark_Gray_Base" : "World_Light_Gray_Base"), { attribution: "Basemap &copy; Esri, HERE, Garmin, &copy; OpenStreetMap contributors", maxZoom: 16 }).addTo(map);
    map.createPane("labels").style.zIndex = 450; map.getPane("labels").style.pointerEvents = "none";
    L.tileLayer(esri(dark ? "World_Dark_Gray_Reference" : "World_Light_Gray_Reference"), { pane: "labels", maxZoom: 16 }).addTo(map);
    countyLayer = L.geoJSON(D.counties, {
      style: styleCounty,
      onEachFeature: (f, l) => {
        l.on({ mouseover: () => { l.setStyle({ weight: 2.5, color: css("--ink") }); l.bringToFront(); }, mouseout: () => countyLayer.resetStyle(l), click: () => select(f.properties.name) });
        l.bindTooltip(() => {
          const n = f.properties.name, v = outAt(state.src, n, state.t);
          return `<b>${esc(n)}</b><span class="m">${pct(v)} without power · ~${num(v * pop(n))} people</span>`;
        }, { className: "tt", sticky: true, direction: "top", offset: [0, -8] });
      },
    }).addTo(map);
    const fit = () => map.fitBounds(countyLayer.getBounds(), { padding: [10, 10] });
    fit();
    // grid layout settles after init: re-measure and re-fit on resize until the user moves the map
    let userMoved = false;
    map.on("dragstart", () => (userMoved = true));
    map.getContainer().addEventListener("wheel", () => (userMoved = true), { passive: true });
    new ResizeObserver(() => { map.invalidateSize(); if (!userMoved && map.getSize().y > 100) fit(); })
      .observe(document.getElementById("map"));
    hospLayer = L.layerGroup().addTo(map);
  }
  function styleCounty(f) {
    const n = f.properties.name, sel = n === state.sel;
    return { fillColor: colorFor(outAt(state.src, n, state.t)), fillOpacity: 0.85, color: sel ? css("--ink") : css("--surface"), weight: sel ? 3 : 1 };
  }
  function drawHospitals() {
    hospLayer.clearLayers();
    for (const h of D.hospitals.features) {
      const v = outAt(state.src, h.properties.county, state.t);
      if (v < 0.05) continue;
      const [lon, lat] = h.geometry.coordinates;
      L.circleMarker([lat, lon], { radius: 4, fillColor: css("--crit"), fillOpacity: 1, color: css("--surface"), weight: 1.5 })
        .bindTooltip(`<b>${esc(h.properties.name || "Hospital")}</b><span class="m">${esc(h.properties.county)} · ${pct(v)} of county without power</span>`, { className: "tt", direction: "top" })
        .addTo(hospLayer);
    }
  }
  function drawLegend() {
    const labels = ["<0.5%", "1%", "2%", "5%", "10%", "20%+"];
    document.getElementById("legend").innerHTML = `<div>Share of people without power</div><div class="ramp">${RAMP().map(c => `<i style="background:${c}"></i>`).join("")}</div>
      <div class="ends"><span>0</span><span>${labels.slice(2, 5).join(" · ")}</span><span>20%+</span></div>
      <div class="h"><svg width="10" height="10"><circle cx="5" cy="5" r="4" fill="${css("--crit")}"/></svg>Hospital in a county with ≥5% out (!)</div>`;
  }

  // ---------------- panels ----------------
  function national(src, t) { return D.event.national[src][t]; }
  function renderKpis() {
    const t = state.t, src = state.src;
    const names = Object.keys(D.pop);
    const now = national(src, t);
    const nCounties = names.filter(n => outAt(src, n, t) >= D.event.flag).length;
    const hosp = names.reduce((s, n) => s + outAt(src, n, t) * D.hosp[n], 0);
    const nat = D.event.national[src], pk = Math.max(...nat), pi = nat.indexOf(pk);
    document.getElementById("kpis").innerHTML = `
      <div class="kpi"><b>${big(now)}</b><span>people without power now</span></div>
      <div class="kpi"><b>${nCounties}</b><span>counties with ≥${D.event.flag * 100}% out</span></div>
      <div class="kpi"><b>${hosp.toFixed(0)}</b><span>hospitals expected to be on backup power</span></div>
      <div class="kpi"><b>${big(pk)}</b><span>event peak · ${tfmt(D.event.times[pi], false)}</span></div>`;
  }
  function renderSide() {
    const el = document.getElementById("county"), src = state.src, t = state.t;
    if (!state.sel) {
      const names = Object.keys(D.pop).map(n => [n, outAt(src, n, t) * pop(n), outAt(src, n, t)]).sort((a, b) => b[1] - a[1]).slice(0, 10);
      el.innerHTML = `<h2>Most people out now</h2><ol class="rank">${names.map(([n, p, v]) => `<li data-n="${esc(n)}">${esc(n)}<span class="s">${big(p)} · ${pct(v)}</span></li>`).join("")}</ol>
        <p class="empty" style="margin-top:12px">Click a county for its outage curve, weather drivers and restoration estimate.</p>`;
      el.querySelectorAll("li").forEach(li => li.addEventListener("click", () => select(li.dataset.n, true)));
      return;
    }
    const n = state.sel, s = D.event.summary[src][n], ser = D.series[src][n];
    el.innerHTML = `<div class="cty"><h3>${esc(n)} <button class="link" id="back" style="font-size:12px;float:right;border:0;background:none;color:var(--accent);cursor:pointer">All counties</button></h3>
      <div class="meta">Population ${num(pop(n))} · ${D.hosp[n]} hospitals · ${D.subs[n]} substations (OSM)</div>
      <div class="facts">
        <div><span>Now (${esc(SRC[src].short)})</span><b>${pct(ser.out[t])} · ${num(ser.out[t] * pop(n))} people</b></div>
        <div><span>Peak</span><b>${pct(s.peak)} · ${tfmt(s.peak_time)}</b></div>
        <div><span>People out at peak</span><b>${num(s.people_peak)}</b></div>
        <div><span>Time to 90% restored after peak</span><b>${s.etr90_h == null ? (s.peak > 0.005 ? "beyond event window" : "–") : s.etr90_h + " h (" + (s.etr90_h / 24).toFixed(1) + " d)"}</b></div>
        <div><span>People-hours without power</span><b>${big(s.people_hours)}</b></div>
      </div>
      <div class="ctitle">Share without power, by weather input</div><div class="chart sm" id="cOut"></div>
      <div class="ctitle">Rain, county mean (mm per 3 h) · ${esc(SRC[src].short)}</div><div class="chart sm" id="cRain"></div>
      <div class="ctitle">Strongest gust in county (km/h) · ${esc(SRC[src].short)}</div><div class="chart sm" id="cGust"></div></div>`;
    document.getElementById("back").addEventListener("click", () => select(null));
    lineChart(document.getElementById("cOut"), {
      times: D.event.times, now: t, yfmt: (v, tip) => (tip ? pct(v) : Math.round(v * 100) + "%"),
      series: Object.keys(SRC).map(k => ({ name: SRC[k].short, color: css(SRC[k].c), values: D.series[k][n].out, w: k === src ? 2.5 : 1.5 })),
      events: D.event.notes, onPick: setTime,
    });
    barChart(document.getElementById("cRain"), { times: D.event.times, values: ser.rain, now: t, color: css("--s1"), yfmt: (v, tip) => (tip ? v.toFixed(1) + " mm" : Math.round(v)) });
    lineChart(document.getElementById("cGust"), {
      times: D.event.times, now: t, yfmt: (v, tip) => Math.round(v) + (tip ? " km/h" : ""),
      series: [{ name: "Max gust", color: css("--s1"), values: ser.gust }], onPick: setTime,
    });
  }
  function renderNational() {
    document.getElementById("natKey").innerHTML = Object.keys(SRC).map(k => `<span><i style="background:${css(SRC[k].c)}"></i>${SRC[k].short}</span>`).join("");
    lineChart(document.getElementById("natChart"), {
      times: D.event.times, now: state.t, yfmt: (v, tip) => (tip ? num(v) : big(v)),
      series: Object.keys(SRC).map(k => ({ name: SRC[k].short, color: css(SRC[k].c), values: D.event.national[k], w: k === state.src ? 2.5 : 1.5 })),
      events: D.event.notes, onPick: setTime,
    });
  }
  function renderNote() {
    const t = D.event.times[state.t];
    const near = D.event.notes.filter(e => Math.abs(new Date(e.date + "T12:00Z") - new Date(t + ":00Z")) <= 36 * 3600e3);
    document.getElementById("note").innerHTML = near.map(e => `<b>${esc(e.date)}</b> · ${esc(e.text)}`).join("<br>");
  }
  function renderSkill() {
    const sk = D.event.skill;
    const rows = [["Counties flagged in hindcast", k => sk[k].n_flagged_analysis], ["Counties flagged by forecast", k => sk[k].n_flagged_forecast],
      ["Hit rate (flagged counties caught)", k => pct(sk[k].hit_rate, 0)], ["False alarm ratio", k => pct(sk[k].false_alarm_ratio, 0)],
      ["Correlation of county peak outage", k => sk[k].corr_peak.toFixed(2)], ["Median peak timing error", k => sk[k].median_peak_timing_error_h == null ? "–" : sk[k].median_peak_timing_error_h + " h"],
      ["National peak vs hindcast", k => pct(sk[k].national_peak_ratio, 0)]];
    const ks = ["lead1", "lead2", "lead3"];
    document.getElementById("skillTbl").innerHTML = `<thead><tr><th>Metric</th>${ks.map(k => `<th>${SRC[k].short}</th>`).join("")}</tr></thead><tbody>${rows.map(([l, f]) => `<tr><td>${l}</td>${ks.map(k => `<td>${f(k)}</td>`).join("")}</tr>`).join("")}</tbody>`;
    document.querySelector(".flag").textContent = D.event.flag * 100;
    const nb = D.series.analysis.Nairobi, nbs = D.event.summary.analysis.Nairobi;
    document.getElementById("gap").innerHTML = `Nairobi had severe flash flooding in late April 2024, but ERA5's wettest 3-hour county-mean rainfall there is only <b>${Math.max(...nb.rain).toFixed(1)} mm</b>. As a result the hindcast peaks at just <b>${pct(nbs.peak)}</b> out. A ~25–30 km model smooths away intense, localised convective storms, and the outage model can only be as good as its rainfall input. This is exactly the gap that our 1 km / 1 hour <b>Aircast SR</b> model is built to close, and it's where KPLC outage logs would expose and correct the bias.`;
  }

  // ---------------- interaction ----------------
  function setTime(i) {
    state.t = i;
    document.getElementById("time").value = i;
    document.getElementById("tlabel").textContent = tfmt(D.event.times[i]);
    countyLayer.setStyle(styleCounty); drawHospitals(); renderKpis(); renderSide(); renderNational(); renderNote();
  }
  function select(name, zoom) {
    state.sel = name; countyLayer.setStyle(styleCounty);
    if (zoom && name) map.fire("dragstart");
    if (zoom && name) countyLayer.eachLayer(l => l.feature.properties.name === name && map.fitBounds(l.getBounds(), { maxZoom: 8, padding: [30, 30] }));
    renderSide();
  }
  function setSource(src) {
    state.src = src;
    document.querySelectorAll("#source button").forEach(b => b.classList.toggle("on", b.dataset.src === src));
    setTime(state.t);
  }

  function initControls() {
    document.getElementById("source").innerHTML = Object.entries(SRC).map(([k, s]) => `<button data-src="${k}" class="${k === state.src ? "on" : ""}"><span class="sw" style="background:${css(s.c)}"></span>${s.label}</button>`).join("");
    document.querySelectorAll("#source button").forEach(b => b.addEventListener("click", () => setSource(b.dataset.src)));
    const tr = document.getElementById("time");
    tr.max = D.event.times.length - 1;
    tr.addEventListener("input", e => setTime(+e.target.value));
    const play = document.getElementById("play");
    play.addEventListener("click", () => {
      if (state.playing) { clearInterval(state.playing); state.playing = null; play.textContent = "▶"; play.setAttribute("aria-label", "Play"); return; }
      if (state.t >= D.event.times.length - 1) setTime(0);
      play.textContent = "❚❚"; play.setAttribute("aria-label", "Pause");
      state.playing = setInterval(() => { if (state.t >= D.event.times.length - 1) return play.click(); setTime(state.t + 1); }, 180);
    });
    document.querySelectorAll(".tabs button").forEach(b => b.addEventListener("click", () => {
      document.querySelectorAll(".tabs button").forEach(x => x.setAttribute("aria-selected", x === b));
      ["map", "skill", "eagle", "method"].forEach(v => document.getElementById(`view-${v}`).classList.toggle("hidden", v !== b.dataset.view));
      document.querySelector(".bar").classList.toggle("hidden", b.dataset.view !== "map");
      if (b.dataset.view === "map") { map.invalidateSize(); renderNational(); renderSide(); }
    }));
    let rt; addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => { renderNational(); renderSide(); }, 150); });
  }

  function renderMethod() {
    const p = D.event.params;
    document.getElementById("params").innerHTML = [
      ["F<sub>gust</sub>", p.gust, "km/h max 10 m gust"], ["F<sub>rain 24h</sub>", p.rain24, "mm in 24 h"], ["F<sub>rain 72h</sub>", p.rain72, "mm in 72 h"],
    ].map(([n, q, u]) => `<li>${n}: median ${q.median} ${u}, log-std β = ${q.beta}</li>`).join("");
    document.querySelector(".taur").textContent = p.TAU_RAIN;
    document.querySelector(".sg").textContent = p.SAFE_GUST;
    document.querySelector(".sr").textContent = p.SAFE_RAIN;
    document.querySelector(".eq").insertAdjacentHTML("afterend", `<p>τ₀ = ${p.TAU0} h; faults need ${p.SUSTAIN_H} h of sustained exposure.</p>`);
  }

  async function load() {
    const get = n => fetch(`data/${n}`).then(r => r.json());
    const [counties, series, hospitals, event] = await Promise.all(["counties.geojson", "series.json", "hospitals.geojson", "event.json"].map(get));
    const popm = {}, hosp = {}, subs = {};
    counties.features.forEach(f => { popm[f.properties.name] = f.properties.pop; hosp[f.properties.name] = f.properties.hospitals; subs[f.properties.name] = f.properties.substations; });
    D = { counties, series, hospitals, event, pop: popm, hosp, subs };
    document.getElementById("evName").textContent = `${event.name} · ${event.start} to ${event.end}`;
    initMap(); initControls(); drawLegend(); renderSkill(); renderMethod();
    const nat = event.national.analysis;
    setTime(nat.indexOf(Math.max(...nat)));
  }
  load();
})();
