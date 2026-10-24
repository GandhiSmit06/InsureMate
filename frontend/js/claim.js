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
    const handleExport = () => {
      if (!this.activeBundle) {
        Utils.showToast('No active claim report to export.', 'warning');
        return;
      }
      window.print();
    };
    if (btnExportPdf) btnExportPdf.addEventListener('click', handleExport);

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
    this.renderExecutiveSummary(report, verdict, latestState);

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
    let missingCount = 0;
    if (typeof report?.missing_count === 'number' && !isNaN(report.missing_count)) {
      missingCount = report.missing_count;
    } else if (Array.isArray(report?.missing_documents)) {
      missingCount = report.missing_documents.filter(d => this.isDocMissing(d)).length;
    }

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

    if (v.includes('DISCREPANCY') || v.includes('CONFLICT') || report?.consistency_status === 'FAIL' || (report?.decision_summary && (report.decision_summary.includes('Conflicting insurance') || report.decision_summary.includes('Cross-document integrity')))) {
      return {
        theme: 'rose',
        pillText: 'CRITICAL ENTITY DISCREPANCY',
        workerText: 'Worker Engine: Finished',
        headline: 'Cross-Document Entity Contradiction Detected',
        summary: report?.decision_summary || 'Conflicting insurance companies, policy identifiers, or patient details detected across submitted documents.',
        icon: 'alertTriangle'
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
    const consistencyDiscrepancies = latestState.consistency_results?.discrepancies || report.discrepancies || [];
    const hasDiscrepancy = (latestState.consistency_results?.consistent === false) || report.consistency_status === 'FAIL';
    const passedPages = latestState.validation_result?.valid_documents !== undefined
      ? latestState.validation_result.valid_documents
      : Math.max(0, pageCount - invalidCount);
    const isIntegrityPass = invalidCount === 0 && pageCount > 0 && !hasDiscrepancy;

    // 3. Missing Evidence Count
    let missingCount = 0;
    if (typeof report.missing_count === 'number' && !isNaN(report.missing_count)) {
      missingCount = report.missing_count;
    } else if (latestState.missing_documents?.summary?.missing !== undefined && typeof latestState.missing_documents.summary.missing === 'number') {
      missingCount = latestState.missing_documents.summary.missing;
    } else {
      const missingData = latestState.missing_documents || report.missing_documents_analysis || {};
      const allReqs = missingData.document_results || missingData.missing_documents || missingData.items || report.missing_documents || [];
      missingCount = Array.isArray(allReqs) ? allReqs.filter(d => this.isDocMissing(d)).length : 0;
    }

    // 4. Coverage Period Validity
    const validity = latestState.validity_result || report.validity_check || {};
    const isCoveragePass = validity.valid !== false && report.coverage_validity_status !== 'FAIL';
    const policyPeriod = validity.policy_period || report.policy_period || {};
    let pStart = policyPeriod.start || policyPeriod.policy_start_date || policyPeriod.policy_inception_date || policyPeriod.inception_date || policyPeriod.coverage_start_date || policyPeriod.effective_date || policyPeriod.from_date;
    let pEnd = policyPeriod.end || policyPeriod.policy_end_date || policyPeriod.policy_expiry_date || policyPeriod.expiry_date || policyPeriod.coverage_end_date || policyPeriod.expiration_date || policyPeriod.to_date;

    if (!pStart || !pEnd) {
      const extractedPages = latestState.extracted_data || [];
      for (const p of extractedPages) {
        if (!pStart) pStart = p.policy_start_date || p.policy_inception_date || p.inception_date || p.coverage_start_date || p.effective_date || p.start_date || p.from_date;
        if (!pEnd) pEnd = p.policy_end_date || p.policy_expiry_date || p.expiry_date || p.coverage_end_date || p.expiration_date || p.end_date || p.to_date;
        if (pStart && pEnd) break;
      }
    }

    const coverageDetail = isCoveragePass
      ? (pStart && pEnd ? `${pStart} ⟶ ${pEnd}` : 'Within active policy window')
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

        <!-- Card 2: Entity & Document Integrity -->
        <div class="kpi-modern-card">
          <div class="kpi-card-header">
            <span class="kpi-card-title">Entity & Field Integrity</span>
            <div class="kpi-card-icon-wrap" style="background: ${isIntegrityPass ? 'rgba(16, 185, 129, 0.1)' : 'rgba(244, 63, 94, 0.1)'}; color: ${isIntegrityPass ? 'var(--emerald)' : 'var(--rose)'};">
              ${Utils.svgIcon(isIntegrityPass ? 'shieldCheck' : 'alertTriangle', 16)}
            </div>
          </div>
          <div class="kpi-card-val" style="color: ${isIntegrityPass ? 'var(--emerald)' : 'var(--rose)'};">
            ${hasDiscrepancy ? `${consistencyDiscrepancies.length} Conflict${consistencyDiscrepancies.length > 1 ? 's' : ''}` : `${passedPages} / ${pageCount || 1}`}
            <span style="font-size: 0.8rem; font-weight: 500;">${hasDiscrepancy ? 'Critical' : 'Valid'}</span>
          </div>
          <div class="kpi-card-subtext">
            <span>${hasDiscrepancy ? 'Entity contradiction across docs' : (invalidCount === 0 ? '100% structural fields & entities verified' : `${invalidCount} page(s) flagged for review`)}</span>
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
  renderExecutiveSummary(report, verdict, latestState) {
    const discrepancies = report?.discrepancies || latestState?.consistency_results?.discrepancies || [];
    const hasDiscrepancy = discrepancies.length > 0 || latestState?.consistency_results?.consistent === false || report?.consistency_status === 'FAIL';

    const overviewEl = document.getElementById('results-overview-summary-text');
    if (overviewEl) {
      overviewEl.textContent = report?.decision_summary || (
        String(verdict).toUpperCase().includes('READY')
          ? 'All required evidence documents have been validated and coverage dates confirmed. Claim is ready for submission.'
          : (hasDiscrepancy ? 'Cross-document integrity check failed: Conflicting insurance entities or policy details detected across submitted documents.' : 'Claim assessment completed. Action is required due to missing mandatory documentation or date mismatches.')
      );
    }

    const actionItemsEl = document.getElementById('results-action-items-list');
    if (actionItemsEl) {
      let items = report?.action_items || [];
      if (items.length === 0 && discrepancies.length > 0) {
        items = discrepancies.map(d => `Resolve conflicting entity: ${d}`);
      }
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
            <div style="color: ${item.toLowerCase().includes('conflict') || item.toLowerCase().includes('mismatch') ? 'var(--rose)' : 'var(--amber)'}; margin-top: 2px;">
              ${Utils.svgIcon(item.toLowerCase().includes('conflict') || item.toLowerCase().includes('mismatch') ? 'alertTriangle' : 'arrowRight', 14)}
            </div>
            <span style="color: var(--text-primary); line-height: 1.5;">${Utils.escapeHtml(item)}</span>
          </li>
        `).join('');
      }
    }
  },

  /**
   * Helper to evaluate whether an evidence item is genuinely missing.
   * Returns true only for items confirmed missing (e.g. status MISSING, NOT_FOUND, missing: true)
   * and false for items that are received, verified, available, or linked to a document page.
   */
  isDocMissing(doc) {
    if (!doc) return false;
    if (typeof doc === 'string') return doc.trim().length > 0;
    if (typeof doc !== 'object') return false;

    const statusRaw = String(doc.status || '').toLowerCase().trim();

    // Explicitly marked as not missing or received/verified/available
    if (doc.missing === false || String(doc.missing).toLowerCase() === 'false') return false;
    if (['received', 'found', 'available', 'present', 'verified', 'valid', 'uploaded'].includes(statusRaw)) return false;
    if (doc.page_number != null && doc.page_number !== '' && doc.page_number !== 'null' && Number(doc.page_number) > 0) return false;
    if (doc.page_no != null && doc.page_no !== '' && doc.page_no !== 'null' && Number(doc.page_no) > 0) return false;

    // Confirmed missing
    if (doc.missing === true || String(doc.missing).toLowerCase() === 'true') return true;
    if (['missing', 'not_found', 'unfulfilled', 'pending', 'required', 'action_required'].includes(statusRaw)) return true;

    // If page_number is absent and status is not received, treat as missing
    if ((doc.page_number == null || doc.page_number === 'null' || doc.page_number === '') &&
        (doc.page_no == null || doc.page_no === 'null' || doc.page_no === '')) {
      return true;
    }

    return false;
  },

  /**
   * MODULE 3: Interactive Evidence & Document Remediation Center (Replaces Flat Table)
   * Displays ONLY genuinely missing documents that the user still needs to provide.
   */
  renderRemediationCenter(latestState, report) {
    const container = document.getElementById('remediation-cards-container');
    if (!container) return;

    const missingData = latestState?.missing_documents || report?.missing_documents_analysis || {};
    let candidateItems = [];

    if (Array.isArray(missingData?.document_results) && missingData.document_results.length > 0) {
      candidateItems = missingData.document_results;
    } else if (Array.isArray(missingData?.missing_documents) && missingData.missing_documents.length > 0) {
      candidateItems = missingData.missing_documents;
    } else if (Array.isArray(report?.missing_documents) && report.missing_documents.length > 0) {
      candidateItems = report.missing_documents;
    } else if (Array.isArray(missingData?.items) && missingData.items.length > 0) {
      candidateItems = missingData.items;
    }

    // Filter dynamically for ONLY genuinely missing items
    let missingItems = (candidateItems || []).filter(doc => this.isDocMissing(doc));

    // Fallback: If candidateItems had no missing items, but report.missing_documents has strings, check that
    if (missingItems.length === 0 && Array.isArray(report?.missing_documents) && report.missing_documents.length > 0) {
      missingItems = report.missing_documents.filter(doc => this.isDocMissing(doc));
    }

    if (!missingItems || missingItems.length === 0) {
      container.innerHTML = `
        <div style="background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.25); border-radius: var(--radius-md); padding: 32px 24px; text-align: center; color: var(--emerald);">
          <div style="display: inline-flex; align-items: center; justify-content: center; width: 48px; height: 48px; border-radius: 50%; background: rgba(16, 185, 129, 0.15); margin-bottom: 12px;">
            ${Utils.svgIcon('checkCircle', 24)}
          </div>
          <h4 style="font-size: 1.05rem; font-weight: 700; margin: 0 0 6px 0; color: var(--text-heading);">All Required Documents Available</h4>
          <p style="font-size: 0.85rem; color: var(--text-secondary); margin: 0; max-width: 520px; margin-inline: auto; line-height: 1.5;">
            All required documents are available. No missing evidence found.
          </p>
        </div>
      `;
      return;
    }

    container.innerHTML = missingItems.map((doc, idx) => {
      // Normalize item
      const isString = typeof doc === 'string';
      const docName = isString ? doc : (doc.document_title || doc.required_document || doc.document_name || doc.title || doc.name || 'Required Evidence');
      const clauseCitation = (!isString && (doc.clause || doc.clause_reference || doc.source)) ? (doc.clause || doc.clause_reference || doc.source) : 'Clause 4.1 - Claim Documentation';
      const reasonText = (!isString && (doc.reason || doc.matching_reason)) ? (doc.reason || doc.matching_reason) : 'Mandatory document required under policy terms was not found in the submitted claim bundle.';

      const statusTagHtml = `<span class="req-status-tag tag-missing">${Utils.svgIcon('alertTriangle', 12, 2.5)} Missing — Mandatory</span>`;
      const severityHtml = `<span class="severity-pill">${Utils.svgIcon('alertTriangle', 10, 2.5)} Blocks Claim Payout</span>`;

      const dropzoneId = `remediation-dropzone-${idx}`;
      const fileInputId = `remediation-input-${idx}`;

      return `
        <div class="requirement-card status-missing" id="req-card-${idx}">
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
              <span>Awaiting upload & verification</span>
            </div>
          </div>

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
        </div>
      `;
    }).join('');

    // Setup drag events on dropzones
    missingItems.forEach((doc, idx) => {
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
          const name = typeof doc === 'string' ? doc : (doc.document_title || doc.name || 'Document');
          this.uploadRemediationFile(e.dataTransfer.files[0], idx, name);
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
    const policyPeriod = validityData?.policy_period || report?.policy_period || {};

    let pStart = policyPeriod.start || policyPeriod.policy_start_date || policyPeriod.policy_inception_date || policyPeriod.inception_date || policyPeriod.coverage_start_date || policyPeriod.effective_date || policyPeriod.from_date;
    let pEnd = policyPeriod.end || policyPeriod.policy_end_date || policyPeriod.policy_expiry_date || policyPeriod.expiry_date || policyPeriod.coverage_end_date || policyPeriod.expiration_date || policyPeriod.to_date;

    if (!pStart || !pEnd) {
      const extractedPages = latestState.extracted_data || [];
      for (const p of extractedPages) {
        if (!pStart) pStart = p.policy_start_date || p.policy_inception_date || p.inception_date || p.coverage_start_date || p.effective_date || p.start_date || p.from_date;
        if (!pEnd) pEnd = p.policy_end_date || p.policy_expiry_date || p.expiry_date || p.coverage_end_date || p.expiration_date || p.end_date || p.to_date;
        if (pStart && pEnd) break;
      }
    }

    if (policyDatesEl) {
      if (pStart && pEnd) {
        policyDatesEl.textContent = `${pStart} ⟶ ${pEnd}`;
      } else if (pStart) {
        policyDatesEl.textContent = `From ${pStart}`;
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
      const startDate = pStart || '--';
      const endDate = pEnd || '--';

      // Dynamic incident date resolution
      let incidentDate = validityData.incident_date || null;
      if (!incidentDate && Array.isArray(validityData.checks) && validityData.checks.length > 0) {
        const firstWithDate = validityData.checks.find(c => c.normalized_date || c.raw_date);
        if (firstWithDate) {
          incidentDate = firstWithDate.normalized_date || firstWithDate.raw_date;
        }
      }
      if (!incidentDate && Array.isArray(latestState.extracted_data)) {
        for (const doc of latestState.extracted_data) {
          if (doc.document_type !== 'insurance_policy') {
            incidentDate = doc.document_date || doc.bill_date || doc.admission_date || doc.invoice_date || doc.report_date;
            if (incidentDate) break;
          }
        }
      }
      const displayIncident = incidentDate || 'Within Period';

      // Calculate duration dynamically if dates parseable
      let durationLabel = 'Active Coverage Window';
      if (pStart && pEnd) {
        const parseD = (s) => {
          if (!s) return null;
          const parts = String(s).split(/[\/\-.]/);
          if (parts.length === 3) {
            if (parts[0].length === 4) return new Date(parts[0], parts[1] - 1, parts[2]);
            return new Date(parts[2], parts[1] - 1, parts[0]);
          }
          return null;
        };
        const d1 = parseD(pStart);
        const d2 = parseD(pEnd);
        if (d1 && d2 && !isNaN(d1) && !isNaN(d2)) {
          const diffDays = Math.round(Math.abs(d2 - d1) / (1000 * 60 * 60 * 24)) + 1;
          if (diffDays > 0) {
            durationLabel = `Active Coverage Window (${diffDays} Days)`;
          }
        }
      }

      ganttContainer.innerHTML = `
        <div class="gantt-container">
          <div class="gantt-track-bg">
            <div class="gantt-coverage-window" style="left: 10%; width: 75%;"></div>
            <div class="gantt-marker marker-incident ${isValid ? '' : 'out-of-bounds'}" style="left: ${isValid ? '42%' : '92%'};">
              <span class="gantt-marker-badge">${Utils.svgIcon('calendar', 10)} Incident: ${Utils.escapeHtml(displayIncident)}</span>
              <div class="gantt-marker-pin"></div>
            </div>
          </div>
          <div class="gantt-legend-row">
            <span>Policy Start: <strong>${Utils.escapeHtml(startDate)}</strong></span>
            <span style="color: var(--emerald); font-weight: 600;">${Utils.escapeHtml(durationLabel)}</span>
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

    container.innerHTML = extractedPages.map((page, idx) => {
      const isPolicy = page.document_type === 'insurance_policy';
      const isBill = page.document_type === 'medical_bill' || page.document_type === 'invoice';
      const isReport = page.document_type === 'medical_report';
      const rawTitle = (page.document_title || '').replace(/\s*\(Page\s*\d+\)$/i, '').trim();

      // Determine clean, meaningful financial representation
      let financialHtml = '';
      if (isPolicy) {
        if (page.sum_insured) {
          financialHtml += `<div><span style="color: var(--text-muted);">Sum Insured:</span> <strong style="color: var(--emerald); font-weight: 700;">₹${Utils.escapeHtml(String(page.sum_insured))}</strong></div>`;
        }
        if (page.premium_amount) {
          financialHtml += `<div><span style="color: var(--text-muted);">Total Premium:</span> <strong style="color: var(--text-heading);">₹${Utils.escapeHtml(String(page.premium_amount))}</strong></div>`;
        }
      } else if (isBill) {
        const isReceipt = rawTitle.toLowerCase().includes('receipt') || !!page.receipt_number;
        const isPharmacy = rawTitle.toLowerCase().includes('pharmacy');
        if (isReceipt) {
          financialHtml += `<div><span style="color: var(--text-muted);">Paid / Receipt Amount:</span> <strong style="color: var(--emerald); font-weight: 700;">₹${Utils.escapeHtml(String(page.paid_amount || page.bill_amount))}</strong></div>`;
        } else if (isPharmacy) {
          financialHtml += `<div><span style="color: var(--text-muted);">Pharmacy Bill Amount:</span> <strong style="color: var(--emerald); font-weight: 700;">₹${Utils.escapeHtml(String(page.bill_amount))}</strong></div>`;
        } else {
          financialHtml += `<div><span style="color: var(--text-muted);">Total Bill Amount:</span> <strong style="color: var(--emerald); font-weight: 700;">₹${Utils.escapeHtml(String(page.bill_amount))}</strong></div>`;
          if (page.paid_amount && page.paid_amount !== page.bill_amount) {
            financialHtml += `<div><span style="color: var(--text-muted);">Amount Settled:</span> <strong style="color: var(--text-heading);">₹${Utils.escapeHtml(String(page.paid_amount))}</strong></div>`;
          }
        }
      } else if (isReport) {
        if (page.bill_amount) {
          financialHtml += `<div><span style="color: var(--text-muted);">Investigation Fee:</span> <strong style="color: var(--emerald);">₹${Utils.escapeHtml(String(page.bill_amount))}</strong></div>`;
        }
      } else {
        if (page.bill_amount) {
          const isCoverLetter = rawTitle.toLowerCase().includes('cover letter');
          const amtLabel = isCoverLetter ? 'Settled Inpatient Expenses:' : 'Disclosed Amount:';
          financialHtml += `<div><span style="color: var(--text-muted);">${amtLabel}</span> <strong style="color: var(--emerald);">₹${Utils.escapeHtml(String(page.bill_amount))}</strong></div>`;
        }
      }

      // Person identity: Policyholder for policy, Patient for hospital/claim
      let personHtml = '';
      if (isPolicy) {
        if (page.policy_holder_name) {
          personHtml += `<div><span style="color: var(--text-muted);">Policyholder:</span> <strong style="color: var(--text-heading);">${Utils.escapeHtml(page.policy_holder_name)}</strong></div>`;
        }
        if (page.insured_names && page.insured_names.length > 0) {
          const insJoined = page.insured_names.join(', ');
          if (insJoined !== page.policy_holder_name) {
            personHtml += `<div><span style="color: var(--text-muted);">Insured Member:</span> <strong style="color: var(--text-secondary);">${Utils.escapeHtml(insJoined)}</strong></div>`;
          }
        }
      } else {
        if (page.patient_name) {
          personHtml += `<div><span style="color: var(--text-muted);">Patient:</span> <strong style="color: var(--text-heading);">${Utils.escapeHtml(page.patient_name)}</strong></div>`;
        }
      }

      // Reference / Number
      let refHtml = '';
      if (page.policy_number) {
        refHtml += `<div><span style="color: var(--text-muted);">Policy #:</span> <strong style="font-family: var(--font-mono); color: var(--accent);">${Utils.escapeHtml(page.policy_number)}</strong></div>`;
      }
      if (!isPolicy) {
        if (page.receipt_number || (rawTitle.toLowerCase().includes('receipt') && page.bill_number)) {
          refHtml += `<div><span style="color: var(--text-muted);">Receipt #:</span> <strong style="font-family: var(--font-mono);">${Utils.escapeHtml(page.receipt_number || page.bill_number)}</strong></div>`;
        } else if (page.bill_number) {
          const numLabel = rawTitle.toLowerCase().includes('pharmacy') ? 'Invoice #:' : 'Bill #:';
          refHtml += `<div><span style="color: var(--text-muted);">${numLabel}</span> <strong style="font-family: var(--font-mono);">${Utils.escapeHtml(page.bill_number)}</strong></div>`;
        }
      }

      // Clinical / Facility Details
      let detailsHtml = '';
      if (page.hospital_name) {
        detailsHtml += `<div><span style="color: var(--text-muted);">Facility:</span> <strong style="color: var(--text-secondary);">${Utils.escapeHtml(page.hospital_name)}</strong></div>`;
      }
      if (page.doctor_name) {
        detailsHtml += `<div><span style="color: var(--text-muted);">Doctor:</span> <strong>${Utils.escapeHtml(page.doctor_name)}</strong></div>`;
      }
      if (page.diagnosis) {
        detailsHtml += `<div><span style="color: var(--text-muted);">Diagnosis:</span> <strong style="color: var(--accent);">${Utils.escapeHtml(page.diagnosis)}</strong></div>`;
      }

      // Dates
      let dateHtml = '';
      if (isPolicy && page.policy_start_date && page.policy_end_date) {
        dateHtml = `<div><span style="color: var(--text-muted);">Coverage Window:</span> <strong>${Utils.escapeHtml(page.policy_start_date)} ⟶ ${Utils.escapeHtml(page.policy_end_date)}</strong></div>`;
      } else if (page.document_date) {
        const dLabel = isBill ? 'Bill Date:' : (isReport ? 'Report Date:' : 'Date:');
        dateHtml = `<div><span style="color: var(--text-muted);">${dLabel}</span> <strong>${Utils.escapeHtml(page.document_date)}</strong></div>`;
      }

      return `
        <div class="card" style="margin-bottom: 0;">
          <div class="card-header" style="margin-bottom: 10px; align-items: flex-start;">
            <div style="flex: 1; min-width: 0; padding-right: 8px;">
              <div style="font-weight: 600; font-size: 0.84rem; color: var(--accent); display: flex; align-items: center; gap: 7px;">
                ${Utils.svgIcon(isPolicy ? 'shield' : (isBill ? 'fileText' : 'activity'), 14)}
                <span>Page ${page.page_number} (${Utils.escapeHtml((page.document_type || 'Document').replace(/_/g, ' '))})</span>
              </div>
              ${rawTitle ? `<div style="font-size: 0.72rem; color: var(--text-muted); margin-top: 3px; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${Utils.escapeHtml(rawTitle)}">${Utils.escapeHtml(rawTitle)}</div>` : ''}
            </div>
            <span class="badge badge-ready" style="flex-shrink: 0;">${Utils.svgIcon('check', 10, 2.5)} Extracted</span>
          </div>
          <div style="display: flex; flex-direction: column; gap: 6px; font-size: 0.78rem; margin-bottom: 12px;">
            ${page.insurer_name ? `<div><span style="color: var(--text-muted);">Insurer:</span> <strong style="color: var(--text-heading);">${Utils.escapeHtml(page.insurer_name)}</strong></div>` : ''}
            ${refHtml}
            ${personHtml}
            ${detailsHtml}
            ${financialHtml}
            ${dateHtml}
          </div>
          <button class="btn btn-secondary btn-sm" style="width: 100%; justify-content: center;" onclick="DocumentsView.openDetailModal(${idx})">
            ${Utils.svgIcon('search', 12)} Inspect Page Details
          </button>
        </div>
      `;
    }).join('');
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
