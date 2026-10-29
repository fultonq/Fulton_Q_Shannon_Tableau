/* FY26 Public Space Construction Permit dashboards for tableau_notes.html.

   Generates the data views (Dashboard, Where Times Differ, Deeper Dive, Worksheets): their tabs, panels,
   filter bar, worksheets and charts. The permits come from the <script id="permit-data"> JSON that
   build_html.py embeds; every chart is computed here, so filters and click-to-filter need no server.

   The page script calls PermitDashboards.show(id, panel) when one of these tabs is opened.
*/
(function () {
  'use strict';

  // ------------------------------------------------------------------ data
  const RAW = JSON.parse(document.getElementById('permit-data').textContent);
  const ROWS = RAW.cols.a.map((a, i) => {
    const c = k => RAW.dict[k][RAW.cols[k][i]];
    const blocks = RAW.cols.blocks[i];
    return {
      cat: c('cat'), fam: c('fam'), app: c('app'), loc: c('loc'), ward: c('ward'),
      month: RAW.cols.month[i], resub: RAW.cols.resub[i] ? 'Yes' : 'No', psc: RAW.cols.psc[i] ? 'Yes' : 'No',
      size: blocks === 1 ? '1 block' : '2+ blocks', blocks, a, i: RAW.cols.i[i]
    };
  });
  const LOC_ORDER = ['1 block', '2-5 blocks', '6-20 blocks', '21+ blocks'];
  const BANDS = [['Same day', 0, 0], ['1-5 days', 1, 5], ['6-10 days', 6, 10], ['11-20 days', 11, 20],
                 ['21-40 days', 21, 40], ['41-60 days', 41, 60], ['61+ days', 61, Infinity]];
  const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const FILTER_KEYS = ['cat', 'app', 'resub', 'loc', 'ward', 'psc'];
  const FILTER_LABELS = { cat: 'Permit category', app: 'Applicant type', resub: 'Resubmission', loc: 'Project size', ward: 'Ward', psc: 'PSC review' };
  const F = Object.fromEntries(FILTER_KEYS.map(k => [k, '']));

  const f1 = v => v == null || isNaN(v) ? '–' : v.toFixed(1);
  const fi = v => Math.round(v).toLocaleString('en-US');
  const fmed = v => isNaN(v) ? '–' : Number.isInteger(v) ? String(v) : v.toFixed(1);
  const pct = v => (v * 100).toFixed(0) + '%';
  const esc = s => String(s).replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));

  // Rows matching every filter except `own`, so a chart that drives a filter keeps showing all of its marks.
  function rowsFor(own) {
    return ROWS.filter(r => FILTER_KEYS.every(k => !F[k] || k === own || r[k] === F[k]));
  }
  function median(xs) {
    if (!xs.length) return NaN;
    const s = [...xs].sort((x, y) => x - y), m = s.length >> 1;
    return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
  }
  function stats(rows) {
    const m = rows.filter(r => r.a != null), a = m.map(r => r.a), iss = m.filter(r => r.i != null).map(r => r.i);
    const sum = a.reduce((x, y) => x + y, 0);
    return {
      scope: rows.length, n: m.length, sum, avg: m.length ? sum / m.length : NaN, med: median(a),
      iss: iss.length ? iss.reduce((x, y) => x + y, 0) / iss.length : NaN,
      same: m.length ? a.filter(v => v === 0).length / m.length : NaN,
      in10: m.length ? a.filter(v => v <= 10).length / m.length : NaN,
      over60: m.length ? a.filter(v => v > 60).length / m.length : NaN
    };
  }
  function group(rows, key, order) {
    const g = new Map();
    rows.forEach(r => { if (!g.has(r[key])) g.set(r[key], []); g.get(r[key]).push(r); });
    let out = [...g].map(([k, rs]) => Object.assign({ k }, stats(rs))).filter(d => d.n);
    if (order) out.sort((x, y) => order.indexOf(x.k) - order.indexOf(y.k));
    else out.sort((x, y) => y.avg - x.avg);
    return out;
  }
  function tipFor(d, total) {
    return `<div class="t">${esc(d.k)}</div>Avg business days to approve: <b>${f1(d.avg)}</b><br>` +
      `Median: ${fmed(d.med)} · Permits: ${fi(d.n)}<br>Avg business days to issue: ${f1(d.iss)}` +
      (total ? `<br>Share of approval days: ${pct(d.sum / total)}` : '');
  }

  // ------------------------------------------------------------------ chart primitives
  const ctx = document.createElement('canvas').getContext('2d');
  function textW(s, size = 12) { ctx.font = `${size}px system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`; return ctx.measureText(s).width; }
  function fit(s, w) {
    if (textW(s) <= w) return s;
    while (s.length > 1 && textW(s + '…') > w) s = s.slice(0, -1);
    return s + '…';
  }
  // Bar shapes are square at the baseline and rounded (4px) at the data end.
  function hBar(x, y, w, h, r = 4) {
    if (w <= 0) return '';
    r = Math.min(r, w, h / 2);
    return `M${x},${y}h${w - r}a${r},${r} 0 0 1 ${r},${r}v${h - 2 * r}a${r},${r} 0 0 1 ${-r},${r}h${r - w}z`;
  }
  function vBar(x, y, w, h, r = 4) {
    if (h <= 0) return '';
    r = Math.min(r, h, w / 2);
    return `M${x},${y + h}v${r - h}a${r},${r} 0 0 1 ${r},${-r}h${w - 2 * r}a${r},${r} 0 0 1 ${r},${r}v${h - r}z`;
  }
  const EMPTY = '<p class="empty">No permits match the current filters.</p>';

  // Horizontal bars of average business days, one series, with an overall-average reference line.
  function hbars(W, data, o) {
    if (!data.length) return EMPTY;
    const total = data.reduce((s, d) => s + d.sum, 0);
    const labW = Math.min(W * 0.42, Math.max(...data.map(d => textW(d.k))) + 10);
    const valW = Math.max(...data.map(d => textW(`${f1(d.avg)} (n=${fi(d.n)})`))) + 10;
    const plotW = Math.max(30, W - labW - valW);
    const bh = 18, gap = 10, top = 20, H = top + data.length * (bh + gap);
    const max = Math.max(...data.map(d => d.avg), o.ref || 0) || 1;
    const x = v => labW + v / max * plotW;
    let s = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="${esc(o.aria)}">`;
    if (o.ref != null && !isNaN(o.ref)) {
      const rx = x(o.ref), anchor = rx > W - 70 ? 'end' : rx < labW + 60 ? 'start' : 'middle';
      s += `<line x1="${rx}" x2="${rx}" y1="${top - 4}" y2="${H - gap / 2}" class="ref"/>` +
        `<text x="${rx}" y="${top - 8}" class="reflbl" text-anchor="${anchor}">Overall avg ${f1(o.ref)}</text>`;
    }
    data.forEach((d, i) => {
      const y = top + i * (bh + gap), sel = o.key && F[o.key];
      const cls = o.key ? 'hit click' : 'hit';
      const fv = o.key ? ` data-fk="${o.key}" data-fv="${esc(d.k)}" tabindex="0" role="button" aria-pressed="${F[o.key] === d.k}"` : '';
      s += `<g class="${cls}"${fv} data-tip="${esc(tipFor(d, total))}"${sel && F[o.key] !== d.k ? ' opacity=".35"' : ''}>` +
        `<rect x="0" y="${y - gap / 2}" width="${W}" height="${bh + gap}" fill="transparent"/>` +
        `<text x="${labW - 8}" y="${y + bh / 2}" class="lbl" text-anchor="end" dominant-baseline="central">${esc(fit(d.k, labW - 10))}</text>` +
        `<path d="${hBar(labW, y, x(d.avg) - labW, bh)}" class="${o.cls ? o.cls(d) : 'm1'}"/>` +
        `<text x="${x(d.avg) + 6}" y="${y + bh / 2}" class="val" dominant-baseline="central"><tspan class="b">${f1(d.avg)}</tspan> (n=${fi(d.n)})</text></g>`;
    });
    s += `<line x1="${labW}" x2="${labW}" y1="${top - 4}" y2="${H - gap / 2}" class="gridln"/>`;
    return s + '</svg>';
  }

  function heat(W, rows, rk, ck, rOrder, cOrder) {
    const cells = new Map();
    rows.forEach(r => { if (r.a == null) return; const k = r[rk] + '\u0000' + r[ck]; if (!cells.has(k)) cells.set(k, []); cells.get(k).push(r); });
    if (!cells.size) return { html: EMPTY, table: null };
    const rs = rOrder.filter(v => cOrder.some(c => cells.has(v + '\u0000' + c)));
    const cs = cOrder.filter(c => rs.some(v => cells.has(v + '\u0000' + c)));
    const labW = Math.min(W * 0.38, Math.max(...rs.map(v => textW(v))) + 10);
    const cw = (W - labW) / cs.length, ch = 46, top = 22, H = top + rs.length * ch;
    const st = new Map([...cells].map(([k, v]) => [k, stats(v)]));
    const max = Math.max(...[...st.values()].map(d => d.avg)) || 1;
    const RAMP = ['#cde2fb', '#b7d3f6', '#9ec5f4', '#86b6ef', '#6da7ec', '#5598e7', '#3987e5', '#2a78d6', '#256abf', '#1c5cab', '#184f95', '#104281', '#0d366b'];
    let s = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="Heat map of average business days">`;
    cs.forEach((c, j) => { s += `<text x="${labW + j * cw + cw / 2}" y="12" class="axis" text-anchor="middle">${esc(fit(c, cw - 4))}</text>`; });
    const table = [];
    rs.forEach((v, i) => {
      const y = top + i * ch;
      s += `<text x="${labW - 8}" y="${y + ch / 2}" class="lbl" text-anchor="end" dominant-baseline="central">${esc(fit(v, labW - 10))}</text>`;
      cs.forEach((c, j) => {
        const d = st.get(v + '\u0000' + c);
        table.push([v, c, d ? f1(d.avg) : '–', d ? fi(d.n) : '0']);
        if (!d) return;
        const step = Math.min(RAMP.length - 1, Math.round(d.avg / max * (RAMP.length - 1)));
        const ink = step >= 6 ? '#ffffff' : '#0b0b0b', x = labW + j * cw;
        d.k = `${v} · ${c}`;
        s += `<g class="hit" data-tip="${esc(tipFor(d))}"><rect class="cell" x="${x + 1}" y="${y + 1}" width="${cw - 2}" height="${ch - 2}" rx="4" fill="${RAMP[step]}"/>` +
          `<text x="${x + cw / 2}" y="${y + ch / 2 - 6}" text-anchor="middle" dominant-baseline="central" font-size="14" font-weight="650" fill="${ink}">${f1(d.avg)}</text>` +
          `<text x="${x + cw / 2}" y="${y + ch / 2 + 10}" text-anchor="middle" dominant-baseline="central" font-size="11" fill="${ink}" opacity=".85">n=${fi(d.n)}</text></g>`;
      });
    });
    return {
      html: `<div class="legend"><span><i class="ramp"></i>lighter = faster, darker = slower</span></div>${s}</svg>`,
      table: { head: [rk, ck, 'Avg days', 'Permits'], rows: table }
    };
  }

  function barTable(data, label) {
    return { head: [label, 'Avg days', 'Median', 'Permits', 'Avg days to issue'],
             rows: data.map(d => [d.k, f1(d.avg), fmed(d.med), fi(d.n), f1(d.iss)]) };
  }

  // ------------------------------------------------------------------ worksheets
  const appOrder = rows => group(rows, 'app').sort((x, y) => y.n - x.n).map(d => d.k);
  function barSheet(key, label, order) {
    return (W) => {
      const rows = rowsFor(key), data = group(rows, key, order);
      return { html: hbars(W, data, { key, ref: stats(rows).avg, aria: label }), table: barTable(data, label) };
    };
  }
  const SHEETS = {
    kpi: { title: 'KPI - Overall', sub: 'Overall FY26 performance', req: 1, render() {
      const s = stats(rowsFor());
      const tile = (v, l, hero) => `<div class="kpi${hero ? ' hero' : ''}"><div class="v">${v}</div><div class="l">${l}</div></div>`;
      return { html: s.n ? `<div class="kpis">` +
        tile(`${f1(s.avg)} <small>business days</small>`, 'Average business days to approve', true) +
        tile(fmed(s.med), 'Median business days to approve') +
        tile(pct(s.in10), '% approved within 10 business days') +
        tile(f1(s.iss), 'Avg business days to issue (incl. applicant payment)') +
        tile(fi(s.n), `Permits measured (of ${fi(s.scope)} in scope)`) + '</div>' : EMPTY,
        table: { head: ['Measure', 'Value'], rows: [['Average business days to approve', f1(s.avg)], ['Median', fmed(s.med)],
          ['% within 10 business days', pct(s.in10)], ['% same day', pct(s.same)], ['% over 60 days', pct(s.over60)],
          ['Avg business days to issue', f1(s.iss)], ['Permits measured', fi(s.n)], ['Permits in scope', fi(s.scope)]] } };
    } },
    dist: { title: 'Distribution', sub: 'How long approvals take: permits by approval-time band', req: 1, render(W) {
      const m = rowsFor().filter(r => r.a != null);
      if (!m.length) return { html: EMPTY, table: null };
      const data = BANDS.map(([k, lo, hi]) => ({ k, n: m.filter(r => r.a >= lo && r.a <= hi).length }));
      const max = Math.max(...data.map(d => d.n)) || 1, top = 18, bot = 34, H = 190, ph = H - top - bot;
      const bw = W / data.length, w = Math.max(6, bw - 8);
      let s = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="Permits by approval-time band">`;
      data.forEach((d, i) => {
        const h = d.n / max * ph, x = i * bw + (bw - w) / 2, y = top + ph - h;
        s += `<g class="hit" data-tip="${esc(`<div class="t">${d.k}</div>Permits: <b>${fi(d.n)}</b> (${pct(d.n / m.length)})`)}">` +
          `<rect x="${i * bw}" y="0" width="${bw}" height="${H}" fill="transparent"/><path d="${vBar(x, y, w, h)}" class="m1"/>` +
          `<text x="${x + w / 2}" y="${y - 5}" class="val" text-anchor="middle">${fi(d.n)}</text>` +
          `<text x="${x + w / 2}" y="${H - bot + 16}" class="axis" text-anchor="middle">${esc(d.k.replace(' days', ''))}</text></g>`;
      });
      s += `<line x1="0" x2="${W}" y1="${top + ph}" y2="${top + ph}" class="gridln"/><text x="${W / 2}" y="${H - 2}" class="axis" text-anchor="middle">business days to approve</text>`;
      return { html: s + '</svg>', table: { head: ['Band', 'Permits', 'Share'], rows: data.map(d => [d.k, fi(d.n), pct(d.n / m.length)]) } };
    } },
    cat: { title: 'By Permit Category', sub: 'Average business days to approve, by permit category. Click a bar to filter.', req: 2, render: barSheet('cat', 'Permit category') },
    app: { title: 'By Applicant Type', sub: 'Average business days to approve, by applicant type', req: 3, render: barSheet('app', 'Applicant type') },
    resub: { title: 'Resubmission Impact', sub: 'Resubmission requested vs. not', req: 3, render: barSheet('resub', 'Resubmission requested', ['No', 'Yes']) },
    loc: { title: 'Work Location Size', sub: 'By number of blocks on the permit', req: 3, render: barSheet('loc', 'Blocks on permit', LOC_ORDER) },
    avi: { title: 'Approval vs Issuance', sub: 'Business days to approve (DDOT) vs. to issue (incl. applicant payment)', req: 3, render(W) {
      const data = group(rowsFor(), 'cat');
      if (!data.length) return { html: EMPTY, table: null };
      const labW = Math.min(W * 0.42, Math.max(...data.map(d => textW(d.k))) + 10), valW = 40;
      const plotW = Math.max(30, W - labW - valW), bh = 9, gap = 12, row = bh * 2 + 2 + gap, H = data.length * row + 4;
      const max = Math.max(...data.map(d => Math.max(d.avg, d.iss || 0))) || 1, x = v => labW + v / max * plotW;
      let s = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="Approval vs issuance by category">`;
      data.forEach((d, i) => {
        const y = 2 + i * row;
        s += `<g class="hit" data-tip="${esc(`<div class="t">${esc(d.k)}</div>To approve: <b>${f1(d.avg)}</b> business days<br>To issue: <b>${f1(d.iss)}</b><br>Gap after approval: ${f1(d.iss - d.avg)} · Permits: ${fi(d.n)}`)}">` +
          `<rect x="0" y="${y - gap / 2}" width="${W}" height="${row}" fill="transparent"/>` +
          `<text x="${labW - 8}" y="${y + bh + 1}" class="lbl" text-anchor="end" dominant-baseline="central">${esc(fit(d.k, labW - 10))}</text>` +
          `<path d="${hBar(labW, y, x(d.avg) - labW, bh, 3)}" class="m1"/><text x="${x(d.avg) + 4}" y="${y + bh / 2}" class="val" dominant-baseline="central" font-size="11">${f1(d.avg)}</text>` +
          `<path d="${hBar(labW, y + bh + 2, x(d.iss || 0) - labW, bh, 3)}" class="m2"/><text x="${x(d.iss || 0) + 4}" y="${y + bh * 1.5 + 2}" class="val" dominant-baseline="central" font-size="11">${f1(d.iss)}</text></g>`;
      });
      return { html: `<div class="legend"><span><i style="background:var(--s1)"></i>To approve (DDOT)</span><span><i style="background:var(--s2)"></i>To issue (incl. applicant payment)</span></div>${s}</svg>`,
               table: { head: ['Permit category', 'Avg days to approve', 'Avg days to issue', 'Gap', 'Permits'], rows: data.map(d => [d.k, f1(d.avg), f1(d.iss), f1(d.iss - d.avg), fi(d.n)]) } };
    } },
    ward: { title: 'By Ward', sub: 'Average business days to approve, by ward (little variation)', req: 3,
      render: W => barSheet('ward', 'Ward', ['1', '2', '3', '4', '5', '6', '7', '8', 'Multiple Wards', 'Unknown'])(W) },
    axr: { title: 'Applicant x Resubmission', sub: 'Avg business days: applicant type × resubmission (the gap holds in every row)', req: 'seg', render(W) {
      const rows = rowsFor(); return heat(W, rows, 'app', 'resub', appOrder(rows), ['No', 'Yes']);
    } },
    trend: { title: 'Monthly Trend (censored)', sub: 'Average business days to approve, by application month', req: 'seg', render(W) {
      const data = group(rowsFor(), 'month').sort((x, y) => x.k < y.k ? -1 : 1);
      if (!data.length) return { html: EMPTY, table: null };
      const L = 34, R = 12, top = 16, bot = 26, H = 210, ph = H - top - bot, pw = W - L - R;
      const max = Math.ceil(Math.max(...data.map(d => d.avg)) / 10) * 10 || 10;
      const x = i => L + (data.length === 1 ? pw / 2 : i / (data.length - 1) * pw), y = v => top + ph - v / max * ph;
      const mlab = k => { const [yr, mo] = k.split('-'); return MONTHS[+mo - 1] + (mo === '01' || mo === '10' ? ` ’${yr.slice(2)}` : ''); };
      let s = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="Average business days by application month">`;
      for (let t = 0; t <= 4; t++) { const v = max * t / 4; s += `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" class="gridln"/><text x="${L - 6}" y="${y(v)}" class="axis" text-anchor="end" dominant-baseline="central">${v}</text>`; }
      const every = W < 480 ? 2 : 1;
      data.forEach((d, i) => { if (i % every === 0) s += `<text x="${x(i)}" y="${H - 8}" class="axis" text-anchor="middle">${mlab(d.k)}</text>`; });
      s += `<path class="ln" d="${data.map((d, i) => `${i ? 'L' : 'M'}${x(i)},${y(d.avg)}`).join('')}"/>`;
      data.forEach((d, i) => {
        d.k = mlab(d.k);
        s += `<g class="hit" data-tip="${esc(tipFor(d))}"><circle cx="${x(i)}" cy="${y(d.avg)}" r="12" fill="transparent"/><circle class="dot" cx="${x(i)}" cy="${y(d.avg)}" r="5"/>` +
          (i === 0 || i === data.length - 1 ? `<text x="${x(i) + (i ? -8 : 8)}" y="${y(d.avg) - 12}" class="val" text-anchor="${i ? 'end' : 'start'}"><tspan class="b">${f1(d.avg)}</tspan></text>` : '') + '</g>';
      });
      return { html: s + '</svg><p class="caveat">Caution: late-FY months only include permits issued by 9/30/2026, so they are biased toward fast approvals.</p>',
               table: { head: ['Application month', 'Avg days', 'Permits'], rows: data.map(d => [d.k, f1(d.avg), fi(d.n)]) } };
    } },
    bxr: { title: 'Blocks x Resubmission', sub: 'Avg business days: project size × resubmission', req: 'seg', render(W) {
      return heat(W, rowsFor(), 'loc', 'resub', LOC_ORDER, ['No', 'Yes']);
    } },
    axs: { title: 'Applicant x Project Size', sub: 'Avg business days: applicant type × single vs. multi-block', req: 'seg', render(W) {
      const rows = rowsFor(); return heat(W, rows, 'app', 'size', appOrder(rows), ['1 block', '2+ blocks']);
    } },
    psc: { title: 'PSC Review Impact', sub: 'Public Space Committee review vs. not', req: 'seg', render: barSheet('psc', 'PSC review', ['No', 'Yes']) },
  };
  const HEAT_LABELS = { app: 'Applicant type', resub: 'Resubmission', loc: 'Blocks on permit', size: 'Project size' };
  const REQS = [
    [1, '(1) Average business days to approve', ['kpi', 'dist']],
    [2, '(2) Average by permit type category', ['cat']],
    [3, '(3) Another helpful segment', ['app', 'resub', 'loc', 'avi', 'ward']],
    ['seg', 'Segmentation and cross-checks', ['bxr', 'axs', 'psc', 'axr', 'trend']],
    [4, '(4) Dashboards with layout, titles and guiding text', []],
  ];

  // ------------------------------------------------------------------ rendering
  const tableOpen = new Set();
  function renderCard(el) {
    const id = el.dataset.sheet, sh = SHEETS[id];
    if (!el.firstChild) {
      el.innerHTML = `<div class="card-h"><div><h3>${esc(sh.title)}</h3><p>${esc(sh.sub)}</p></div>` +
        `<button type="button" data-table="${id}" aria-pressed="false">Table</button></div><div class="card-b"></div>`;
    }
    const body = el.querySelector('.card-b'), btn = el.querySelector('[data-table]');
    const out = sh.render(Math.max(200, body.clientWidth));
    const open = tableOpen.has(id) && out.table;
    btn.textContent = open ? 'Chart' : 'Table';
    btn.setAttribute('aria-pressed', !!open);
    btn.hidden = !out.table;
    if (open) {
      const head = out.table.head.map(h => HEAT_LABELS[h] || h);
      const isNum = v => /^[\d.,%–-]+$/.test(v);
      body.innerHTML = `<div class="table-wrap"><table><thead><tr>${head.map((h, j) => `<th${j ? ' class="num"' : ''}>${esc(h)}</th>`).join('')}</tr></thead><tbody>` +
        out.table.rows.map(r => `<tr>${r.map(c => `<td${isNum(c) ? ' class="num"' : ''}>${esc(c)}</td>`).join('')}</tr>`).join('') + '</tbody></table></div>';
    } else body.innerHTML = out.html;
  }
  function renderView(panel) {
    if (!panel) return;
    panel.querySelectorAll('[data-sheet]').forEach(renderCard);
    const s = stats(rowsFor()), active = FILTER_KEYS.filter(k => F[k]).length;
    document.querySelector('[data-match]').innerHTML = active
      ? `<b>${fi(s.n)}</b> of ${fi(stats(ROWS).n)} permits match` : `<b>${fi(s.n)}</b> permits, no filters`;
  }
  const activePanel = () => document.querySelector('[data-dash]:not([hidden])');

  // ------------------------------------------------------------------ events
  document.addEventListener('click', e => {
    const t = e.target.closest('[data-table]');
    if (t) { const id = t.dataset.table; tableOpen.has(id) ? tableOpen.delete(id) : tableOpen.add(id); renderCard(t.closest('[data-sheet]')); return; }
    const g = e.target.closest('[data-fk]');
    if (g) { hideTip(); setFilter(g.dataset.fk, g.dataset.fv); }
  });
  document.addEventListener('keydown', e => {
    const g = e.target.closest && e.target.closest('[data-fk]');
    if (g && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); setFilter(g.dataset.fk, g.dataset.fv); }
  });

  // ------------------------------------------------------------------ tooltip
  const tip = document.body.appendChild(Object.assign(document.createElement('div'), { id: 'tip', hidden: true }));
  function hideTip() { tip.hidden = true; }
  document.addEventListener('mousemove', e => {
    const g = e.target.closest && e.target.closest('[data-tip]');
    if (!g) return hideTip();
    tip.innerHTML = g.dataset.tip; tip.hidden = false;
    const r = tip.getBoundingClientRect();
    let x = e.clientX + 14, y = e.clientY + 14;
    if (x + r.width > innerWidth - 8) x = e.clientX - r.width - 14;
    if (y + r.height > innerHeight - 8) y = e.clientY - r.height - 14;
    tip.style.left = Math.max(8, x) + 'px'; tip.style.top = Math.max(8, y) + 'px';
  });
  document.addEventListener('scroll', hideTip, { passive: true });
  let rt, lastW = 0;
  new ResizeObserver(() => {
    const w = document.documentElement.clientWidth;
    if (w === lastW) return;
    lastW = w; clearTimeout(rt); rt = setTimeout(() => renderView(activePanel()), 120);
  }).observe(document.body);

  // ------------------------------------------------------------------ dashboard layouts
  // Each view mirrors a dashboard in FY26_Public_Space_Permit_Approvals.twbx. A `data-sheet` element is filled
  // by the worksheet of that id; everything else is static layout and guiding text.
  const section = (num, title, note) =>
    `<h2 class="sec"><span class="sec-num">${num}</span>${title}${note ? `<span class="sec-note">${note}</span>` : ''}</h2>`;
  const box = (title, items, ordered, foot = '') => {
    const tag = ordered ? 'ol' : 'ul';
    return `<div class="note-box"><h3>${title}</h3><${tag}>${items.map(i => `<li>${i}</li>`).join('')}</${tag}>${foot}</div>`;
  };
  const card = id => `<div class="card" data-sheet="${id}"></div>`;
  const SCOPE_TEXT = 'New permits applied for on or after Oct 1, 2025 and issued in FY26 (Oct 1, 2025 – Sep 30, 2026). ' +
    "Business days count from application to DDOT's final approval and exclude weekends and DC holidays. " +
    'Source: DDOT TOPS, deduplicated to one row per permit.';
  const STATIC_NOTE = '<p class="static-note">Text boxes quote the unfiltered FY26 figures; the charts follow the filters.</p>';
  const holidayText = () => {
    const hol = RAW.holidays.map(h => { const [, m, d] = h.HolidayDate.split('-'); return `${+m}/${+d}`; });
    return `Holidays excluded (${hol.length}): ${hol.join(', ')}`;
  };

  const VIEWS = {
    dashboard: { label: 'Dashboard', html: () => `
<div class="dash">
  <h1>FY2026 Public Space Construction Permits: Business Days to Approve</h1>
  <p class="lede">${SCOPE_TEXT} Click a bar to filter the whole dashboard; click it again to clear.</p>
  <div class="grid g-main">
    <div class="col">${section(1, 'Overall performance')}${card('kpi')}${card('dist')}</div>
    <div class="col span2">${section(2, 'By permit type category',
      'Line = overall average. Excavation is split by utility because it is 90% of permits.')}${card('cat')}</div>
  </div>
  ${section(3, 'Where approval times differ', 'Resubmission and project size separate fast from slow; geography does not.')}
  <div class="grid g3">${card('app')}${card('resub')}${card('loc')}</div>
  <div class="grid g-notes">
    ${box('Key takeaways', [
      '<b>22.2 avg / 13 median</b> business days. The average blends a same-day group (22%) with a 60+ day tail (9%).',
      '<b>Widest gap is resubmission:</b> 12.4 vs 48.3 days. 27% of permits account for 59% of approval days.',
      '<b>Project size:</b> 1 block 13.5 days vs 6–20 blocks 51.7. DC Water single-block permits take 7 days, multi-block 41–52.',
      '<b>Category:</b> Sewer/Storm 0.9 and Gas 8.0, up to Water 35.7 and Multiple Work Types 51.0. Water is 32% of permits and 51% of approval days.',
      '<b>Applicant:</b> Washington Gas 8.9, DC Water 31.2, Private 44.1. Private applicants are asked to resubmit 68% of the time.',
    ], false, STATIC_NOTE)}
    ${box('Next steps', [
      'Analyze reasons for Revise &amp; Resubmit requests by category.',
      'Review DC Water multi-block lateral work as a program.',
      'Split time into queue, review, and applicant-payment stages.',
      'Use cohort-based trends (the monthly view is cut off at year end).',
    ], true, `<p class="small">${holidayText()}</p><p class="small">${fi(stats(ROWS).scope - stats(ROWS).n)} of ` +
      `${fi(stats(ROWS).scope)} in-scope permits have no approval date and are left out of the business-day averages ` +
      `(n = ${fi(stats(ROWS).n)}).</p>`)}
  </div>
</div>` },

    segments: { label: 'Where Times Differ', html: () => `
<div class="dash">
  <h1>Where approval times are meaningfully different</h1>
  <p class="lede">Segments that each explain a large share of the variation, tested against each other.
  FY26 new permits issued; business days from application to DDOT's last approval.</p>
  <div class="grid g2">${card('bxr')}${card('axs')}</div>
  <div class="grid g-notes">
    ${card('psc')}
    ${box('Key takeaways', [
      '<b>Fast lane:</b> single-block permits never sent back average 7.0 days (median 1). They are 1,763 permits, 59% of the total.',
      '<b>Slow lane:</b> multi-block permits that were sent back average 58.2 days (379 permits).',
      '<b>Both gaps are real:</b> resubmission adds 33 days on single-block permits and 22 on multi-block ones, and size adds 18 to 29 days whether or not a permit is sent back.',
      '<b>DC Water:</b> its single-block permits average 7.1 days, close to Washington Gas (8.4). The slowness is its multi-block lateral work, at 48.3 days.',
      '<b>PSC review:</b> 41 permits average 86.4 days vs. 21.3, and 71% take over 60 days. Mostly private applicants doing multiple work types or fixtures.',
      '<b>Read with care:</b> groups under about 30 permits (Landscaping, Projections, Government Agency) have wide uncertainty; the n on each bar shows the count.',
    ], false, STATIC_NOTE)}
  </div>
</div>` },

    deeper: { label: 'Deeper Dive', html: () => `
<div class="dash">
  <h1>Deeper dive: what separates fast and slow approvals</h1>
  <p class="lede">Cross-checks behind the main dashboard: is the gap real within each group, and where does time go after approval?</p>
  <div class="grid g2">${card('axr')}${card('avi')}${card('ward')}${card('trend')}</div>
</div>` },

    sheets: { label: 'Worksheets', html: () => `
<div class="dash">
  <h1>Worksheets</h1>
  <p class="lede">Every worksheet in the packaged workbook, grouped by the assignment requirement it answers.
  The filters above apply here too.</p>
  <div class="table-wrap"><table class="req-table"><thead><tr><th>Requirement</th><th>Worksheets</th></tr></thead><tbody>
  ${REQS.map(([, label, ids]) => `<tr><td>${esc(label)}</td><td>${ids.length
    ? ids.map(id => `<a href="#sheets-${id}">${esc(SHEETS[id].title)}</a>`).join(', ')
    : '<a href="#dashboard">FY26 Permit Approval Times</a>, <a href="#segments">Where Times Differ</a>, <a href="#deeper">Deeper Dive</a>'
  }</td></tr>`).join('')}
  </tbody></table></div>
  ${REQS.filter(r => r[2].length).map(([, label, ids]) => `<section class="sheet-group"><h2>${esc(label)}</h2>` +
    `<div class="grid">${ids.map(id => `<div class="card" id="sheets-${id}" data-sheet="${id}"></div>`).join('')}</div></section>`).join('')}
</div>` },
  };

  // ------------------------------------------------------------------ filter bar
  let selects = [];
  function mountFilters(el) {
    el.innerHTML = `<div class="bar">${FILTER_KEYS.map(k =>
      `<label>${FILTER_LABELS[k]}<select data-filter="${k}"></select></label>`).join('')}` +
      '<button type="button" data-clear-filters>Clear filters</button><span class="match" data-match></span></div>';
    selects = [...el.querySelectorAll('[data-filter]')];
    selects.forEach(sel => {
      const k = sel.dataset.filter;
      let vals = [...new Set(ROWS.map(r => r[k]))];
      if (k === 'loc') vals = LOC_ORDER.filter(v => vals.includes(v));
      else if (k === 'ward') vals.sort((x, y) => (isNaN(x) ? 99 : +x) - (isNaN(y) ? 99 : +y));
      else vals.sort();
      sel.innerHTML = `<option value="">All</option>` + vals.map(v => `<option>${esc(v)}</option>`).join('');
      sel.addEventListener('change', () => { F[k] = sel.value; renderView(activePanel()); });
    });
    el.querySelector('[data-clear-filters]').addEventListener('click', () => {
      FILTER_KEYS.forEach(k => F[k] = ''); selects.forEach(s => s.value = ''); renderView(activePanel());
    });
  }
  function setFilter(k, v) {
    F[k] = F[k] === v ? '' : v;
    selects.find(s => s.dataset.filter === k).value = F[k];
    renderView(activePanel());
  }

  // ------------------------------------------------------------------ mount
  const tablist = document.querySelector('[role="tablist"]'), main = document.querySelector('main');
  Object.entries(VIEWS).reverse().forEach(([id, v]) => {
    tablist.insertAdjacentHTML('afterbegin', `<button role="tab" id="tab-${id}" aria-controls="panel-${id}" ` +
      `data-tab="${id}" data-view="data" aria-selected="false">${esc(v.label)}</button>`);
    main.insertAdjacentHTML('afterbegin', `<section role="tabpanel" id="panel-${id}" aria-labelledby="tab-${id}" data-dash="${id}" hidden></section>`);
  });
  mountFilters(document.getElementById('filters'));

  window.PermitDashboards = {
    // Build the view's layout on first open, then (re)draw its worksheets with the current filters.
    show(id, panel) {
      if (!panel.dataset.mounted) { panel.innerHTML = VIEWS[id].html(); panel.dataset.mounted = '1'; }
      renderView(panel);
    }
  };
})();
