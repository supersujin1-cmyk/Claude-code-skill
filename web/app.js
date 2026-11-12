/* 가계부 대시보드: data.json(ledger.export가 생성)을 읽어 그립니다. 데이터 값은 textContent로만 넣습니다. */
(async function () {
  const D = await (await fetch("data.json", { cache: "no-store" })).json();
  const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();

  // ---------- 서식 ----------
  const nf = new Intl.NumberFormat("ko-KR");
  const won = (v) => `${nf.format(Math.round(v))}원`;
  const man = (v) => {
    const a = Math.abs(v);
    if (a >= 1e8) return `${(v / 1e8).toFixed(1)}억`;
    if (a >= 1e4) return `${nf.format(Math.round(v / 1e4))}만`;
    return nf.format(Math.round(v));
  };
  const pct = (v, d = 1) => `${v.toFixed(d)}%`;
  const signed = (v) => (v > 0 ? "+" : v < 0 ? "−" : "") + won(Math.abs(v));

  // ---------- DOM 도우미 ----------
  const $ = (s) => document.querySelector(s);
  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function frag(parts) { // ["문장", {b:"굵게", cls}] 형태로 문장을 만듭니다
    const f = document.createDocumentFragment();
    for (const p of parts) {
      if (typeof p === "string") f.append(p);
      else { const b = el("b", p.cls || "", p.b); f.append(b); }
    }
    return f;
  }
  function take(id, parts) { const t = $(id); t.replaceChildren(frag(parts)); }
  function tile(box, label, big, delta) {
    const t = el("div", "tile");
    t.append(el("span", "label", label), el("span", "big", big));
    if (delta) { const d = el("span", "delta"); d.append(frag(delta)); t.append(d); }
    box.append(t);
  }
  function bar(box, name, ratio, level, valText, sub) {
    const r = el("div", "row");
    const n = el("span", "name", name);
    if (sub) n.title = sub;
    const tr = el("div", "track");
    const fi = el("div", `fill ${level || ""}`);
    fi.style.width = `${Math.max(0, Math.min(100, ratio))}%`;
    tr.append(fi);
    r.append(n, tr, el("span", "val", valText));
    box.append(r);
  }
  function empty(box, text) { box.append(el("p", "empty", text)); }

  // ---------- 차트 ----------
  function tipFor(box) {
    let t = box.querySelector(".tip");
    if (!t) { t = el("div", "tip"); t.hidden = true; box.append(t); }
    return {
      show(ev, lines) {
        t.replaceChildren(...lines.map(([h, v], i) => {
          const d = el("div", i === 0 ? "h" : ""); d.textContent = v == null ? h : `${h}  ${v}`; return d;
        }));
        t.hidden = false;
        const [x, y] = d3.pointer(ev, box);
        const w = t.offsetWidth;
        t.style.left = `${Math.min(Math.max(0, x + 12), box.clientWidth - w)}px`;
        t.style.top = `${Math.max(0, y - 40)}px`;
      },
      hide() { t.hidden = true; },
    };
  }
  const draws = [];
  function chart(id, fn) { const box = $(id); const run = () => fn(box); draws.push(run); return run; }
  new ResizeObserver(() => draws.forEach((f) => f())).observe(document.body);

  // 묶음 막대: series = [{key, label, color}]
  function bars(box, rows, xKey, series, opts = {}) {
    box.querySelectorAll("svg").forEach((s) => s.remove());
    const W = box.clientWidth, H = opts.height || 240, m = { t: 8, r: 8, b: 26, l: 44 };
    if (!W) return;
    const svg = d3.select(box).append("svg").attr("width", W).attr("height", H);
    const x = d3.scaleBand().domain(rows.map((r) => r[xKey])).range([m.l, W - m.r]).padding(0.25);
    const xi = d3.scaleBand().domain(series.map((s) => s.key)).range([0, x.bandwidth()]).padding(0.08);
    const max = d3.max(rows, (r) => d3.max(series, (s) => r[s.key])) || 1;
    const y = d3.scaleLinear().domain([0, max]).nice().range([H - m.b, m.t]);
    svg.append("g").attr("transform", `translate(${m.l},0)`)
      .call(d3.axisLeft(y).ticks(4).tickSize(-(W - m.l - m.r)).tickFormat(man));
    const every = Math.ceil(rows.length / Math.max(1, Math.floor((W - m.l) / 56)));
    svg.append("g").attr("transform", `translate(0,${H - m.b})`)
      .call(d3.axisBottom(x).tickSize(0).tickPadding(8).tickFormat((d, i) => (i % every ? "" : opts.xFmt ? opts.xFmt(d) : d)));
    const tip = tipFor(box);
    const g = svg.append("g").selectAll("g").data(rows).join("g").attr("transform", (r) => `translate(${x(r[xKey])},0)`);
    g.selectAll("rect").data((r) => series.map((s) => ({ s, r, v: r[s.key] }))).join("rect")
      .attr("x", (d) => xi(d.s.key)).attr("width", xi.bandwidth())
      .attr("y", (d) => y(Math.max(0, d.v))).attr("height", (d) => Math.abs(y(d.v) - y(0)))
      .attr("rx", 2).attr("fill", (d) => (d.r.future ? css("--grid") : d.s.color))
      .on("pointermove", (ev, d) => tip.show(ev, [[opts.xFmt ? opts.xFmt(d.r[xKey]) : d.r[xKey]],
        ...series.map((s) => [s.label, (opts.vFmt || won)(d.r[s.key])])]))
      .on("pointerleave", () => tip.hide());
  }

  function line(box, rows, xKey, series, opts = {}) {
    box.querySelectorAll("svg").forEach((s) => s.remove());
    const W = box.clientWidth, H = opts.height || 240, m = { t: 10, r: 12, b: 26, l: 48 };
    if (!W) return;
    const svg = d3.select(box).append("svg").attr("width", W).attr("height", H);
    const x = d3.scalePoint().domain(rows.map((r) => r[xKey])).range([m.l, W - m.r]).padding(0.3);
    const vals = rows.flatMap((r) => series.map((s) => r[s.key]));
    const lo = opts.zero ? Math.min(0, d3.min(vals)) : d3.min(vals) * 0.95;
    const y = d3.scaleLinear().domain([lo, d3.max(vals)]).nice().range([H - m.b, m.t]);
    svg.append("g").attr("transform", `translate(${m.l},0)`)
      .call(d3.axisLeft(y).ticks(4).tickSize(-(W - m.l - m.r)).tickFormat(opts.yFmt || man));
    const every = Math.ceil(rows.length / Math.max(1, Math.floor((W - m.l) / 60)));
    svg.append("g").attr("transform", `translate(0,${H - m.b})`)
      .call(d3.axisBottom(x).tickSize(0).tickPadding(8).tickFormat((d, i) => (i % every ? "" : opts.xFmt ? opts.xFmt(d) : d)));
    for (const s of series) {
      svg.append("path").datum(rows).attr("fill", "none").attr("stroke", s.color).attr("stroke-width", 2)
        .attr("d", d3.line().x((r) => x(r[xKey])).y((r) => y(r[s.key])));
      svg.append("g").selectAll("circle").data(rows).join("circle")
        .attr("cx", (r) => x(r[xKey])).attr("cy", (r) => y(r[s.key])).attr("r", 3).attr("fill", s.color);
    }
    const tip = tipFor(box);
    svg.append("rect").attr("x", m.l).attr("y", m.t).attr("width", W - m.l - m.r).attr("height", H - m.t - m.b)
      .attr("fill", "transparent")
      .on("pointermove", (ev) => {
        const [px] = d3.pointer(ev);
        const r = rows.reduce((a, b) => (Math.abs(x(b[xKey]) - px) < Math.abs(x(a[xKey]) - px) ? b : a));
        tip.show(ev, [[opts.xFmt ? opts.xFmt(r[xKey]) : r[xKey]], ...series.map((s) => [s.label, (opts.vFmt || won)(r[s.key])])]);
      })
      .on("pointerleave", () => tip.hide());
  }

  function hbars(box, rows, nameKey, valKey) {
    box.querySelectorAll("svg").forEach((s) => s.remove());
    const W = box.clientWidth, rowH = 26, m = { l: 84, r: 70 };
    if (!W) return;
    const H = rows.length * rowH + 4;
    const svg = d3.select(box).append("svg").attr("width", W).attr("height", H);
    const x = d3.scaleLinear().domain([0, d3.max(rows, (r) => r[valKey]) || 1]).range([0, W - m.l - m.r]);
    const tip = tipFor(box);
    const g = svg.selectAll("g").data(rows).join("g").attr("transform", (r, i) => `translate(0,${i * rowH})`);
    g.append("text").attr("x", m.l - 8).attr("y", rowH / 2 + 4).attr("text-anchor", "end").text((r) => r[nameKey]);
    g.append("rect").attr("x", m.l).attr("y", 6).attr("height", rowH - 12).attr("rx", 2)
      .attr("width", (r) => Math.max(1, x(r[valKey]))).attr("fill", css("--bar"))
      .on("pointermove", (ev, r) => tip.show(ev, [[r[nameKey]], ["금액", won(r[valKey])]]))
      .on("pointerleave", () => tip.hide());
    g.append("text").attr("x", (r) => m.l + x(r[valKey]) + 6).attr("y", rowH / 2 + 4).text((r) => man(r[valKey]));
  }

  function table(tblEl, cols, rows, opts = {}) {
    let sortKey = opts.sort || null, asc = false;
    const render = () => {
      const data = sortKey ? [...rows].sort((a, b) => (a[sortKey] > b[sortKey] ? 1 : -1) * (asc ? 1 : -1)) : rows;
      const thead = el("thead"), tr = el("tr");
      for (const c of cols) {
        const th = el("th", c.left ? "l" : "");
        const b = el("button", "sort", c.label + (sortKey === c.key ? (asc ? " ↑" : " ↓") : ""));
        b.onclick = () => { asc = sortKey === c.key ? !asc : false; sortKey = c.key; render(); };
        th.append(b); tr.append(th);
      }
      thead.append(tr);
      const tbody = el("tbody");
      for (const r of data) {
        const row = el("tr", opts.dim && opts.dim(r) ? "dim" : "");
        for (const c of cols) {
          const td = el("td", c.left ? "l" : "");
          const v = c.fmt ? c.fmt(r[c.key], r) : r[c.key];
          if (v instanceof Node) td.append(v); else td.textContent = v;
          if (c.cls) td.className += " " + c.cls(r[c.key], r);
          row.append(td);
        }
        tbody.append(row);
      }
      tblEl.replaceChildren(thead, tbody);
    };
    render();
  }

  // ---------- 탭 ----------
  const tabs = document.querySelectorAll(".tab");
  function openTab(name) {
    tabs.forEach((t) => t.setAttribute("aria-selected", String(t.dataset.tab === name)));
    document.querySelectorAll(".page").forEach((p) => (p.hidden = p.dataset.page !== name));
    history.replaceState(null, "", `#${name}`);
    draws.forEach((f) => f());
  }
  tabs.forEach((t) => (t.onclick = () => openTab(t.dataset.tab)));

  // ---------- 공통 ----------
  const K = D.kpi;
  $("#asof").textContent = `기준일 ${D.meta.today}`;
  $("#demo-badge").hidden = !D.meta.demo;
  const weekDiff = K.week - K.last_week_same;
  const fc = D.forecast;

  // ---------- 요약 ----------
  take("#summary-take", [
    "이번 주 지출은 ", { b: won(K.week) }, "로 지난주 같은 기간보다 ",
    { b: signed(weekDiff), cls: weekDiff > 0 ? "bad" : "good" }, " ", weekDiff > 0 ? "많습니다" : "적습니다",
    ". 이 속도라면 이번 달 지출은 ", { b: won(fc.projected) }, "로 예상되고, 순자산은 ", { b: won(K.net_worth) }, "입니다.",
  ]);
  const sk = $("#summary-kpis");
  tile(sk, "오늘 지출", won(K.today));
  tile(sk, "이번 주 지출", won(K.week), ["지난주 같은 기간 ", { b: signed(weekDiff), cls: weekDiff > 0 ? "bad" : "good" }]);
  tile(sk, "이번 달 지출", won(K.month_expense), ["월말 예상 ", { b: won(fc.projected) }]);
  tile(sk, `저축률 (${K.savings_month.slice(5)}월)`, K.savings_rate == null ? "—" : pct(K.savings_rate),
    ["수입 중 남긴 비율"]);
  tile(sk, "순자산", won(K.net_worth), ["카드대금 차감"]);

  $("#week-legend").replaceChildren(
    frag([]), (() => { const s = el("span"); const i = el("i", "sw"); i.style.background = css("--bar"); s.append(i, "이번 주"); return s; })(),
    (() => { const s = el("span"); const i = el("i", "sw"); i.style.background = css("--bar-2"); s.append(i, "지난주"); return s; })());
  chart("#ch-week", (box) => bars(box, D.week_daily, "label",
    [{ key: "last", label: "지난주", color: css("--bar-2") }, { key: "amount", label: "이번 주", color: css("--bar") }]))();

  const al = $("#alert-list");
  if (!D.anomalies.length) empty(al, "특이한 지출이 없습니다.");
  for (const a of D.anomalies) {
    const box = el("div", "alert");
    const body = el("div");
    body.append(el("div", "t", `${a.description} · ${won(a.amount)}`), el("div", "s", `${a.date} · ${a.reason}`));
    box.append(el("span", "", "⚠️"), body);
    al.append(box);
  }

  const bm = $("#budget-mini-list");
  for (const b of [...D.budgets].sort((a, b) => b.pct - a.pct).slice(0, 4))
    bar(bm, b.category, b.pct, b.level, `${pct(b.pct, 0)} · ${man(b.spent)}/${man(b.budget)}`);

  const up = $("#upcoming-list");
  const left = D.recurring.filter((r) => !r.charged).sort((a, b) => a.day - b.day);
  if (!left.length) empty(up, "이번 달 고정지출은 모두 나갔습니다.");
  for (const r of left) {
    const row = el("div", "row plain");
    row.append(el("span", "name", r.name), el("span", "pill", `매달 ${r.day}일`), el("span", "val", won(r.amount)));
    up.append(row);
  }

  // ---------- 지출 ----------
  const topCat = D.category_month[0];
  take("#spending-take", [
    "이번 달 가장 많이 쓴 곳은 ", { b: topCat ? topCat.category : "—" }, "(", { b: topCat ? won(topCat.amount) : "—" },
    ")입니다. 매달 나가는 고정지출은 ", { b: `${D.recurring.length}건` }, ", 합계 ",
    { b: won(d3.sum(D.recurring, (r) => r.amount)) }, "입니다.",
  ]);
  let period = "weekly";
  const trend = chart("#ch-trend", (box) => bars(box, D[period], "label",
    [{ key: "expense", label: "지출", color: css("--bar") }, { key: "income", label: "수입", color: css("--ok") }],
    { xFmt: (d) => (period === "weekly" ? d.slice(5) : d.slice(2)) }));
  trend();
  document.querySelectorAll("[data-period]").forEach((b) => (b.onclick = () => {
    period = b.dataset.period;
    document.querySelectorAll("[data-period]").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    trend();
  }));
  chart("#ch-category", (box) => hbars(box, D.category_month.slice(0, 10), "category", "amount"))();

  const fb = $("#forecast-body");
  const ft = el("div", "tiles");
  tile(ft, "지금까지", won(fc.spent), [`${fc.days_elapsed}일 / ${fc.days_in_month}일`]);
  tile(ft, "월말 예상", won(fc.projected), ["남은 고정지출 ", { b: won(fc.fixed_left) }]);
  if (K.prev_month_expense != null) {
    const d = fc.projected - K.prev_month_expense;
    tile(ft, "지난달 지출", won(K.prev_month_expense), ["예상 대비 ", { b: signed(d), cls: d > 0 ? "bad" : "good" }]);
  }
  fb.append(ft);

  const cl = $("#card-list");
  for (const c of D.cards)
    bar(cl, c.name, c.pct, c.remaining ? "warn" : "", c.remaining ? `${won(c.remaining)} 더 · ${c.days_left}일 남음` : `달성 (${won(c.spent)})`);

  table($("#tbl-recurring"), [
    { key: "name", label: "항목", left: true }, { key: "category", label: "카테고리", left: true },
    { key: "day", label: "결제일", fmt: (v) => `매달 ${v}일` }, { key: "months", label: "확인된 달", fmt: (v) => `${v}개월` },
    { key: "amount", label: "금액", fmt: won }, { key: "charged", label: "이번 달", fmt: (v) => (v ? "결제됨" : "예정") },
  ], D.recurring, { sort: "amount" });

  // ---------- 예산·목표 ----------
  const over = D.budgets.filter((b) => b.level === "over");
  const lastSav = D.monthly.length ? D.monthly[D.monthly.length - 2] : null;
  take("#plan-take", [
    "예산을 넘은 카테고리는 ", { b: `${over.length}개`, cls: over.length ? "bad" : "good" },
    over.length ? `(${over.map((b) => b.category).join(", ")})` : "", "이고, ",
    "목표 저축은 매달 ", { b: won(d3.sum(D.goals, (g) => g.monthly_needed)) }, "씩 모으면 기한에 맞출 수 있습니다.",
  ]);
  const bl = $("#budget-list");
  for (const b of D.budgets)
    bar(bl, b.category, b.pct, b.level, `${won(b.spent)} / ${won(b.budget)} (${pct(b.pct, 0)})`);
  const gl = $("#goal-list");
  for (const g of D.goals)
    bar(gl, g.name, g.pct, "accent", `${man(g.saved)}/${man(g.target)} · 월 ${won(g.monthly_needed)} · ~${g.deadline.slice(0, 7)}`);
  chart("#ch-savings", (box) => line(box, D.monthly.slice(0, -1), "label",
    [{ key: "savings_rate", label: "저축률", color: css("--ok") }],
    { yFmt: (v) => `${v}%`, vFmt: (v) => pct(v), xFmt: (d) => d.slice(2), zero: true }))();

  // ---------- 투자 ----------
  const I = D.invest;
  take("#invest-take", [
    "보유 주식 평가금액은 ", { b: won(I.value) }, ", 평가손익은 ",
    { b: signed(I.unrealized), cls: I.unrealized >= 0 ? "good" : "bad" }, "입니다. 올해 받은 배당은 세후 ",
    { b: won(D.dividends.total) }, "입니다.",
  ]);
  const ik = $("#invest-kpis");
  tile(ik, "평가금액", won(I.value));
  tile(ik, "평가손익", signed(I.unrealized));
  tile(ik, "실현손익", signed(I.realized));
  tile(ik, `${D.dividends.year}년 배당 (세후)`, won(D.dividends.total));
  tile(ik, "환율", Object.entries(I.fx).map(([c, r]) => `${c} ${nf.format(r)}`).join(", ") || "—");
  table($("#tbl-holdings"), [
    { key: "name", label: "종목", left: true }, { key: "market", label: "시장", left: true },
    { key: "quantity", label: "수량", fmt: (v) => nf.format(v) },
    { key: "avg_price", label: "평단", fmt: (v, r) => `${nf.format(v)} ${r.currency}` },
    { key: "price", label: "현재가", fmt: (v, r) => `${nf.format(v)} ${r.currency}` },
    { key: "value", label: "평가액(원)", fmt: won },
    { key: "unrealized", label: "평가손익", fmt: signed, cls: (v) => (v >= 0 ? "good" : "bad") },
    { key: "return_pct", label: "수익률", fmt: (v) => `${v > 0 ? "+" : ""}${pct(v)}`, cls: (v) => (v >= 0 ? "good" : "bad") },
  ], I.holdings, { sort: "value" });
  chart("#ch-div", (box) => bars(box, D.dividends.calendar, "month",
    [{ key: "amount", label: "배당", color: css("--accent") }], { xFmt: (m) => `${m}월` }))();
  const dl = $("#div-list");
  const dmax = d3.max(D.dividends.by_symbol, (d) => d.amount) || 1;
  for (const d of D.dividends.by_symbol) bar(dl, d.name, (d.amount / dmax) * 100, "accent", won(d.amount));

  // ---------- 자산 ----------
  const A = D.assets, nwh = D.networth_history;
  const nwChange = nwh.length > 1 ? nwh[nwh.length - 1].value - nwh[0].value : 0;
  take("#assets-take", [
    "순자산은 ", { b: won(A.net_worth) }, "로 1년 전보다 ", { b: signed(nwChange), cls: nwChange >= 0 ? "good" : "bad" },
    " 변했습니다. 자산의 ", { b: pct((A.cash / A.total) * 100, 0) }, "가 현금입니다.",
  ]);
  const ak = $("#asset-kpis");
  tile(ak, "순자산", won(A.net_worth));
  tile(ak, "총자산", won(A.total));
  tile(ak, "결제 예정 카드대금", won(A.card_due));
  chart("#ch-nw", (box) => line(box, nwh, "month", [{ key: "value", label: "순자산", color: css("--accent") }],
    { xFmt: (d) => d.slice(2) }))();
  const alc = $("#alloc-list");
  for (const [n, v] of [["현금", A.cash], ["국내주식", A.domestic], ["해외주식", A.foreign]])
    bar(alc, n, (v / A.total) * 100, "accent", `${won(v)} · ${pct((v / A.total) * 100, 0)}`);

  // ---------- 연말정산 ----------
  const Y = D.yearend, P = Y.pension;
  take("#tax-take", [
    "올해 카드 등 사용액은 ", { b: won(Y.total_spend) }, ", 예상 소득공제는 ", { b: won(Y.deduction) },
    "입니다. 연금저축·IRP는 ", { b: won(P.room_left) }, "을 더 넣으면 세액공제 한도를 채웁니다.",
  ]);
  const tk = $("#tax-kpis");
  tile(tk, "총급여 (설정값)", won(Y.salary));
  tile(tk, "카드 등 사용액", won(Y.total_spend), ["문턱 ", { b: won(Y.threshold) }]);
  tile(tk, "예상 소득공제", won(Y.deduction), ["기본한도 ", { b: won(Y.basic_limit) }]);
  tile(tk, "연금 예상 세액공제", won(P.credit), [`공제율 ${pct(P.rate)}`]);

  const db = $("#deduction-body");
  const rowsBox = el("div", "rows");
  bar(rowsBox, "공제 문턱", Math.min(100, (Y.total_spend / Y.threshold) * 100), "accent",
    Y.remaining_to_threshold ? `${won(Y.remaining_to_threshold)} 남음` : "달성");
  const gmax = d3.max(Y.groups, (g) => g.spend) || 1;
  for (const g of Y.groups) bar(rowsBox, g.label, (g.spend / gmax) * 100, "", `${won(g.spend)} · ${g.rate}%`);
  const adv = el("div", "alert"); adv.append(el("span", "", "💡"), el("div", "", Y.advice));
  db.append(rowsBox, adv);

  const pb = $("#pension-body");
  const pr = el("div", "rows");
  bar(pr, "연금저축", (P.pension_paid / 6e6) * 100, "accent", `${won(P.pension_paid)} / 600만`);
  bar(pr, "연금저축+IRP", (P.eligible / 9e6) * 100, "accent", `${won(P.eligible)} / 900만`);
  const pa = el("div", "alert");
  pa.append(el("span", "", "💡"), el("div", "", `${won(P.room_left)}을 연말까지 더 넣으면 약 ${won(P.room_left * P.rate / 100)}을 더 돌려받습니다.`));
  pb.append(pr, pa);

  // ---------- 거래내역 ----------
  const cats = [...new Set(D.transactions.map((t) => t.category))].sort();
  const sel = $("#cat");
  sel.append(new Option("전체", ""));
  cats.forEach((c) => sel.append(new Option(c, c)));
  const drawTx = () => {
    const q = $("#q").value.trim(), c = sel.value, inc = $("#inc-only").checked;
    const rows = D.transactions.filter((t) => (!q || t.description.includes(q)) && (!c || t.category === c) && (!inc || t.included));
    table($("#tbl-txs"), [
      { key: "date", label: "날짜", left: true }, { key: "description", label: "내용", left: true },
      { key: "category", label: "카테고리", left: true },
      { key: "amount", label: "금액", fmt: (v) => (v > 0 ? "+" : "") + won(v), cls: (v) => (v > 0 ? "good" : "") },
      { key: "included", label: "집계", fmt: (v) => (v ? "포함" : "제외") },
    ], rows, { dim: (r) => !r.included });
  };
  ["#q", "#cat", "#inc-only"].forEach((s) => $(s).addEventListener("input", drawTx));
  drawTx();

  openTab((location.hash || "#summary").slice(1));
})();
