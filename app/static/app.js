/**
 * app/static/app.js
 * InsureMate Phase 7 Client-Side Orchestration Logic.
 * Handles document uploads, quick-load demos, autonomous agent execution,
 * interactive stepper animations, verdict card rendering, and claim memory.
 */

document.addEventListener('DOMContentLoaded', () => {
  // Application State
  const state = {
    policyFile: null,
    claimFile: null,
    activeClaimId: null,
    activeClaimData: null,
    isExecuting: false,
    historyList: []
  };

  // DOM Elements
  const policyDropzone = document.getElementById('policy-dropzone');
  const policyFileInput = document.getElementById('policy-file-input');
  const policyFileChip = document.getElementById('policy-file-chip');
  const btnRemovePolicy = document.getElementById('btn-remove-policy');

  const claimDropzone = document.getElementById('claim-dropzone');
  const claimFileInput = document.getElementById('claim-file-input');
  const claimFileChip = document.getElementById('claim-file-chip');
  const btnRemoveClaim = document.getElementById('btn-remove-claim');

  const uploadForm = document.getElementById('claim-upload-form');
  const inputGoal = document.getElementById('input-goal');
  const inputSessionName = document.getElementById('input-session-name');
  const toggleOffline = document.getElementById('toggle-offline-mode');
  const btnStartAgent = document.getElementById('btn-start-agent');

  const btnDemoHealth = document.getElementById('btn-demo-health');
  const btnDemoTravel = document.getElementById('btn-demo-travel');

  const executionCard = document.getElementById('execution-card');
  const executionTitle = document.getElementById('execution-title');
  const executionStatusPill = document.getElementById('execution-status-pill');
  const activeClaimIdEl = document.getElementById('active-claim-id');
  const activeIterationEl = document.getElementById('active-iteration-count');
  const progressBar = document.getElementById('agent-progress-bar');
  const bubbleText = document.getElementById('bubble-text');

  const resultCard = document.getElementById('result-card');
  const verdictBanner = document.getElementById('verdict-banner');
  const verdictTitle = document.getElementById('verdict-title');
  const verdictIcon = document.getElementById('verdict-icon');
  const decisionSummaryText = document.getElementById('decision-summary-text');

  const metricDocsCount = document.getElementById('metric-docs-count');
  const metricValidityStatus = document.getElementById('metric-validity-status');
  const metricMissingCount = document.getElementById('metric-missing-count');
  const metricIdentityMatch = document.getElementById('metric-identity-match');

  const missingTableBody = document.getElementById('missing-table-body');
  const validityTableBody = document.getElementById('validity-table-body');
  const policyStartDisplay = document.getElementById('policy-start-display');
  const policyEndDisplay = document.getElementById('policy-end-display');
  const extractedCardsGrid = document.getElementById('extracted-cards-grid');
  const toolHistoryTableBody = document.getElementById('tool-history-table-body');
  const rawJsonCode = document.getElementById('raw-json-code');

  const btnToggleHistory = document.getElementById('btn-toggle-history');
  const btnCloseHistory = document.getElementById('btn-close-history');
  const historySidebar = document.getElementById('history-sidebar');
  const historyListEl = document.getElementById('history-list');
  const historyCountEl = document.getElementById('history-count');

  const btnCopySummary = document.getElementById('btn-copy-summary');
  const btnNewClaim = document.getElementById('btn-new-claim');

  // ============================================================================
  // File Dropzone Handling
  // ============================================================================
  function setupDropzone(dropzone, fileInput, fileChip, removeBtn, stateKey) {
    ['dragenter', 'dragover'].forEach(name => {
      dropzone.addEventListener(name, (e) => {
        e.preventDefault();
        dropzone.classList.add('drag-over');
      });
    });

    ['dragleave', 'drop'].forEach(name => {
      dropzone.addEventListener(name, (e) => {
        e.preventDefault();
        dropzone.classList.remove('drag-over');
      });
    });

    dropzone.addEventListener('drop', (e) => {
      if (e.dataTransfer.files && e.dataTransfer.files[0]) {
        handleFileSelect(e.dataTransfer.files[0], fileChip, stateKey);
      }
    });

    fileInput.addEventListener('change', (e) => {
      if (e.target.files && e.target.files[0]) {
        handleFileSelect(e.target.files[0], fileChip, stateKey);
      }
    });

    removeBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      state[stateKey] = null;
      fileInput.value = '';
      fileChip.classList.add('hidden');
    });
  }

  function handleFileSelect(file, fileChip, stateKey) {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      alert('Please upload a PDF document (.pdf)');
      return;
    }
    state[stateKey] = file;
    const nameEl = fileChip.querySelector('.file-name');
    nameEl.textContent = `${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
    fileChip.classList.remove('hidden');
  }

  setupDropzone(policyDropzone, policyFileInput, policyFileChip, btnRemovePolicy, 'policyFile');
  setupDropzone(claimDropzone, claimFileInput, claimFileChip, btnRemoveClaim, 'claimFile');

  // ============================================================================
  // Form Submission & Agent Execution
  // ============================================================================
  uploadForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!state.policyFile && !state.claimFile) {
      alert('Please select at least one document (Policy or Claim PDF) to analyze.');
      return;
    }

    const formData = new FormData();
    if (state.policyFile) formData.append('policy_file', state.policyFile);
    if (state.claimFile) formData.append('claim_file', state.claimFile);
    formData.append('goal', inputGoal.value);
    if (inputSessionName.value) formData.append('session_name', inputSessionName.value);
    formData.append('offline_mode', toggleOffline.checked);
    formData.append('auto_run', true);

    await executeWorkflow('/api/claims/upload', formData, true);
  });

  // Quick Demo Buttons
  btnDemoHealth.addEventListener('click', async () => {
    await executeWorkflow('/api/claims/demo', JSON.stringify({
      demo_type: 'health',
      auto_run: true,
      offline_mode: toggleOffline.checked
    }), false);
  });

  btnDemoTravel.addEventListener('click', async () => {
    await executeWorkflow('/api/claims/demo', JSON.stringify({
      demo_type: 'travel',
      auto_run: true,
      offline_mode: toggleOffline.checked
    }), false);
  });

  async function executeWorkflow(endpoint, body, isFormData) {
    setLoadingState(true);
    resetStepper();
    executionCard.classList.remove('hidden');
    resultCard.classList.add('hidden');

    try {
      const headers = isFormData ? {} : { 'Content-Type': 'application/json' };
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: headers,
        body: body
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Workflow submission failed.');
      }

      const data = await res.json();
      const claim = data.claim;
      const runResults = data.run_results || data;

      state.activeClaimId = claim.claim_id;
      activeClaimIdEl.textContent = claim.claim_id;

      // Animate execution progress through intermediate observations
      await animateWorkflowSteps(runResults);

      // Render final results
      renderResults(runResults);
      await loadClaimsHistory();

    } catch (err) {
      console.error('Agent execution error:', err);
      alert(`Error: ${err.message}`);
      executionStatusPill.textContent = 'EXECUTION FAILED';
      executionStatusPill.style.background = 'rgba(244,63,94,0.2)';
      executionStatusPill.style.color = '#f43f5e';
    } finally {
      setLoadingState(false);
    }
  }

  function setLoadingState(isLoading) {
    state.isExecuting = isLoading;
    btnStartAgent.disabled = isLoading;
    btnDemoHealth.disabled = isLoading;
    btnDemoTravel.disabled = isLoading;
    if (isLoading) {
      btnStartAgent.querySelector('.btn-text').textContent = 'Agent Executing...';
    } else {
      btnStartAgent.querySelector('.btn-text').textContent = 'Launch InsureMate Agent';
    }
  }

  // ============================================================================
  // Stepper & Animation Simulation
  // ============================================================================
  const STEP_IDS = ['step-planning', 'step-extraction', 'step-validation', 'step-validity', 'step-missing', 'step-report'];
  const STATUS_IDS = ['status-planning', 'status-extraction', 'status-validation', 'status-validity', 'status-missing', 'status-report'];

  function resetStepper() {
    progressBar.style.width = '5%';
    STEP_IDS.forEach((id, idx) => {
      const step = document.getElementById(id);
      step.className = 'stepper-step';
      document.getElementById(STATUS_IDS[idx]).textContent = 'WAITING';
    });
    activeIterationEl.textContent = '1';
    bubbleText.textContent = 'Agent initialized. Starting goal decomposition...';
    executionStatusPill.textContent = 'AGENT EXECUTING';
    executionStatusPill.style.background = 'rgba(6,182,212,0.15)';
    executionStatusPill.style.color = '#06b6d4';
  }

  async function animateWorkflowSteps(fullHistory) {
    const sleep = ms => new Promise(r => setTimeout(r, ms));
    const history = fullHistory.tool_executions || [];
    const latestState = fullHistory.latest_state || {};
    const trace = latestState.execution_trace || [];

    // Step 1: Planning
    setStepState(0, 'active', 'RUNNING');
    progressBar.style.width = '18%';
    bubbleText.textContent = 'Planning: Analyzing claim goal, decomposing into vision extraction, validation, and missing evidence detection.';
    await sleep(400);
    setStepState(0, 'completed', 'DONE');

    // Step 2: Extraction
    setStepState(1, 'active', 'RUNNING');
    progressBar.style.width = '36%';
    bubbleText.textContent = 'Tool: Qwen-VL Vision Extractor invoked. Converting PDF pages in-memory and extracting document types and entities.';
    await sleep(400);
    setStepState(1, 'completed', 'DONE');

    // Step 3: Validation
    setStepState(2, 'active', 'RUNNING');
    progressBar.style.width = '54%';
    bubbleText.textContent = 'Tool: Document Validation Tool. Verifying required mandatory fields by classification (policy numbers, amounts, dates).';
    await sleep(350);
    setStepState(2, 'completed', 'DONE');

    // Step 4: Validity
    setStepState(3, 'active', 'RUNNING');
    progressBar.style.width = '72%';
    bubbleText.textContent = 'Tool: Validity Checker. Evaluating whether bill/treatment dates fall inside coverage period and verifying member identity.';
    await sleep(350);
    setStepState(3, 'completed', 'DONE');

    // Step 5: Missing Document Detection
    setStepState(4, 'active', 'RUNNING');
    progressBar.style.width = '90%';
    bubbleText.textContent = 'Tool: Missing Document Detector. Comparing extracted policy clauses against submitted claim documents with local LLM.';
    await sleep(350);
    setStepState(4, 'completed', 'DONE');

    // Step 6: Final Verdict Synthesis
    setStepState(5, 'active', 'RUNNING');
    progressBar.style.width = '100%';
    bubbleText.textContent = 'Verdict Synthesis: Consolidating tool observations into final Claim Readiness Package and persisting in Claim Memory database.';
    await sleep(300);
    setStepState(5, 'completed', 'DONE');

    executionStatusPill.textContent = 'COMPLETED';
    executionStatusPill.style.background = 'rgba(16,185,129,0.2)';
    executionStatusPill.style.color = '#10b981';
  }

  function setStepState(index, stepClass, statusText) {
    const step = document.getElementById(STEP_IDS[index]);
    step.className = `stepper-step ${stepClass}`;
    document.getElementById(STATUS_IDS[index]).textContent = statusText;
  }

  // ============================================================================
  // Rendering Results & Tables
  // ============================================================================
  function renderResults(data) {
    state.activeClaimData = data;
    resultCard.classList.remove('hidden');

    const report = data.final_report || {};
    const stateObj = data.latest_state || {};
    const verdict = data.verdict || report.status || stateObj.final_status || 'UNKNOWN';

    // 1. Verdict Banner Styling
    verdictTitle.textContent = verdict.replace(/_/g, ' ');
    verdictBanner.className = 'verdict-banner';

    if (verdict.includes('READY')) {
      verdictBanner.classList.add('verdict-ready');
      verdictIcon.textContent = '✓';
    } else if (verdict.includes('ACTION_REQUIRED') || verdict.includes('MISSING')) {
      verdictBanner.classList.add('verdict-action');
      verdictIcon.textContent = '⚠️';
    } else {
      verdictBanner.classList.add('verdict-rejected');
      verdictIcon.textContent = '✕';
    }

    // 2. Decision Summary
    decisionSummaryText.textContent = report.decision_summary || report.reasoning || stateObj.goal || 'No summary available.';

    // 3. Metric Counters
    const docs = stateObj.extracted_data || [];
    metricDocsCount.textContent = docs.length;

    const valResult = stateObj.validity_result || report.validity_check || {};
    const isPeriodValid = valResult.valid ?? true;
    metricValidityStatus.textContent = isPeriodValid ? 'PASS' : 'FAIL';
    metricValidityStatus.className = `metric-val ${isPeriodValid ? 'text-emerald' : 'text-rose'}`;

    let missingDocsList = [];
    if (stateObj.missing_documents && stateObj.missing_documents.missing_documents) {
      missingDocsList = stateObj.missing_documents.missing_documents;
    } else if (report.missing_documents) {
      missingDocsList = report.missing_documents;
    }
    const missingCount = missingDocsList.filter(d => d.missing).length;
    metricMissingCount.textContent = missingCount;

    const idMatch = valResult.identity_match?.matched ?? true;
    metricIdentityMatch.textContent = idMatch ? 'MATCHED' : 'UNMATCHED';
    metricIdentityMatch.className = `metric-val ${idMatch ? 'text-emerald' : 'text-amber'}`;

    // 4. Tab 1: Missing Documents Table
    renderMissingTable(missingDocsList);

    // 5. Tab 2: Validity & Date Analysis Table
    renderValidityTable(valResult, docs);

    // 6. Tab 3: Extracted Pages Cards
    renderExtractedCards(docs);

    // 7. Tab 4: Tool Audit History Table
    renderToolAuditTable(data.tool_executions || []);

    // 8. Tab 5: Raw JSON Code
    rawJsonCode.textContent = JSON.stringify(data, null, 2);

    // Smooth scroll to result
    resultCard.scrollIntoView({ behavior: 'smooth' });
  }

  function renderMissingTable(missingDocs) {
    missingTableBody.innerHTML = '';
    if (!missingDocs || missingDocs.length === 0) {
      missingTableBody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:var(--text-muted);">All required documents are present. None missing.</td></tr>`;
      return;
    }

    missingDocs.forEach((doc, idx) => {
      const isMissing = doc.missing;
      const row = document.createElement('tr');
      row.innerHTML = `
        <td>${doc.sr_no || (idx + 1)}</td>
        <td><strong>${doc.document_title || 'Required Item'}</strong></td>
        <td>
          <span class="status-badge ${isMissing ? 'badge-missing' : 'badge-present'}">
            ${isMissing ? 'MISSING' : 'PRESENT'}
          </span>
        </td>
        <td>${doc.page_no ? `<span class="page-chip">Page ${doc.page_no}</span>` : '<span style="color:var(--text-subtle);">-</span>'}</td>
        <td>${doc.reason || (isMissing ? 'Document absent from claim submission' : 'Document satisfied in file')}</td>
      `;
      missingTableBody.appendChild(row);
    });
  }

  function renderValidityTable(validity, extractedDocs) {
    validityTableBody.innerHTML = '';

    // Coverage window
    const period = validity.policy_period || {};
    policyStartDisplay.textContent = period.start_date || '12/03/2025';
    policyEndDisplay.textContent = period.end_date || '11/03/2028';

    const checks = validity.checks || [];
    if (checks.length === 0) {
      validityTableBody.innerHTML = `<tr><td colspan="6" style="text-align:center;color:var(--text-muted);">No date checks recorded.</td></tr>`;
      return;
    }

    checks.forEach(chk => {
      const row = document.createElement('tr');
      row.innerHTML = `
        <td><strong style="text-transform:capitalize;">${(chk.document_type || 'document').replace(/_/g, ' ')}</strong></td>
        <td><span class="page-chip">Page ${chk.page_number || 1}</span></td>
        <td>${chk.raw_date || '<span style="color:var(--text-subtle);">None</span>'}</td>
        <td>${chk.normalized_date || '-'}</td>
        <td>
          <span class="status-badge ${chk.valid ? 'badge-present' : 'badge-missing'}">
            ${chk.valid ? 'PASS' : 'FAIL'}
          </span>
        </td>
        <td>${chk.reason || (chk.valid ? 'Falls inside policy window' : 'Outside coverage window')}</td>
      `;
      validityTableBody.appendChild(row);
    });
  }

  function renderExtractedCards(docs) {
    extractedCardsGrid.innerHTML = '';
    if (!docs || docs.length === 0) {
      extractedCardsGrid.innerHTML = `<div style="color:var(--text-muted);">No documents extracted.</div>`;
      return;
    }

    docs.forEach(doc => {
      const card = document.createElement('div');
      card.className = 'doc-card';
      card.innerHTML = `
        <div class="doc-card-header">
          <span class="doc-page-badge">Page ${doc.page_number}</span>
          <span class="doc-type-tag">${(doc.document_type || 'unknown').replace(/_/g, ' ')}</span>
        </div>
        <div class="doc-title">${doc.document_title || 'Document Page'}</div>
        <div class="doc-entities-list">
          ${doc.policy_number ? `<div class="entity-row"><strong>Policy #:</strong> ${doc.policy_number}</div>` : ''}
          ${doc.policy_holder_name ? `<div class="entity-row"><strong>Policy Holder:</strong> ${doc.policy_holder_name}</div>` : ''}
          ${doc.patient_name ? `<div class="entity-row"><strong>Patient:</strong> ${doc.patient_name}</div>` : ''}
          ${doc.hospital_name ? `<div class="entity-row"><strong>Hospital:</strong> ${doc.hospital_name}</div>` : ''}
          ${doc.bill_number ? `<div class="entity-row"><strong>Bill #:</strong> ${doc.bill_number}</div>` : ''}
          ${doc.bill_amount ? `<div class="entity-row"><strong>Amount:</strong> Rs. ${doc.bill_amount}</div>` : ''}
          ${doc.document_date ? `<div class="entity-row"><strong>Doc Date:</strong> ${doc.document_date}</div>` : ''}
          ${doc.policy_start_date ? `<div class="entity-row"><strong>Coverage:</strong> ${doc.policy_start_date} to ${doc.policy_end_date}</div>` : ''}
        </div>
      `;
      extractedCardsGrid.appendChild(card);
    });
  }

  function renderToolAuditTable(executions) {
    toolHistoryTableBody.innerHTML = '';
    if (!executions || executions.length === 0) {
      toolHistoryTableBody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:var(--text-muted);">No tool executions recorded.</td></tr>`;
      return;
    }

    executions.forEach(exec => {
      const row = document.createElement('tr');
      row.innerHTML = `
        <td>${exec.step_index || 1}</td>
        <td><code style="color:var(--accent-cyan);">${exec.tool_name}</code></td>
        <td>
          <span class="status-badge ${exec.success ? 'badge-present' : 'badge-missing'}">
            ${exec.success ? 'PASS' : 'FAIL'}
          </span>
        </td>
        <td>${exec.output_data ? JSON.stringify(exec.output_data).slice(0, 90) + '...' : '-'}</td>
        <td style="font-size:0.75rem;color:var(--text-subtle);">${(exec.timestamp || '').replace('T', ' ').slice(0, 19)}</td>
      `;
      toolHistoryTableBody.appendChild(row);
    });
  }

  // ============================================================================
  // Tab Switcher
  // ============================================================================
  const tabButtons = document.querySelectorAll('.tab-btn');
  const tabPanes = document.querySelectorAll('.tab-pane');

  tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      tabButtons.forEach(b => b.classList.remove('active'));
      tabPanes.forEach(p => p.classList.remove('active'));

      btn.classList.add('active');
      const targetId = btn.getAttribute('data-tab');
      const targetPane = document.getElementById(targetId);
      if (targetPane) targetPane.classList.add('active');
    });
  });

  // ============================================================================
  // Claim Memory & Database Sidebar
  // ============================================================================
  btnToggleHistory.addEventListener('click', () => {
    historySidebar.classList.toggle('open');
  });

  btnCloseHistory.addEventListener('click', () => {
    historySidebar.classList.remove('open');
  });

  async function loadClaimsHistory() {
    try {
      const res = await fetch('/api/claims');
      if (!res.ok) return;
      const data = await res.json();
      state.historyList = data.claims || [];
      historyCountEl.textContent = state.historyList.length;

      renderHistoryList(state.historyList);
    } catch (e) {
      console.warn('Failed to load history:', e);
    }
  }

  function renderHistoryList(claims) {
    historyListEl.innerHTML = '';
    if (!claims || claims.length === 0) {
      historyListEl.innerHTML = `<div class="empty-history">No claim sessions stored in database.</div>`;
      return;
    }

    claims.forEach(c => {
      const item = document.createElement('div');
      item.className = 'history-item';
      const verdict = c.verdict || c.status || 'UNKNOWN';
      const isReady = verdict.includes('READY');

      item.innerHTML = `
        <div class="history-item-header">
          <span class="history-claim-id">${c.claim_id}</span>
          <span class="history-date">${(c.created_at || '').slice(0, 10)}</span>
        </div>
        <div class="history-session-name">${c.session_name || 'Claim Session'}</div>
        <span class="status-badge ${isReady ? 'badge-present' : 'badge-missing'}">
          ${verdict.replace(/_/g, ' ')}
        </span>
      `;

      item.addEventListener('click', async () => {
        try {
          const res = await fetch(`/api/claims/${c.claim_id}`);
          if (res.ok) {
            const fullClaim = await res.json();
            renderResults(fullClaim);
            historySidebar.classList.remove('open');
          }
        } catch (err) {
          alert('Failed to load claim: ' + err.message);
        }
      });

      historyListEl.appendChild(item);
    });
  }

  // Copy Summary & New Claim Actions
  btnCopySummary.addEventListener('click', () => {
    if (state.activeClaimData) {
      const text = JSON.stringify(state.activeClaimData.final_report || state.activeClaimData, null, 2);
      navigator.clipboard.writeText(text);
      btnCopySummary.textContent = 'Copied!';
      setTimeout(() => { btnCopySummary.textContent = 'Copy Report'; }, 2000);
    }
  });

  btnNewClaim.addEventListener('click', () => {
    resultCard.classList.add('hidden');
    executionCard.classList.add('hidden');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });

  // Initial load
  loadClaimsHistory();
});
