/**
 * frontend/js/agent.js
 * Agent Execution Screen — Demonstrates the Autonomous Agentic AI Track.
 * Renders 8-node visual workflow stepper, Agent Decision Panel (Objective, Completed Actions,
 * Next Action, Reasoning), and Real-Time Tool Execution Timeline.
 */

const AgentView = {
  isPolling: false,
  pollInterval: null,

  // Stepper definition mapping backend steps/tools to visual nodes
  STEPS: [
    { id: 'claim_received', name: 'Claim Received', desc: 'Initialize session & docs' },
    { id: 'policy_analysis', name: 'Policy Analysis', desc: 'Inspect policy clauses' },
    { id: 'document_extraction', name: 'Vision Extraction', desc: 'Qwen-VL page parsing' },
    { id: 'document_validation', name: 'Document Validation', desc: 'Completeness check' },
    { id: 'validity_checker', name: 'Coverage Validity', desc: 'Policy period match' },
    { id: 'missing_document_detector', name: 'Missing Evidence', desc: 'Dynamic clause audit' },
    { id: 'agent_decision', name: 'Decision Engine', desc: 'Evaluate synthesis' },
    { id: 'claim_readiness', name: 'Claim Readiness', desc: 'Final verdict package' }
  ],

  init() {
    this.renderStepper();
    this.bindEvents();

    // Subscribe to active claim updates
    AppState.subscribe('activeClaimBundle', (bundle) => {
      this.renderBundle(bundle);
    });
  },

  bindEvents() {
    const btnStart = document.getElementById('btn-agent-start-run');
    if (btnStart) {
      btnStart.addEventListener('click', () => {
        const claimId = AppState.get().activeClaimId;
        if (claimId) {
          this.startExecution(claimId);
        } else {
          Utils.showToast('No active claim selected.', 'warning');
        }
      });
    }

    const btnViewResults = document.getElementById('btn-agent-view-results');
    if (btnViewResults) {
      btnViewResults.addEventListener('click', () => {
        window.App.navigateTo('results');
      });
    }
  },

  renderStepper() {
    const track = document.getElementById('stepper-track');
    if (!track) return;

    track.innerHTML = this.STEPS.map((step, idx) => `
      <div class="step-node" id="step-node-${step.id}">
        <div class="step-circle" id="step-circle-${step.id}">${idx + 1}</div>
        <div class="step-label">${Utils.escapeHtml(step.name)}</div>
        <div class="step-subtext">${Utils.escapeHtml(step.desc)}</div>
      </div>
    `).join('');
  },

  renderBundle(bundle) {
    if (!bundle) {
      this.resetStepper();
      this.resetDecisionPanel();
      this.resetTimeline();
      return;
    }

    const claim = bundle.claim || {};
    const tools = bundle.tool_executions || [];
    const report = bundle.final_report;
    const latestState = bundle.latest_state || {};
    const verdict = bundle.verdict || claim.status || 'PENDING';

    // Update Header Meta
    const claimIdEl = document.getElementById('agent-claim-id-display');
    const goalEl = document.getElementById('agent-goal-display');
    const iterEl = document.getElementById('agent-iteration-count');
    const statusPill = document.getElementById('agent-status-pill');

    if (claimIdEl) claimIdEl.textContent = claim.claim_id || '--';
    if (goalEl) goalEl.textContent = claim.goal || 'Determine claim readiness and missing evidence.';
    if (iterEl) iterEl.textContent = latestState.iteration_count || tools.length || 0;

    if (statusPill) {
      statusPill.textContent = verdict.replace(/_/g, ' ');
      statusPill.className = `badge ${Dashboard.getStatusBadgeClass(verdict)}`;
    }

    // Update Stepper Nodes according to completed steps & tools executed
    this.updateStepperFromState(bundle);

    // Update Orchestrated Tools Panel
    this.updateToolsPanel(tools);

    // Update Decision Panel
    this.renderDecisionPanel(bundle);

    // Update Tool Activity Timeline
    this.renderTimeline(tools, latestState.execution_trace || []);

    // Toggle Results Button if report exists
    const btnResults = document.getElementById('btn-agent-view-results');
    if (btnResults) {
      btnResults.style.display = report ? 'inline-flex' : 'none';
    }

    // Update Start / Run Agent button state
    const isRunning = bundle.is_running || String(claim.status).toLowerCase().includes('in_progress');
    const btnStart = document.getElementById('btn-agent-start-run');
    if (btnStart) {
      if (isRunning) {
        btnStart.disabled = true;
        btnStart.style.cursor = 'not-allowed';
        btnStart.style.opacity = '0.75';
        btnStart.innerHTML = `
          <span class="spinner-sm" style="width: 14px; height: 14px; border: 2px solid #fff; border-top-color: transparent; border-radius: 50%; display: inline-block; animation: spin 1s linear infinite;"></span>
          Agent Running…
        `;
      } else {
        btnStart.disabled = false;
        btnStart.style.cursor = 'pointer';
        btnStart.style.opacity = '1';
        btnStart.innerHTML = report ? `
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="1 4 1 10 7 10"/><polyline points="23 20 23 14 17 14"/><path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 0 1 3.51 15"/></svg>
          Re-run Agent
        ` : `
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
          Start InsureMate Agent
        `;
      }
    }
  },

  updateToolsPanel(tools = []) {
    const executedTools = new Set(tools.map(t => t.tool_name));
    
    const updateCard = (cardId, isExecuted) => {
      const card = document.getElementById(cardId);
      if (!card) return;
      const badge = card.querySelector('.badge');
      if (badge) {
        if (isExecuted) {
          badge.className = 'badge badge-success';
          badge.textContent = 'Executed ✓';
        } else {
          badge.className = 'badge badge-ready';
          badge.textContent = 'Online';
        }
      }
    };

    updateCard('tool-card-extraction', executedTools.has('document_extraction_tool'));
    updateCard('tool-card-validation', executedTools.has('document_validation_tool'));
    updateCard('tool-card-validity', executedTools.has('validity_checker_tool'));
    updateCard('tool-card-missing', executedTools.has('missing_document_tool'));
  },

  updateStepperFromState(bundle) {
    const tools = bundle.tool_executions || [];
    const latestState = bundle.latest_state || {};
    const completedSteps = latestState.completed_steps || [];
    const isCompleted = bundle.final_report !== null && bundle.final_report !== undefined;
    const isRunning = String(bundle.claim?.status).toLowerCase().includes('in_progress');

    const executedTools = new Set(tools.map(t => t.tool_name));

    this.STEPS.forEach((step, idx) => {
      const nodeEl = document.getElementById(`step-node-${step.id}`);
      const circleEl = document.getElementById(`step-circle-${step.id}`);
      if (!nodeEl || !circleEl) return;

      nodeEl.className = 'step-node';
      circleEl.innerHTML = String(idx + 1);

      if (step.id === 'claim_received') {
        nodeEl.classList.add('completed');
        circleEl.innerHTML = '✓';
      } else if (step.id === 'policy_analysis') {
        if (executedTools.has('document_extraction_tool') || completedSteps.includes('document_extraction') || isCompleted) {
          nodeEl.classList.add('completed');
          circleEl.innerHTML = '✓';
        } else if (isRunning) {
          nodeEl.classList.add('running');
        }
      } else if (step.id === 'document_extraction') {
        if (completedSteps.includes('document_extraction') || isCompleted || executedTools.has('document_extraction_tool')) {
          nodeEl.classList.add('completed');
          circleEl.innerHTML = '✓';
        } else if (isRunning && !completedSteps.includes('document_extraction')) {
          nodeEl.classList.add('running');
        }
      } else if (step.id === 'document_validation') {
        if (completedSteps.includes('document_validation') || isCompleted || executedTools.has('document_validation_tool')) {
          nodeEl.classList.add('completed');
          circleEl.innerHTML = '✓';
        }
      } else if (step.id === 'validity_checker') {
        if (completedSteps.includes('validity_checker') || isCompleted || executedTools.has('validity_checker_tool')) {
          nodeEl.classList.add('completed');
          circleEl.innerHTML = '✓';
        }
      } else if (step.id === 'missing_document_detector') {
        if (completedSteps.includes('missing_document_detector') || isCompleted || executedTools.has('missing_document_tool')) {
          nodeEl.classList.add('completed');
          circleEl.innerHTML = '✓';
        }
      } else if (step.id === 'agent_decision') {
        if (isCompleted || completedSteps.includes('claim_preparation')) {
          nodeEl.classList.add('completed');
          circleEl.innerHTML = '✓';
        }
      } else if (step.id === 'claim_readiness') {
        if (isCompleted) {
          nodeEl.classList.add('completed');
          circleEl.innerHTML = '✓';
        }
      }
    });
  },

  renderDecisionPanel(bundle) {
    const claim = bundle.claim || {};
    const report = bundle.final_report;
    const latestState = bundle.latest_state || {};
    const trace = latestState.execution_trace || [];
    const tools = bundle.tool_executions || [];

    const objEl = document.getElementById('agent-current-objective');
    const actionsListEl = document.getElementById('agent-completed-actions');
    const nextActionEl = document.getElementById('agent-next-action');
    const reasonEl = document.getElementById('agent-decision-reason');

    if (objEl) {
      objEl.textContent = claim.goal || 'Determine whether the claim contains sufficient valid evidence.';
    }

    // Build completed actions list
    if (actionsListEl) {
      const completedItems = [];
      if (tools.some(t => t.tool_name.includes('extraction'))) completedItems.push('Extracted policy & incident documents via Qwen-VL');
      if (tools.some(t => t.tool_name.includes('validation'))) completedItems.push('Validated field completeness across submitted documents');
      if (tools.some(t => t.tool_name.includes('validity'))) completedItems.push('Audited document dates against active policy period');
      if (tools.some(t => t.tool_name.includes('missing'))) completedItems.push('Checked dynamic required evidence from policy clauses');
      if (report) completedItems.push('Synthesized autonomous final claim readiness assessment');

      if (completedItems.length === 0) {
        actionsListEl.innerHTML = '<li style="color: var(--text-muted);">No actions completed yet.</li>';
      } else {
        actionsListEl.innerHTML = completedItems.map(item => `
          <li>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
            <span>${Utils.escapeHtml(item)}</span>
          </li>
        `).join('');
      }
    }

    // Next action & Reasoning
    if (nextActionEl) {
      if (report) {
        nextActionEl.textContent = 'None — Workflow Complete';
      } else if (latestState.current_step) {
        nextActionEl.textContent = latestState.current_step.replace(/_/g, ' ');
      } else {
        nextActionEl.textContent = 'Autonomous Planning & Evaluation';
      }
    }

    if (reasonEl) {
      if (report && report.decision_summary) {
        reasonEl.textContent = report.decision_summary;
      } else if (trace.length > 0) {
        const lastTrace = trace[trace.length - 1];
        reasonEl.textContent = lastTrace.decision || 'Processing intermediate evidence.';
      } else {
        reasonEl.textContent = 'Agent initialized. Ready to execute multi-step planning and tool invocation.';
      }
    }
  },

  renderTimeline(tools = [], trace = []) {
    const container = document.getElementById('agent-timeline-container');
    if (!container) return;

    if (tools.length === 0 && trace.length === 0) {
      container.innerHTML = `
        <div class="empty-state" style="padding: 30px;">
          <div class="empty-state-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
          </div>
          <h4>No Agent Activity Recorded</h4>
          <p>Click "Start InsureMate Agent" to begin autonomous execution.</p>
        </div>
      `;
      return;
    }

    container.innerHTML = tools.map((tool, idx) => {
      const success = tool.success;
      const statusBadge = success
        ? '<span class="badge badge-success">✓ Success</span>'
        : '<span class="badge badge-error">✕ Failed</span>';

      return `
        <div class="timeline-item">
          <div class="timeline-marker" style="background-color: ${success ? 'var(--emerald)' : 'var(--rose)'};"></div>
          <div class="timeline-header">
            <div class="timeline-tool">
              <span>Step ${tool.step_index || idx + 1}:</span>
              <strong style="color: var(--navy);">${Utils.escapeHtml(tool.tool_name.replace(/_/g, ' '))}</strong>
              ${statusBadge}
            </div>
            <div class="timeline-time">${Utils.formatDate(tool.timestamp)}</div>
          </div>
          <div class="timeline-body">
            <p>${Utils.escapeHtml(tool.output_data?.summary || tool.output_data?.decision_summary || (typeof tool.output_data === 'string' ? tool.output_data : 'Executed successfully.'))}</p>
            ${tool.error_data ? `<p style="color: var(--rose); margin-top: 4px;"><strong>Error:</strong> ${Utils.escapeHtml(JSON.stringify(tool.error_data))}</p>` : ''}
          </div>
          <div class="timeline-tag">${Utils.escapeHtml(tool.tool_name)}</div>
        </div>
      `;
    }).join('');
  },

  resetStepper() {
    this.STEPS.forEach((step, idx) => {
      const nodeEl = document.getElementById(`step-node-${step.id}`);
      const circleEl = document.getElementById(`step-circle-${step.id}`);
      if (nodeEl && circleEl) {
        nodeEl.className = 'step-node';
        circleEl.innerHTML = String(idx + 1);
      }
    });
  },

  resetDecisionPanel() {
    const objEl = document.getElementById('agent-current-objective');
    const actionsListEl = document.getElementById('agent-completed-actions');
    const nextActionEl = document.getElementById('agent-next-action');
    const reasonEl = document.getElementById('agent-decision-reason');

    if (objEl) objEl.textContent = '--';
    if (actionsListEl) actionsListEl.innerHTML = '<li>--</li>';
    if (nextActionEl) nextActionEl.textContent = '--';
    if (reasonEl) reasonEl.textContent = '--';
  },

  resetTimeline() {
    const container = document.getElementById('agent-timeline-container');
    if (container) container.innerHTML = '';
  },

  /**
   * Start Autonomous Agent execution and poll status until complete.
   */
  async startExecution(claimId) {
    if (!claimId) return;

    const btnStart = document.getElementById('btn-agent-start-run');
    if (btnStart) {
      btnStart.disabled = true;
      btnStart.style.cursor = 'not-allowed';
      btnStart.style.opacity = '0.75';
      btnStart.innerHTML = `
        <span class="spinner-sm" style="width: 14px; height: 14px; border: 2px solid #fff; border-top-color: transparent; border-radius: 50%; display: inline-block; animation: spin 1s linear infinite;"></span>
        Agent Running…
      `;
    }

    // Set first steps as running immediately
    const firstNode = document.getElementById('step-node-document_extraction');
    if (firstNode) firstNode.classList.add('running');

    Utils.showToast(`InsureMate Agent started for claim ${claimId}`, 'info');

    try {
      // Execute Agent call
      const runData = await API.startAgent(claimId, { background: false });

      // Refresh claim state
      const bundle = await AppState.setActiveClaim(claimId);
      Utils.showToast(`Agent completed claim assessment!`, 'success');

      // Refresh dashboard list
      Dashboard.refresh();

      // Show View Results button
      const btnResults = document.getElementById('btn-agent-view-results');
      if (btnResults) btnResults.style.display = 'inline-flex';

    } catch (err) {
      console.error('Agent execution failed:', err);
      Utils.showToast(`Agent execution error: ${err.message}`, 'error');
      // Still refresh bundle to show partial state or failure
      await AppState.setActiveClaim(claimId).catch(() => {});
    } finally {
      if (btnStart) {
        btnStart.disabled = false;
        btnStart.innerHTML = `
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
          Re-run Agent
        `;
      }
    }
  }
};

window.AgentView = AgentView;
