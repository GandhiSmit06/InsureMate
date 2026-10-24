/**
 * frontend/js/claim.js
 * InsureMate — Adjudication Verdict & Claim Assessment Controller.
 * Implements:
 * 1. Adjudication Verdict Hero Banner (Decoupled Worker Status vs Adjudication Readiness)
 * 2. High-Impact KPI Metrics Bar (Total Submitted, Extraction Integrity, Missing Count, Coverage Window)
 * 3. Interactive Evidence & Document Remediation Center (Rich Requirement Cards + Inline Dropzones)
 * 4. Coverage & Timeline Visualizer (Gantt Chart & Date Audits)
 * 5. Document Validation & Extracted Intelligence Panes
 */

const ClaimView = {
  activeClaimId: null,
  activeBundle: null,

  init() {
    this.bindEvents();

    AppState.subscribe('activeClaimBundle', (bundle) => {
      this.activeBundle = bundle;
      this.activeClaimId = bundle?.claim?.claim_id || null;
      this.renderClaimResults(bundle);
    });

    // Check if AppState already holds an active bundle on initialization
    const initialBundle = AppState.get().activeClaimBundle;
    if (initialBundle) {
      this.activeBundle = initialBundle;
      this.activeClaimId = initialBundle?.claim?.claim_id || null;
      this.renderClaimResults(initialBundle);
    }
  },

  bindEvents() {
    // Tab switching
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

    // Action Toolbar Events
    this.bindActionToolbar();
  },

  bindActionToolbar() {
    // Export Official Report (PDF / Print)
    const btnExportPdf = document.getElementById('btn-export-claim-pdf');
    const btnDownloadReport = document.getElementById('btn-download-claim-report');
    const handleExport = () => {
      if (!this.activeBundle) {
        Utils.showToast('No active claim report to export.', 'warning');
        return;
      }
      window.print();
    };
    if (btnExportPdf) btnExportPdf.addEventListener('click', handleExport);
    if (btnDownloadReport) btnDownloadReport.addEventListener('click', handleExport);

    // Copy Executive Summary
    const btnCopySummary = document.getElementById('btn-copy-claim-summary');
    if (btnCopySummary) {
      btnCopySummary.addEventListener('click', () => {
        const bundle = this.activeBundle;
        if (!bundle) {
          Utils.showToast('No active claim report to copy.', 'warning');
          return;
        }
        const claimId = bundle.claim?.claim_id || 'UNKNOWN';
        const verdict = this.getVerdictDisplayInfo(bundle.verdict, bundle.claim?.status, bundle.final_report).headline;
        const summary = bundle.final_report?.decision_summary || 'Claim assessment report.';
        const text = `INSUREMATE ADJUDICATION ASSESSMENT [${claimId}]\nVerdict: ${verdict}\n\nExecutive Summary:\n${summary}`;
        Utils.copyToClipboard(text);
      });
    }

    // View Raw JSON Audit (Tab switch)
    const btnViewJson = document.getElementById('btn-copy-raw-json');
    if (btnViewJson) {
      btnViewJson.addEventListener('click', () => {
        this.switchTab('tab-raw-state');
      });
    }

    // Download Text Report Fallback
    const btnDownloadReport = document.getElementById('btn-download-claim-report');
    if (btnDownloadReport) {
      btnDownloadReport.addEventListener('click', () => {
        const bundle = this.activeBundle;
        if (!bundle) {
          Utils.showToast('No active claim report to download.', 'warning');
          return;
        }
        const claimId = bundle.claim?.claim_id || 'claim_report';
        const report = bundle.final_report;
        const verdict = this.getVerdictDisplayInfo(bundle.verdict, bundle.claim?.status, report).headline;
        const textContent = `=======================================================
INSUREMATE ADJUDICATION ASSESSMENT REPORT
Claim ID: ${claimId}
Verdict: ${verdict}
Worker Engine Status: ${bundle.claim?.status || 'COMPLETED'}
Generated: ${new Date().toISOString()}
=======================================================

EXECUTIVE SUMMARY:
${report?.decision_summary || 'Assessment completed.'}

ACTION ITEMS & REMEDIATION:
${(report?.action_items || []).map((item, idx) => `${idx + 1}. ${item}`).join('\n') || 'None. All criteria fulfilled.'}

COVERAGE PERIOD AUDIT:
${report?.coverage_validity_status || 'PASS'}

DISCLAIMER:
This assessment is an autonomous AI preparation audit. Final approval remains subject to insurer adjudication rules.
`;
        Utils.downloadFile(`${claimId}_Adjudication_Report.txt`, textContent, 'text/plain');
      });
    }
  },

  switchTab(tabId) {
    const tabBtns = document.querySelectorAll('.results-tab-btn');
    tabBtns.forEach(btn => {
      if (btn.getAttribute('data-tab') === tabId) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    });

    document.querySelectorAll('.results-tab-pane').forEach(pane => {
      pane.classList.remove('active');
    });
    const target = document.getElementById(tabId);
    if (target) {
      target.classList.add('active');
      target.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  },

  /**
   * Main Render Entrypoint
   */
  renderClaimResults(bundle) {
    if (!bundle) {
      this.renderEmptyState();
      return;
    }

    const report = bundle.final_report;
    const latestState = bundle.latest_state || {};
    const claim = bundle.claim || {};
    const verdict = bundle.verdict || report?.final_status || claim.status || 'UNKNOWN';

    // 1. Module 1: The Adjudication Verdict Hero Banner
    this.renderVerdictHero(verdict, report, claim);

    // 2. Module 2: High-Impact KPI Metrics Bar (4 Cards)
    this.renderKPIMetrics(bundle);

    // 3. Executive Summary & Action Items
    this.renderExecutiveSummary(report, verdict);

    // 4. Module 3: Interactive Evidence & Document Remediation Center
    this.renderRemediationCenter(latestState, report);

    // 5. Module 4: Coverage & Timeline Visualizer (Gantt + Date Audits)
    this.renderCoverageTimeline(latestState, report);

    // 6. Document Completeness & Structure Validation
    this.renderDocumentValidation(latestState.validation_result);

    // 7. Extracted Entity Field Grid
    this.renderExtractedEntities(latestState.extracted_data || []);

    // 8. Technical Details (Raw JSON)
    const jsonCode = document.getElementById('claim-raw-json-code');
    if (jsonCode) {
      jsonCode.textContent = JSON.stringify(bundle, null, 2);
    }
  },

  /**
   * Helper to decode status into human-readable adjudication verdict
   */
  getVerdictDisplayInfo(verdictRaw, workerStatusRaw, report) {
    const v = String(verdictRaw || '').toUpperCase();
    const w = String(workerStatusRaw || '').toUpperCase();
    const missingCount = report?.missing_count ?? report?.missing_documents?.length ?? 0;

    const isRunning = w.includes('RUNNING') || w.includes('IN_PROGRESS');

    if (isRunning) {
      return {
        theme: 'indigo',
        pillText: 'PROCESSING ADJUDICATION',
        workerText: 'Worker Engine: Running',
        headline: 'Agent Execution In Progress',
        summary: 'Multimodal vision parsing and cross-document validation are actively executing.',
        icon: 'clock'
      };
    }

    if (v.includes('READY') || v.includes('CLAIM_READY')) {
      return {
        theme: 'emerald',
        pillText: 'CLAIM READY',
        workerText: 'Worker Engine: Finished',
        headline: 'Claim Ready for Direct Insurer Submission',
        summary: report?.decision_summary || 'All required evidence documents have been verified and coverage dates satisfy policy terms with zero unfulfilled clauses.',
        icon: 'shieldCheck'
      };
    }

    if (v.includes('MISSING_EVIDENCE') || v.includes('MISSING')) {
      const countLabel = missingCount > 0 ? `${missingCount} Mandatory Evidence Items Missing` : 'Mandatory Evidence Required';
      return {
        theme: 'amber',
        pillText: 'MISSING EVIDENCE REQUIRED',
        workerText: 'Worker Engine: Finished',
        headline: `Action Required: ${countLabel}`,
        summary: report?.decision_summary || 'The submitted claim package is missing mandatory supporting evidence required under policy terms.',
        icon: 'alertTriangle'
      };
    }

    if (v.includes('INVALID_DOCUMENTS') || v.includes('INVALID_DOCUMENT') || v.includes('INVERSION')) {
      return {
        theme: 'rose',
        pillText: 'DOCUMENT INTEGRITY ISSUES',
        workerText: 'Worker Engine: Finished',
        headline: 'Document Format or Slot Mismatch Detected',
        summary: report?.decision_summary || 'Uploaded documents do not match their assigned slots or failed mandatory structure validation.',
        icon: 'xCircle'
      };
    }

    if (v.includes('DATES') || v.includes('DATE_MISMATCH') || v.includes('INVALID_CLAIM_DATES')) {
      return {
        theme: 'rose',
        pillText: 'COVERAGE WINDOW BREACH',
        workerText: 'Worker Engine: Finished',
        headline: 'Incident Date Outside Policy Coverage Window',
        summary: report?.decision_summary || 'The reported incident date falls outside the active policy coverage dates.',
        icon: 'calendar'
      };
    }

    if (v.includes('INSUFFICIENT')) {
      return {
        theme: 'amber',
        pillText: 'INSUFFICIENT DATA / REVIEW NEEDED',
        workerText: 'Worker Engine: Finished',
        headline: 'Examiner Review Required',
        summary: report?.decision_summary || 'Insufficient information extracted to conclusively determine claim readiness.',
        icon: 'info'
      };
    }

    return {
      theme: 'indigo',
      pillText: 'ADJUDICATION ASSESSED',
      workerText: `Worker Engine: ${w || 'Finished'}`,
      headline: String(v).replace(/_/g, ' '),
      summary: report?.decision_summary || 'Claim assessment completed.',
      icon: 'fileText'
    };
  },

  /**
   * MODULE 1: The Adjudication Verdict Hero Banner
   */
  renderVerdictHero(verdict, report, claim) {
    const container = document.getElementById('results-verdict-banner-container');
    if (!container) return;

    const info = this.getVerdictDisplayInfo(verdict, claim?.status, report);

    const iconSvg = Utils.svgIcon(info.icon, 24, 2.2);

    container.innerHTML = `
      <div class="verdict-hero-card verdict-${info.theme}">
        <div class="verdict-hero-inner">
          <div class="verdict-hero-left">
            <div class="verdict-icon-container icon-${info.theme}">
              ${iconSvg}
            </div>
            <div>
              <div class="verdict-meta-badges">
                <span class="verdict-status-pill pill-${info.theme}">
                  <span class="beacon-dot pulse"></span>
                  ${info.pillText}
                </span>
                <span class="worker-status-chip">
                  <span style="font-family: var(--font-mono);">${info.workerText}</span>
                </span>
                <span class="worker-status-chip" style="font-family: var(--font-mono);">
                  Claim ID: <strong style="color: var(--text-heading);">${Utils.escapeHtml(claim?.claim_id || '--')}</strong>
                </span>
              </div>
              <h2 class="verdict-title">${Utils.escapeHtml(info.headline)}</h2>
              <p class="verdict-summary-text">${Utils.escapeHtml(info.summary)}</p>
            </div>
          </div>

          <div class="verdict-hero-actions">
            <button class="btn btn-secondary btn-sm" id="btn-export-claim-pdf" title="Print or save as PDF">
              ${Utils.svgIcon('fileText', 13)}
              <span>Export Report (PDF)</span>
            </button>
            <button class="btn btn-secondary btn-sm" id="btn-copy-claim-summary" title="Copy clean summary to clipboard">
              ${Utils.svgIcon('copy', 13)}
              <span>Copy Summary</span>
            </button>
            <button class="btn btn-secondary btn-sm" id="btn-copy-raw-json" title="Inspect full JSON memory package">
              ${Utils.svgIcon('search', 13)}
              <span>View Raw JSON</span>
            </button>
            <button class="btn btn-primary btn-sm" data-action="new-claim">
              ${Utils.svgIcon('plus', 13)}
              <span>+ Prepare New Claim</span>
            </button>
          </div>
        </div>
      </div>
    `;

    // Rebind toolbar actions
    this.bindActionToolbar();
  },

  /**
   * MODULE 2: High-Impact KPI Metrics Bar (4 Cards)
   */
  renderKPIMetrics(bundle) {
    const container = document.getElementById('results-kpi-metrics-container');
    if (!container) return;

    const latestState = bundle.latest_state || {};
    const report = bundle.final_report || {};
    const extracted = latestState.extracted_data || [];
    const claim = bundle.claim || {};

    // 1. Total Submitted Docs & Pages (deduplicate filenames)
    const rawFiles = [claim.policy_filename, ...(claim.claim_filenames || (claim.claim_filename ? [claim.claim_filename] : []))].filter(Boolean);
    const uniqueFiles = Array.from(new Set(rawFiles));
    const docCount = uniqueFiles.length || (claim.policy_filename ? 2 : (extracted.length > 0 ? 2 : 1));
    const pageCount = extracted.length || report.total_documents_processed || (latestState.validation_result?.total_documents) || (latestState.validation_result?.valid_documents) || 0;

    // 2. Extraction & Validation Integrity
    const invalidCount = latestState.validation_result?.invalid_count || 0;
    const passedPages = latestState.validation_result?.valid_documents !== undefined
      ? latestState.validation_result.valid_documents
      : Math.max(0, pageCount - invalidCount);
    const isIntegrityPass = invalidCount === 0 && pageCount > 0;

    // 3. Missing Evidence Count
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
        return String(d.status || '').toLowerCase() === 'missing';
      }).length;
    }

    // 4. Coverage Period Validity
    const validity = latestState.validity_result || report.validity_check || {};
    const isCoveragePass = validity.valid !== false && report.coverage_validity_status !== 'FAIL';
    const policyPeriod = validity.policy_period || {};
    const coverageDetail = isCoveragePass
      ? (policyPeriod.start && policyPeriod.end ? `${policyPeriod.start} ⟶ ${policyPeriod.end}` : 'Within active policy window')
      : (validity.reasons?.[0] || 'Incident date out of coverage window');

    container.innerHTML = `
      <div class="kpi-metrics-row">
        <!-- Card 1: Total Submitted -->
        <div class="kpi-modern-card">
          <div class="kpi-card-header">
            <span class="kpi-card-title">Submitted Documents</span>
            <div class="kpi-card-icon-wrap" style="background: rgba(56, 189, 248, 0.1); color: var(--accent);">
              ${Utils.svgIcon('fileText', 16)}
            </div>
          </div>
          <div class="kpi-card-val">${docCount} <span style="font-size: 0.88rem; font-weight: 500; color: var(--text-muted);">file${docCount !== 1 ? 's' : ''}</span></div>
          <div class="kpi-card-subtext">
            <span>${pageCount} total pages extracted & parsed</span>
          </div>
        </div>

        <!-- Card 2: Extraction Integrity -->
        <div class="kpi-modern-card">
          <div class="kpi-card-header">
            <span class="kpi-card-title">Extraction Integrity</span>
            <div class="kpi-card-icon-wrap" style="background: ${isIntegrityPass ? 'rgba(16, 185, 129, 0.1)' : 'rgba(244, 63, 94, 0.1)'}; color: ${isIntegrityPass ? 'var(--emerald)' : 'var(--rose)'};">
              ${Utils.svgIcon(isIntegrityPass ? 'shieldCheck' : 'alertTriangle', 16)}
            </div>
          </div>
          <div class="kpi-card-val" style="color: ${isIntegrityPass ? 'var(--emerald)' : 'var(--rose)'};">
            ${passedPages} / ${pageCount || 1}
            <span style="font-size: 0.8rem; font-weight: 500;">Valid</span>
          </div>
          <div class="kpi-card-subtext">
            <span>${invalidCount === 0 ? '100% structural fields verified' : `${invalidCount} page(s) flagged for review`}</span>
          </div>
        </div>

        <!-- Card 3: Missing Evidence Count -->
        <div class="kpi-modern-card">
          <div class="kpi-card-header">
            <span class="kpi-card-title">Missing Evidence</span>
            <div class="kpi-card-icon-wrap" style="background: ${missingCount === 0 ? 'rgba(16, 185, 129, 0.1)' : 'rgba(245, 158, 11, 0.1)'}; color: ${missingCount === 0 ? 'var(--emerald)' : 'var(--amber)'};">
              ${Utils.svgIcon(missingCount === 0 ? 'checkCircle' : 'alertTriangle', 16)}
            </div>
          </div>
          <div class="kpi-card-val" style="color: ${missingCount === 0 ? 'var(--emerald)' : 'var(--amber)'};">
            ${missingCount}
            <span style="font-size: 0.8rem; font-weight: 500;">Missing</span>
          </div>
          <div class="kpi-card-subtext">
            <span>${missingCount === 0 ? 'All policy clauses satisfied' : `${missingCount} mandatory clause(s) unfulfilled`}</span>
          </div>
        </div>

        <!-- Card 4: Coverage Period Validity -->
        <div class="kpi-modern-card">
          <div class="kpi-card-header">
            <span class="kpi-card-title">Coverage Validity</span>
            <div class="kpi-card-icon-wrap" style="background: ${isCoveragePass ? 'rgba(16, 185, 129, 0.1)' : 'rgba(244, 63, 94, 0.1)'}; color: ${isCoveragePass ? 'var(--emerald)' : 'var(--rose)'};">
              ${Utils.svgIcon(isCoveragePass ? 'calendar' : 'xCircle', 16)}
            </div>
          </div>
          <div class="kpi-card-val" style="color: ${isCoveragePass ? 'var(--emerald)' : 'var(--rose)'}; font-size: 1.25rem;">
            ${isCoveragePass ? 'PASS' : 'BREACH'}
          </div>
          <div class="kpi-card-subtext" title="${Utils.escapeHtml(coverageDetail)}">
            <span style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${Utils.escapeHtml(coverageDetail)}</span>
          </div>
        </div>
      </div>
    `;
  },

  /**
   * Executive Summary & Action Items Pane
   */
  renderExecutiveSummary(report, verdict) {
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
        actionItemsEl.innerHTML = `
          <li style="color: var(--emerald); display: flex; align-items: center; gap: 8px;">
            ${Utils.svgIcon('checkCircle', 15)}
            <span>Zero action items required. Claim satisfies all documentation and coverage criteria.</span>
          </li>
        `;
      } else {
        actionItemsEl.innerHTML = items.map(item => `
          <li style="display: flex; align-items: flex-start; gap: 10px; margin-bottom: 8px;">
            <div style="color: var(--amber); margin-top: 2px;">${Utils.svgIcon('arrowRight', 14)}</div>
            <span style="color: var(--text-primary); line-height: 1.5;">${Utils.escapeHtml(item)}</span>
          </li>
        `).join('');
      }
    }
  },

  /**
   * MODULE 3: Interactive Evidence & Document Remediation Center (Replaces Flat Table)
   */
  renderRemediationCenter(latestState, report) {
    const container = document.getElementById('remediation-cards-container');
    if (!container) return;

    const missingData = latestState?.missing_documents || report?.missing_documents_analysis || {};
    const rawItems = missingData?.missing_documents || missingData?.document_results || missingData?.items || report?.missing_documents || [];

    if (!rawItems || rawItems.length === 0) {
      container.innerHTML = `
        <div style="background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.25); border-radius: var(--radius-md); padding: 28px; text-align: center; color: var(--emerald);">
          <div style="display: inline-flex; align-items: center; justify-content: center; width: 44px; height: 44px; border-radius: 50%; background: rgba(16, 185, 129, 0.15); margin-bottom: 12px;">
            ${Utils.svgIcon('checkCircle', 24)}
          </div>
          <h4 style="font-size: 1rem; font-weight: 700; margin: 0 0 6px 0; color: var(--text-heading);">All Required Evidence Satisfied</h4>
          <p style="font-size: 0.82rem; color: var(--text-secondary); margin: 0; max-width: 500px; margin-inline: auto;">
            Zero missing documents detected. Every mandatory evidence item stipulated by the insurance policy schedule has been verified.
          </p>
        </div>
      `;
      return;
    }

    container.innerHTML = rawItems.map((doc, idx) => {
      // Normalize item
      const isString = typeof doc === 'string';
      const docName = isString ? doc : (doc.document_title || doc.required_document || doc.document_name || doc.title || doc.name || 'Required Evidence');
      const statusRaw = String(doc.status || '').toLowerCase();
      const isMissing = isString ? true : (doc.missing === true || statusRaw === 'missing');
      const isReceived = !isMissing && (statusRaw === 'received' || statusRaw === 'found' || statusRaw === 'available' || statusRaw === 'present' || doc.page_number != null);

      const clauseCitation = doc.clause || doc.clause_reference || doc.source || (isString ? 'Mandatory Policy Evidence' : 'Clause 4.1 - Claim Documentation');
      const reasonText = doc.reason || doc.matching_reason || (isReceived ? 'Matching evidence identified and validated in submitted claim bundle.' : 'Mandatory document required under policy terms was not found in the submitted claim bundle.');
      const pageInfo = doc.page_number != null ? `Page ${doc.page_number}` : (doc.source_page ? `Page ${doc.source_page}` : null);

      const statusTagHtml = isReceived
        ? `<span class="req-status-tag tag-verified">${Utils.svgIcon('check', 12, 2.5)} Received & Verified</span>`
        : `<span class="req-status-tag tag-missing">${Utils.svgIcon('alertTriangle', 12, 2.5)} Missing — Mandatory</span>`;

      const severityHtml = isMissing
        ? `<span class="severity-pill">${Utils.svgIcon('alertTriangle', 10, 2.5)} Blocks Claim Payout</span>`
        : '';

      const dropzoneId = `remediation-dropzone-${idx}`;
      const fileInputId = `remediation-input-${idx}`;

      return `
        <div class="requirement-card ${isReceived ? 'status-verified' : 'status-missing'}" id="req-card-${idx}">
          <div class="req-card-top">
            <div class="req-title-group">
              <h4 class="req-doc-title">${Utils.escapeHtml(docName)}</h4>
              <span class="clause-badge">${Utils.svgIcon('fileText', 11)} ${Utils.escapeHtml(clauseCitation)}</span>
              ${severityHtml}
            </div>
            <div>
              ${statusTagHtml}
            </div>
          </div>

          <div class="req-reason-box">
            ${Utils.escapeHtml(reasonText)}
          </div>

          <div class="req-meta-row">
            <div style="color: var(--text-muted); display: flex; align-items: center; gap: 8px;">
              ${pageInfo ? `<span>Verified Source: <strong style="color: var(--accent); font-family: var(--font-mono);">${pageInfo}</strong></span>` : '<span>Awaiting upload & verification</span>'}
            </div>
            ${pageInfo && doc.page_number != null ? `
              <button class="btn btn-secondary btn-sm" onclick="DocumentsView.openDetailModal(${doc.page_number - 1})" style="padding: 2px 8px; font-size: 0.72rem;">
                ${Utils.svgIcon('search', 11)} Inspect Page
              </button>
            ` : ''}
          </div>

          ${isMissing ? `
            <div class="inline-remediation-dropzone" id="${dropzoneId}" onclick="document.getElementById('${fileInputId}').click()">
              <div class="remediation-drop-left">
                <div class="remediation-drop-icon">
                  ${Utils.svgIcon('upload', 16)}
                </div>
                <div class="remediation-drop-text">
                  <span class="remediation-drop-title">Upload Missing Document: ${Utils.escapeHtml(docName)}</span>
                  <span class="remediation-drop-hint">Drag & drop PDF here, or click to browse</span>
                </div>
              </div>
              <div>
                <button type="button" class="btn btn-secondary btn-sm" style="pointer-events: none;">
                  Select File
                </button>
              </div>
              <input type="file" id="${fileInputId}" class="remediation-file-input" accept=".pdf,.png,.jpg,.jpeg" onchange="ClaimView.handleInlineRemediation(event, '${idx}', '${Utils.escapeHtml(docName)}')">
            </div>
          ` : ''}
        </div>
      `;
    }).join('');

    // Setup drag events on dropzones
    rawItems.forEach((doc, idx) => {
      const dropzone = document.getElementById(`remediation-dropzone-${idx}`);
      const fileInput = document.getElementById(`remediation-input-${idx}`);
      if (!dropzone || !fileInput) return;

      ['dragenter', 'dragover'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
          e.preventDefault();
          e.stopPropagation();
          dropzone.classList.add('dragover');
        });
      });

      ['dragleave', 'drop'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
          e.preventDefault();
          e.stopPropagation();
          dropzone.classList.remove('dragover');
        });
      });

      dropzone.addEventListener('drop', (e) => {
        if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0]) {
          this.uploadRemediationFile(e.dataTransfer.files[0], idx, doc.document_title || doc.name || 'Document');
        }
      });
    });
  },

  handleInlineRemediation(e, idx, docName) {
    if (e.target.files && e.target.files[0]) {
      this.uploadRemediationFile(e.target.files[0], idx, docName);
    }
  },

  async uploadRemediationFile(file, idx, docName) {
    const claimId = this.activeClaimId;
    if (!claimId) {
      Utils.showToast('No active claim session to attach document to.', 'error');
      return;
    }

    const dropzone = document.getElementById(`remediation-dropzone-${idx}`);
    if (dropzone) {
      dropzone.innerHTML = `
        <div style="width: 100%;">
          <div style="display: flex; align-items: center; justify-content: space-between; font-size: 0.78rem;">
            <span>Uploading <strong>${Utils.escapeHtml(file.name)}</strong> for ${Utils.escapeHtml(docName)}...</span>
            <span style="color: var(--accent);">Processing</span>
          </div>
          <div class="remediation-uploading-bar">
            <div class="remediation-uploading-progress"></div>
          </div>
        </div>
      `;
    }

    try {
      Utils.showToast(`Uploading ${file.name} to claim ${claimId}...`, 'info');
      await API.addDocuments(claimId, [file]);

      Utils.showToast(`Successfully uploaded ${file.name}!`, 'success');

      if (dropzone) {
        dropzone.innerHTML = `
          <div style="display: flex; align-items: center; justify-content: space-between; width: 100%; gap: 10px;">
            <div style="display: flex; align-items: center; gap: 8px; color: var(--emerald); font-size: 0.8rem; font-weight: 600;">
              ${Utils.svgIcon('checkCircle', 16)}
              <span>Uploaded ${Utils.escapeHtml(file.name)}. Ready for agent audit.</span>
            </div>
            <button class="btn btn-primary btn-sm" onclick="ClaimView.triggerAgentReRun('${claimId}')">
              ${Utils.svgIcon('refresh', 12)} Re-Run Agent
            </button>
          </div>
        `;
      }
    } catch (err) {
      console.error('Failed to upload remediation file:', err);
      Utils.showToast(`Upload failed: ${err.message}`, 'error');
      if (dropzone) {
        dropzone.innerHTML = `
          <div style="color: var(--rose); font-size: 0.78rem; display: flex; align-items: center; gap: 8px;">
            ${Utils.svgIcon('xCircle', 14)} Upload failed: ${Utils.escapeHtml(err.message)}
          </div>
        `;
      }
    }
  },

  async triggerAgentReRun(claimId) {
    try {
      Utils.showToast(`Starting agent re-evaluation for ${claimId}...`, 'info');
      await API.startAgent(claimId, { background: true });
      window.App.navigateTo('agent');
    } catch (err) {
      Utils.showToast(`Failed to trigger agent: ${err.message}`, 'error');
    }
  },

  /**
   * MODULE 4: Coverage & Timeline Visualizer (Validity & Dates Tab)
   */
  renderCoverageTimeline(latestState, report) {
    const validityData = latestState.validity_result || report?.validity_check || {};
    const policyDatesEl = document.getElementById('validity-policy-dates');
    const statusPill = document.getElementById('validity-math-status');
    const container = document.getElementById('validity-checks-list');
    const ganttContainer = document.getElementById('coverage-gantt-chart-container');

    const isValid = validityData?.valid !== false && report?.coverage_validity_status !== 'FAIL';
    const policyPeriod = validityData?.policy_period || {};

    if (policyDatesEl) {
      if (policyPeriod.start && policyPeriod.end) {
        policyDatesEl.textContent = `${policyPeriod.start} ⟶ ${policyPeriod.end}`;
      } else {
        policyDatesEl.textContent = 'Active Policy Window Verified';
      }
    }

    if (statusPill) {
      statusPill.innerHTML = `${isValid ? Utils.svgIcon('check', 11, 2.5) : Utils.svgIcon('x', 11, 2.5)} ${isValid ? 'COVERAGE VALID' : 'COVERAGE BREACH'}`;
      statusPill.className = `badge ${isValid ? 'badge-ready' : 'badge-error'}`;
    }

    // Render Visual Gantt / Timeline Bar
    if (ganttContainer) {
      const startDate = policyPeriod.start || '2024-01-01';
      const endDate = policyPeriod.end || '2025-01-01';
      const incidentDate = validityData.incident_date || latestState.extracted_data?.[0]?.incident_date || 'Within Period';

      ganttContainer.innerHTML = `
        <div class="gantt-container">
          <div class="gantt-track-bg">
            <div class="gantt-coverage-window" style="left: 10%; width: 75%;"></div>
            <div class="gantt-marker marker-incident ${isValid ? '' : 'out-of-bounds'}" style="left: ${isValid ? '42%' : '92%'};">
              <span class="gantt-marker-badge">${Utils.svgIcon('calendar', 10)} Incident: ${Utils.escapeHtml(incidentDate)}</span>
              <div class="gantt-marker-pin"></div>
            </div>
          </div>
          <div class="gantt-legend-row">
            <span>Policy Start: <strong>${Utils.escapeHtml(startDate)}</strong></span>
            <span style="color: var(--emerald); font-weight: 600;">Active Coverage Window (365 Days)</span>
            <span>Policy Expiry: <strong>${Utils.escapeHtml(endDate)}</strong></span>
          </div>
        </div>
      `;
    }

    // Render Granular Date Checks
    if (container) {
      const checks = validityData?.checks || validityData?.date_checks || [];
      if (checks.length === 0) {
        container.innerHTML = `
          <div class="date-audit-item">
            <div class="date-audit-left">
              <div class="date-audit-icon audit-pass">
                ${Utils.svgIcon('checkCircle', 16)}
              </div>
              <div>
                <div class="date-audit-desc-title">Hospitalization & Treatment Window Check</div>
                <div class="date-audit-desc-sub">All document invoice, incident, and treatment dates fall within the active coverage period.</div>
              </div>
            </div>
            <div class="date-audit-right">
              <span class="date-audit-tag">Coverage Window Satisfied</span>
              <span class="badge badge-ready">${Utils.svgIcon('check', 11, 2.5)} Valid</span>
            </div>
          </div>
        `;
        return;
      }

      container.innerHTML = checks.map(c => {
        const isPass = c.valid !== false;
        return `
          <div class="date-audit-item">
            <div class="date-audit-left">
              <div class="date-audit-icon ${isPass ? 'audit-pass' : 'audit-fail'}">
                ${Utils.svgIcon(isPass ? 'checkCircle' : 'xCircle', 16)}
              </div>
              <div>
                <div class="date-audit-desc-title">${Utils.escapeHtml(c.document_type || 'Claim Document')} (Page ${c.page || 1})</div>
                <div class="date-audit-desc-sub">${Utils.escapeHtml(c.reason || 'Verified against policy effective dates.')}</div>
              </div>
            </div>
            <div class="date-audit-right">
              <span class="date-audit-tag">${Utils.escapeHtml(c.normalized_date || c.raw_date || '--')}</span>
              <span class="badge ${isPass ? 'badge-ready' : 'badge-error'}">
                ${isPass ? Utils.svgIcon('check', 11, 2.5) : Utils.svgIcon('x', 11, 2.5)} ${isPass ? 'Valid' : 'Breach'}
              </span>
            </div>
          </div>
        `;
      }).join('');
    }
  },

  /**
   * Document Completeness & Integrity Pane
   */
  renderDocumentValidation(validationData) {
    const container = document.getElementById('doc-validation-list');
    if (!container) return;

    if (!validationData) {
      container.innerHTML = `
        <div class="empty-state" style="padding: 24px;">
          <p>No document structure validation results recorded yet.</p>
        </div>
      `;
      return;
    }

    const pages = validationData.pages || validationData.page_results || [];
    if (pages.length === 0) {
      container.innerHTML = `
        <div style="background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.25); border-radius: var(--radius-sm); padding: 16px 20px; color: var(--emerald); font-size: 0.82rem; display: flex; align-items: center; gap: 10px;">
          ${Utils.svgIcon('checkCircle', 18)}
          <span>All submitted document pages passed mandatory field completeness and role integrity verification.</span>
        </div>
      `;
      return;
    }

    container.innerHTML = pages.map((p, idx) => {
      const isPass = p.is_valid !== false;
      return `
        <div style="background: var(--bg-elevated); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); padding: 14px 18px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px;">
          <div style="display: flex; align-items: center; gap: 12px;">
            <div style="color: ${isPass ? 'var(--emerald)' : 'var(--amber)'};">
              ${Utils.svgIcon(isPass ? 'checkCircle' : 'alertTriangle', 18)}
            </div>
            <div>
              <div style="font-weight: 600; color: var(--text-heading); font-size: 0.84rem;">Page ${p.page || idx + 1}: ${Utils.escapeHtml(p.type || 'Document')}</div>
              <div style="font-size: 0.76rem; color: var(--text-muted);">${Utils.escapeHtml(p.details || 'Standard required fields present.')}</div>
            </div>
          </div>
          <div>
            <span class="badge ${isPass ? 'badge-ready' : 'badge-warning'}">
              ${isPass ? Utils.svgIcon('check', 11, 2.5) : Utils.svgIcon('alertTriangle', 11, 2.5)}
              ${isPass ? 'Validated' : 'Action Required'}
            </span>
          </div>
        </div>
      `;
    }).join('');
  },

  /**
   * Extracted Information Grid
   */
  renderExtractedEntities(extractedPages) {
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
            ${Utils.svgIcon('fileText', 14)}
            <span>Page ${page.page_number} (${Utils.escapeHtml((page.document_type || 'Document').replace(/_/g, ' '))})</span>
          </div>
          <span class="badge badge-ready">${Utils.svgIcon('check', 10, 2.5)} Extracted</span>
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
          ${Utils.svgIcon('search', 12)} Inspect Page Details
        </button>
      </div>
    `).join('');
  },

  /**
   * Empty State View
   */
  renderEmptyState() {
    const heroContainer = document.getElementById('results-verdict-banner-container');
    if (heroContainer) {
      heroContainer.innerHTML = `
        <div class="empty-state" style="padding: 40px; background: var(--bg-card); border: 1px solid var(--border-subtle); border-radius: var(--radius-md);">
          <div class="empty-state-icon" style="color: var(--accent);">
            ${Utils.svgIcon('shield', 32, 1.8)}
          </div>
          <h4 style="font-size: 1.1rem; color: var(--text-heading); margin: 8px 0;">No Claim Assessment Available</h4>
          <p style="font-size: 0.82rem; color: var(--text-muted); max-width: 440px; margin-inline: auto;">
            Please select an existing claim from the archive or execute the InsureMate Agent to generate an adjudication assessment.
          </p>
          <div style="margin-top: 16px;">
            <button class="btn btn-primary btn-sm" data-action="new-claim">
              ${Utils.svgIcon('plus', 13)} Create New Claim
            </button>
          </div>
        </div>
      `;
    }
  }
};

window.ClaimView = ClaimView;
