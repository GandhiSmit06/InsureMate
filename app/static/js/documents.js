/**
 * frontend/js/documents.js
 * Document Management & Detailed Entity Inspection View.
 * Displays uploaded files summary and page-by-page OCR extraction records.
 * Opens rich modal with structured Qwen-VL fields, policy clauses, and coverage dates.
 */

const DocumentsView = {
  selectedDocIndex: null,

  init() {
    this.bindEvents();

    AppState.subscribe('activeClaimBundle', (bundle) => {
      this.renderDocumentsTable(bundle);
    });
  },

  bindEvents() {
    // Modal close button
    const btnClose = document.getElementById('btn-close-doc-modal');
    if (btnClose) {
      btnClose.addEventListener('click', () => Utils.closeModal('doc-detail-modal'));
    }

    const modalOverlay = document.getElementById('doc-detail-modal');
    if (modalOverlay) {
      modalOverlay.addEventListener('click', (e) => {
        if (e.target === modalOverlay) Utils.closeModal('doc-detail-modal');
      });
    }
  },

  renderDocumentsTable(bundle) {
    const tbody = document.getElementById('docs-table-tbody');
    if (!tbody) return;

    if (!bundle) {
      tbody.innerHTML = `
        <tr>
          <td colspan="8" class="empty-state" style="padding: 40px;">
            <div class="empty-state-icon">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
            </div>
            <h4>No Active Claim Selected</h4>
            <p>Select or create a claim session to inspect uploaded documents.</p>
          </td>
        </tr>
      `;
      return;
    }

    const claim = bundle.claim || {};
    const latestState = bundle.latest_state || {};
    const extractedPages = latestState.extracted_data || [];
    const validationResult = latestState.validation_result || {};
    const validityResult = latestState.validity_result || {};

    // If extracted pages exist, show full page-by-page vision breakdown
    if (extractedPages.length > 0) {
      tbody.innerHTML = extractedPages.map((page, idx) => {
        const isPolicy = page.document_type === 'insurance_policy';
        const docTitle = page.document_title || (isPolicy ? 'Insurance Policy Document' : 'Claim Supporting Evidence');
        const sourceFile = (isPolicy && claim.policy_filename) ? claim.policy_filename : (claim.claim_filenames?.[idx] || claim.policy_filename || `Document Page ${page.page_number}`);
        
        let detailsSummary = [];
        if (page.policy_number) detailsSummary.push(`Policy: ${page.policy_number}`);
        if (page.policy_holder_name) detailsSummary.push(`Holder: ${page.policy_holder_name}`);
        if (page.patient_name) detailsSummary.push(`Patient: ${page.patient_name}`);
        if (page.policy_start_date && page.policy_end_date) detailsSummary.push(`Period: ${page.policy_start_date} to ${page.policy_end_date}`);
        if (page.bill_amount) detailsSummary.push(`Amount: ₹${page.bill_amount}`);
        if (page.policy_clauses && page.policy_clauses.length > 0) detailsSummary.push(`${page.policy_clauses.length} clause(s)`);

        const summaryText = detailsSummary.join(' • ') || 'Vision entities extracted';

        return `
          <tr>
            <td>
              <div style="font-weight: 600; color: #FFFFFF; display: flex; align-items: center; gap: 8px;">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                <span>${Utils.escapeHtml(docTitle)}</span>
              </div>
              <div style="font-size: 0.72rem; color: var(--text-muted);">${Utils.escapeHtml(sourceFile)} • ${Utils.escapeHtml(summaryText)}</div>
            </td>
            <td>
              <span class="badge" style="background: var(--bg-elevated); color: var(--primary); text-transform: capitalize; border: 1px solid var(--border-subtle);">
                ${Utils.escapeHtml((page.document_type || 'Document').replace(/_/g, ' '))}
              </span>
            </td>
            <td style="font-family: var(--font-mono); font-weight: 600;">Page ${page.page_number}</td>
            <td>
              <span class="badge badge-success">✓ Extracted</span>
            </td>
            <td>
              <span class="badge ${validationResult.valid !== false ? 'badge-success' : 'badge-warning'}">
                ${validationResult.valid !== false ? '✓ Valid' : '⚠ Review'}
              </span>
            </td>
            <td>
              <span class="badge ${validityResult.valid !== false ? 'badge-success' : 'badge-pending'}">
                ${validityResult.valid !== false ? '✓ Verified' : '○ Pending'}
              </span>
            </td>
            <td>
              <span class="badge badge-success">Active</span>
            </td>
            <td>
              <button class="btn btn-secondary btn-sm" onclick="DocumentsView.openDetailModal(${idx})">
                Inspect Details
              </button>
            </td>
          </tr>
        `;
      }).join('');
      return;
    }

    // Fallback if extraction hasn't executed yet
    const docs = [];
    if (claim.policy_filename) {
      docs.push({
        name: claim.policy_filename,
        type: 'insurance_policy',
        role: 'Policy Document',
        pages: '1+',
        extraction: 'Pending',
        validation: 'Pending',
        validity: 'Pending',
        status: 'Pending Analysis'
      });
    }

    const claimFiles = Array.isArray(claim.claim_filenames) ? claim.claim_filenames : (claim.claim_filename ? [claim.claim_filename] : []);
    claimFiles.forEach((fname) => {
      docs.push({
        name: fname,
        type: 'claim_evidence',
        role: 'Supporting Claim File',
        pages: '1+',
        extraction: 'Pending',
        validation: 'Pending',
        validity: 'Pending',
        status: 'Pending Analysis'
      });
    });

    if (docs.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="8" class="empty-state" style="padding: 40px;">
            <div class="empty-state-icon">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
            </div>
            <h4>No Documents Attached</h4>
            <p>This claim has no policy or supporting files uploaded.</p>
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = docs.map((doc, idx) => `
      <tr>
        <td>
          <div style="font-weight: 600; color: #FFFFFF; display: flex; align-items: center; gap: 8px;">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
            <span>${Utils.escapeHtml(doc.name)}</span>
          </div>
          <div style="font-size: 0.72rem; color: var(--text-muted);">${Utils.escapeHtml(doc.role)}</div>
        </td>
        <td>
          <span class="badge" style="background: var(--bg-elevated); color: var(--text-secondary); text-transform: capitalize;">
            ${Utils.escapeHtml(doc.type.replace(/_/g, ' '))}
          </span>
        </td>
        <td style="font-family: var(--font-mono);">${doc.pages}</td>
        <td>
          <span class="badge badge-pending">○ Pending</span>
        </td>
        <td>
          <span class="badge badge-pending">○ Pending</span>
        </td>
        <td>
          <span class="badge badge-pending">○ Pending</span>
        </td>
        <td>
          <span class="badge badge-pending">○ Ready for Agent</span>
        </td>
        <td>
          <button class="btn btn-secondary btn-sm" onclick="DocumentsView.openDetailModal(${idx})">
            Inspect Details
          </button>
        </td>
      </tr>
    `).join('');
  },

  openDetailModal(pageIndex) {
    const bundle = AppState.get().activeClaimBundle;
    if (!bundle) return;

    const claim = bundle.claim || {};
    const latestState = bundle.latest_state || {};
    const extractedPages = latestState.extracted_data || [];

    const titleEl = document.getElementById('modal-doc-title');
    const metaContainer = document.getElementById('modal-doc-meta');
    const fieldsContainer = document.getElementById('modal-doc-fields');

    const pageData = extractedPages[pageIndex] || extractedPages[0] || {};
    const isPolicy = pageData.document_type === 'insurance_policy';
    const docName = pageData.document_title || (isPolicy ? (claim.policy_filename || 'Insurance Policy') : (claim.claim_filenames?.[pageIndex] || 'Claim Document'));

    if (titleEl) {
      titleEl.textContent = `Page ${pageData.page_number || (pageIndex + 1)}: ${docName}`;
    }

    if (metaContainer) {
      metaContainer.innerHTML = `
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; margin-bottom: 20px; background: var(--bg-elevated); padding: 14px; border-radius: var(--border-radius-sm); border: 1px solid var(--border-subtle);">
          <div>
            <div style="font-size: 0.70rem; color: var(--text-muted); text-transform: uppercase;">Document Title</div>
            <div style="font-weight: 600; font-size: 0.85rem; color: var(--text-primary);">${Utils.escapeHtml(docName)}</div>
          </div>
          <div>
            <div style="font-size: 0.70rem; color: var(--text-muted); text-transform: uppercase;">Classified Type</div>
            <div style="font-weight: 600; font-size: 0.85rem; color: var(--primary); text-transform: capitalize;">${Utils.escapeHtml((pageData.document_type || 'Unknown').replace(/_/g, ' '))}</div>
          </div>
          <div>
            <div style="font-size: 0.70rem; color: var(--text-muted); text-transform: uppercase;">Page Reference</div>
            <div style="font-weight: 600; font-size: 0.85rem; color: var(--text-primary); font-family: var(--font-mono);">Page ${pageData.page_number || (pageIndex + 1)}</div>
          </div>
          <div>
            <div style="font-size: 0.70rem; color: var(--text-muted); text-transform: uppercase;">Extraction Engine</div>
            <div style="font-weight: 600; font-size: 0.85rem; color: var(--emerald);">✓ Qwen-VL Multimodal Vision</div>
          </div>
        </div>
      `;
    }

    if (fieldsContainer) {
      const entities = [];
      const addField = (label, val) => {
        if (val !== undefined && val !== null && val !== '' && !(Array.isArray(val) && val.length === 0)) {
          entities.push({ label, val: Array.isArray(val) ? val.join(', ') : String(val) });
        }
      };

      // Populate structured OCR entities
      addField('Insurer Name', pageData.insurer_name);
      addField('Policy Number', pageData.policy_number);
      addField('Policy Holder Name', pageData.policy_holder_name);
      addField('Insured Members', pageData.insured_names);
      addField('Policy Coverage Start', pageData.policy_start_date);
      addField('Policy Coverage End', pageData.policy_end_date);
      addField('Sum Insured', pageData.sum_insured ? (String(pageData.sum_insured).startsWith('₹') ? pageData.sum_insured : `₹${pageData.sum_insured}`) : null);
      addField('Patient Name', pageData.patient_name);
      addField('Hospital / Provider', pageData.hospital_name);
      addField('Bill / Invoice Number', pageData.bill_number || pageData.invoice_number);
      addField('Bill / Claim Amount', pageData.bill_amount ? (pageData.bill_amount.toString().startsWith('₹') ? pageData.bill_amount : `₹${pageData.bill_amount}`) : (pageData.total_amount ? Utils.formatCurrency(pageData.total_amount) : null));
      addField('Admission Date', pageData.admission_date);
      addField('Discharge Date', pageData.discharge_date);
      addField('Document / Incident Date', pageData.document_date);

      let clausesHtml = '';
      if (pageData.policy_clauses && pageData.policy_clauses.length > 0) {
        clausesHtml = `
          <div style="margin-top: 18px; background: rgba(56, 189, 248, 0.05); border: 1px solid rgba(56, 189, 248, 0.2); border-radius: 8px; padding: 14px;">
            <div style="font-size: 0.78rem; font-weight: 700; text-transform: uppercase; color: var(--accent); margin-bottom: 8px; letter-spacing: 0.05em; display: flex; align-items: center; gap: 6px;">
              <span>📋 Extracted Policy Clauses & Mandatory Evidence Requirements:</span>
            </div>
            <ul style="margin: 0; padding-left: 20px; font-size: 0.82rem; color: var(--text-primary); line-height: 1.6;">
              ${pageData.policy_clauses.map(c => `<li>${Utils.escapeHtml(c)}</li>`).join('')}
            </ul>
          </div>
        `;
      }

      let conditionsHtml = '';
      if (pageData.relevant_conditions && pageData.relevant_conditions.length > 0) {
        conditionsHtml = `
          <div style="margin-top: 12px; background: rgba(16, 185, 129, 0.05); border: 1px solid rgba(16, 185, 129, 0.2); border-radius: 8px; padding: 14px;">
            <div style="font-size: 0.78rem; font-weight: 700; text-transform: uppercase; color: var(--emerald); margin-bottom: 8px; letter-spacing: 0.05em;">
              🛡️ Policy Conditions & Benefits:
            </div>
            <ul style="margin: 0; padding-left: 20px; font-size: 0.82rem; color: var(--text-primary); line-height: 1.6;">
              ${pageData.relevant_conditions.map(c => `<li>${Utils.escapeHtml(c)}</li>`).join('')}
            </ul>
          </div>
        `;
      }

      let summaryHtml = '';
      if (pageData.extracted_text_summary || pageData.policy_relevant_text) {
        summaryHtml = `
          <div style="margin-top: 12px; padding: 12px; background: var(--bg-elevated); border: 1px solid var(--border-subtle); border-radius: 8px;">
            <div style="font-size: 0.72rem; text-transform: uppercase; color: var(--text-muted); font-weight: 600; margin-bottom: 4px;">Vision Text Summary:</div>
            <div style="font-size: 0.80rem; color: var(--text-secondary); line-height: 1.5;">${Utils.escapeHtml(pageData.extracted_text_summary || pageData.policy_relevant_text)}</div>
          </div>
        `;
      }

      let tableHtml = '';
      if (entities.length > 0) {
        tableHtml = `
          <h4 style="font-size: 0.82rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 10px; letter-spacing: 0.05em;">
            Extracted Structured Entities
          </h4>
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th style="width: 35%;">Field Entity</th>
                  <th>Extracted Value</th>
                </tr>
              </thead>
              <tbody>
                ${entities.map(e => `
                  <tr>
                    <td style="font-weight: 600; color: var(--text-secondary);">${Utils.escapeHtml(e.label)}</td>
                    <td style="color: var(--text-primary); font-family: var(--font-mono); font-weight: 600;">${Utils.escapeHtml(e.val)}</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        `;
      } else {
        tableHtml = `
          <div class="empty-state" style="padding: 16px;">
            <p>No individual key-value fields detected on this page.</p>
          </div>
        `;
      }

      fieldsContainer.innerHTML = tableHtml + clausesHtml + conditionsHtml + summaryHtml;
    }

    Utils.openModal('doc-detail-modal');
  }
};

window.DocumentsView = DocumentsView;
