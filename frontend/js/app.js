(function () {
  const api = window.InsureMateAPI;
  const app = document.getElementById("app");
  const state = {
    view: "new",
    reportTab: "fields",
    policyDocument: null,
    hospitalDocument: null,
    policyValidating: false,
    hospitalValidating: false,
    policySeq: 0,
    hospitalSeq: 0,
    policyPreviewUrl: null,
    hospitalPreviewUrl: null,
    analysis: null,
    history: null,
    historyQuery: "",
    loading: false,
    error: null,
    processingError: null,
    assistantMessages: [],
    review: {},
    selectedEvidence: null,
    pollTimer: null
  };
  const stepDescriptions = {
    "Document ingestion and preprocessing": "Preparing document pages and structure.",
    "OCR and visual understanding": "Reading text, tables, and visual layout.",
    "Structured extraction and validation": "Turning evidence into structured fields.",
    Reasoning: "Connecting extracted facts across documents.",
    "Insurance analysis": "Reviewing policy coverage and exclusions.",
    "Evidence and confidence checks": "Linking findings back to source pages."
  };

  const escapeHtml = value => String(value).replace(/[&<>"']/g, character => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
  }[character]));
  const value = (object, keys) => {
    if (!object) return undefined;
    for (const key of keys) if (object[key] !== undefined && object[key] !== null && object[key] !== "") return object[key];
    return undefined;
  };
  const formatSize = bytes => bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  const fileLabel = file => file ? `${file.name} · ${formatSize(file.size)}` : "";
  const notify = message => {
    const toast = document.getElementById("toast");
    toast.textContent = message;
    toast.classList.add("show");
    window.setTimeout(() => toast.classList.remove("show"), 2800);
  };
  const setView = view => {
    if (state.view === view && !state.error && !state.loading) return;
    if (state.pollTimer) {
      clearTimeout(state.pollTimer);
      state.pollTimer = null;
    }
    state.view = view;
    state.error = null;
    render();
    if (location.hash !== `#${view}`) {
      history.replaceState({}, "", `#${view}`);
    }
  };
  const isSupported = file => (file.type === "application/pdf" || file.type.startsWith("image/")) && file.size <= 25 * 1024 * 1024;

  function render() {
    document.querySelectorAll(".nav-item").forEach(item => item.classList.toggle("active", item.dataset.view === state.view));
    const views = { new: renderNew, processing: renderProcessing, report: renderReport, history: renderHistory, assistant: renderAssistant };
    app.innerHTML = (views[state.view] || renderNew)();
  }

  function renderNew() {
    return `<section class="hero page-enter">
      <div class="hero-brand-badge" aria-hidden="true">
        <img class="hero-icon-img dark-logo" src="assets/insuremate-icon-dark.svg" alt="" width="72" height="76">
        <img class="hero-icon-img light-logo" src="assets/insuremate-icon-light.svg" alt="" width="72" height="76">
      </div>
      <p class="eyebrow">New analysis</p>
      <h1>InsureMate</h1>
      <p class="hero-copy">AI-powered medical insurance document understanding and analysis.</p>
      ${state.error ? errorCard(state.error, "retry-upload") : ""}
      <div class="upload-grid ${state.policyDocument && state.hospitalDocument ? "paired" : ""}">
        ${uploadCard("policy", "Policy document", "Insurance policy, claim form")}
        ${uploadCard("hospital", "Hospital document", "Medical bills and reports")}
      </div>
      <div class="upload-action"><span class="required-note">${state.policyDocument && state.hospitalDocument ? "Both documents are ready." : `Add the ${state.policyDocument ? "hospital" : state.hospitalDocument ? "policy" : "policy and hospital"} document${state.policyDocument || state.hospitalDocument ? "" : "s"} to continue.`}</span><button class="button primary" id="analyze-btn" ${state.policyDocument && state.hospitalDocument && !state.loading ? "" : "disabled"}>Analyze <span aria-hidden="true">→</span></button></div>
      <div style="margin-top: 18px; text-align: center;"><button class="text-button" id="demo-btn" type="button" style="font-size: 13px; opacity: 0.85;">⚡ Try with sample health claim documents →</button></div>
      <p class="upload-footnote">PDF documents and scanned documents · Up to 25 MB per document</p>
    </section>`;
  }

  function uploadCard(kind, title, description) {
    const file = state[`${kind}Document`];
    const isValidating = state[`${kind}Validating`];
    const label = kind === "policy" ? "Policy document" : "Hospital document";
    return `<article class="upload-card ${file ? "attached" : ""} ${isValidating ? "validating" : ""}">
      <div class="upload-card-header"><div><span class="eyebrow">${label}</span><h2>${title}</h2><p>${description}</p></div><span class="required-badge">${isValidating ? "Validating…" : file ? "Ready" : "Required"}</span></div>
      <div class="file-drop ${file ? "has-file" : ""} ${isValidating ? "is-loading" : ""}" data-drop="${kind}" tabindex="0">
        ${isValidating ? `<div class="validating-state" style="padding: 14px 0; text-align: center;"><strong style="display:block; margin-bottom: 4px;">Validating ${kind === "policy" ? "policy" : "document"}…</strong><span style="font-size: 12px; opacity: 0.75;">Checking file structure & intelligent content alignment</span></div>` :
          file ? `<div class="attached-file"><span class="file-symbol">${file.type === "application/pdf" ? "PDF" : "IMG"}</span><div><strong>${escapeHtml(file.name)}</strong><span>${formatSize(file.size)}</span></div><button class="remove-file" type="button" data-remove-document="${kind}" aria-label="Remove ${escapeHtml(file.name)}" title="Remove ${escapeHtml(file.name)}">×</button></div>` :
          `<span class="upload-symbol" aria-hidden="true">↑</span><strong>Choose or drop a document</strong><span>PDF, JPG, PNG, or scanned image</span>`}
        <input class="file-input" data-input="${kind}" type="file" accept=".pdf,image/*" aria-label="Choose ${title}" ${file || isValidating ? "disabled" : ""}>
      </div>
      ${state[`${kind}Error`] ? `<p class="inline-error">${escapeHtml(state[`${kind}Error`])}</p>` : ""}
    </article>`;
  }

  function renderProcessing() {
    const steps = value(state.analysis, ["steps", "processing_steps", "status_steps"]);
    if (state.processingError) return `<section class="narrow page-enter">${errorCard(state.processingError, "retry-processing")}</section>`;
    const processingBadge = `<div class="processing-brand-badge" aria-hidden="true"><img class="processing-icon-img dark-logo" src="assets/insuremate-icon-dark.svg" alt="" width="56" height="60"><img class="processing-icon-img light-logo" src="assets/insuremate-icon-light.svg" alt="" width="56" height="60"></div>`;
    if (!Array.isArray(steps)) return `<section class="processing-layout page-enter"><div class="section-intro">${processingBadge}<p class="eyebrow">Processing</p><h1>Understanding your<br><em>documents.</em></h1><p>Loading status from the analysis service.</p></div><div class="processing-workspace"><div class="paper-stage scanning">${paperSheet("policy", state.policyDocument)}${paperSheet("hospital", state.hospitalDocument)}<span class="scan-band" aria-hidden="true"></span></div>${loadingState("Loading processing status…")}</div></section>`;
    return `<section class="processing-layout page-enter"><div class="section-intro">${processingBadge}<p class="eyebrow">Processing</p><h1>Understanding your<br><em>documents.</em></h1><p>Status is reported by the analysis service.</p></div><div class="processing-workspace"><div class="paper-stage scanning">${paperSheet("policy", state.policyDocument)}${paperSheet("hospital", state.hospitalDocument)}<span class="scan-band" aria-hidden="true"></span></div><div class="processing-card" id="processing-steps-card">${renderStepsHtml(steps)}</div></div>${steps.some(step => value(step, ["status", "state"]) === "failed") ? `<button class="button secondary" id="retry-analysis">Retry</button>` : ""}</section>`;
  }

  function renderStepsHtml(steps) {
    if (!Array.isArray(steps)) return "";
    return steps.map(step => {
      const name = value(step, ["name", "step", "title"]) || "";
      const status = value(step, ["status", "state"]) || "unknown";
      const description = value(step, ["description"]) || stepDescriptions[name] || "";
      const err = value(step, ["message", "error"]);
      return `<div class="process-step ${escapeHtml(status)}"><div class="step-marker">${status === "done" ? "✓" : status === "failed" ? "!" : "·"}</div><div><strong>${escapeHtml(name)}</strong><span>${escapeHtml(description)}</span>${status === "failed" && err ? `<small class="inline-error">${escapeHtml(err)}</small>` : ""}</div><span class="step-state">${escapeHtml(status)}</span></div>`;
    }).join("");
  }

  function updateProcessingSteps(steps) {
    const card = document.getElementById("processing-steps-card");
    if (!card || !Array.isArray(steps)) return;
    const html = renderStepsHtml(steps);
    if (card.innerHTML !== html) {
      card.innerHTML = html;
    }
  }
  function paperSheet(kind, file) {
    return `<div class="paper-sheet ${kind}"><span class="sheet-label">${kind === "policy" ? "Policy sheet" : "Hospital sheet"}</span>${file ? `<strong>${escapeHtml(file.name)}</strong><span>${formatSize(file.size)}</span>` : `<span>Document</span>`}</div>`;
  }

  function renderReport() {
    if (state.loading) return loadingState("Loading analysis…");
    if (!state.analysis) return emptyState("Open an analysis from History or start a new analysis.", "New analysis", "new");
    const title = value(state.analysis, ["title", "name", "analysis_id", "id"]);
    const currentTab = (state.reportTab === "warnings" || state.reportTab === "evidence") ? "fields" : (state.reportTab || "fields");
    const tabs = [
      { id: "fields", label: "Extracted fields" },
      { id: "missing", label: "Missing documents" },
      { id: "validity", label: "Validity & dates" },
      { id: "coverage", label: "Coverage summary" }
    ];
    const renderers = {
      fields: renderFields,
      missing: renderMissingDocuments,
      validity: renderValidityDates,
      coverage: renderCoverage
    };
    const activeRenderer = renderers[currentTab] || renderFields;

    return `<section class="report-layout page-enter">
      <div class="report-header">
        <div>
          <p class="eyebrow">Analysis report${title ? ` · ${escapeHtml(title)}` : ""}</p>
          <h1>Document findings,<br><em>clearly presented.</em></h1>
        </div>
        <button class="button secondary" id="download-btn">↓ Download PDF report</button>
      </div>
      ${renderVerdictCard()}
      <div class="segmented" role="tablist">
        ${tabs.map(tab => `<button class="${tab.id === currentTab ? "active" : ""}" data-tab="${tab.id}">${escapeHtml(tab.label)}</button>`).join("")}
      </div>
      <div id="report-panel">${activeRenderer()}</div>
    </section>`;
  }

  function renderVerdictCard() {
    const verdictObj = value(state.analysis, ["verdict"]);
    const rawVerdict = typeof verdictObj === "object" ? verdictObj?.status : verdictObj || value(state.analysis, ["status", "final_status"]);
    const title = (typeof verdictObj === "object" && verdictObj?.title) ? verdictObj.title : (rawVerdict ? String(rawVerdict).replace(/_/g, " ") : "Analysis Completed");
    const isReady = typeof verdictObj === "object" ? Boolean(verdictObj?.is_ready) : (String(rawVerdict).toUpperCase() === "CLAIM_READY_FOR_SUBMISSION");
    const severity = typeof verdictObj === "object" && verdictObj?.severity ? verdictObj.severity : (isReady ? "success" : (String(rawVerdict).toUpperCase().includes("MISSING") ? "warning" : "danger"));
    const badge = (typeof verdictObj === "object" && verdictObj?.badge) ? verdictObj.badge : (isReady ? "Ready For Submission" : (String(rawVerdict).toUpperCase().includes("MISSING") ? "Missing Required Evidence" : "Discrepancy Detected"));
    const summary = (typeof verdictObj === "object" && verdictObj?.summary) ? verdictObj.summary : (value(state.analysis, ["decision_summary"]) || "Policy conditions and submitted claim records have been analyzed for claim admissibility.");

    const missingDocs = getArray(["missing_documents"]);
    const missingCount = missingDocs.filter(d => Boolean(d.missing)).length;
    const validity = value(state.analysis, ["validity"]) || {};
    const pStart = validity.policy_start_date;
    const pEnd = validity.policy_end_date;
    const dateWindowText = (pStart && pEnd && pStart !== "Not specified") ? `${pStart} to ${pEnd}` : null;
    const fieldsCount = getArray(["fields", "extracted_fields"]).length;

    return `<article class="card verdict-card ${severity}">
      <div class="verdict-card-header">
        <div>
          <span class="eyebrow">Analysis result · Claim verdict</span>
          <h2>${escapeHtml(title)}</h2>
        </div>
        <span class="status-badge ${severity}">
          <span class="badge-dot"></span>
          ${escapeHtml(badge)}
        </span>
      </div>
      <p class="verdict-summary">${escapeHtml(summary)}</p>
      <div class="verdict-metrics">
        ${dateWindowText ? `<div class="metric-chip"><span class="chip-label">Policy coverage</span><strong>${escapeHtml(dateWindowText)}</strong></div>` : ""}
        <div class="metric-chip"><span class="chip-label">Mandatory evidence</span><strong class="${missingCount > 0 ? "metric-amber" : "metric-green"}">${missingCount > 0 ? `${missingCount} Missing` : "Complete (0 Missing)"}</strong></div>
        <div class="metric-chip"><span class="chip-label">Dates validation</span><strong class="${validity.valid === false ? "metric-red" : "metric-green"}">${validity.valid === false ? "Discrepancy Detected" : "Within Policy Period"}</strong></div>
        <div class="metric-chip"><span class="chip-label">Verified fields</span><strong>${fieldsCount} Extracted</strong></div>
      </div>
    </article>`;
  }

  function getArray(keys) {
    const result = value(state.analysis, keys);
    return Array.isArray(result) ? result : [];
  }

  function renderFields() {
    const fields = getArray(["fields", "extracted_fields"]);
    if (!fields.length) return emptyPanel("No extracted fields were returned by the analysis.");
    const grouped = fields.reduce((groups, field) => {
      const source = value(field, ["source", "document", "document_name"]) || "Document";
      (groups[source] ||= []).push(field);
      return groups;
    }, {});
    return Object.entries(grouped).map(([source, items]) => `<div class="card table-card field-group"><div class="card-heading"><div><p class="eyebrow">${escapeHtml(source)}</p><h2>Extracted fields</h2></div></div>${items.map(field => {
      const name = value(field, ["name", "label", "field"]) || "";
      const fieldValue = value(field, ["value", "text", "content"]);
      const confidence = value(field, ["confidence", "confidence_score"]);
      const flag = value(field, ["flag", "status", "review_status"]);
      return `<div class="field-row"><span>${escapeHtml(name)}</span><strong>${fieldValue === undefined ? "Not returned" : escapeHtml(fieldValue)}</strong></div>`;
    }).join("")}</div>`).join("");
  }

  function renderMissingDocuments() {
    const items = getArray(["missing_documents"]);
    const summary = value(state.analysis, ["missing_summary"]) || {};
    const missingItems = items.filter(d => Boolean(d.missing));
    const missing = summary.missing_count !== undefined ? summary.missing_count : missingItems.length;

    // IF NOTHING IS MISSING: Do not show any list or table!
    if (missing === 0) {
      return `<div class="card prose-card" style="border-left: 4px solid var(--green);">
        <div class="card-heading">
          <div><p class="eyebrow">Checklist status · Complete</p><h2>All required documents are available</h2></div>
          <span class="status-badge success"><span class="badge-dot"></span>No Missing Evidence Found</span>
        </div>
        <p>All required documents are available. No missing evidence found. All mandatory medical evidence, bills, and discharge records specified by the policy schedule have been verified.</p>
      </div>`;
    }

    // IF THERE ARE MISSING DOCUMENTS: Show the missing evidence summary and table
    const total = summary.total_required !== undefined ? summary.total_required : items.length;
    const present = summary.present_count !== undefined ? summary.present_count : (total - missing);

    return `<div class="panel-stack">
      <div class="summary-chips-row">
        <div class="card summary-mini-card">
          <span class="eyebrow">Required evidence</span>
          <span class="metric-large">${total}</span>
          <span class="metric-sub">Mandatory items</span>
        </div>
        <div class="card summary-mini-card">
          <span class="eyebrow">Submitted & verified</span>
          <span class="metric-large metric-green">${present}</span>
          <span class="metric-sub">Accounted in file</span>
        </div>
        <div class="card summary-mini-card">
          <span class="eyebrow">Action needed</span>
          <span class="metric-large metric-amber">${missing}</span>
          <span class="metric-sub">Missing document${missing > 1 ? "s" : ""}</span>
        </div>
      </div>

      <div class="card table-card">
        <div class="card-heading">
          <div>
            <p class="eyebrow">Action required · Policy checklist</p>
            <h2>List of missing & required documents</h2>
          </div>
          <span class="status-badge warning">
            <span class="badge-dot"></span>
            ${missing} Missing Required
          </span>
        </div>
        <div class="docs-checklist-table">
          <div class="docs-table-head">
            <span>Sr.</span>
            <span>Document Title</span>
            <span>Status</span>
            <span>Page No.</span>
            <span>Policy Clause / Reason</span>
          </div>
          ${missingItems.map((doc, idx) => {
            const sr = value(doc, ["sr_no"]) || (idx + 1);
            const title = value(doc, ["title", "document_title", "document_name"]) || "Required Document";
            const page = value(doc, ["page_number", "page_no", "page"]);
            const reason = value(doc, ["reason", "details"]) || "Mandated by policy schedule";
            return `<div class="docs-table-row row-missing">
              <span class="doc-sr">${escapeHtml(sr)}</span>
              <strong class="doc-title">${escapeHtml(title)}</strong>
              <span>
                <span class="tag tag-missing">
                  ! Missing
                </span>
              </span>
              <span class="doc-page">${page ? `Page ${escapeHtml(page)}` : "—"}</span>
              <span class="doc-reason">${escapeHtml(reason)}</span>
            </div>`;
          }).join("")}
        </div>
      </div>
    </div>`;
  }

  function renderValidityDates() {
    const validity = value(state.analysis, ["validity"]) || {};
    const isValid = validity.valid !== false;
    const pStart = validity.policy_start_date || "Not specified";
    const pEnd = validity.policy_end_date || "Not specified";
    const dates = Array.isArray(validity.dates) ? validity.dates : [];
    const reasons = Array.isArray(validity.reasons) ? validity.reasons : [];

    return `<div class="panel-stack">
      <div class="card validity-banner ${isValid ? "valid" : "invalid"}">
        <div class="validity-banner-top">
          <div>
            <p class="eyebrow">Coverage period validation</p>
            <h2>${isValid ? "Claim Dates Within Policy Window" : "Claim Dates Require Verification"}</h2>
          </div>
          <span class="status-badge ${isValid ? "success" : "danger"}">
            <span class="badge-dot"></span>
            ${isValid ? "Policy In Force" : "Discrepancy"}
          </span>
        </div>
        <div class="validity-dates-summary">
          <div class="date-summary-box">
            <span class="eyebrow">Policy start</span>
            <strong>${escapeHtml(pStart)}</strong>
          </div>
          <div class="date-arrow">→</div>
          <div class="date-summary-box">
            <span class="eyebrow">Policy expiry</span>
            <strong>${escapeHtml(pEnd)}</strong>
          </div>
          <div class="date-status-box">
            <span class="eyebrow">Validation audit</span>
            <strong class="${isValid ? "metric-green" : "metric-red"}">${isValid ? "Pass: Event in Period" : "Fail: Date Mismatch"}</strong>
          </div>
        </div>
      </div>

      <div class="card table-card">
        <div class="card-heading">
          <div>
            <p class="eyebrow">Chronological timeline</p>
            <h2>Document dates & event timeline</h2>
          </div>
        </div>
        ${dates.length ? `
          <div class="docs-checklist-table">
            <div class="docs-table-head dates-table-head">
              <span>Event / Document</span>
              <span>Recorded Date</span>
              <span>Location</span>
              <span>Coverage Check</span>
              <span>Details</span>
            </div>
            ${dates.map(item => {
              const type = value(item, ["type", "document_type", "name"]) || "Document Date";
              const dateVal = value(item, ["date", "normalized_date", "raw_date"]) || "—";
              const details = value(item, ["details", "reason"]) || "";
              let page = value(item, ["page_number", "page", "page_no"]);
              if (!page || page === "—" || page === 1 || page === "1") {
                const match = String(details).match(/\b(?:Page|page)\s*(\d+)\b/);
                if (match && match[1]) {
                  page = match[1];
                }
              }
              const checkValid = item.valid !== false;
              const statusText = value(item, ["status"]) || (checkValid ? "Within Coverage" : "Outside Period");
              return `<div class="docs-table-row dates-table-row">
                <strong>${escapeHtml(type)}</strong>
                <span class="date-badge">${escapeHtml(dateVal)}</span>
                <span>${page ? `Page ${escapeHtml(page)}` : "—"}</span>
                <span>
                  <span class="tag ${checkValid ? "fact" : "tag-danger"}">
                    ${checkValid ? "✓ " : "✕ "}${escapeHtml(statusText)}
                  </span>
                </span>
                <span class="doc-reason">${escapeHtml(details)}</span>
              </div>`;
            }).join("")}
          </div>
        ` : `<div class="empty-panel">No document dates were extracted from submitted files.</div>`}
      </div>

      ${reasons.length ? `
        <div class="card prose-card">
          <div class="card-heading">
            <div><p class="eyebrow">Validation reasoning</p><h2>Audit findings</h2></div>
          </div>
          ${reasons.map(r => `<div class="soft-item"><span class="bullet ${isValid ? "green" : "amber"}"></span><span>${escapeHtml(r)}</span></div>`).join("")}
        </div>
      ` : ""}
    </div>`;
  }

  function renderCoverage() {
    const coverage = value(state.analysis, ["coverage_summary", "coverage"]);
    const exclusions = getArray(["exclusions", "potential_exclusions"]);
    if (coverage === undefined && !exclusions.length) return emptyPanel("No coverage summary was returned by the analysis.");
    return `<div class="panel-grid">
      <div class="card prose-card">
        <div class="card-heading">
          <div><p class="eyebrow">Policy evaluation</p><h2>Coverage terms & clauses</h2></div>
        </div>
        ${coverage !== undefined ? `<p>${escapeHtml(coverage)}</p>` : ""}
        ${exclusions.length ? `<h3>Mandatory requirements & exclusions</h3>${exclusions.map(item => `<div class="soft-item"><span class="bullet amber"></span><span>${escapeHtml(value(item, ["text", "detail", "description"]) || item)}</span></div>`).join("")}` : ""}
      </div>
      <aside class="side-note">
        <div class="mini-icon blue">i</div>
        <h3>Policy interpretation</h3>
        <p>Coverage analysis is verified deterministically against policy clauses and hospital bills.</p>
      </aside>
    </div>`;
  }


  function renderHistory() {
    if (!state.history) return loadingState("Loading history…");
    const items = Array.isArray(state.history) ? state.history : value(state.history, ["items", "analyses", "history"]) || [];
    const sorted = [...items].sort((left, right) => {
      const leftDate = value(left, ["created_at", "date", "updated_at"]);
      const rightDate = value(right, ["created_at", "date", "updated_at"]);
      if (!leftDate || !rightDate) return 0;
      return new Date(rightDate) - new Date(leftDate);
    });
    const filtered = sorted.filter(item => JSON.stringify(item).toLowerCase().includes(state.historyQuery.toLowerCase()));
    return `<section class="history-layout page-enter"><div class="section-intro compact"><p class="eyebrow">History</p><h1>Your analyses.</h1><p>Reopen an analysis stored in the workspace.</p></div>${state.error ? errorCard(state.error, "retry-history") : ""}<div class="history-tools"><input id="history-search" value="${escapeHtml(state.historyQuery)}" placeholder="Search history" aria-label="Search history"><button class="button primary" data-view="new">New analysis</button></div><div class="history-list-container">${!filtered.length ? `<div class="empty-line">No analyses found. <button class="text-button" data-view="new">Start a new analysis</button></div>` : `<div class="history-list">${filtered.map(item => historyRow(item)).join("")}</div>`}</div></section>`;
  }

  function updateHistoryList() {
    const container = document.querySelector(".history-list-container");
    if (!container || !state.history) return;
    const items = Array.isArray(state.history) ? state.history : value(state.history, ["items", "analyses", "history"]) || [];
    const sorted = [...items].sort((left, right) => {
      const leftDate = value(left, ["created_at", "date", "updated_at"]);
      const rightDate = value(right, ["created_at", "date", "updated_at"]);
      if (!leftDate || !rightDate) return 0;
      return new Date(rightDate) - new Date(leftDate);
    });
    const filtered = sorted.filter(item => JSON.stringify(item).toLowerCase().includes(state.historyQuery.toLowerCase()));
    container.innerHTML = !filtered.length 
      ? `<div class="empty-line">No analyses found. <button class="text-button" data-view="new">Start a new analysis</button></div>` 
      : `<div class="history-list">${filtered.map(item => historyRow(item)).join("")}</div>`;
  }
  function historyRow(item) {
    const id = value(item, ["analysis_id", "id"]);
    const name = value(item, ["name", "title", "policy_document_name", "document_name"]);
    const date = value(item, ["created_at", "date", "updated_at"]);
    const status = value(item, ["status", "state"]);
    return `<div class="history-row" data-history-id="${escapeHtml(id || "")}"><span class="history-sheets" aria-hidden="true"><i></i><i></i></span><div>${name || id ? `<strong>${escapeHtml(name || id)}</strong>` : ""}${date ? `<span>${escapeHtml(date)}</span>` : ""}</div>${status ? `<span class="history-status">${escapeHtml(status)}</span>` : ""}${id ? `<button class="delete-history" data-delete-history="${escapeHtml(id)}" aria-label="Delete analysis">×</button>` : ""}</div>`;
  }

  function formatInline(str) {
    return str
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*([^*]+?)\*/g, "<em>$1</em>");
  }

  function formatChatMessage(text) {
    if (!text) return "";
    const safe = escapeHtml(text);
    const paragraphs = safe.split(/\n\s*\n/);
    return paragraphs.map(p => {
      const rawLines = p.split("\n").map(l => l.trim()).filter(Boolean);
      if (!rawLines.length) return "";
      const isList = rawLines.every(l => /^[•\-\*]\s+/.test(l));
      if (isList) {
        return `<ul class="chat-list">${rawLines.map(l => `<li>${formatInline(l.replace(/^[•\-\*]\s+/, ""))}</li>`).join("")}</ul>`;
      }
      return `<p>${rawLines.map(l => formatInline(l)).join("<br>")}</p>`;
    }).join("");
  }

  function renderAssistant() {
    if (!state.analysis) return emptyState("Open an analysis before using the assistant.", "Open History", "history");
    return `<section class="assistant-layout page-enter"><div class="section-intro"><p class="eyebrow">AI document assistant</p><h1>Ask about your<br><em>documents.</em></h1><p>Answers are returned by the analysis service and grounded in the current analysis.</p></div><div class="chat-card"><div class="chat-messages">${state.assistantMessages.length ? state.assistantMessages.map(message => `<div class="message ${message.role}"><span class="message-label">${message.role === "user" ? "You" : "InsureMate"}</span><div class="message-body">${formatChatMessage(message.text || "")}</div></div>`).join("") : `<div class="chat-empty"><p>No conversation has been saved for this analysis.</p></div>`}</div><form id="chat-form" class="chat-input"><input id="chat-question" placeholder="Ask about your documents…" aria-label="Ask the assistant" required><button class="button primary" type="submit">Ask →</button></form></div></section>`;
  }


  function loadingState(text) { return `<section class="loading-state page-enter"><div class="skeleton large"></div><div class="skeleton"></div><div class="skeleton short"></div><p>${escapeHtml(text)}</p></section>`; }
  function emptyState(text, action, view) { return `<section class="empty-state page-enter"><div class="empty-mark">✦</div><p>${escapeHtml(text)}</p><button class="button primary" data-view="${view}">${escapeHtml(action)} →</button></section>`; }
  function emptyPanel(text) { return `<div class="empty-panel">${escapeHtml(text)}</div>`; }
  function errorCard(message, retryId) { return `<div class="error-card" role="alert"><strong>Something needs another try.</strong><p>${escapeHtml(message)}</p><button class="text-button" id="${retryId}">Retry</button></div>`; }

  function removeDocument(kind) {
    state[`${kind}Seq`] = (state[`${kind}Seq`] || 0) + 1;
    state[`${kind}Document`] = null;
    state[`${kind}Error`] = null;
    state[`${kind}Validating`] = false;
    state.error = null;

    if (state[`${kind}PreviewUrl`]) {
      try { URL.revokeObjectURL(state[`${kind}PreviewUrl`]); } catch (_) {}
      state[`${kind}PreviewUrl`] = null;
    }

    const input = document.querySelector(`[data-input="${kind}"]`);
    if (input) {
      input.value = "";
    }

    render();
  }

  function selectEvidence(raw) {
    try {
      state.selectedEvidence = JSON.parse(raw);
      if (state.view === "report" && state.reportTab === "evidence") {
        const panel = document.getElementById("report-panel");
        if (panel) panel.innerHTML = renderEvidence();
      } else {
        openEvidence(raw);
      }
    } catch (_) {
      openEvidence(raw);
    }
  }

  async function attachDocument(kind, file) {
    if (!file) return;
    state[`${kind}Seq`] = (state[`${kind}Seq`] || 0) + 1;
    const currentSeq = state[`${kind}Seq`];
    state[`${kind}Error`] = null;
    state.error = null;

    if (!isSupported(file)) {
      state[`${kind}Error`] = "Choose a PDF or scanned image up to 25 MB.";
      render();
      return;
    }

    state[`${kind}Validating`] = true;
    render();

    try {
      const check = await api.validateDocumentSlot(file, kind);
      if (state[`${kind}Seq`] !== currentSeq) return; // Stale or removed
      if (check && check.valid === false) {
        state[`${kind}Error`] = check.error || `Invalid document for the ${kind === "policy" ? "Policy" : "Hospital"} field.`;
        state[`${kind}Document`] = null;
      } else {
        state[`${kind}Document`] = file;
        state[`${kind}Error`] = null;
      }
    } catch (err) {
      if (state[`${kind}Seq`] !== currentSeq) return; // Stale or removed
      state[`${kind}Error`] = err.message || `Validation error for the ${kind} field.`;
      state[`${kind}Document`] = null;
    } finally {
      if (state[`${kind}Seq`] === currentSeq) {
        state[`${kind}Validating`] = false;
        render();
      }
    }
  }

  async function startAnalysis() {
    if (!state.policyDocument || !state.hospitalDocument) {
      state.error = `Add the ${state.policyDocument ? "hospital" : "policy"} document before analyzing.`;
      render();
      return;
    }

    // Deep content-based pair validation
    try {
      const pairCheck = await api.validateDocumentPair(state.policyDocument, state.hospitalDocument);
      if (pairCheck && pairCheck.valid === false) {
        state.error = pairCheck.error || "Document role mismatch or swapped document pair detected.";
        render();
        return;
      }
    } catch (err) {
      console.warn("Pair validation check:", err);
    }

    state.loading = true; state.processingError = null; state.error = null; state.reportTab = "fields"; setView("processing");
    try {
      state.analysis = await api.uploadAndAnalyze(state.policyDocument, state.hospitalDocument);
      state.loading = false;
      render();
      await pollAnalysis();
    }
    catch (error) { state.loading = false; state.error = error.message; setView("new"); }
  }

  async function loadSampleAnalysis() {
    state.loading = true; state.processingError = null; state.error = null; state.reportTab = "fields"; setView("processing");
    try {
      state.analysis = await api.createDemoAnalysis();
      state.loading = false;
      render();
      await pollAnalysis();
    }
    catch (error) { state.loading = false; state.error = error.message; setView("new"); }
  }

  async function pollAnalysis() {
    if (state.pollTimer) {
      clearTimeout(state.pollTimer);
      state.pollTimer = null;
    }
    if (state.view !== "processing") return;

    const id = value(state.analysis, ["analysis_id", "id"]);
    if (!id) {
      state.processingError = "The analysis identifier was not returned by the service.";
      render();
      return;
    }

    try {
      state.analysis = await api.getAnalysis(id);
      if (state.view !== "processing") return;

      const status = value(state.analysis, ["status", "state"]);
      const steps = value(state.analysis, ["steps", "processing_steps", "status_steps"]);

      if (status === "failed" || (Array.isArray(steps) && steps.some(step => value(step, ["status", "state"]) === "failed"))) {
        state.processingError = value(state.analysis, ["error", "message"]) || "The analysis could not be completed.";
        render();
        return;
      }

      if (status && ["completed", "complete", "done", "ready"].includes(String(status).toLowerCase())) {
        setView("report");
        return;
      }

      // In-place steps update stops blinking and keeps scanning animation running smoothly
      const stepsCard = document.getElementById("processing-steps-card");
      if (stepsCard) {
        updateProcessingSteps(steps);
      } else {
        render();
      }

      if (state.view === "processing") {
        state.pollTimer = window.setTimeout(pollAnalysis, 1000);
      }
    } catch (error) {
      if (state.view === "processing") {
        state.processingError = error.message;
        render();
      }
    }
  }

  async function loadHistory() {
    state.history = null; state.error = null; render();
    try { state.history = await api.listHistory(); render(); } catch (error) { state.error = error.message; state.history = []; render(); }
  }

  async function openHistoryItem(id) {
    if (!id) return;
    state.loading = true;
    state.reportTab = "fields";
    state.view = "report";
    render();
    try {
      state.analysis = await api.getHistoryItem(id);
      state.assistantMessages = value(state.analysis, ["assistant_conversation", "conversation", "messages"]) || [];
      state.review = value(state.analysis, ["review"]) || {};
      state.loading = false;
      render();
    } catch (error) {
      state.loading = false;
      state.error = error.message;
      render();
    }
  }

  async function deleteHistory(id) {
    if (!id || !window.confirm("Delete this analysis from History?")) return;
    try { await api.deleteHistoryItem(id); notify("Analysis deleted."); loadHistory(); } catch (error) { state.error = error.message; render(); }
  }

  async function askAssistant() {
    const input = document.getElementById("chat-question"); const question = input ? input.value.trim() : ""; const id = value(state.analysis, ["analysis_id", "id"]);
    if (!question || !id) return;
    state.assistantMessages.push({ role: "user", text: question }); render();
    try { const answer = await api.askAssistant(id, question); state.assistantMessages.push({ role: "assistant", text: value(answer, ["answer", "text", "message"]) || "" }); render(); }
    catch (error) { notify(error.message); }
  }

  async function saveReview(key, status) {
    const id = value(state.analysis, ["analysis_id", "id"]); state.review[key] = status; render();
    try { state.review = await api.saveReview(id, state.review) || state.review; } catch (error) { notify(error.message); }
  }

  async function downloadReport() {
    const id = value(state.analysis, ["analysis_id", "id"]);
    if (!id) return;
    try {
      const blob = await api.downloadReport(id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `insuremate-report-${id}.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) {
      notify(error.message);
    }
  }

  function openEvidence(raw) {
    let item; try { item = JSON.parse(raw); } catch (_) { item = {}; }
    const source = value(item, ["source", "document", "document_name"]) || "";
    const page = value(item, ["page", "page_number"]);
    const text = value(item, ["text", "detail", "excerpt", "highlight"]) || "";
    const panel = document.createElement("aside");
    panel.className = "evidence-drawer";
    panel.innerHTML = `<div class="drawer-backdrop" data-close></div><div class="drawer-panel"><div class="drawer-header"><div><p class="eyebrow">Supporting evidence</p><h2>${escapeHtml(source)}</h2></div><button class="icon-button" data-close aria-label="Close evidence panel">×</button></div><div class="evidence-preview">${page ? `<span>Page ${escapeHtml(page)}</span>` : ""}<div class="preview-paper">${text ? `<mark>${escapeHtml(text)}</mark>` : "No preview text was returned."}</div></div></div>`;
    document.body.appendChild(panel);
    panel.querySelectorAll("[data-close]").forEach(el => el.addEventListener("click", () => panel.remove()));
  }

  function initEventListeners() {
    // 1. Static Topbar Navigation Buttons (outside #app, bound once)
    document.querySelectorAll(".topbar [data-view]").forEach(item => {
      item.addEventListener("click", () => {
        const v = item.dataset.view;
        if (v === "history" && !state.history) loadHistory();
        setView(v);
      });
    });

    // 2. Hash change navigation (browser back/forward & brand logo)
    window.addEventListener("hashchange", () => {
      const h = location.hash.slice(1);
      if (h === "review") {
        location.hash = "#report";
        return;
      }
      if (["new", "report", "history", "assistant"].includes(h)) {
        if (state.view !== h) {
          if (h === "history" && !state.history) loadHistory();
          setView(h);
        }
      }
    });

    // 3. Delegated Click Listener on #app (handles dynamically rendered content without leaking listeners)
    app.addEventListener("click", event => {
      // Remove file button
      const removeBtn = event.target.closest("[data-remove-document]");
      if (removeBtn) {
        event.stopPropagation();
        event.preventDefault();
        removeDocument(removeBtn.dataset.removeDocument);
        return;
      }

      // In-page view links (e.g. empty states, hero button)
      const viewBtn = event.target.closest("[data-view]");
      if (viewBtn) {
        event.stopPropagation();
        const v = viewBtn.dataset.view;
        if (v === "history" && !state.history) loadHistory();
        setView(v);
        return;
      }

      // Analyze button
      const analyzeBtn = event.target.closest("#analyze-btn");
      if (analyzeBtn && !analyzeBtn.disabled) {
        startAnalysis();
        return;
      }

      // Demo analysis
      if (event.target.closest("#demo-btn")) {
        loadSampleAnalysis();
        return;
      }

      // Retry actions
      if (event.target.closest("#retry-upload")) {
        state.error = null;
        render();
        return;
      }
      if (event.target.closest("#retry-processing") || event.target.closest("#retry-analysis")) {
        pollAnalysis();
        return;
      }
      if (event.target.closest("#retry-history")) {
        loadHistory();
        return;
      }

      // Download PDF report
      if (event.target.closest("#download-btn")) {
        downloadReport();
        return;
      }

      // Report tab switching
      const tabBtn = event.target.closest("[data-tab]");
      if (tabBtn) {
        state.reportTab = tabBtn.dataset.tab;
        document.querySelectorAll("[data-tab]").forEach(tab => tab.classList.remove("active"));
        tabBtn.classList.add("active");
        const renderers = {
          fields: renderFields,
          missing: renderMissingDocuments,
          validity: renderValidityDates,
          coverage: renderCoverage
        };
        const renderer = renderers[tabBtn.dataset.tab] || renderFields;
        const panel = document.getElementById("report-panel");
        if (panel) panel.innerHTML = renderer();
        return;
      }

      // Evidence chips
      const evidenceBtn = event.target.closest("[data-evidence]");
      if (evidenceBtn) {
        selectEvidence(evidenceBtn.dataset.evidence);
        return;
      }

      // Delete history item
      const deleteHistBtn = event.target.closest("[data-delete-history]");
      if (deleteHistBtn) {
        event.stopPropagation();
        deleteHistory(deleteHistBtn.dataset.deleteHistory);
        return;
      }

      // Open history item
      const historyRow = event.target.closest("[data-history-id]");
      if (historyRow) {
        openHistoryItem(historyRow.dataset.historyId);
        return;
      }


    });

    // 4. Delegated Change Listener for File Inputs
    app.addEventListener("change", event => {
      const input = event.target.closest("[data-input]");
      if (input) {
        const file = input.files && input.files[0];
        input.value = "";
        if (file) attachDocument(input.dataset.input, file);
      }
    });

    // 5. Delegated Input Listener for History Search
    app.addEventListener("input", event => {
      if (event.target.id === "history-search") {
        state.historyQuery = event.target.value;
        updateHistoryList();
      }
    });

    // 6. Delegated Submit Listener for Assistant Chat
    app.addEventListener("submit", event => {
      if (event.target.id === "chat-form") {
        event.preventDefault();
        askAssistant();
      }
    });

    // 7. Delegated Drag and Drop Events on #app
    app.addEventListener("dragover", event => {
      const zone = event.target.closest("[data-drop]");
      if (zone && !zone.classList.contains("has-file") && !zone.classList.contains("is-loading")) {
        event.preventDefault();
        zone.classList.add("dragging");
      }
    });

    app.addEventListener("dragleave", event => {
      const zone = event.target.closest("[data-drop]");
      if (zone) zone.classList.remove("dragging");
    });

    app.addEventListener("drop", event => {
      const zone = event.target.closest("[data-drop]");
      if (zone) {
        event.preventDefault();
        zone.classList.remove("dragging");
        if (!zone.classList.contains("has-file") && !zone.classList.contains("is-loading")) {
          const file = event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files[0];
          if (file) attachDocument(zone.dataset.drop, file);
        }
      }
    });

    app.addEventListener("keydown", event => {
      if (event.key === "Enter" || event.key === " ") {
        const zone = event.target.closest("[data-drop]");
        if (zone && !zone.classList.contains("has-file") && !zone.classList.contains("is-loading")) {
          zone.querySelector("input")?.click();
        }
      }
    });
  }

  // Theme toggle
  const updateThemeButton = () => {
    const btn = document.getElementById("theme-toggle");
    if (!btn) return;
    const isDark = document.documentElement.dataset.theme === "dark";
    btn.textContent = isDark ? "☼" : "☾";
    btn.setAttribute("aria-label", isDark ? "Switch to light theme" : "Switch to dark theme");
    btn.setAttribute("title", isDark ? "Switch to light theme" : "Switch to dark theme");
  };
  document.getElementById("theme-toggle").addEventListener("click", () => {
    document.documentElement.dataset.theme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    updateThemeButton();
  });
  updateThemeButton();

  // Initialize
  initEventListeners();
  const initialView = location.hash.slice(1);
  if (initialView === "review") {
    location.hash = "#report";
  }
  if (["new", "report", "history", "assistant"].includes(initialView)) {
    state.view = initialView;
    if (initialView === "history") loadHistory();
  }
  render();
})();
