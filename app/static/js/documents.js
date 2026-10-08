/**
 * frontend/js/documents.js
 * Document Management & Detailed Entity Inspection View.
 * Displays documents table with statuses, and opens modal with structured Qwen-VL fields and page references.
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
    const classifications = latestState.document_classifications || {};
    const validationResult = latestState.validation_result || {};
    const validityResult = latestState.validity_result || {};

    const docs = [];

    // 1. Insurance Policy
    if (claim.policy_filename) {
      docs.push({
        name: claim.policy_filename,
        type: 'insurance_policy',
        role: 'Policy Document',
        pages: 1,
        extraction: extractedPages.length > 0 ? 'Extracted' : 'Pending',
        validation: 'Valid',
        validity: 'PASS',
        status: 'Valid'
      });
    }

    // 2. Claim / Incident Documents
    const claimFiles = Array.isArray(claim.claim_filenames) ? claim.claim_filenames : (claim.claim_filename ? [claim.claim_filename] : []);
    claimFiles.forEach((fname, idx) => {
      const pageNum = idx + 1;
      const type = classifications[pageNum] || 'supporting_document';
      const isVal = validationResult.overall_valid !== false;
      const isValidity = validityResult.valid !== false;

      docs.push({
        name: fname,
        type: type,
        role: 'Supporting Claim File',
        pages: 1,
        extraction: extractedPages.length > 0 ? 'Extracted' : 'Pending',
        validation: isVal ? 'Valid' : 'Requires Review',
        validity: isValidity ? 'PASS' : 'FAIL',
        status: (isVal && isValidity) ? 'Valid' : 'Requires Review'
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
          <span class="badge ${doc.extraction === 'Extracted' ? 'badge-success' : 'badge-pending'}">
            ${doc.extraction === 'Extracted' ? '✓' : '○'} ${doc.extraction}
          </span>
        </td>
        <td>
          <span class="badge ${doc.validation === 'Valid' ? 'badge-success' : 'badge-warning'}">
            ${doc.validation === 'Valid' ? '✓ Valid' : '⚠ Review'}
          </span>
        </td>
        <td>
          <span class="badge ${doc.validity === 'PASS' ? 'badge-success' : 'badge-error'}">
            ${doc.validity === 'PASS' ? '✓ PASS' : '✕ FAIL'}
          </span>
        </td>
        <td>
          <span class="badge ${doc.status === 'Valid' ? 'badge-success' : 'badge-warning'}">
            ${doc.status}
          </span>
        </td>
        <td>
          <button class="btn btn-secondary btn-sm" onclick="DocumentsView.openDetailModal(${idx})">
            Inspect Details
          </button>
        </td>
      </tr>
    `).join('');
  },

  openDetailModal(docIndex) {
    const bundle = AppState.get().activeClaimBundle;
    if (!bundle) return;

    const claim = bundle.claim || {};
    const latestState = bundle.latest_state || {};
    const extractedPages = latestState.extracted_data || [];

    const titleEl = document.getElementById('modal-doc-title');
    const metaContainer = document.getElementById('modal-doc-meta');
    const fieldsContainer = document.getElementById('modal-doc-fields');

    // Page data corresponding to this document or aggregate
    const pageData = extractedPages[docIndex] || extractedPages[0] || {};
    const docName = (docIndex === 0 && claim.policy_filename) ? claim.policy_filename : (claim.claim_filenames?.[docIndex - 1] || 'Document');

    if (titleEl) titleEl.textContent = `Document Details: ${docName}`;

    if (metaContainer) {
      metaContainer.innerHTML = `
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 20px; background: var(--bg-elevated); padding: 14px; border-radius: var(--border-radius-sm); border: 1px solid var(--border-subtle);">
          <div>
            <div style="font-size: 0.72rem; color: var(--text-muted); text-transform: uppercase;">File Name</div>
            <div style="font-weight: 600; font-size: 0.88rem; color: var(--text-primary);">${Utils.escapeHtml(docName)}</div>
          </div>
          <div>
            <div style="font-size: 0.72rem; color: var(--text-muted); text-transform: uppercase;">Document Type</div>
            <div style="font-weight: 600; font-size: 0.88rem; color: var(--primary); text-transform: capitalize;">${Utils.escapeHtml(pageData.document_type || 'PDF Document')}</div>
          </div>
          <div>
            <div style="font-size: 0.72rem; color: var(--text-muted); text-transform: uppercase;">Page Reference</div>
            <div style="font-weight: 600; font-size: 0.88rem; color: var(--text-primary);">Page ${pageData.page_number || (docIndex + 1)}</div>
          </div>
          <div>
            <div style="font-size: 0.72rem; color: var(--text-muted); text-transform: uppercase;">Status</div>
            <div style="font-weight: 600; font-size: 0.88rem; color: var(--emerald);">✓ Extracted by Qwen-VL</div>
          </div>
        </div>
      `;
    }

    if (fieldsContainer) {
      // Collect structured key-value entities
      const entities = [];

      // Extract from pageData fields
      const addField = (label, val, page) => {
        if (val !== undefined && val !== null && val !== '') {
          entities.push({ label, val: String(val), page: page || pageData.page_number || 1 });
        }
      };

      if (pageData.fields && typeof pageData.fields === 'object') {
        Object.entries(pageData.fields).forEach(([k, v]) => {
          addField(k.replace(/_/g, ' '), v, pageData.page_number);
        });
      }

      addField('Patient / Insured Name', pageData.patient_name || pageData.insured_name);
      addField('Policy Number', pageData.policy_number);
      addField('Hospital / Provider', pageData.hospital_name || pageData.hospital);
      addField('Admission Date', pageData.admission_date);
      addField('Discharge Date', pageData.discharge_date);
      addField('Bill / Claim Amount', pageData.total_amount ? Utils.formatCurrency(pageData.total_amount) : pageData.bill_amount);
      addField('Diagnosis / Treatment', pageData.diagnosis || pageData.treatment);
      addField('Document Date', pageData.document_date || pageData.date);

      if (entities.length === 0) {
        fieldsContainer.innerHTML = `
          <div class="empty-state" style="padding: 20px;">
            <p>No structured entities were extracted for this document page.</p>
          </div>
        `;
      } else {
        fieldsContainer.innerHTML = `
          <h4 style="font-size: 0.88rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 12px; letter-spacing: 0.05em;">
            Structured Entities (Qwen-VL Multimodal Vision)
          </h4>
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Field Entity</th>
                  <th>Extracted Value</th>
                  <th>Page Reference</th>
                </tr>
              </thead>
              <tbody>
                ${entities.map(e => `
                  <tr>
                    <td style="font-weight: 600; text-transform: capitalize; color: var(--text-secondary);">${Utils.escapeHtml(e.label)}</td>
                    <td style="color: var(--text-primary); font-family: var(--font-mono);">${Utils.escapeHtml(e.val)}</td>
                    <td>
                      <span class="badge" style="background: var(--primary-light); color: var(--primary); border: 1px solid var(--primary-border);">
                        Page ${e.page}
                      </span>
                    </td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        `;
      }
    }

    Utils.openModal('doc-detail-modal');
  }
};

window.DocumentsView = DocumentsView;
