/* Kentucky power outage & restoration forecast dashboard */
(() => {
  const SRC = {
    observed: { label: "Observed (EAGLE-I)", short: "Observed", c: "--ink" },
    analysis: { label: "Hindcast (ERA5)", short: "Hindcast", c: "--s1" },
    lead1: { label: "1 day ahead", short: "1 day ahead", c: "--s2" },
    lead2: { label: "2 days ahead", short: "2 days ahead", c: "--s3" },
    lead3: { label: "3 days ahead", short: "3 days ahead", c: "--s4" },
  };
  const BINS = [0.005, 0.01, 0.02, 0.05, 0.1, 0.2];
  const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const RAMP = () => ["--b0", "--b1", "--b2", "--b3", "--b4", "--b5", "--b6"].map(css);
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const pct = (v, d = 1) => (v == null ? "–" : (v * 100).toFixed(v < 0.1 && d ? d : 0) + "%");
  const num = v => (v == null ? "–" : Math.round(v).toLocaleString());
  const big = v => (v == null ? "–" : v >= 1e6 ? (v / 1e6).toFixed(2) + "M" : v >= 1e4 ? Math.round(v / 1e3) + "k" : num(v));
  const DOW = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"], MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const tfmt = (iso, long = true) => {
    const d = new Date(iso + ":00Z");
    const day = `${d.getUTCDate()} ${MON[d.getUTCMonth()]}`;
    return long ? `${DOW[d.getUTCDay()]} ${day} ${iso.slice(11, 16)} ${E.tz}` : day;
  };

  const state = { src: "observed", t: 0, sel: null, playing: null };
  let META, C, HOSP, E, cust = {}, hospN = {}, subsN = {}, map, countyLayer, hospLayer;
  const cache = {};

  const sources = () => ["observed", ...E.sources];
  const outAt = (src, n, t) => E.series[src][n].out[t];
  const drivers = n => E.series[state.src === "observed" ? "analysis" : state.src][n];

  function colorFor(v) {
    const r = RAMP();
    let i = 0;
    while (i < BINS.length && v >= BINS[i]) i++;
    return v < 0.001 ? css("--nodata") : r[i];
  }

  // ---------------- charts ----------------
  function lineChart(el, { times, series, now, yfmt, events = [], onPick }) {
    const W = el.clientWidth || 600, H = el.clientHeight || 150, m = { l: 44, r: 10, t: 8, b: 20 };
    const iw = W - m.l - m.r, ih = H - m.t - m.b, n = times.length;
    const max = Math.max(1e-9, ...series.flatMap(s => s.values)) * 1.1;
    const x = i => m.l + (i / (n - 1)) * iw, y = v => m.t + ih - (v / max) * ih;
    const yt = Array.from({ length: 5 }, (_, k) => (max / 4) * k);
    const days = times.map((t, i) => [t, i]).filter(([t]) => t.slice(11, 13) < "03");
    const every = Math.ceil(days.length / Math.max(2, Math.floor(iw / 60)));
    let svg = `<svg viewBox="0 0 ${W} ${H}" role="img">`;
    yt.forEach(v => svg += `<line class="gl" x1="${m.l}" x2="${W - m.r}" y1="${y(v)}" y2="${y(v)}"/><text x="${m.l - 6}" y="${y(v) + 4}" text-anchor="end">${yfmt(v)}</text>`);
    days.forEach(([t, i], k) => k % every === 0 && (svg += `<text x="${x(i)}" y="${H - 4}" text-anchor="middle">${tfmt(t, false)}</text>`));
    events.forEach(e => { const i = times.findIndex(t => t >= e.time); if (i >= 0) svg += `<line class="ev" x1="${x(i)}" x2="${x(i)}" y1="${m.t}" y2="${m.t + ih}"><title>${esc(e.text)}</title></line>`; });
    svg += `<line class="ax" x1="${m.l}" x2="${W - m.r}" y1="${m.t + ih}" y2="${m.t + ih}"/>`;
    series.forEach(s => svg += `<polyline class="ln" style="stroke:${s.color};stroke-width:${s.w || 2}${s.dash ? ";stroke-dasharray:" + s.dash : ""}" points="${s.values.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ")}"/>`);
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
      tip.innerHTML = `<b>${tfmt(times[i])}</b>` + series.map(sr => `<div class="row"><i style="background:${sr.color}"></i><span>${esc(sr.name)}</span><span>${yfmt(sr.values[i], true)}</span></div>`).join("");
      tip.classList.remove("hidden");
      const r = s.getBoundingClientRect(), px = (x(i) / W) * r.width;
      tip.style.left = Math.max(0, Math.min(px + 12, r.width - tip.offsetWidth - 4)) + "px"; tip.style.top = "4px";
    });
    rect.addEventListener("mouseleave", () => { xh.setAttribute("visibility", "hidden"); s.querySelectorAll(".hd").forEach(c => c.setAttribute("visibility", "hidden")); tip.classList.add("hidden"); });
    if (onPick) rect.addEventListener("click", e => onPick(idx(e)));
  }

  function barChart(el, { times, values, now, color, yfmt }) {
    const W = el.clientWidth || 300, H = el.clientHeight || 100, m = { l: 44, r: 10, t: 6, b: 18 };
    const iw = W - m.l - m.r, ih = H - m.t - m.b, n = values.length, max = Math.max(1, ...values) * 1.1;
    const bw = Math.max(1, iw / n - 0.5), y = v => m.t + ih - (v / max) * ih;
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
    countyLayer = L.geoJSON(C, {
      style: styleCounty,
      onEachFeature: (f, l) => {
        l.on({ mouseover: () => { l.setStyle({ weight: 2.5, color: css("--ink") }); l.bringToFront(); }, mouseout: () => countyLayer.resetStyle(l), click: () => select(f.properties.name) });
        l.bindTooltip(() => {
          const n = f.properties.name, v = outAt(state.src, n, state.t), o = outAt("observed", n, state.t);
          return `<b>${esc(n)} County</b><span class="m">${esc(SRC[state.src].short)}: ${pct(v)} · ${num(v * cust[n])} customers</span>` +
            (state.src !== "observed" ? `<br><span class="m">Observed: ${pct(o)} · ${num(o * cust[n])}</span>` : "");
        }, { className: "tt", sticky: true, direction: "top", offset: [0, -8] });
      },
    }).addTo(map);
    const fit = () => map.fitBounds(countyLayer.getBounds(), { padding: [10, 10] });
    fit();
    let userMoved = false;
    map.on("dragstart", () => (userMoved = true));
    map.getContainer().addEventListener("wheel", () => (userMoved = true), { passive: true });
    new ResizeObserver(() => { map.invalidateSize(); if (!userMoved && map.getSize().y > 100) fit(); }).observe(document.getElementById("map"));
    hospLayer = L.layerGroup().addTo(map);
  }
  function styleCounty(f) {
    const n = f.properties.name, sel = n === state.sel;
    return { fillColor: colorFor(outAt(state.src, n, state.t)), fillOpacity: 0.85, color: sel ? css("--ink") : css("--surface"), weight: sel ? 3 : 0.8 };
  }
  function drawHospitals() {
    hospLayer.clearLayers();
    for (const h of HOSP.features) {
      const v = outAt(state.src, h.properties.county, state.t);
      if (v < 0.05) continue;
      const [lon, lat] = h.geometry.coordinates;
      L.circleMarker([lat, lon], { radius: 4, fillColor: css("--crit"), fillOpacity: 1, color: css("--surface"), weight: 1.5 })
        .bindTooltip(`<b>${esc(h.properties.name || "Hospital")}</b><span class="m">${esc(h.properties.county)} County · ${pct(v)} of customers out</span>`, { className: "tt", direction: "top" })
        .addTo(hospLayer);
    }
  }
  function drawLegend() {
    document.getElementById("legend").innerHTML = `<div>Share of customers without power</div><div class="ramp">${RAMP().map(c => `<i style="background:${c}"></i>`).join("")}</div>
      <div class="ends"><span>0</span><span>2% · 5% · 10%</span><span>20%+</span></div>
      <div class="h"><svg width="10" height="10"><circle cx="5" cy="5" r="4" fill="${css("--crit")}"/></svg>Hospital in a county with ≥5% out (!)</div>`;
  }

  // ---------------- panels ----------------
  function renderKpis() {
    const t = state.t, src = state.src, names = Object.keys(cust);
    const now = E.statewide[src][t], obs = E.statewide.observed[t];
    const nC = names.filter(n => outAt(src, n, t) >= E.flag).length;
    const hosp = names.reduce((s, n) => s + outAt(src, n, t) * hospN[n], 0);
    const pk = Math.max(...E.statewide[src]), pi = E.statewide[src].indexOf(pk);
    document.getElementById("kpis").innerHTML = `
      <div class="kpi"><b>${big(now)}</b><span>customers out now · ${esc(SRC[src].short)}</span></div>
      <div class="kpi"><b>${big(obs)}</b><span>observed by EAGLE-I at this time</span></div>
      <div class="kpi"><b>${nC}</b><span>counties with ≥${E.flag * 100}% out</span></div>
      <div class="kpi"><b>${hosp.toFixed(0)}</b><span>hospitals expected on backup power</span></div>
      <div class="kpi" style="grid-column:1/3"><b>${big(pk)}</b><span>${esc(SRC[src].short)} event peak · ${tfmt(E.times[pi])}</span></div>`;
  }
  function renderSide() {
    const el = document.getElementById("county"), src = state.src, t = state.t;
    if (!state.sel) {
      const rows = Object.keys(cust).map(n => [n, outAt(src, n, t) * cust[n], outAt(src, n, t)]).sort((a, b) => b[1] - a[1]).slice(0, 10);
      el.innerHTML = `<h2>Most customers out now · ${esc(SRC[src].short)}</h2><ol class="rank">${rows.map(([n, c, v]) => `<li data-n="${esc(n)}">${esc(n)}<span class="s">${big(c)} · ${pct(v)}</span></li>`).join("")}</ol>
        <p class="empty" style="margin-top:12px">Click a county to compare predicted and observed outages and see the weather drivers.</p>`;
      el.querySelectorAll("li").forEach(li => li.addEventListener("click", () => select(li.dataset.n, true)));
      return;
    }
    const n = state.sel, dsrc = state.src === "observed" ? "analysis" : state.src, s = E.summary[dsrc][n], ser = drivers(n);
    const obs = E.series.observed[n].out, opk = Math.max(...obs);
    el.innerHTML = `<div class="cty"><h3>${esc(n)} County <button id="back" style="font-size:12px;float:right;border:0;background:none;color:var(--accent);cursor:pointer">All counties</button></h3>
      <div class="meta">${num(cust[n])} customers · ${hospN[n]} hospitals · ${subsN[n]} substations (OSM)</div>
      <div class="facts">
        <div><span>Observed peak (EAGLE-I)</span><b>${pct(opk)} · ${num(opk * cust[n])}</b></div>
        <div><span>${esc(SRC[dsrc].short)} peak</span><b>${pct(s.peak)} · ${num(s.customers_peak)}</b></div>
        <div><span>${esc(SRC[dsrc].short)} time to 90% restored</span><b>${s.etr90_h == null ? (s.peak > 0.005 ? "beyond window" : "–") : s.etr90_h + " h"}</b></div>
      </div>
      <div class="ctitle">Share of customers out: observed vs predicted</div><div class="chart sm" id="cOut"></div>
      <div class="ctitle">Strongest gust in county (km/h) · ${esc(SRC[dsrc].short)}</div><div class="chart sm" id="cGust"></div>
      <div class="ctitle">Rain, county mean (mm per 3 h) · ${esc(SRC[dsrc].short)}</div><div class="chart sm" id="cRain"></div></div>`;
    document.getElementById("back").addEventListener("click", () => select(null));
    lineChart(document.getElementById("cOut"), {
      times: E.times, now: t, yfmt: (v, tip) => (tip ? pct(v) : Math.round(v * 100) + "%"), events: E.notes, onPick: setTime,
      series: sources().map(k => ({ name: SRC[k].short, color: css(SRC[k].c), values: E.series[k][n].out, w: k === "observed" ? 2.5 : k === src ? 2.5 : 1.5 })),
    });
    lineChart(document.getElementById("cGust"), { times: E.times, now: t, yfmt: (v, tip) => Math.round(v) + (tip ? " km/h" : ""), series: [{ name: "Max gust", color: css("--s1"), values: ser.gust }], onPick: setTime });
    barChart(document.getElementById("cRain"), { times: E.times, values: ser.rain, now: t, color: css("--s1"), yfmt: (v, tip) => (tip ? v.toFixed(1) + " mm" : Math.round(v)) });
  }
  function renderNational() {
    document.getElementById("natKey").innerHTML = sources().map(k => `<span><i style="background:${css(SRC[k].c)}"></i>${SRC[k].short}</span>`).join("");
    lineChart(document.getElementById("natChart"), {
      times: E.times, now: state.t, yfmt: (v, tip) => (tip ? num(v) : big(v)), events: E.notes, onPick: setTime,
      series: sources().map(k => ({ name: SRC[k].short, color: css(SRC[k].c), values: E.statewide[k], w: k === "observed" || k === state.src ? 2.5 : 1.5 })),
    });
  }
  function renderNote() {
    const t = new Date(E.times[state.t] + ":00Z");
    const near = (E.notes || []).filter(e => Math.abs(new Date(e.time + ":00Z") - t) <= 18 * 3600e3);
    document.getElementById("note").innerHTML = near.map(e => esc(e.text)).join("<br>");
  }

  async function renderSkill() {
    const tests = META.events.filter(e => e.role !== "calibration");
    const evs = await Promise.all(tests.map(e => loadEvent(e.id)));
    const hs = e => e.skill;
    const sumRow = e => `<tr><td>${esc(e.name)}</td><td>${big(hs(e).obs_peak_customers)}</td><td>${big(hs(e).peak_customers)}</td><td>${pct(hs(e).peak_ratio, 0)}</td>
      <td>${(hs(e).peak_timing_error_h > 0 ? "+" : "") + hs(e).peak_timing_error_h} h</td><td>${hs(e).corr_statewide_curve.toFixed(2)}</td><td>${hs(e).hit_rate == null ? "–" : pct(hs(e).hit_rate, 0) + ` of ${hs(e).n_flagged_obs}`}</td></tr>`;
    const group = (label, list) => `<tr class="grp"><td colspan="7">${label}</td></tr>` + list.map(sumRow).join("");
    const cal = META.events.filter(e => e.role === "calibration");
    const ratios = cal.map(e => hs(e).peak_ratio).filter(r => r > 0).sort((a, b) => a - b);
    const median = ratios[Math.floor(ratios.length / 2)];
    const summary = `<h3>All events, ERA5 hindcast <span class="badge">${cal.length} calibration + ${tests.length} test</span></h3>
      <div class="tablewrap"><table><thead><tr><th>Event</th><th>Observed peak</th><th>Model peak</th><th>Peak vs observed</th><th>Peak timing</th><th>Curve corr.</th><th>Hard-hit counties caught</th></tr></thead><tbody>
      ${group("Independent tests (not used in fitting)", tests)}${group("Calibration events", cal)}</tbody></table></div>`;
    const rows = [
      ["Statewide peak (customers)", s => big(s.peak_customers), s => big(s.obs_peak_customers)],
      ["Peak vs observed", s => pct(s.peak_ratio, 0)],
      ["Peak timing error", s => (s.peak_timing_error_h > 0 ? "+" : "") + s.peak_timing_error_h + " h"],
      ["Statewide curve correlation", s => s.corr_statewide_curve.toFixed(2)],
      ["Customer-hours vs observed", s => pct(s.customer_hours_ratio, 0)],
      ["Hard-hit counties caught (≥5% out)", s => pct(s.hit_rate, 0) + ` of ${s.n_flagged_obs}`],
      ["False alarm ratio", s => (s.false_alarm_ratio == null ? "–" : pct(s.false_alarm_ratio, 0))],
      ["County peak correlation", s => s.corr_county_peak.toFixed(2)],
      ["Time to 90% restored", s => (s.etr90_h == null ? "beyond window" : s.etr90_h + " h"), s => (s.obs_etr90_h == null ? "–" : s.obs_etr90_h + " h")],
    ];
    document.getElementById("skillTables").innerHTML = summary + evs.map(ev => {
      const ks = ev.sources;
      return `<h3>${esc(ev.name)} <span class="badge">independent test</span></h3>
        <div class="tablewrap"><table><thead><tr><th>Metric</th><th>Observed</th>${ks.map(k => `<th>${SRC[k].short}</th>`).join("")}</tr></thead><tbody>
        ${rows.map(([l, f, fo]) => `<tr><td>${l}</td><td>${fo ? fo(ev.skill[ks[0]]) : "–"}</td>${ks.map(k => `<td>${f(ev.skill[k])}</td>`).join("")}</tr>`).join("")}
        </tbody></table></div>`;
    }).join("");
    const may = evs.find(e => e.id.includes("2024-05")), sep = evs.find(e => e.id.includes("helene")), ss = (e, k) => e.skill[k];
    document.getElementById("findings").innerHTML = `
      <li><b>Large-scale windstorms are predictable days ahead.</b> For Helene's remnants, the statewide peak ${ss(sep, "lead3").peak_timing_error_h === 0 ? "landed in the same 3-hour step as the observed peak" : `arrived within ${Math.abs(ss(sep, "lead3").peak_timing_error_h)} h of the observed peak`} in a forecast issued <b>3 days earlier</b>, and ${pct(ss(sep, "lead2").hit_rate, 0)} of hard-hit counties were flagged 2 days ahead.</li>
      <li><b>Fitting on ${cal.length} events instead of one.</b> Helene's hindcast peak is now ${pct(ss(sep, "analysis").peak_ratio, 0)} of observed (209% when calibrated on March 2023 alone), and customer-hours ${pct(ss(sep, "analysis").customer_hours_ratio, 0)} (456% before). But the fitted τ₀ is only ${META.params.TAU0} h, so restoration is now too fast: 90% restored in ${ss(sep, "analysis").etr90_h} h vs ${ss(sep, "analysis").obs_etr90_h} h observed. Across calibration events the peak ratio ranges from ${pct(ratios[0], 0)} to ${pct(ratios[ratios.length - 1], 0)} (median ${pct(median, 0)}): on 25 km weather, one set of gust fragility curves can't separate a 40k-customer windstorm from a 500k one.</li>
      <li><b>Thunderstorms are the gap.</b> The May 2024 storms put ${big(ss(may, "analysis").obs_peak_customers)} customers out, but ERA5 and GFS at ~25 km don't resolve convective gusts. The hindcast reached ${pct(ss(may, "analysis").peak_ratio, 0)} of the observed peak (4% with the single-event fit). This is why we're building <b>Aircast SR at 1 km</b> (and should test HRRR at 3 km).</li>`;
  }

  // ---------------- interaction ----------------
  function setTime(i) {
    state.t = i;
    document.getElementById("time").value = i;
    document.getElementById("tlabel").textContent = tfmt(E.times[i]);
    countyLayer.setStyle(styleCounty); drawHospitals(); renderKpis(); renderSide(); renderNational(); renderNote();
  }
  function select(name, zoom) {
    state.sel = name; countyLayer.setStyle(styleCounty);
    if (zoom && name) { map.fire("dragstart"); countyLayer.eachLayer(l => l.feature.properties.name === name && map.fitBounds(l.getBounds(), { maxZoom: 9, padding: [40, 40] })); }
    renderSide();
  }
  function setSource(src) {
    state.src = src;
    document.querySelectorAll("#source button").forEach(b => b.classList.toggle("on", b.dataset.src === src));
    setTime(state.t);
  }
  function renderSources() {
    if (!sources().includes(state.src)) state.src = "observed";
    document.getElementById("source").innerHTML = sources().map(k => `<button data-src="${k}" class="${k === state.src ? "on" : ""}"><span class="sw" style="background:${css(SRC[k].c)}"></span>${SRC[k].label}</button>`).join("");
    document.querySelectorAll("#source button").forEach(b => b.addEventListener("click", () => setSource(b.dataset.src)));
  }

  async function loadEvent(id) {
    if (!cache[id]) cache[id] = fetch(`data/${id}.json`).then(r => r.json());
    return cache[id];
  }
  async function setEvent(id) {
    E = await loadEvent(id);
    document.getElementById("evName").textContent = `${E.name} (${E.role === "calibration" ? "calibration" : "independent test"})`;
    renderSources();
    const tr = document.getElementById("time"); tr.max = E.times.length - 1;
    const obs = E.statewide.observed;
    setTime(obs.indexOf(Math.max(...obs)));
  }

  function initControls() {
    const sel = document.getElementById("event");
    sel.innerHTML = [...META.events].sort((a, b) => a.start.localeCompare(b.start)).map(e => `<option value="${e.id}">${esc(e.name)}${e.role === "calibration" ? " (calibration)" : ""}</option>`).join("");
    sel.value = META.events.find(e => e.id.includes("helene"))?.id || META.events[0].id;
    sel.addEventListener("change", () => setEvent(sel.value));
    document.getElementById("time").addEventListener("input", e => setTime(+e.target.value));
    const play = document.getElementById("play");
    play.addEventListener("click", () => {
      if (state.playing) { clearInterval(state.playing); state.playing = null; play.textContent = "▶"; play.setAttribute("aria-label", "Play"); return; }
      if (state.t >= E.times.length - 1) setTime(0);
      play.textContent = "❚❚"; play.setAttribute("aria-label", "Pause");
      state.playing = setInterval(() => { if (state.t >= E.times.length - 1) return play.click(); setTime(state.t + 1); }, 220);
    });
    document.querySelectorAll(".tabs button").forEach(b => b.addEventListener("click", () => {
      document.querySelectorAll(".tabs button").forEach(x => x.setAttribute("aria-selected", x === b));
      ["map", "skill", "eagle", "method"].forEach(v => document.getElementById(`view-${v}`).classList.toggle("hidden", v !== b.dataset.view));
      document.querySelector(".bar").classList.toggle("hidden", b.dataset.view !== "map");
      if (b.dataset.view === "map") { map.invalidateSize(); renderNational(); renderSide(); }
    }));
    let rt; addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => { renderNational(); renderSide(); }, 150); });
    return sel.value;
  }

  function renderMethod() {
    const p = META.params, c = META.calibration;
    document.getElementById("params").innerHTML = [["F<sub>gust</sub>", p.gust, "km/h max 10 m gust", true], ["F<sub>rain 24h</sub>", p.rain24, "mm in 24 h"], ["F<sub>rain 72h</sub>", p.rain72, "mm in 72 h"]]
      .map(([n, q, u, cal]) => `<li>${n}: median ${q.median} ${u}, log-std β = ${q.beta}${cal ? " <b>(calibrated)</b>" : " (prior)"}</li>`).join("") + `<li>τ₀ = ${p.TAU0} h, stand-down gust ${p.SAFE_GUST} km/h, flood slow-down ${p.TAU_RAIN} mm <b>(calibrated)</b></li>`;
    document.querySelector(".sus").textContent = p.SUSTAIN_H;
    document.querySelector(".taur").textContent = p.TAU_RAIN;
    document.querySelector(".sg").textContent = p.SAFE_GUST;
    document.querySelector(".sr").textContent = p.SAFE_RAIN;
    document.getElementById("calib").innerHTML = `Gust fragility, τ₀, the crew stand-down gust and the flood slow-down were fitted jointly by grid search on <b>${c.calibrated_on.length} EAGLE-I wind and rain events from 2018–2025</b>. Each event counts equally: the loss is the squared log error of the statewide peak plus that of total customer-hours, so 2× over and 2× under cost the same (mean ${c.mean_loss.toFixed(2)}). The two 2024 test events weren't used in fitting.`;
  }

  async function load() {
    const get = n => fetch(`data/${n}`).then(r => r.json());
    [META, C, HOSP] = await Promise.all(["meta.json", "counties.geojson", "hospitals.geojson"].map(get));
    C.features.forEach(f => { const p = f.properties; cust[p.name] = p.customers; hospN[p.name] = p.hospitals; subsN[p.name] = p.substations; });
    const first = initControls();
    E = await loadEvent(first);
    initMap(); drawLegend(); renderMethod();
    await setEvent(first);
    renderSkill();
  }
  load();
})();
