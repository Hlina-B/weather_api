// Weather UI for the Flask weather API.
// Served by Flask (same origin) -> API_BASE is "".
// Opened straight from disk (file://) -> calls the dev server, which then needs CORS.
const API_BASE = location.protocol === "file:" ? "http://127.0.0.1:5000" : "";

const UNITS = {
  us:     { temp: "°F", speed: "mph",  dist: "mi", precip: "in" },
  metric: { temp: "°C", speed: "km/h", dist: "km", precip: "mm" },
  uk:     { temp: "°C", speed: "mph",  dist: "mi", precip: "mm" },
  base:   { temp: "K",  speed: "m/s",  dist: "km", precip: "mm" },
};

const STORAGE_KEY = "forecast:last-query";

const $ = (id) => document.getElementById(id);
const els = {
  form: $("search"), zip: $("zip"), submit: $("submit"), status: $("status"), main: $("main"),
  empty: $("empty"), alerts: $("alerts"), now: $("now"), days: $("days"),
  place: $("place"), localtime: $("localtime"), nowIcon: $("now-icon"), nowTemp: $("now-temp"),
  nowCond: $("now-cond"), nowFeels: $("now-feels"), details: $("details"),
  curveTitle: $("curve-title"), curveChart: $("curve-chart"),
  daysTitle: $("days-title"), dayList: $("day-list"), clear: $("clear"),
};

// What is on screen now; the day list re-draws the curve from it.
let state = null;

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------
async function requestJson(method, path, params) {
  const url = `${API_BASE}${path}?${new URLSearchParams(params)}`;
  let response;
  try {
    response = await fetch(url, { method, headers: { Accept: "application/json" } });
  } catch {
    throw new Error(`Can't reach the weather API at ${API_BASE || location.origin}. Check that the Flask server is running.`);
  }

  let body = null;
  try { body = await response.json(); } catch { /* non-JSON error page */ }

  if (response.status === 429) throw new Error("Too many requests. Wait a minute and try again.");
  if (!response.ok) {
    const detail = body && body.error ? body.error : `The server returned ${response.status}.`;
    throw new Error(detail);
  }
  return body;
}

// ---------------------------------------------------------------------------
// Formatting helpers (all times are shown in the location's own time zone)
// ---------------------------------------------------------------------------
const round = (n) => (n == null ? "–" : Math.round(n));

function fmtTime(epoch, timeZone, opts) {
  return new Intl.DateTimeFormat(undefined, { timeZone, ...opts }).format(epoch * 1000);
}

function dateKey(epoch, timeZone) {
  // en-CA formats as YYYY-MM-DD, the same keys the API uses
  return new Intl.DateTimeFormat("en-CA", { timeZone, year: "numeric", month: "2-digit", day: "2-digit" })
    .format(epoch * 1000);
}

function fmtDay(key, opts) {
  const [y, m, d] = key.split("-").map(Number);
  return new Intl.DateTimeFormat(undefined, { timeZone: "UTC", ...opts }).format(Date.UTC(y, m - 1, d));
}

function compass(deg) {
  const names = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"];
  return names[Math.round(((deg % 360) + 360) % 360 / 22.5) % 16];
}

function hoursSorted(dayHours) {
  return Object.values(dayHours || {}).sort((a, b) => a.date_time.date_time_epoch - b.date_time.date_time_epoch);
}

// ---------------------------------------------------------------------------
// Icons: small SVGs composed from parts, keyed by Visual Crossing icon names
// ---------------------------------------------------------------------------
const PART = {
  sun: `<g class="sun" stroke="currentColor"><circle cx="24" cy="24" r="8"/>${
    [0, 45, 90, 135, 180, 225, 270, 315].map((a) => {
      const r = (a * Math.PI) / 180;
      return `<line x1="${24 + 12 * Math.cos(r)}" y1="${24 + 12 * Math.sin(r)}" x2="${24 + 17 * Math.cos(r)}" y2="${24 + 17 * Math.sin(r)}"/>`;
    }).join("")}</g>`,
  sunSmall: `<g class="sun" stroke="currentColor"><circle cx="17" cy="16" r="6"/>${
    [180, 225, 270, 315, 0].map((a) => {
      const r = (a * Math.PI) / 180;
      return `<line x1="${17 + 9 * Math.cos(r)}" y1="${16 + 9 * Math.sin(r)}" x2="${17 + 12.5 * Math.cos(r)}" y2="${16 + 12.5 * Math.sin(r)}"/>`;
    }).join("")}</g>`,
  moon: `<path d="M29 9a15 15 0 1 0 10 26A12 12 0 0 1 29 9z"/>`,
  moonSmall: `<path d="M19 7a9 9 0 1 0 7 15 7 7 0 0 1-7-15z"/>`,
  cloud: `<path d="M14 36h21a8 8 0 0 0 1-16 11 11 0 0 0-21-1 8.5 8.5 0 0 0-1 17z"/>`,
  cloudHigh: `<path d="M14 30h21a8 8 0 0 0 1-16 11 11 0 0 0-21-1 8.5 8.5 0 0 0-1 17z"/>`,
  rain: `<path d="M18 35l-2.5 6M26 35l-2.5 6M34 35l-2.5 6"/>`,
  snow: `<g fill="currentColor" stroke="none"><circle cx="17" cy="38" r="1.8"/><circle cx="25" cy="41" r="1.8"/><circle cx="33" cy="38" r="1.8"/></g>`,
  bolt: `<path d="M25 32l-4 7h5l-3 6"/>`,
  fog: `<path d="M8 18h32M12 25h28M8 32h32M14 39h22"/>`,
  wind: `<path d="M6 20h22a5 5 0 1 0-5-5M6 28h30a5 5 0 1 1-5 5M6 36h14"/>`,
};

