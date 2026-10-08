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

    // 3. Missing Evidence Table (Section 16)
    this.renderMissingTable(latestState.missing_documents || report?.missing_documents_analysis);

    // 4. Validity Analysis (Section 17)
    this.renderValiditySection(latestState.validity_result || report?.validity_check);

    // 5. Validation Analysis (Section 18)
    this.renderValidationSection(latestState.validation_result);

    // 6. Extracted Entities Grid
    this.renderExtractedGrid(latestState.extracted_data || []);

    // 7. Raw JSON Viewer
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

    if (s.includes('READY') || s.includes('CLAIM_READY')) {
      banner.className = 'card' ;
      banner.style.background = 'linear-gradient(135deg, rgba(16, 185, 129, 0.15) 0%, rgba(15, 23, 42, 0.8) 100%)';
      banner.style.borderColor = 'rgba(16, 185, 129, 0.35)';
      iconEl.textContent = '✓';
      iconEl.style.color = 'var(--emerald-primary)';
      titleEl.textContent = 'CLAIM READY FOR SUBMISSION';
      descEl.textContent = report?.decision_summary || 'All required evidence has been submitted and verified. The claim satisfies coverage validity and required evidence policies.';
    } else if (s.includes('MISSING')) {
      banner.className = 'card';
      banner.style.background = 'linear-gradient(135deg, rgba(245, 158, 11, 0.15) 0%, rgba(15, 23, 42, 0.8) 100%)';
      banner.style.borderColor = 'rgba(245, 158, 11, 0.35)';
      iconEl.textContent = '⚠';
      iconEl.style.color = 'var(--amber-primary)';
      titleEl.textContent = 'ACTION REQUIRED: MISSING EVIDENCE DETECTED';
      descEl.textContent = report?.decision_summary || 'The submitted documents do not contain all mandatory evidence required by the insurance policy clauses.';
    } else if (s.includes('INVALID') || s.includes('FAILED')) {
      banner.className = 'card';
      banner.style.background = 'linear-gradient(135deg, rgba(244, 63, 94, 0.15) 0%, rgba(15, 23, 42, 0.8) 100%)';
      banner.style.borderColor = 'rgba(244, 63, 94, 0.35)';
      iconEl.textContent = '✕';
      iconEl.style.color = 'var(--rose-primary)';
      titleEl.textContent = s.includes('DATES') ? 'INVALID CLAIM DATES (OUTSIDE POLICY PERIOD)' : 'ACTION REQUIRED: INVALID DOCUMENTS';
      descEl.textContent = report?.decision_summary || 'Document validation or policy coverage verification failed.';
    } else {
      banner.className = 'card';
      banner.style.background = 'linear-gradient(135deg, rgba(6, 182, 212, 0.1) 0%, rgba(15, 23, 42, 0.8) 100%)';
      banner.style.borderColor = 'rgba(6, 182, 212, 0.25)';
      iconEl.textContent = '●';
      iconEl.style.color = 'var(--cyan-primary)';
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
      const isFound = doc.status === 'found' || doc.status === 'available';
      const statusBadge = isFound
        ? '<span class="badge badge-success">✓ Available</span>'
        : '<span class="badge badge-warning">⚠ Missing</span>';

      return `
        <tr>
          <td style="font-family: var(--font-mono);">${idx + 1}</td>
          <td style="font-weight: 600; color: var(--text-primary);">${Utils.escapeHtml(doc.required_document || doc.document_name || 'Evidence Document')}</td>
          <td>${statusBadge}</td>
          <td>${Utils.escapeHtml(doc.reason || doc.matching_reason || 'Required by policy conditions')}</td>
          <td style="font-family: var(--font-mono);">${doc.page_number ? `Page ${doc.page_number}` : '—'}</td>
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

    container.innerHTML = extractedPages.map(page => `
      <div class="card" style="margin-bottom: 0;">
        <div class="card-header" style="margin-bottom: 12px;">
          <div style="font-weight: 600; font-size: 0.95rem; color: var(--cyan-primary);">
            📄 Page ${page.page_number} (${Utils.escapeHtml(page.document_type || 'Document')})
          </div>
          <span class="badge badge-success">✓ Extracted</span>
        </div>
        <div style="display: flex; flex-direction: column; gap: 6px; font-size: 0.85rem;">
          ${page.patient_name ? `<div><span style="color: var(--text-muted);">Patient:</span> <strong>${Utils.escapeHtml(page.patient_name)}</strong></div>` : ''}
          ${page.policy_number ? `<div><span style="color: var(--text-muted);">Policy #:</span> <strong>${Utils.escapeHtml(page.policy_number)}</strong></div>` : ''}
          ${page.hospital_name ? `<div><span style="color: var(--text-muted);">Hospital:</span> <strong>${Utils.escapeHtml(page.hospital_name)}</strong></div>` : ''}
          ${page.total_amount ? `<div><span style="color: var(--text-muted);">Amount:</span> <strong style="color: var(--emerald-primary);">${Utils.formatCurrency(page.total_amount)}</strong></div>` : ''}
          ${page.admission_date ? `<div><span style="color: var(--text-muted);">Admission:</span> <strong>${Utils.escapeHtml(page.admission_date)}</strong></div>` : ''}
          ${page.discharge_date ? `<div><span style="color: var(--text-muted);">Discharge:</span> <strong>${Utils.escapeHtml(page.discharge_date)}</strong></div>` : ''}
        </div>
      </div>
    `).join('');
  },

  renderEmptyState() {
    const banner = document.getElementById('results-verdict-banner');
    if (banner) {
      banner.innerHTML = `
        <div class="empty-state" style="padding: 40px;">
          <div class="empty-state-icon">⚖️</div>
          <h4>No Claim Assessment Available</h4>
          <p>Please select a claim or launch the InsureMate Agent to generate an assessment.</p>
        </div>
      `;
    }
  }
};

window.ClaimView = ClaimView;
