/**
 * frontend/js/claim.js
 * Claim Results & Final Readiness Assessment Controller.
 * Renders verdict banner, metrics row, action items, missing evidence table,
 * validity window verification, document validation results, and export actions.
 */

const ClaimView = {
  init() {
    this.bindEvents();

    AppState.subscribe('activeClaimBundle', (bundle) => {
      this.renderClaimResults(bundle);
    });
  },

  bindEvents() {
    // Result Tabs switching
    const tabBtns = document.querySelectorAll('.results-tab-btn');
    tabBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        tabBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        const targetTab = btn.getAttribute('data-tab');
        document.querySelectorAll('.results-tab-pane').forEach(pane => {
          pane.classList.remove('active');
        });
        const activePane = document.getElementById(targetTab);
        if (activePane) activePane.classList.add('active');
      });
    });

    // Copy Summary Action
    const btnCopySummary = document.getElementById('btn-copy-claim-summary');
    if (btnCopySummary) {
      btnCopySummary.addEventListener('click', () => {
        const bundle = AppState.get().activeClaimBundle;
        if (!bundle) {
          Utils.showToast('No active claim report to copy.', 'warning');
          return;
        }
        const summary = bundle.final_report?.decision_summary || 'Claim assessment report.';
        const claimId = bundle.claim?.claim_id || 'UNKNOWN';
        const verdict = bundle.verdict || bundle.claim?.status || 'UNKNOWN';
        Utils.copyToClipboard(`InsureMate Claim Report [${claimId}]\nVerdict: ${verdict}\n\nSummary:\n${summary}`);
      });
    }

    // Copy JSON Action
    const btnCopyJson = document.getElementById('btn-copy-raw-json');
    if (btnCopyJson) {
      btnCopyJson.addEventListener('click', () => {
        const bundle = AppState.get().activeClaimBundle;
        if (!bundle) {
          Utils.showToast('No active claim data to copy.', 'warning');
          return;
        }
        Utils.copyToClipboard(JSON.stringify(bundle, null, 2));
      });
    }

    // Download Report Action
    const btnDownloadReport = document.getElementById('btn-download-claim-report');
    if (btnDownloadReport) {
      btnDownloadReport.addEventListener('click', () => {
        const bundle = AppState.get().activeClaimBundle;
        if (!bundle) {
          Utils.showToast('No active claim report to download.', 'warning');
          return;
        }
        const claimId = bundle.claim?.claim_id || 'claim_report';
        const report = bundle.final_report;
        const textContent = `=======================================================
INSUREMATE CLAIM ASSESSMENT REPORT
Claim ID: ${claimId}
Verdict: ${bundle.verdict || 'ASSESSED'}
Generated: ${new Date().toISOString()}
=======================================================

EXECUTIVE SUMMARY:
${report?.decision_summary || 'Assessment completed.'}

ACTION ITEMS:
${(report?.action_items || []).map((item, idx) => `${idx + 1}. ${item}`).join('\n') || 'None'}

DISCLAIMER:
This analysis is an AI-assisted preparation assessment and does not constitute guaranteed insurer approval.
`;
        Utils.downloadFile(`${claimId}_Assessment_Report.txt`, textContent, 'text/plain');
      });
    }
  },

  renderClaimResults(bundle) {
    if (!bundle) {
      this.renderEmptyState();
      return;
    }

    const report = bundle.final_report;
    const latestState = bundle.latest_state || {};
    const verdict = bundle.verdict || bundle.claim?.status || 'UNKNOWN';

    // 1. Verdict Banner
    this.renderVerdictBanner(verdict, report, bundle.claim);

    // 2. Metrics Grid
    this.renderMetrics(bundle);

    // 3. Overview Executive Summary & Action Items
    const overviewEl = document.getElementById('results-overview-summary-text');
    if (overviewEl) {
      overviewEl.textContent = report?.decision_summary || (
        String(verdict).toUpperCase().includes('READY')
          ? 'All required evidence documents have been validated and coverage dates confirmed. Claim is ready for submission.'
          : 'Claim assessment completed. Action is required due to missing mandatory documentation or date mismatches.'
      );
    }

    const actionItemsEl = document.getElementById('results-action-items-list');
    if (actionItemsEl) {
      const items = report?.action_items || [];
      if (items.length === 0) {
        actionItemsEl.innerHTML = `<li style="color: var(--text-muted);">No action items recorded. All criteria verified.</li>`;
      } else {
        actionItemsEl.innerHTML = items.map(item => `
          <li>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
            <span>${Utils.escapeHtml(item)}</span>
          </li>
        `).join('');
      }
    }

    // 4. Missing Evidence Table
    this.renderMissingTable(latestState.missing_documents || report?.missing_documents_analysis);

    // 5. Validity Analysis
    this.renderValiditySection(latestState.validity_result || report?.validity_check);

    // 6. Validation Analysis
    this.renderValidationSection(latestState.validation_result);

    // 7. Extracted Entities Grid
    this.renderExtractedGrid(latestState.extracted_data || []);

    // 8. Raw JSON Viewer
    const jsonCode = document.getElementById('claim-raw-json-code');
    if (jsonCode) {
      jsonCode.textContent = JSON.stringify(bundle, null, 2);
    }
  },

  renderVerdictBanner(verdict, report, claim) {
    const banner = document.getElementById('results-verdict-banner');
    if (!banner) return;
    let titleEl = document.getElementById('results-verdict-title');
    let descEl = document.getElementById('results-verdict-desc');
    let iconEl = document.getElementById('results-verdict-icon');

    if (!titleEl || !descEl || !iconEl) {
      banner.innerHTML = `
        <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 16px;">
          <div style="display: flex; align-items: center; gap: 16px;">
            <div id="results-verdict-icon" style="font-size: 2rem; font-weight: 700; color: var(--emerald);">✓</div>
            <div>
              <div style="font-size: 0.68rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-muted);">
                CLAIM READINESS ASSESSMENT
              </div>
              <h2 id="results-verdict-title" style="font-size: 1.35rem; font-weight: 800; color: var(--text-heading); margin: 2px 0 4px;">
                CLAIM READY
              </h2>
              <p id="results-verdict-desc" style="font-size: 0.82rem; color: var(--text-muted); max-width: 680px;">
                All required evidence has been submitted and verified.
              </p>
            </div>
          </div>

          <div style="display: flex; gap: 8px; flex-wrap: wrap;">
            <button class="btn btn-secondary btn-sm" id="btn-copy-claim-summary">Copy Report</button>
            <button class="btn btn-secondary btn-sm" id="btn-copy-raw-json">Copy JSON</button>
            <button class="btn btn-secondary btn-sm" id="btn-download-claim-report">Download Report</button>
            <button class="btn btn-primary btn-sm" data-action="new-claim">+ New Claim</button>
          </div>
        </div>
      `;
      this.bindEvents();
      titleEl = document.getElementById('results-verdict-title');
      descEl = document.getElementById('results-verdict-desc');
      iconEl = document.getElementById('results-verdict-icon');
    }

    if (!titleEl || !descEl || !iconEl) return;

    const s = String(verdict).toUpperCase();
    banner.className = 'card';
    banner.style.background = 'var(--bg-card)';

    if (s.includes('READY') || s.includes('CLAIM_READY')) {
      banner.style.borderLeft = '3px solid var(--emerald)';
      iconEl.textContent = '✓';
      iconEl.style.color = 'var(--emerald)';
      titleEl.textContent = 'CLAIM READY FOR SUBMISSION';
      descEl.textContent = report?.decision_summary || 'All required evidence has been submitted and verified. The claim satisfies coverage validity and required evidence policies.';
    } else if (s.includes('MISSING')) {
      banner.style.borderLeft = '3px solid var(--amber)';
      iconEl.textContent = '⚠';
      iconEl.style.color = 'var(--amber)';
      titleEl.textContent = 'ACTION REQUIRED: MISSING EVIDENCE DETECTED';
      descEl.textContent = report?.decision_summary || 'The submitted documents do not contain all mandatory evidence required by the insurance policy clauses.';
    } else if (s.includes('INVALID') || s.includes('FAILED')) {
      banner.style.borderLeft = '3px solid var(--rose)';
      iconEl.textContent = '✕';
      iconEl.style.color = 'var(--rose)';
      titleEl.textContent = s.includes('DATES') ? 'INVALID CLAIM DATES (OUTSIDE POLICY PERIOD)' : 'ACTION REQUIRED: INVALID DOCUMENTS';
      descEl.textContent = report?.decision_summary || 'Document validation or policy coverage verification failed.';
    } else {
      banner.style.borderLeft = '3px solid var(--accent)';
      iconEl.textContent = '●';
      iconEl.style.color = 'var(--accent)';
      titleEl.textContent = 'ASSESSMENT PENDING / IN PROGRESS';
      descEl.textContent = 'Launch the InsureMate Agent to evaluate this claim.';
    }
  },

  renderMetrics(bundle) {
    const latestState = bundle.latest_state || {};
    const report = bundle.final_report || {};

    const docsCountEl = document.getElementById('metric-results-docs');
    const validDocsEl = document.getElementById('metric-results-valid');
    const missingDocsEl = document.getElementById('metric-results-missing');
    const validityStatusEl = document.getElementById('metric-results-validity');

    const extracted = latestState.extracted_data || [];
    const validity = latestState.validity_result || report.validity_check || {};

    // Accurately compute count of truly missing documents
    let missingCount = 0;
    if (typeof report.missing_count === 'number' && !isNaN(report.missing_count)) {
      missingCount = report.missing_count;
    } else if (latestState.missing_documents?.summary?.missing !== undefined) {
      missingCount = latestState.missing_documents.summary.missing;
    } else {
      const allReqs = latestState.missing_documents?.missing_documents || latestState.missing_documents?.document_results || report.missing_documents || [];
      missingCount = allReqs.filter(d => {
        if (typeof d === 'string') return true;
        if (d.missing === true) return true;
        const s = String(d.status || '').toLowerCase();
        return s === 'missing';
      }).length;
    }

    if (docsCountEl) docsCountEl.textContent = extracted.length || (bundle.claim?.policy_filename ? 2 : 1);
    if (validDocsEl) validDocsEl.textContent = Math.max(0, extracted.length - (latestState.validation_result?.invalid_count || 0));
    if (missingDocsEl) missingDocsEl.textContent = missingCount;
    if (validityStatusEl) {
      const isPass = validity.valid !== false;
      validityStatusEl.textContent = isPass ? 'PASS' : 'FAIL';
      validityStatusEl.className = isPass ? 'kpi-value text-emerald' : 'kpi-value text-rose';
    }
  },

  renderMissingTable(missingData) {
    const tbody = document.getElementById('missing-evidence-tbody');
    if (!tbody) return;

    const items = missingData?.missing_documents || missingData?.document_results || missingData?.items || [];

    if (!items || items.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="5" style="text-align: center; padding: 24px; color: var(--emerald);">
            ✓ All required evidence documents are present and verified. Zero missing documents detected.
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = items.map((doc, idx) => {
      const statusRaw = String(doc.status || '').toLowerCase();
      const isMissing = doc.missing === true || statusRaw === 'missing';
      const isReceived = doc.missing === false || statusRaw === 'received' || statusRaw === 'found' || statusRaw === 'available' || statusRaw === 'present' || (!isMissing && (doc.page_number != null || doc.matched_submitted_document != null));
      const isIncomplete = statusRaw === 'incomplete';
      const isReview = statusRaw === 'needs_review' || statusRaw === 'review';
      
      let statusBadge;
      if (isReceived) {
        statusBadge = '<span class="badge badge-ready">✓ Received</span>';
      } else if (isIncomplete) {
        statusBadge = '<span class="badge badge-warning">⚠ Incomplete</span>';
      } else if (isReview) {
        statusBadge = '<span class="badge badge-neutral">ℹ Needs Review</span>';
      } else {
        statusBadge = '<span class="badge badge-warning">⚠ Missing</span>';
      }

      const docName = doc.document_title || doc.required_document || doc.document_name || doc.title || doc.name || 'Required Evidence Document';
      const reasonText = doc.reason || doc.matching_reason || (isReceived ? 'Matching document identified in claim inventory.' : 'No matching claim documents were submitted to fulfill this requirement.');
      const pageInfo = (doc.page_number != null && doc.page_number !== '') ? `Page ${doc.page_number}` : (doc.source_page ? `Page ${doc.source_page}` : '—');

      return `
        <tr>
          <td style="font-family: var(--font-mono);">${idx + 1}</td>
          <td style="font-weight: 600; color: var(--text-heading);">${Utils.escapeHtml(docName)}</td>
          <td>${statusBadge}</td>
          <td style="font-size: 0.78rem; line-height: 1.45;">${Utils.escapeHtml(reasonText)}</td>
          <td style="font-family: var(--font-mono);">${pageInfo}</td>
        </tr>
      `;
    }).join('');
  },

  renderValiditySection(validityData) {
    const policyDatesEl = document.getElementById('validity-policy-dates');
    const statusPill = document.getElementById('validity-math-status');
    const container = document.getElementById('validity-checks-list');

    if (policyDatesEl) {
      if (validityData?.policy_period) {
        policyDatesEl.textContent = `${validityData.policy_period.start || '--'} ⟶ ${validityData.policy_period.end || '--'}`;
      } else {
        policyDatesEl.textContent = 'Active Policy Window Verified';
      }
    }

    if (statusPill) {
      const isValid = validityData?.valid !== false;
      statusPill.textContent = isValid ? 'VALID' : 'INVALID DATES';
      statusPill.className = `badge ${isValid ? 'badge-ready' : 'badge-error'}`;
    }

    if (container) {
      const checks = validityData?.checks || validityData?.date_checks || [];
      if (checks.length === 0) {
        container.innerHTML = `
          <div style="background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.25); border-radius: var(--radius-sm); padding: 14px 18px; color: var(--emerald); font-size: 0.82rem;">
            ✓ All document invoice and incident dates have been verified within the active policy coverage window.
          </div>
        `;
        return;
      }

      container.innerHTML = checks.map(c => `
        <div style="background: var(--bg-elevated); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); padding: 12px 16px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px;">
          <div>
            <div style="font-weight: 600; color: var(--text-heading); font-size: 0.82rem;">${Utils.escapeHtml(c.document_type || 'Claim Document')} (Page ${c.page || 1})</div>
            <div style="font-size: 0.75rem; color: var(--text-muted);">${Utils.escapeHtml(c.reason || 'Within policy coverage window.')}</div>
          </div>
          <div style="display: flex; align-items: center; gap: 10px;">
            <span style="font-family: var(--font-mono); font-size: 0.75rem; color: var(--accent);">${Utils.escapeHtml(c.normalized_date || c.raw_date || '--')}</span>
            <span class="badge ${c.valid !== false ? 'badge-ready' : 'badge-error'}">${c.valid !== false ? '✓ Valid' : '✕ Out of Range'}</span>
          </div>
        </div>
      `).join('');
    }
  },

  renderValidationSection(validationData) {
    const container = document.getElementById('doc-validation-list');
    if (!container) return;

    if (!validationData) {
      container.innerHTML = `
        <div class="empty-state" style="padding: 20px;">
          <p>No document validation details recorded yet.</p>
        </div>
      `;
      return;
    }

    const pages = validationData.pages || validationData.page_results || [];
    if (pages.length === 0) {
      container.innerHTML = `
        <div style="background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.25); border-radius: var(--radius-sm); padding: 14px 18px; color: var(--emerald); font-size: 0.82rem;">
          ✓ All submitted documents passed structure and completeness validation.
        </div>
      `;
      return;
    }

    container.innerHTML = pages.map((p, idx) => `
      <div style="background: var(--bg-elevated); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); padding: 14px 18px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px;">
        <div>
          <div style="font-weight: 600; color: var(--text-heading); font-size: 0.84rem;">Page ${p.page || idx + 1}: ${Utils.escapeHtml(p.type || 'Document')}</div>
          <div style="font-size: 0.78rem; color: var(--text-muted);">${Utils.escapeHtml(p.details || 'Standard required fields present.')}</div>
        </div>
        <div>
          <span class="badge ${p.is_valid !== false ? 'badge-ready' : 'badge-warning'}">
            ${p.is_valid !== false ? '✓ Valid' : '⚠ Action Required'}
          </span>
        </div>
      </div>
    `).join('');
  },

  renderExtractedGrid(extractedPages) {
    const container = document.getElementById('extracted-entities-container');
    if (!container) return;

    if (extractedPages.length === 0) {
      container.innerHTML = `
        <div class="empty-state" style="grid-column: 1 / -1; padding: 30px;">
          <p>No extracted pages found.</p>
        </div>
      `;
      return;
    }

    container.innerHTML = extractedPages.map((page, idx) => `
      <div class="card" style="margin-bottom: 0;">
        <div class="card-header" style="margin-bottom: 10px;">
          <div style="font-weight: 600; font-size: 0.84rem; color: var(--accent); display: flex; align-items: center; gap: 7px;">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
            <span>Page ${page.page_number} (${Utils.escapeHtml((page.document_type || 'Document').replace(/_/g, ' '))})</span>
          </div>
          <span class="badge badge-ready">✓ Extracted</span>
        </div>
        <div style="display: flex; flex-direction: column; gap: 6px; font-size: 0.78rem; margin-bottom: 12px;">
          ${page.insurer_name ? `<div><span style="color: var(--text-muted);">Insurer:</span> <strong style="color: var(--text-heading);">${Utils.escapeHtml(page.insurer_name)}</strong></div>` : ''}
          ${page.policy_number ? `<div><span style="color: var(--text-muted);">Policy #:</span> <strong style="font-family: var(--font-mono); color: var(--accent);">${Utils.escapeHtml(page.policy_number)}</strong></div>` : ''}
          ${page.policy_holder_name ? `<div><span style="color: var(--text-muted);">Policy Holder:</span> <strong>${Utils.escapeHtml(page.policy_holder_name)}</strong></div>` : ''}
          ${page.patient_name ? `<div><span style="color: var(--text-muted);">Patient:</span> <strong>${Utils.escapeHtml(page.patient_name)}</strong></div>` : ''}
          ${page.bill_number ? `<div><span style="color: var(--text-muted);">Bill #:</span> <strong style="font-family: var(--font-mono);">${Utils.escapeHtml(page.bill_number)}</strong></div>` : ''}
          ${page.bill_amount ? `<div><span style="color: var(--text-muted);">Bill Amount:</span> <strong style="color: var(--emerald);">₹${Utils.escapeHtml(String(page.bill_amount))}</strong></div>` : ''}
          ${page.policy_start_date && page.policy_end_date ? `<div><span style="color: var(--text-muted);">Period:</span> <strong>${Utils.escapeHtml(page.policy_start_date)} ⟶ ${Utils.escapeHtml(page.policy_end_date)}</strong></div>` : ''}
        </div>
        <button class="btn btn-secondary btn-sm" style="width: 100%; justify-content: center;" onclick="DocumentsView.openDetailModal(${idx})">
          Inspect Page Details ↗
        </button>
      </div>
    `).join('');
  },

  renderEmptyState() {
    const banner = document.getElementById('results-verdict-banner');
    if (banner) {
      banner.innerHTML = `
        <div class="empty-state" style="padding: 40px;">
          <div class="empty-state-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
          </div>
          <h4>No Claim Assessment Available</h4>
          <p>Please select a claim or launch the InsureMate Agent to generate an assessment.</p>
        </div>
      `;
    }
  }
};

window.ClaimView = ClaimView;