const ICONS = {
  "clear-day": ["sun"],
  "clear-night": ["moon"],
  "partly-cloudy-day": ["sunSmall", "cloud"],
  "partly-cloudy-night": ["moonSmall", "cloud"],
  cloudy: ["cloud"],
  rain: ["cloudHigh", "rain"],
  "showers-day": ["sunSmall", "cloudHigh", "rain"],
  "showers-night": ["moonSmall", "cloudHigh", "rain"],
  snow: ["cloudHigh", "snow"],
  "snow-showers-day": ["sunSmall", "cloudHigh", "snow"],
  "snow-showers-night": ["moonSmall", "cloudHigh", "snow"],
  "thunder-rain": ["cloudHigh", "bolt"],
  "thunder-showers-day": ["sunSmall", "cloudHigh", "bolt"],
  "thunder-showers-night": ["moonSmall", "cloudHigh", "bolt"],
  fog: ["fog"],
  wind: ["wind"],
};

function iconSvg(name) {
  const parts = ICONS[name] || ["cloud"];
  return `<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="2.4"
    stroke-linecap="round" stroke-linejoin="round">${parts.map((p) => PART[p]).join("")}</svg>`;
}

// ---------------------------------------------------------------------------
// Sky colour: time of day at the location, greyed by cloud cover
// ---------------------------------------------------------------------------
const SKIES = {
  night: { top: "#0f1e3d", bottom: "#2c4373", ink: "light" },
  dawn:  { top: "#3d5385", bottom: "#f0a77f", ink: "light" },
  day:   { top: "#4a90d9", bottom: "#bfe0f5", ink: "dark" },
  dusk:  { top: "#2e2b5c", bottom: "#d9806a", ink: "light" },
};

function mix(hexA, hexB, t) {
  const a = hexA.match(/\w\w/g).map((h) => parseInt(h, 16));
  const b = hexB.match(/\w\w/g).map((h) => parseInt(h, 16));
  return "#" + a.map((v, i) => Math.round(v + (b[i] - v) * t).toString(16).padStart(2, "0")).join("");
}

function skyFor(nowEpoch, today, cloudCover, icon) {
  const rise = today?.astronomy?.sunrise_epoch;
  const set = today?.astronomy?.sunset_epoch;
  const edge = 45 * 60; // 45 minutes either side of sunrise/sunset
  let phase = "day";
  if (rise && set) {
    if (Math.abs(nowEpoch - rise) <= edge) phase = "dawn";
    else if (Math.abs(nowEpoch - set) <= edge) phase = "dusk";
    else if (nowEpoch < rise || nowEpoch > set) phase = "night";
  }
  const sky = SKIES[phase];
  const wet = /rain|showers|snow|thunder|fog/.test(icon || "");
  const grey = phase === "day" ? "#8e9aa7" : "#3b4352";
  const t = Math.min(0.75, ((cloudCover ?? 0) / 100) * 0.6 + (wet ? 0.2 : 0));
  return { top: mix(sky.top, grey, t), bottom: mix(sky.bottom, grey, t), ink: sky.ink };
}

