/* CareerSync dashboard — vanilla ES2020, no build step, no external deps. */

const STAGES = [
  { key: "Leads", states: ["DISCOVERED", "INTERESTED"] },
  { key: "Applied", states: ["APPLIED"] },
  { key: "Assessment", states: ["ASSESSMENT"] },
  { key: "Interview", states: ["INTERVIEW"] },
  { key: "Offer", states: ["OFFER_SELECTED"] },
  { key: "Closed", states: ["REJECTED", "WITHDRAWN", "EXPIRED"] },
];

const LIFECYCLE_STATES = [
  "DISCOVERED", "INTERESTED", "APPLIED", "ASSESSMENT", "INTERVIEW",
  "OFFER_SELECTED", "REJECTED", "WITHDRAWN", "EXPIRED",
];

const $ = (id) => document.getElementById(id);

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[ch]));
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    let detail = response.statusText;
    try { detail = (await response.json()).detail || detail; } catch (_) { /* ignore */ }
    throw new Error(detail);
  }
  return response.status === 204 ? null : response.json();
}

function toast(message, isError = false) {
  const el = $("toast");
  el.textContent = message;
  el.classList.toggle("error", isError);
  el.classList.remove("hidden");
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => el.classList.add("hidden"), 3200);
}

function fmtDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString();
}

/* ------------------------------------------------------------------ render */

function renderStats(applications, reviews, proposals, opportunities) {
  $("stat-active").textContent = applications.length;
  $("stat-review").textContent = reviews.length;
  $("stat-calendar").textContent = proposals.filter((p) => p.status === "PENDING").length;
  $("stat-opportunities").textContent = opportunities.length;
}

function renderBoard(applications) {
  const board = $("board");
  board.innerHTML = STAGES.map((stage) => {
    const cards = applications.filter((a) => stage.states.includes(a.current_state));
    return `
      <div class="column">
        <div class="column-head"><span>${esc(stage.key)}</span>
          <span class="column-count">${cards.length}</span></div>
        <div class="column-body">
          ${cards.map(cardHtml).join("") || '<div class="empty">No applications</div>'}
        </div>
      </div>`;
  }).join("");

  board.querySelectorAll("[data-app-id]").forEach((card) => {
    card.addEventListener("click", () => openTimeline(card.dataset.appId));
  });
}

function cardHtml(app) {
  return `
    <article class="card" data-app-id="${esc(app.id)}" title="View timeline">
      <h3>${esc(app.company_name)}</h3>
      <p class="role">${esc(app.job_title)}</p>
      <div class="meta">
        <span class="state-badge state-${esc(app.current_state)}">${esc(app.current_state)}</span>
        <span class="muted">${esc(app.review_status === "NEEDS_REVIEW" ? "review" : app.platform || "")}</span>
      </div>
    </article>`;
}

function renderReviews(reviews) {
  $("review-count").textContent = reviews.length;
  $("review-list").innerHTML = reviews.length
    ? reviews.map((app) => `
        <li class="list-item">
          <div class="title">${esc(app.company_name)} — ${esc(app.job_title)}</div>
          <div class="sub">Current state ${esc(app.current_state)} · needs human confirmation</div>
          <div class="actions">
            <button class="btn btn-sm btn-primary" data-resolve="${esc(app.id)}">Resolve</button>
            <button class="btn btn-sm" data-app-id="${esc(app.id)}">Timeline</button>
          </div>
        </li>`).join("")
    : '<li class="empty">Nothing awaiting review.</li>';

  $("review-list").querySelectorAll("[data-resolve]").forEach((btn) =>
    btn.addEventListener("click", () => openResolve(btn.dataset.resolve)));
  $("review-list").querySelectorAll("[data-app-id]").forEach((btn) =>
    btn.addEventListener("click", () => openTimeline(btn.dataset.appId)));
}

function renderCalendar(proposals) {
  $("calendar-count").textContent = proposals.length;
  $("calendar-list").innerHTML = proposals.length
    ? proposals.map((proposal) => `
        <li class="list-item">
          <div class="title">${esc(proposal.title)}</div>
          <div class="sub">${esc(proposal.event_type)} · ${fmtDate(proposal.start_at)} ·
            <span class="state-badge">${esc(proposal.status)}</span></div>
          ${proposal.status === "PENDING" ? `
            <div class="actions">
              <button class="btn btn-sm btn-primary" data-approve="${esc(proposal.id)}">Approve &amp; add</button>
              <button class="btn btn-sm btn-danger" data-reject="${esc(proposal.id)}">Reject</button>
            </div>` : ""}
        </li>`).join("")
    : '<li class="empty">No calendar proposals.</li>';

  $("calendar-list").querySelectorAll("[data-approve]").forEach((btn) =>
    btn.addEventListener("click", () => decideProposal(btn.dataset.approve, "approve")));
  $("calendar-list").querySelectorAll("[data-reject]").forEach((btn) =>
    btn.addEventListener("click", () => decideProposal(btn.dataset.reject, "reject")));
}

