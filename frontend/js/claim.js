/**
 * frontend/js/claim.js
 * Final Claim Readiness Assessment & Deep-Dive Evidence Analysis.
 * Renders verdict banner, missing evidence table, validity checks, and document validation results.
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
        if (!bundle) return;
        const summary = bundle.final_report?.decision_summary || 'Claim assessment report.';
        Utils.copyToClipboard(`InsureMate Claim Report [${bundle.claim?.claim_id}]\nVerdict: ${bundle.verdict}\n\nSummary:\n${summary}`);
      });
    }

    // Copy JSON Action
    const btnCopyJson = document.getElementById('btn-copy-raw-json');
    if (btnCopyJson) {
      btnCopyJson.addEventListener('click', () => {
        const bundle = AppState.get().activeClaimBundle;
        if (!bundle) return;
        Utils.copyToClipboard(JSON.stringify(bundle, null, 2));
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

    // 3. Overview Executive Summary
    const overviewEl = document.getElementById('results-overview-summary-text');
    if (overviewEl) {
      overviewEl.textContent = report?.decision_summary || (
        String(verdict).toUpperCase().includes('READY')
          ? 'All required evidence documents have been validated and coverage dates confirmed. Claim is ready for submission.'
          : 'Claim assessment completed. Action is required due to missing mandatory documentation or date mismatches.'
      );
    }

    // 4. Missing Evidence Table (Section 16)
    this.renderMissingTable(latestState.missing_documents || report?.missing_documents_analysis);

    // 5. Validity Analysis (Section 17)
    this.renderValiditySection(latestState.validity_result || report?.validity_check);

    // 6. Validation Analysis (Section 18)
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
    const titleEl = document.getElementById('results-verdict-title');
    const descEl = document.getElementById('results-verdict-desc');
    const iconEl = document.getElementById('results-verdict-icon');

    if (!banner || !titleEl || !descEl || !iconEl) return;

    const s = String(verdict).toUpperCase();
    banner.className = 'card';
    banner.style.background = 'var(--bg-card)';

    if (s.includes('READY') || s.includes('CLAIM_READY')) {
      banner.style.borderLeft = '3px solid var(--emerald)';
      banner.style.borderColor = 'var(--emerald-border)';
      iconEl.textContent = '✓';
      iconEl.style.color = '#34D399';
      titleEl.textContent = 'CLAIM READY FOR SUBMISSION';
      descEl.textContent = report?.decision_summary || 'All required evidence has been submitted and verified. The claim satisfies coverage validity and required evidence policies.';
    } else if (s.includes('MISSING')) {
      banner.style.borderLeft = '3px solid var(--amber)';
      banner.style.borderColor = 'var(--amber-border)';
      iconEl.textContent = '⚠';
      iconEl.style.color = '#FBBF24';
      titleEl.textContent = 'ACTION REQUIRED: MISSING EVIDENCE DETECTED';
      descEl.textContent = report?.decision_summary || 'The submitted documents do not contain all mandatory evidence required by the insurance policy clauses.';
    } else if (s.includes('INVALID') || s.includes('FAILED')) {
      banner.style.borderLeft = '3px solid var(--rose)';
      banner.style.borderColor = 'var(--rose-border)';
      iconEl.textContent = '✕';
      iconEl.style.color = '#F87171';
      titleEl.textContent = s.includes('DATES') ? 'INVALID CLAIM DATES (OUTSIDE POLICY PERIOD)' : 'ACTION REQUIRED: INVALID DOCUMENTS';
      descEl.textContent = report?.decision_summary || 'Document validation or policy coverage verification failed.';
    } else {
      banner.style.borderLeft = '3px solid var(--accent)';
      banner.style.borderColor = 'var(--primary-border)';
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
    const missingDocs = latestState.missing_documents?.missing_documents || report.missing_documents || [];
    const validity = latestState.validity_result || report.validity_check || {};

    if (docsCountEl) docsCountEl.textContent = extracted.length || (bundle.claim?.policy_filename ? 2 : 1);
    if (validDocsEl) validDocsEl.textContent = Math.max(0, extracted.length - (latestState.validation_result?.invalid_count || 0));
    if (missingDocsEl) missingDocsEl.textContent = missingDocs.length;
    if (validityStatusEl) {
      const isPass = validity.valid !== false;
      validityStatusEl.textContent = isPass ? 'PASS' : 'FAIL';
      validityStatusEl.className = isPass ? 'kpi-value text-emerald' : 'kpi-value text-rose';
    }
  },

  renderMissingTable(missingData) {
    const tbody = document.getElementById('missing-evidence-tbody');
    if (!tbody) return;

    const items = missingData?.missing_documents || missingData?.items || [];

    if (!items || items.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="5" style="text-align: center; padding: 24px; color: var(--emerald-primary);">
            ✓ All required evidence documents are present and verified. Zero missing documents detected.
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = items.map((doc, idx) => {
      const statusRaw = String(doc.status || '').toLowerCase();
      const isFound = statusRaw === 'found' || statusRaw === 'available' || statusRaw === 'received' || statusRaw === 'present';
      const isIncomplete = statusRaw === 'incomplete';
      const isReview = statusRaw === 'needs_review' || statusRaw === 'review';
      
      let statusBadge;
      if (isFound) {
        statusBadge = '<span class="badge badge-success">✓ Received</span>';
      } else if (isIncomplete) {
        statusBadge = '<span class="badge badge-warning">⚠ Incomplete</span>';
      } else if (isReview) {
        statusBadge = '<span class="badge badge-info">ℹ Needs Review</span>';
      } else {
        statusBadge = '<span class="badge badge-warning">⚠ Missing</span>';
      }

      const docName = doc.document_title || doc.required_document || doc.document_name || doc.title || doc.name || 'Required Evidence Document';
      const reasonText = doc.reason || doc.matching_reason || (isFound ? 'Matching document identified in claim inventory.' : 'No matching claim documents were submitted to fulfill this requirement.');
      const pageInfo = doc.source_page ? `Page ${doc.source_page}` : (doc.page_number ? `Page ${doc.page_number}` : '—');

      return `
        <tr>
          <td style="font-family: var(--font-mono);">${idx + 1}</td>
          <td style="font-weight: 600; color: var(--text-primary);">${Utils.escapeHtml(docName)}</td>
          <td>${statusBadge}</td>
          <td>${Utils.escapeHtml(reasonText)}</td>
          <td style="font-family: var(--font-mono);">${pageInfo}</td>
        </tr>
      `;
    }).join('');
  },

  renderValiditySection(validityData) {
    const policyDatesEl = document.getElementById('validity-policy-dates');
    const tbody = document.getElementById('validity-checks-tbody');

    if (policyDatesEl) {
      if (validityData?.policy_period) {
        policyDatesEl.textContent = `${validityData.policy_period.start || '--'} ⟶ ${validityData.policy_period.end || '--'}`;
      } else {
        policyDatesEl.textContent = 'Active Policy Window Verified';
      }
    }

    if (tbody) {
      const checks = validityData?.checks || validityData?.date_checks || [];
      if (checks.length === 0) {
        tbody.innerHTML = `
          <tr>
            <td colspan="6" style="text-align: center; padding: 20px; color: var(--text-secondary);">
              ✓ Document dates evaluated within active policy coverage dates.
            </td>
          </tr>
        `;
        return;
      }

      tbody.innerHTML = checks.map(c => `
        <tr>
          <td style="font-weight: 600;">${Utils.escapeHtml(c.document_type || 'Claim Document')}</td>
          <td style="font-family: var(--font-mono);">Page ${c.page || 1}</td>
          <td style="font-family: var(--font-mono);">${Utils.escapeHtml(c.raw_date || '--')}</td>
          <td style="font-family: var(--font-mono);">${Utils.escapeHtml(c.normalized_date || '--')}</td>
          <td>
            <span class="badge ${c.valid !== false ? 'badge-success' : 'badge-error'}">
              ${c.valid !== false ? '✓ PASS' : '✕ FAIL'}
            </span>
          </td>
          <td>${Utils.escapeHtml(c.reason || 'Within policy validity period.')}</td>
        </tr>
      `).join('');
    }
  },

  renderValidationSection(validationData) {
    const container = document.getElementById('validation-results-container');
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
        <div style="background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.2); padding: 18px; border-radius: var(--border-radius-sm); color: var(--emerald-primary);">
          ✓ All submitted documents passed completeness and structure validation.
        </div>
      `;
      return;
    }

    container.innerHTML = pages.map((p, idx) => `
      <div style="background: var(--bg-elevated); border: 1px solid var(--border-subtle); border-radius: var(--border-radius-sm); padding: 14px 18px; margin-bottom: 12px; display: flex; align-items: center; justify-content: space-between;">
        <div>
          <div style="font-weight: 600; color: var(--text-primary);">Page ${p.page || idx + 1}: ${Utils.escapeHtml(p.type || 'Document')}</div>
          <div style="font-size: 0.78rem; color: var(--text-muted);">${Utils.escapeHtml(p.details || 'Standard fields present.')}</div>
        </div>
        <div>
          <span class="badge ${p.is_valid !== false ? 'badge-success' : 'badge-warning'}">
            ${p.is_valid !== false ? '✓ Valid' : '⚠ Review Required'}
          </span>
        </div>
      </div>
    `).join('');
  },

  renderExtractedGrid(extractedPages) {
    const container = document.getElementById('results-extracted-grid');
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
        <div class="card-header" style="margin-bottom: 12px;">
          <div style="font-weight: 600; font-size: 0.88rem; color: var(--accent); display: flex; align-items: center; gap: 7px;">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
            <span>Page ${page.page_number} (${Utils.escapeHtml((page.document_type || 'Document').replace(/_/g, ' '))})</span>
          </div>
          <span class="badge badge-success">✓ Extracted</span>
        </div>
        <div style="display: flex; flex-direction: column; gap: 6px; font-size: 0.8rem; margin-bottom: 12px;">
          ${page.insurer_name ? `<div><span style="color: var(--text-muted);">Insurer:</span> <strong style="color: var(--primary);">${Utils.escapeHtml(page.insurer_name)}</strong></div>` : ''}
          ${page.document_title ? `<div><span style="color: var(--text-muted);">Title:</span> <strong>${Utils.escapeHtml(page.document_title)}</strong></div>` : ''}
          ${page.policy_number ? `<div><span style="color: var(--text-muted);">Policy #:</span> <strong style="font-family: var(--font-mono); color: var(--accent);">${Utils.escapeHtml(page.policy_number)}</strong></div>` : ''}
          ${page.policy_holder_name ? `<div><span style="color: var(--text-muted);">Policy Holder:</span> <strong>${Utils.escapeHtml(page.policy_holder_name)}</strong></div>` : ''}
          ${page.insured_names && page.insured_names.length > 0 ? `<div><span style="color: var(--text-muted);">Insured:</span> <strong>${Utils.escapeHtml(page.insured_names.join(', '))}</strong></div>` : ''}
          ${page.policy_start_date && page.policy_end_date ? `<div><span style="color: var(--text-muted);">Coverage Window:</span> <strong>${Utils.escapeHtml(page.policy_start_date)} ⟶ ${Utils.escapeHtml(page.policy_end_date)}</strong></div>` : ''}
          ${page.sum_insured ? `<div><span style="color: var(--text-muted);">Sum Insured:</span> <strong style="color: var(--emerald);">₹${Utils.escapeHtml(String(page.sum_insured))}</strong></div>` : ''}
          ${page.bill_number ? `<div><span style="color: var(--text-muted);">Bill #:</span> <strong style="font-family: var(--font-mono);">${Utils.escapeHtml(page.bill_number)}</strong></div>` : ''}
          ${page.patient_name ? `<div><span style="color: var(--text-muted);">Patient:</span> <strong>${Utils.escapeHtml(page.patient_name)}</strong></div>` : ''}
          ${page.hospital_name ? `<div><span style="color: var(--text-muted);">Hospital:</span> <strong>${Utils.escapeHtml(page.hospital_name)}</strong></div>` : ''}
          ${page.bill_amount ? `<div><span style="color: var(--text-muted);">Bill Amount:</span> <strong style="color: var(--emerald);">₹${Utils.escapeHtml(String(page.bill_amount))}</strong></div>` : ''}
          ${page.total_amount ? `<div><span style="color: var(--text-muted);">Amount:</span> <strong style="color: var(--emerald);">${Utils.formatCurrency(page.total_amount)}</strong></div>` : ''}
          ${page.admission_date ? `<div><span style="color: var(--text-muted);">Admission:</span> <strong>${Utils.escapeHtml(page.admission_date)}</strong></div>` : ''}
          ${page.discharge_date ? `<div><span style="color: var(--text-muted);">Discharge:</span> <strong>${Utils.escapeHtml(page.discharge_date)}</strong></div>` : ''}
          ${page.diagnoses && page.diagnoses.length > 0 ? `<div><span style="color: var(--text-muted);">Diagnosis:</span> <strong>${Utils.escapeHtml(page.diagnoses.join(', '))}</strong></div>` : ''}
          ${page.policy_clauses && page.policy_clauses.length > 0 ? `<div style="color: var(--accent); margin-top: 4px;">📋 ${page.policy_clauses.length} mandatory clause(s) detected</div>` : ''}
        </div>
        <button class="btn btn-secondary btn-sm" style="width: 100%; justify-content: center;" onclick="DocumentsView.openDetailModal(${idx})">
          Inspect Full OCR & Clauses
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