function applySky(sky) {
  const s = els.now.style;
  s.setProperty("--sky-top", sky.top);
  s.setProperty("--sky-bottom", sky.bottom);
  if (sky.ink === "light") {
    s.setProperty("--sky-ink", "#f4f8fc");
    s.setProperty("--sky-muted", "rgba(244, 248, 252, 0.75)");
    s.setProperty("--sky-line", "rgba(244, 248, 252, 0.9)");
  } else {
    s.setProperty("--sky-ink", "#0e2236");
    s.setProperty("--sky-muted", "rgba(14, 34, 54, 0.72)");
    s.setProperty("--sky-line", "rgba(14, 34, 54, 0.85)");
  }
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------
function renderAlerts(alerts) {
  els.alerts.replaceChildren();
  if (!alerts || alerts.length === 0) { els.alerts.hidden = true; return; }
  for (const a of alerts) {
    const box = document.createElement("div");
    box.className = "alert";
    box.setAttribute("role", "alert");
    const title = document.createElement("strong");
    title.textContent = a.event || a.headline || "Weather alert";
    const text = document.createElement("p");
    text.textContent = a.headline && a.event ? a.headline : (a.description || "");
    box.append(title, text);
    els.alerts.append(box);
  }
  els.alerts.hidden = false;
}

function detail(label, value) {
  const wrap = document.createElement("div");
  const dt = document.createElement("dt");
  dt.textContent = label;
  const dd = document.createElement("dd");
  if (value instanceof Node) dd.append(value); else dd.textContent = value;
  wrap.append(dt, dd);
  return wrap;
}

function windValue(w, u) {
  const frag = document.createDocumentFragment();
  if (w.wind_direction != null) {
    // Meteorological direction is where the wind comes FROM; the arrow points where it goes.
    // The arrow is drawn pointing down (south), so rotating by the "from" angle aims it downwind.
    const arrow = document.createElement("span");
    arrow.className = "wind-arrow";
    arrow.setAttribute("aria-hidden", "true");
    arrow.innerHTML = `<svg viewBox="0 0 16 16" style="transform: rotate(${w.wind_direction}deg)">
      <path d="M8 2v12M8 14l-4-4M8 14l4-4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
    frag.append(arrow);
  }
  const dir = w.wind_direction != null ? ` ${compass(w.wind_direction)}` : "";
  frag.append(`${round(w.wind_speed)} ${u.speed}${dir}`);
  return frag;
}

function renderNow(data, units) {
  const u = UNITS[units];
  const cur = data.current_snapshot;
  const loc = data.location_info;
  const tz = loc.time_zone;
  const nowEpoch = cur.date_time.date_time_epoch;
  const today = data.daily_forecast[dateKey(nowEpoch, tz)];

  els.place.textContent = loc.resolved_address;
  els.localtime.textContent = `Local time ${fmtTime(Math.floor(Date.now() / 1000), tz, { weekday: "long", hour: "numeric", minute: "2-digit" })}`;
  els.nowIcon.innerHTML = iconSvg(cur.conditions.weather_icon);
  els.nowTemp.textContent = `${round(cur.temperature.temp)}${u.temp}`;
  els.nowCond.textContent = cur.conditions.condits || "";
  const parts = [];
  if (cur.temperature.feels_like != null) parts.push(`Feels like ${round(cur.temperature.feels_like)}${u.temp}`);
  if (today) parts.push(`High ${round(today.temperature.max_temp)}${u.temp}, low ${round(today.temperature.min_temp)}${u.temp}`);
  els.nowFeels.textContent = parts.join(". ");

  const w = cur.wind_and_pressure;
  const h = cur.humidity_and_clouds;
  const p = cur.precipitation;
  const items = [
    detail("Chance of rain", `${round(p.precip_chance ?? 0)}%`),
    detail("Wind", windValue(w, u)),
    detail("Gusts", w.wind_gust != null ? `${round(w.wind_gust)} ${u.speed}` : "–"),
    detail("Humidity", `${round(h.relative_humidity)}%`),
    detail("Dew point", `${round(cur.temperature.dew_point)}${u.temp}`),
    detail("Cloud cover", `${round(h.cloud_cover)}%`),
    detail("Visibility", h.visibility != null ? `${h.visibility} ${u.dist}` : "–"),
    detail("Pressure", `${round(w.sea_level_pressure)} mb`),
    detail("UV index", `${round(cur.solar.uv_index)}`),
  ];
  if (today?.astronomy?.sunrise_epoch) {
    items.push(detail("Sunrise", fmtTime(today.astronomy.sunrise_epoch, tz, { hour: "numeric", minute: "2-digit" })));
    items.push(detail("Sunset", fmtTime(today.astronomy.sunset_epoch, tz, { hour: "numeric", minute: "2-digit" })));
  }
  els.details.replaceChildren(...items);

  applySky(skyFor(nowEpoch, today, h.cloud_cover, cur.conditions.weather_icon));
}

function renderCurve(hours, title, nowEpoch) {
  const u = UNITS[state.units];
  const tz = state.data.location_info.time_zone;
  els.curveTitle.textContent = title;
  if (hours.length < 2) { els.curveChart.replaceChildren(); return; }

  // Draw at the chart's real pixel width so labels stay readable on phones
  const W = Math.max(300, Math.round(els.curveChart.clientWidth || 960));
  const H = 190, padX = 20, top = 30, bottom = 120, rainTop = 136, rainH = 22;
  const temps = hours.map((x) => x.temperature.temp);
  const lo = Math.min(...temps), hi = Math.max(...temps);
  const span = hi - lo || 1;
  const x = (i) => padX + (i * (W - 2 * padX)) / (hours.length - 1);
  const y = (t) => bottom - ((t - lo) / span) * (bottom - top);

  const pts = hours.map((hr, i) => [x(i), y(hr.temperature.temp)]);
  const line = pts.map(([px, py], i) => `${i ? "L" : "M"}${px.toFixed(1)} ${py.toFixed(1)}`).join(" ");
  const area = `${line} L${x(hours.length - 1)} ${bottom + 6} L${x(0)} ${bottom + 6} Z`;

  // Label every Nth hour so labels stay at least ~48px apart
  const gap = (W - 2 * padX) / (hours.length - 1);
  const step = Math.max(1, Math.ceil(48 / gap));
  const barW = Math.max(3, Math.min(gap - 4, 30));
  let marks = "";
  hours.forEach((hr, i) => {
    const chance = hr.precipitation.precip_chance ?? 0;
    if (chance > 0) {
      const bh = (chance / 100) * rainH;
      marks += `<rect class="curve-rain" x="${x(i) - barW / 2}" y="${rainTop + rainH - bh}" width="${barW}" height="${bh}" rx="2"/>`;
    }
    if (i % step === 0) {
      marks += `<text class="curve-temp" x="${x(i)}" y="${pts[i][1] - 10}">${round(hr.temperature.temp)}°</text>`;
      marks += `<text class="curve-hour" x="${x(i)}" y="${H - 4}">${fmtTime(hr.date_time.date_time_epoch, tz, { hour: "numeric" })}</text>`;
    }
    if (hr.date_time.date_time_epoch === nowEpoch) {
      marks += `<circle class="curve-now" cx="${pts[i][0]}" cy="${pts[i][1]}" r="5"/>`;
    }
  });

  els.curveChart.innerHTML = `
    <svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img"
      aria-label="${title}: from ${round(lo)}${u.temp} to ${round(hi)}${u.temp}. Bars show the chance of rain.">
      <path class="curve-area" d="${area}"/>
      <path class="curve-line" d="${line}"/>
      ${marks}
    </svg>`;
}

function next24Hours(data, nowEpoch) {
  const all = Object.values(data.hourly_forecast).flatMap((day) => Object.values(day));
  return all
    .filter((hr) => hr.date_time.date_time_epoch >= nowEpoch)
    .sort((a, b) => a.date_time.date_time_epoch - b.date_time.date_time_epoch)
    .slice(0, 24);
}

function showDay(key) {
  const { data } = state;
  const nowEpoch = data.current_snapshot.date_time.date_time_epoch;
  state.selected = key;
  for (const btn of els.dayList.querySelectorAll(".day")) {
    btn.setAttribute("aria-pressed", String(btn.dataset.key === key));
  }
  if (key === null) {
    renderCurve(next24Hours(data, nowEpoch), "Next 24 hours", nowEpoch);
  } else {
    const label = fmtDay(key, { weekday: "long", month: "long", day: "numeric" });
    renderCurve(hoursSorted(data.hourly_forecast[key]), `Hour by hour, ${label}`, nowEpoch);
  }
}

function renderDays(data, units) {
  const u = UNITS[units];
  const tz = data.location_info.time_zone;
  const todayKey = dateKey(data.current_snapshot.date_time.date_time_epoch, tz);
  const keys = Object.keys(data.daily_forecast).sort().filter((k) => k >= todayKey);
  const days = keys.map((k) => data.daily_forecast[k]);

  const allLo = Math.min(...days.map((d) => d.temperature.min_temp));
  const allHi = Math.max(...days.map((d) => d.temperature.max_temp));
  const span = allHi - allLo || 1;

  els.daysTitle.textContent = `Next ${days.length} days`;
  els.dayList.replaceChildren(...keys.map((key, i) => {
    const d = days[i];
    const t = d.temperature;
    const left = ((t.min_temp - allLo) / span) * 100;
    const width = Math.max(3, ((t.max_temp - t.min_temp) / span) * 100);
    const name = key === todayKey ? "Today" : fmtDay(key, { weekday: "long" });

    const li = document.createElement("li");
    li.innerHTML = `
      <button type="button" class="day" data-key="${key}" aria-pressed="false">
        <span class="day-name">${name}<span class="day-date">${fmtDay(key, { month: "short", day: "numeric" })}</span></span>
        <span class="icon icon-sm" aria-hidden="true">${iconSvg(d.conditions.weather_icon)}</span>
        <span class="day-cond"></span>
        <span class="day-rain">${round(d.precipitation.precip_chance ?? 0)}% rain</span>
        <span class="range">
          <span class="lo">${round(t.min_temp)}°</span>
          <span class="range-track"><span class="range-fill" style="left:${left}%;width:${width}%"></span></span>
          <span class="hi">${round(t.max_temp)}°</span>
        </span>
      </button>`;
    // Text from the API goes in via textContent, never as HTML
    li.querySelector(".day-cond").textContent = d.conditions.condits || "";
    li.querySelector(".day").setAttribute(
      "aria-label",
      `${name}: ${d.conditions.condits || ""}, high ${round(t.max_temp)}${u.temp}, low ${round(t.min_temp)}${u.temp}`
    );
    return li;
  }));
}

function render(data, zip, units) {
  state = { data, zip, units, selected: null };
  els.empty.hidden = true;
  renderAlerts(data.info?.alerts);
  renderNow(data, units);
  renderDays(data, units);
  els.now.hidden = false;
  els.days.hidden = false;
  els.clear.hidden = false;
  showDay(null); // after un-hiding, so the curve can measure its width
}

// ---------------------------------------------------------------------------
// Status + loading
// ---------------------------------------------------------------------------
function setStatus(message, isError = false) {
  els.status.textContent = message;
  els.status.classList.toggle("error", isError);
}

function setLoading(on) {
  els.submit.disabled = on;
  els.submit.textContent = on ? "Loading…" : "Get forecast";
  els.main.setAttribute("aria-busy", String(on));
}

async function loadForecast(zip, units) {
  setLoading(true);
  setStatus("");
  try {
    const data = await requestJson("GET", "/weather", { zipcode: zip, unit_group: units });
    render(data, zip, units);
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify({ zip, units })); } catch { /* storage unavailable */ }
  } catch (err) {
    setStatus(err.message, true);
  } finally {
    setLoading(false);
  }
}

// ---------------------------------------------------------------------------
// Events
// ---------------------------------------------------------------------------
els.form.addEventListener("submit", (e) => {
  e.preventDefault();
  const zip = els.zip.value.trim();
  const units = new FormData(els.form).get("units");
  if (!/^\d{5}$/.test(zip)) {
    els.zip.setAttribute("aria-invalid", "true");
    setStatus("Enter a 5-digit ZIP code, like 10001.", true);
    els.zip.focus();
    return;
  }
  els.zip.removeAttribute("aria-invalid");
  loadForecast(zip, units);
});

// Switching units reloads the current ZIP right away
els.form.addEventListener("change", (e) => {
  if (e.target.name === "units" && state) loadForecast(state.zip, e.target.value);
});

els.zip.addEventListener("input", () => {
  els.zip.value = els.zip.value.replace(/\D/g, "").slice(0, 5);
  els.zip.removeAttribute("aria-invalid");
});

els.dayList.addEventListener("click", (e) => {
  const btn = e.target.closest(".day");
  if (!btn) return;
  // Selecting the selected day again goes back to the next 24 hours
  showDay(state.selected === btn.dataset.key ? null : btn.dataset.key);
  els.now.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
});

els.clear.addEventListener("click", async () => {
  if (!state) return;
  try {
    await requestJson("DELETE", "/weather/clear", { zipcode: state.zip, unit_group: state.units });
    await loadForecast(state.zip, state.units);
    setStatus(`Cleared cached data for ${state.zip} and loaded a fresh forecast.`);
  } catch (err) {
    setStatus(err.message, true);
  }
});

// Redraw the curve at the new width when the window is resized
let resizeTimer;
window.addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => { if (state) showDay(state.selected); }, 150);
});

// Restore the last search
(function restore() {
  let saved = null;
  try { saved = JSON.parse(localStorage.getItem(STORAGE_KEY)); } catch { /* storage unavailable */ }
  if (!saved || !/^\d{5}$/.test(saved.zip) || !UNITS[saved.units]) return;
  els.zip.value = saved.zip;
  els.form.querySelector(`input[name="units"][value="${saved.units}"]`).checked = true;
  loadForecast(saved.zip, saved.units);
})();