function renderOpportunities(opportunities) {
  $("opportunity-list").innerHTML = opportunities.length
    ? opportunities.map((opp) => `
        <li class="list-item">
          <div class="title">${esc(opp.company_name)}</div>
          <div class="sub">${esc(opp.job_title)} · ${esc(opp.platform || "Unknown")}</div>
        </li>`).join("")
    : '<li class="empty">No leads discovered yet.</li>';
}

/* ------------------------------------------------------------------ actions */

async function decideProposal(proposalId, action) {
  try {
    await api(`/calendar/proposals/${proposalId}/${action}`, {
      method: "POST",
      body: JSON.stringify({ note: action === "reject" ? "Rejected from dashboard." : "" }),
    });
    toast(action === "approve" ? "Calendar event created." : "Proposal rejected.");
    await loadAll();
  } catch (error) {
    toast(`Failed: ${error.message}`, true);
  }
}

async function proposeEvent(applicationId) {
  try {
    await api(`/applications/${applicationId}/calendar/propose`, {
      method: "POST",
      body: JSON.stringify({}),
    });
    toast("Calendar proposal staged — approve it in the sidebar.");
    await loadAll();
  } catch (error) {
    toast(`Failed: ${error.message}`, true);
  }
}

function openModal(title, bodyHtml, footHtml = "") {
  $("modal-title").textContent = title;
  $("modal-body").innerHTML = bodyHtml;
  $("modal-foot").innerHTML = footHtml;
  $("modal").classList.remove("hidden");
}

function closeModal() { $("modal").classList.add("hidden"); }

async function openTimeline(applicationId) {
  try {
    const [app, transitions] = await Promise.all([
      api(`/applications/${applicationId}`),
      api(`/applications/${applicationId}/transitions`),
    ]);
    const timeline = transitions.length
      ? `<ul class="timeline">${transitions.map((t) => `
          <li>
            <div class="t-state">${esc(t.previous_state)} → ${esc(t.new_state)}
              <span class="state-badge">${esc(t.review_status)}</span></div>
            <div class="t-meta">${fmtDate(t.timestamp)} · msg ${esc(t.triggering_message_id)}</div>
            <div class="t-meta">${esc(t.reasoning || "")}</div>
          </li>`).join("")}</ul>`
      : '<div class="empty">No transitions recorded.</div>';

    openModal(
      `${app.company_name} — ${app.job_title}`,
      `<p class="muted">State: <span class="state-badge state-${esc(app.current_state)}">${esc(app.current_state)}</span>
        · Review: ${esc(app.review_status)} · Platform: ${esc(app.platform || "Unknown")}</p>${timeline}`,
      `<button class="btn btn-primary" id="propose-btn" type="button">Propose calendar event</button>`,
    );
    $("propose-btn").addEventListener("click", async () => {
      await proposeEvent(applicationId);
      closeModal();
    });
  } catch (error) {
    toast(`Failed: ${error.message}`, true);
  }
}

function openResolve(applicationId) {
  const options = LIFECYCLE_STATES.map((s) => `<option value="${s}">${s}</option>`).join("");
  openModal(
    "Resolve human review",
    `<div class="field"><label for="confirmed-state">Confirmed lifecycle state</label>
      <select id="confirmed-state">${options}</select></div>
     <div class="field"><label for="review-note">Reviewer note</label>
      <input id="review-note" type="text" placeholder="Optional note" /></div>`,
    `<button class="btn" id="resolve-cancel" type="button">Cancel</button>
     <button class="btn btn-primary" id="resolve-submit" type="button">Confirm state</button>`,
  );
  $("resolve-cancel").addEventListener("click", closeModal);
  $("resolve-submit").addEventListener("click", async () => {
    try {
      await api(`/reviews/${applicationId}/resolve`, {
        method: "POST",
        body: JSON.stringify({
          confirmed_state: $("confirmed-state").value,
          note: $("review-note").value,
        }),
      });
      toast("Review resolved.");
      closeModal();
      await loadAll();
    } catch (error) {
      toast(`Failed: ${error.message}`, true);
    }
  });
}

/* ------------------------------------------------------------------ bootstrap */

async function loadAll() {
  try {
    const [applications, reviews, proposals, opportunities] = await Promise.all([
      api("/applications"),
      api("/reviews"),
      api("/calendar/proposals"),
      api("/opportunities"),
    ]);
    renderStats(applications, reviews, proposals, opportunities);
    renderBoard(applications);
    renderReviews(reviews);
    renderCalendar(proposals);
    renderOpportunities(opportunities);

    const pill = $("connection");
    pill.textContent = "live";
    pill.classList.remove("pill-offline");
    pill.classList.add("pill-online");
  } catch (error) {
    const pill = $("connection");
    pill.textContent = "offline";
    pill.classList.add("pill-offline");
    toast(`API unreachable: ${error.message}`, true);
  }
}

$("refresh").addEventListener("click", loadAll);
$("modal-close").addEventListener("click", closeModal);
$("modal").addEventListener("click", (event) => {
  if (event.target === $("modal")) closeModal();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeModal();
});

loadAll();
