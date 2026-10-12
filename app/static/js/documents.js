/**
 * frontend/js/documents.js
 * Extracted Document Intelligence & Entity Inspection Controller.
 * Displays page-by-page vision breakdown and structured modal viewer.
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

    // If extracted pages exist, show full page-by-page vision breakdown
    if (extractedPages.length > 0) {
      tbody.innerHTML = extractedPages.map((page, idx) => {
        const isPolicy = page.document_type === 'insurance_policy';
        const docTitle = page.document_title || (isPolicy ? 'Insurance Policy Document' : 'Claim Supporting Evidence');
        const sourceFile = (isPolicy && claim.policy_filename) ? claim.policy_filename : (claim.claim_filenames?.[idx] || claim.policy_filename || `Document Page ${page.page_number}`);
        
        const refNo = page.policy_number || page.bill_number || '--';
        const person = page.policy_holder_name || page.patient_name || '--';
        
        let dateStr = '--';
        if (page.policy_start_date && page.policy_end_date) {
          dateStr = `${page.policy_start_date} ⟶ ${page.policy_end_date}`;
        } else if (page.document_date || page.admission_date) {
          dateStr = page.document_date || page.admission_date;
        }

        const amountStr = page.bill_amount ? `₹${page.bill_amount}` : (page.total_amount ? Utils.formatCurrency(page.total_amount) : (page.sum_insured ? `₹${page.sum_insured}` : '--'));

        return `
          <tr>
            <td>
              <div style="font-weight: 600; color: #FFFFFF; display: flex; align-items: center; gap: 8px;">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                <span>Page ${page.page_number}</span>
              </div>
              <div style="font-size: 0.7rem; color: var(--text-muted); font-family: var(--font-mono);">${Utils.escapeHtml(sourceFile)}</div>
            </td>
            <td>
              <span class="badge badge-neutral" style="text-transform: capitalize;">
                ${Utils.escapeHtml((page.document_type || 'Document').replace(/_/g, ' '))}
              </span>
            </td>
            <td style="font-family: var(--font-mono); color: var(--accent);">
              ${Utils.escapeHtml(refNo)}
            </td>
            <td>
              <span style="font-weight: 500; color: #FFFFFF;">${Utils.escapeHtml(person)}</span>
            </td>
            <td style="font-size: 0.75rem; color: var(--text-muted); font-family: var(--font-mono);">
              ${Utils.escapeHtml(dateStr)}
            </td>
            <td style="font-family: var(--font-mono); color: var(--emerald); font-weight: 600;">
              ${Utils.escapeHtml(amountStr)}
            </td>
            <td>
              <span class="badge ${validationResult.valid !== false ? 'badge-ready' : 'badge-warning'}">
                ${validationResult.valid !== false ? '✓ Valid' : '⚠ Review'}
              </span>
            </td>
            <td>
              <button class="btn btn-secondary btn-sm" onclick="DocumentsView.openDetailModal(${idx})">
                Inspect
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
        ref: 'Pending Extraction',
        person: 'Pending Extraction',
        dates: 'Pending Extraction',
        amount: '--'
      });
    }

    const claimFiles = Array.isArray(claim.claim_filenames) ? claim.claim_filenames : (claim.claim_filename ? [claim.claim_filename] : []);
    claimFiles.forEach((fname) => {
      docs.push({
        name: fname,
        type: 'claim_evidence',
        ref: 'Pending Extraction',
        person: 'Pending Extraction',
        dates: 'Pending Extraction',
        amount: '--'
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
          <div style="font-weight: 600; color: #FFFFFF;">${Utils.escapeHtml(doc.name)}</div>
          <div style="font-size: 0.7rem; color: var(--text-muted);">Uploaded PDF File</div>
        </td>
        <td>
          <span class="badge badge-neutral">${Utils.escapeHtml(doc.type.replace(/_/g, ' '))}</span>
        </td>
        <td style="color: var(--text-muted); font-size: 0.78rem;">${doc.ref}</td>
        <td style="color: var(--text-muted); font-size: 0.78rem;">${doc.person}</td>
        <td style="color: var(--text-muted); font-size: 0.78rem;">${doc.dates}</td>
        <td style="color: var(--text-muted); font-size: 0.78rem;">${doc.amount}</td>
        <td>
          <span class="badge badge-processing">Awaiting Agent Run</span>
        </td>
        <td>
          <button class="btn btn-secondary btn-sm" onclick="Dashboard.trackAgent('${claim.claim_id}')">
            Run Agent
          </button>
        </td>
      </tr>
    `).join('');
  },

  openDetailModal(index) {
    const bundle = AppState.get().activeClaimBundle;
    if (!bundle) return;

    const pages = bundle.latest_state?.extracted_data || [];
    const page = pages[index];
    if (!page) return;

    this.selectedDocIndex = index;

    const titleEl = document.getElementById('doc-modal-title');
    const bodyEl = document.getElementById('doc-modal-body');

    if (titleEl) {
      titleEl.textContent = `Page ${page.page_number} — ${Utils.escapeHtml((page.document_type || 'Document').replace(/_/g, ' ').toUpperCase())}`;
    }

    if (bodyEl) {
      const clauses = page.policy_clauses || [];
      const clausesHtml = clauses.length > 0 ? clauses.map(c => `
        <div style="background: #060B14; border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); padding: 10px 14px; margin-bottom: 8px;">
          <div style="font-weight: 600; color: var(--accent); font-size: 0.8rem; margin-bottom: 2px;">Clause: ${Utils.escapeHtml(c.clause_title || c.title || 'Policy Requirement')}</div>
          <div style="font-size: 0.74rem; color: var(--text-secondary); line-height: 1.45;">${Utils.escapeHtml(c.clause_text || c.text || c.description || JSON.stringify(c))}</div>
        </div>
      `).join('') : '<div style="color: var(--text-muted); font-size: 0.78rem;">No mandatory clauses detected on this page.</div>';

      bodyEl.innerHTML = `
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 16px;">
          <div style="background: #09101E; border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); padding: 12px;">
            <div style="font-size: 0.68rem; text-transform: uppercase; color: var(--text-muted); font-weight: 700; margin-bottom: 6px;">Vision Classification</div>
            <div style="font-size: 0.9rem; font-weight: 700; color: #FFFFFF;">${Utils.escapeHtml((page.document_type || 'Document').replace(/_/g, ' '))}</div>
            <div style="font-size: 0.75rem; color: var(--accent); margin-top: 2px;">Page Number: ${page.page_number}</div>
          </div>

          <div style="background: #09101E; border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); padding: 12px;">
            <div style="font-size: 0.68rem; text-transform: uppercase; color: var(--text-muted); font-weight: 700; margin-bottom: 6px;">Entity Reference</div>
            <div style="font-size: 0.9rem; font-weight: 700; font-family: var(--font-mono); color: var(--accent);">${Utils.escapeHtml(page.policy_number || page.bill_number || '--')}</div>
            <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 2px;">Holder/Patient: ${Utils.escapeHtml(page.policy_holder_name || page.patient_name || '--')}</div>
          </div>
        </div>

        <div style="margin-bottom: 16px;">
          <div style="font-size: 0.72rem; text-transform: uppercase; color: var(--text-muted); font-weight: 700; margin-bottom: 6px;">Structured Field Entities</div>
          <div style="background: #060B14; border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); padding: 10px 14px; font-family: var(--font-mono); font-size: 0.74rem;">
            <pre style="margin:0; color:#E2E8F0; white-space:pre-wrap; word-break:break-all; max-height:180px; overflow-y:auto;">${Utils.escapeHtml(JSON.stringify(page, null, 2))}</pre>
          </div>
        </div>

        <div>
          <div style="font-size: 0.72rem; text-transform: uppercase; color: var(--text-muted); font-weight: 700; margin-bottom: 6px;">Extracted Policy Clauses</div>
          ${clausesHtml}
        </div>
      `;
    }

    Utils.openModal('doc-detail-modal');
  }
};

window.DocumentsView = DocumentsView;
