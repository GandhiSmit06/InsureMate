/**
 * frontend/js/agent.js
 * Dynamic Agentic AI Operations Console for InsureMate.
 * Demonstrates autonomous LLM-driven tool selection, dynamic capability discovery,
 * Antigravity-style tool action & summary traces, live streaming, and observable decision rationale.
 */

const AgentView = {
  isPolling: false,
  pollInterval: null,
  activeStream: null,
  liveRunningTool: null,
  liveTimerInterval: null,
  availableTools: [],
  toolSchemas: {},

  async init() {
    this.bindEvents();
    await this.fetchAndRenderToolRegistry();

    // Subscribe to active claim updates
    AppState.subscribe('activeClaimBundle', (bundle) => {
      this.renderBundle(bundle);
    });
  },

  bindEvents() {
    // Run / Re-run agent button
    const btnStart = document.getElementById('btn-agent-start-run');
    if (btnStart) {
      btnStart.addEventListener('click', () => {
        const claimId = AppState.get().activeClaimId;
        if (claimId) {
          if (AppState.isClaimRunning(claimId)) {
            Utils.showToast(`Agent is already executing for claim ${claimId}`, 'info');
            return;
          }
          this.startExecution(claimId);
        } else {
          Utils.showToast('No active claim selected. Create or select a claim first.', 'warning');
        }
      });
    }

    // Refresh agent activity button
    const btnRefresh = document.getElementById('btn-agent-refresh');
    if (btnRefresh) {
      btnRefresh.addEventListener('click', async () => {
        const claimId = AppState.get().activeClaimId;
        if (claimId) {
          Utils.showToast(`Refreshing agent activity for ${claimId}...`, 'info', 1000);
          await AppState.refreshActiveClaim();
          await this.fetchAndRenderToolRegistry();
        } else {
          Utils.showToast('No active claim selected.', 'warning');
        }
      });
    }

    // View results button
    const btnViewResults = document.getElementById('btn-agent-view-results');
    if (btnViewResults) {
      btnViewResults.addEventListener('click', () => {
        window.App.navigateTo('results');
      });
    }

    // Close schema modal
    const btnCloseSchema = document.getElementById('btn-close-schema-modal');
    if (btnCloseSchema) {
      btnCloseSchema.addEventListener('click', () => {
        Utils.closeModal('tool-schema-modal');
      });
    }
  },

  /**
   * Antigravity Action & Summary mapping for tools
   */
  getAntigravityMetadata(toolName) {
    const raw = String(toolName || '').toLowerCase().replace(/_tool$/, '');
    const metaMap = {
      'document_extraction': {
        toolAction: 'Extracting document entities',
        toolSummary: 'Multimodal vision extraction',
        friendlyName: 'Qwen-VL Vision Extractor'
      },
      'qwen_vl_extraction': {
        toolAction: 'Extracting document entities',
        toolSummary: 'Multimodal vision extraction',
        friendlyName: 'Qwen-VL Vision Extractor'
      },
      'document_validation': {
        toolAction: 'Validating field completeness',
        toolSummary: 'Document validation & integrity audit',
        friendlyName: 'Document Validation Engine'
      },
      'validity_checker': {
        toolAction: 'Auditing policy coverage window',
        toolSummary: 'Coverage period & date check',
        friendlyName: 'Coverage Validity Checker'
      },
      'missing_document': {
        toolAction: 'Auditing evidence requirements',
        toolSummary: 'Missing document detection',
        friendlyName: 'Missing Evidence Detector'
      },
      'missing_document_detector': {
        toolAction: 'Auditing evidence requirements',
        toolSummary: 'Missing document detection',
        friendlyName: 'Missing Evidence Detector'
      },
      'policy_clause_search': {
        toolAction: 'Searching policy clauses & limits',
        toolSummary: 'Policy clause search',
        friendlyName: 'Policy Clause Search'
      },
      'clause_search': {
        toolAction: 'Searching policy clauses & limits',
        toolSummary: 'Policy clause search',
        friendlyName: 'Policy Clause Search'
      },
      'cross_document_consistency': {
        toolAction: 'Auditing cross-document consistency',
        toolSummary: 'Discrepancy & contradiction check',
        friendlyName: 'Cross-Document Consistency Auditor'
      },
      'cross_document_consistency_check': {
        toolAction: 'Auditing cross-document consistency',
        toolSummary: 'Discrepancy & contradiction check',
        friendlyName: 'Cross-Document Consistency Auditor'
      },
      'claim_preparation': {
        toolAction: 'Synthesizing claim readiness package',
        toolSummary: 'Readiness verdict & checklist synthesis',
        friendlyName: 'Claim Synthesis Engine'
      }
    };

    return metaMap[raw] || {
      toolAction: `Executing ${raw.replace(/_/g, ' ')}`,
      toolSummary: 'Agent capability execution',
      friendlyName: raw.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
    };
  },

  formatDuration(durationMs) {
    if (!durationMs && durationMs !== 0) return null;
    if (durationMs < 1000) {
      return `${Math.round(durationMs)}ms`;
    }
    return `${(durationMs / 1000).toFixed(2)}s`;
  },

  /**
   * Dynamically fetch tool catalog and schemas from /api/tools
   */
  async fetchAndRenderToolRegistry() {
    try {
      const data = await API.listTools();
      this.availableTools = data.tools || [];
      this.toolSchemas = data.schemas || {};

      AppState.set({ availableTools: this.availableTools });

      // Update badge
      const badge = document.getElementById('agent-tools-count-badge');
      if (badge) {
        badge.textContent = `${this.availableTools.length} Online`;
        badge.className = 'badge badge-ready';
      }

      const sidebarToolsCount = document.getElementById('sidebar-tools-count');
      if (sidebarToolsCount) {
        sidebarToolsCount.textContent = `${this.availableTools.length} tools available`;
      }

      this.renderToolRegistryCards();
    } catch (err) {
      console.warn('Failed to load dynamic tools catalog:', err);
      const badge = document.getElementById('agent-tools-count-badge');
      if (badge) {
        badge.textContent = 'Tools catalog unavailable';
        badge.className = 'badge badge-error';
      }
    }
  },

  /**
   * Render capability cards for each registered tool
   */
  renderToolRegistryCards() {
    const grid = document.getElementById('agent-tools-grid');
    if (!grid) return;

    if (!this.availableTools || this.availableTools.length === 0) {
      grid.innerHTML = `
        <div style="grid-column: 1 / -1; color: var(--text-muted); font-size: 0.8rem; padding: 12px;">
          No agent tools discovered from registry.
        </div>
      `;
      return;
    }

    const bundle = AppState.get().activeClaimBundle;
    const toolsExecuted = (bundle && bundle.tool_executions) || [];
    const executedMap = {};
    toolsExecuted.forEach(t => {
      executedMap[t.tool_name] = (executedMap[t.tool_name] || 0) + 1;
    });

    const isRunning = bundle && (bundle.is_running || AppState.isClaimRunning(bundle.claim?.claim_id));
    const currentStep = bundle?.latest_state?.current_step || this.liveRunningTool?.tool_name;

    grid.innerHTML = this.availableTools.map(tool => {
      const name = tool.name;
      const count = executedMap[name] || 0;
      const isToolRunning = isRunning && currentStep && currentStep.includes(name.replace('_tool', ''));

      let statusBadge = `<span class="tool-status-badge available">Standby</span>`;
      if (isToolRunning) {
        statusBadge = `<span class="tool-status-badge running"><span class="agent-pulse-dot" style="width:6px; height:6px;"></span> Running</span>`;
      } else if (count > 0) {
        statusBadge = `<span class="tool-status-badge completed">✓ Executed (${count}x)</span>`;
      }

      const meta = this.getAntigravityMetadata(name);
      const friendlyName = meta.friendlyName;
      const desc = tool.description || 'Callable tool capability.';

      return `
        <div class="tool-card" onclick="AgentView.openToolSchema('${Utils.escapeHtml(name)}')">
          <div>
            <div class="tool-card-top">
              <div>
                <div class="tool-card-name">${Utils.escapeHtml(friendlyName)}</div>
                <div class="tool-card-system-name">${Utils.escapeHtml(name)}</div>
              </div>
              ${statusBadge}
            </div>
            <div class="tool-card-desc">${Utils.escapeHtml(desc)}</div>
          </div>
          <div class="tool-card-bottom">
            <span>Click to inspect parameters</span>
            <span class="tool-inspect-hint">View Schema ↗</span>
          </div>
        </div>
      `;
    }).join('');
  },

  /**
   * Display tool schema modal with parameter breakdown
   */
  openToolSchema(toolName) {
    const schema = this.toolSchemas[toolName];
    const tool = this.availableTools.find(t => t.name === toolName);

    const titleEl = document.getElementById('tool-schema-modal-title');
    const bodyEl = document.getElementById('tool-schema-modal-body');

    if (titleEl) {
      titleEl.textContent = `${this.formatFriendlyToolName(toolName)} — Parameter Schema`;
    }

    if (bodyEl) {
      if (!schema && !tool) {
        bodyEl.innerHTML = `<p style="color: var(--text-muted);">No schema definition available for this tool.</p>`;
      } else {
        const props = (schema && schema.parameters && schema.parameters.properties) || {};
        const required = (schema && schema.parameters && schema.parameters.required) || [];

        const propRows = Object.keys(props).map(pKey => {
          const p = props[pKey];
          const isReq = required.includes(pKey);
          return `
            <div class="schema-prop-row">
              <div class="schema-prop-header">
                <span class="schema-prop-name">${Utils.escapeHtml(pKey)}</span>
                <span class="schema-prop-type">${Utils.escapeHtml(p.type || 'any')}</span>
                ${isReq ? '<span class="badge badge-warning" style="font-size:0.6rem; padding:1px 5px;">Required</span>' : ''}
              </div>
              <div class="schema-prop-desc">${Utils.escapeHtml(p.description || 'Parameter for tool invocation.')}</div>
            </div>
          `;
        }).join('') || '<div style="color:var(--text-muted); font-size:0.8rem; padding:8px 0;">No input parameters required.</div>';

        bodyEl.innerHTML = `
          <div style="margin-bottom: 14px;">
            <div style="font-size: 0.72rem; text-transform: uppercase; color: var(--text-muted); font-weight: 700; margin-bottom: 4px;">Description</div>
            <div style="font-size: 0.84rem; color: var(--text-secondary); line-height: 1.5;">${Utils.escapeHtml(tool?.description || (schema && schema.description) || 'Autonomous agent capability tool.')}</div>
          </div>
          <div>
            <div style="font-size: 0.72rem; text-transform: uppercase; color: var(--text-muted); font-weight: 700; margin-bottom: 8px;">Parameters</div>
            <div style="background: var(--bg-elevated); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); padding: 8px 14px;">
              ${propRows}
            </div>
          </div>
        `;
      }
      Utils.openModal('tool-schema-modal');
    }
  },

  /**
   * Render bundle details to Agent Activity view
   */
  renderBundle(bundle) {
    if (!bundle) {
      this.resetAgentView();
      return;
    }

    const claim = bundle.claim || {};
    const tools = bundle.tool_executions || [];
    const report = bundle.final_report;
    const latestState = bundle.latest_state || {};
    const verdict = bundle.verdict || claim.status || 'PENDING';
    const isRunning = bundle.is_running || String(claim.status).toLowerCase().includes('in_progress') || AppState.isClaimRunning(claim.claim_id);

    // 1. Header Meta
    const claimIdEl = document.getElementById('agent-claim-id-display');
    const goalEl = document.getElementById('agent-goal-display');
    const iterEl = document.getElementById('agent-iteration-count');
    const statusPill = document.getElementById('agent-status-pill');

    if (claimIdEl) claimIdEl.textContent = claim.claim_id || '--';
    if (goalEl) goalEl.textContent = claim.goal || 'Determine claim readiness and missing evidence.';
    if (iterEl) iterEl.textContent = latestState.iteration_count || tools.length || 0;

    if (statusPill) {
      if (isRunning) {
        statusPill.textContent = 'EXECUTING TOOLS';
        statusPill.className = 'badge badge-processing';
      } else {
        statusPill.textContent = verdict.replace(/_/g, ' ');
        statusPill.className = `badge ${this.getStatusBadgeClass(verdict)}`;
      }
    }

    // 2. Dynamic Observed Execution Sequence (#stepper-track)
    this.renderDynamicExecutionSequence(tools, latestState, isRunning);

    // 3. Dynamic Tool Registry Cards status refresh
    this.renderToolRegistryCards();

    // 4. Decision & Reasoning Workspace
    this.renderDecisionWorkspace(bundle);

    // 5. Chronological Antigravity Tool Activity Timeline
    this.renderTimeline(tools, latestState.execution_trace || []);

    // 6. View Results button visibility
    const btnResults = document.getElementById('btn-agent-view-results');
    if (btnResults) {
      btnResults.style.display = report ? 'inline-flex' : 'none';
    }

    // 7. Start / Run Agent button state
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

        if (!this.isPolling && claim.claim_id) {
          this.startPolling(claim.claim_id);
        }
      } else {
        btnStart.disabled = false;
        btnStart.style.cursor = 'pointer';
        btnStart.style.opacity = '1';
        btnStart.innerHTML = report ? `
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="1 4 1 10 7 10"/><polyline points="23 20 23 14 17 14"/><path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 0 1 3.51 15"/></svg>
          Re-run Agent
        ` : `
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
          Run Agent
        `;
      }
    }
  },

  /**
   * Renders the dynamic sequence of tools actually selected and invoked by the LLM agent.
   */
  renderDynamicExecutionSequence(tools = [], latestState = {}, isRunning = false) {
    const track = document.getElementById('stepper-track');
    if (!track) return;

    if (tools.length === 0) {
      if (isRunning) {
        track.innerHTML = `
          <div class="dynamic-step-card running">
            <div class="step-card-top">
              <span class="step-card-num">ITERATION 01</span>
              <span class="tool-status-badge running"><span class="agent-pulse-dot" style="width:6px; height:6px;"></span> Initializing</span>
            </div>
            <div class="step-card-name">Autonomous Strategic Planning</div>
            <div class="step-card-summary">Formulating tool selection based on document inputs...</div>
            <div class="step-card-footer">
              <span>Goal Decomposing</span>
              <span>Running</span>
            </div>
          </div>
        `;
      } else {
        track.innerHTML = `
          <div class="stepper-empty-state">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
            <span>Awaiting execution trigger. The agent will dynamically select and invoke tools based on observations.</span>
          </div>
        `;
      }
      return;
    }

    const cardsHtml = [];
    tools.forEach((tool, idx) => {
      const stepNum = `STEP 0${idx + 1}`;
      const meta = this.getAntigravityMetadata(tool.tool_name);
      const isFailed = tool.status === 'failed' || Boolean(tool.error);
      const statusClass = isFailed ? 'failed' : 'completed';
      const statusText = isFailed ? 'Failed' : 'Completed ✓';

      cardsHtml.push(`
        <div class="dynamic-step-card ${statusClass}">
          <div class="step-card-top">
            <span class="step-card-num">${stepNum}</span>
            <span class="tool-status-badge ${statusClass}">${statusText}</span>
          </div>
          <div class="step-card-name">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
            <span>${Utils.escapeHtml(meta.friendlyName)}</span>
          </div>
          <div class="step-card-summary">${Utils.escapeHtml(tool.summary || meta.toolSummary)}</div>
          <div class="step-card-footer">
            <span>${Utils.escapeHtml(tool.tool_name)}</span>
            <span>Observed</span>
          </div>
        </div>
      `);

      if (idx < tools.length - 1 || isRunning) {
        cardsHtml.push(`
          <div class="step-arrow-connector">⟶</div>
        `);
      }
    });

    if (isRunning) {
      const runningToolName = this.liveRunningTool?.tool_name || latestState.current_step || 'Autonomous Planning';
      const runningMeta = this.getAntigravityMetadata(runningToolName);

      cardsHtml.push(`
        <div class="dynamic-step-card running">
          <div class="step-card-top">
            <span class="step-card-num">STEP 0${tools.length + 1}</span>
            <span class="tool-status-badge running"><span class="agent-pulse-dot" style="width:6px; height:6px;"></span> Active</span>
          </div>
          <div class="step-card-name">
            <span>${Utils.escapeHtml(runningMeta.friendlyName)}</span>
          </div>
          <div class="step-card-summary">${Utils.escapeHtml(runningMeta.toolAction)}...</div>
          <div class="step-card-footer">
            <span>Autonomous Engine</span>
            <span>Running</span>
          </div>
        </div>
      `);
    }

    track.innerHTML = cardsHtml.join('');
  },

  /**
   * Dynamic Decision & Reasoning Workspace
   */
  renderDecisionWorkspace(bundle) {
    const claim = bundle.claim || {};
    const report = bundle.final_report;
    const latestState = bundle.latest_state || {};
    const trace = latestState.execution_trace || [];
    const tools = bundle.tool_executions || [];
    const isCompleted = report !== null && report !== undefined;
    const isRunning = bundle.is_running || String(claim.status).toLowerCase().includes('in_progress');

    // 1. Current Objective
    const objEl = document.getElementById('agent-current-objective');
    if (objEl) {
      if (this.liveRunningTool) {
        objEl.textContent = `Active Operation: ${this.liveRunningTool.toolAction || this.liveRunningTool.tool_name}`;
      } else {
        objEl.textContent = claim.goal || 'Determine claim readiness, validate medical bills, and detect any missing evidence.';
      }
    }

    // 2. Latest Observed Result
    const obsEl = document.getElementById('agent-latest-observation');
    if (obsEl) {
      if (tools.length > 0) {
        const lastTool = tools[tools.length - 1];
        const lastMeta = this.getAntigravityMetadata(lastTool.tool_name);
        obsEl.textContent = `${lastMeta.friendlyName}: ${lastTool.summary || 'Observation logged.'}`;
      } else if (isRunning) {
        obsEl.textContent = 'Agent formulating initial tool request...';
      } else {
        obsEl.textContent = 'Waiting for initial tool observation.';
      }
    }

    // 3. Next Selected Action
    const nextActionEl = document.getElementById('agent-next-action');
    if (nextActionEl) {
      if (isCompleted) {
        nextActionEl.textContent = 'Execution Complete — Final Readiness Package Synthesized';
        nextActionEl.style.color = 'var(--emerald)';
      } else if (isRunning) {
        const currentStep = this.liveRunningTool?.tool_name || latestState.current_step;
        if (currentStep) {
          const stepMeta = this.getAntigravityMetadata(currentStep);
          nextActionEl.textContent = `${stepMeta.toolAction} (${stepMeta.friendlyName})`;
        } else {
          nextActionEl.textContent = 'Evaluating Intermediate Observations';
        }
        nextActionEl.style.color = 'var(--accent)';
      } else {
        nextActionEl.textContent = 'Autonomous Planning (Ready on trigger)';
        nextActionEl.style.color = 'var(--text-muted)';
      }
    }

    // 4. Operational Reasoning / Decision
    const reasonEl = document.getElementById('agent-decision-reason');
    if (reasonEl) {
      if (trace.length > 0) {
        const lastTrace = trace[trace.length - 1];
        reasonEl.textContent = lastTrace.decision || report?.decision_summary || 'Agent evaluated observations and transitioned to subsequent verification stage.';
      } else if (report && report.decision_summary) {
        reasonEl.textContent = report.decision_summary;
      } else if (isRunning) {
        reasonEl.textContent = 'Analyzing intermediate observations to formulate next strategic tool invocation.';
      } else {
        reasonEl.textContent = 'Awaiting execution trigger to begin autonomous multi-step execution.';
      }
    }

    // 5. Completed Actions Checklist (#agent-completed-actions)
    const checklistEl = document.getElementById('agent-completed-actions');
    if (checklistEl) {
      const completedSteps = latestState.completed_steps || [];
      const distinctToolNames = Array.from(new Set(tools.map(t => t.tool_name)));

      const actionItems = [];
      if (tools.length > 0) {
        distinctToolNames.forEach(tName => {
          const meta = this.getAntigravityMetadata(tName);
          actionItems.push(`Completed: <strong>${meta.toolAction}</strong> <span style="color:var(--text-muted);">(${meta.toolSummary})</span>`);
        });
      }

      if (completedSteps.length > 0) {
        completedSteps.forEach(s => {
          actionItems.push(`Lifecycle check: <strong>${s.replace(/_/g, ' ')}</strong>`);
        });
      }

      if (isCompleted) {
        actionItems.push('Synthesized readiness verdict and structured assessment report');
      }

      if (actionItems.length === 0) {
        checklistEl.innerHTML = `<li style="color: var(--text-muted);">No actions completed yet. Trigger agent to begin.</li>`;
      } else {
        checklistEl.innerHTML = actionItems.map(item => `
          <li>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
            <span>${item}</span>
          </li>
        `).join('');
      }
    }
  },

  /**
   * Chronological Antigravity Tool Activity Timeline
   */
  renderTimeline(tools = [], trace = []) {
    const container = document.getElementById('agent-timeline-container');
    if (!container) return;

    if (tools.length === 0 && !this.liveRunningTool) {
      container.innerHTML = `
        <div class="empty-state" style="padding: 24px 0;">
          <div class="empty-state-icon">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
          </div>
          <h4>No Tool Executions Recorded</h4>
          <p>When the agent runs, every tool invocation, action, duration, and output observation will be displayed here live.</p>
        </div>
      `;
      return;
    }

    const cardsHtml = tools.map((tool, idx) => {
      const isFailed = tool.status === 'failed' || Boolean(tool.error);
      const statusClass = isFailed ? 'failed' : 'completed';
      const statusBadge = isFailed ? '<span class="badge badge-error">Failed</span>' : '<span class="badge badge-ready">Completed ✓</span>';
      const meta = this.getAntigravityMetadata(tool.tool_name);
      const timeStr = tool.timestamp ? Utils.formatDate(tool.timestamp) : `Step ${idx + 1}`;
      const drawerId = `timeline-drawer-${idx}`;
      const durationBadge = tool.duration_ms !== undefined && tool.duration_ms !== null
        ? `<span class="ag-duration-badge" title="Execution Duration">⏱ ${this.formatDuration(tool.duration_ms)}</span>`
        : '';

      // Check if trace has thought for this tool
      const relatedTrace = trace.find(t => t.action === tool.tool_name || (t.tool && t.tool.includes(tool.tool_name)));
      const thoughtHtml = relatedTrace && relatedTrace.decision ? `
        <div class="ag-thought-box">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a7 7 0 0 0-7 7c0 2.38 1.19 4.47 3 5.74V17a2 2 0 0 0 2 2h4a2 2 0 0 0 2-2v-2.26c1.81-1.27 3-3.36 3-5.74a7 7 0 0 0-7-7z"/><line x1="9" y1="21" x2="15" y2="21"/></svg>
          <div><strong>Agent Reasoning:</strong> ${Utils.escapeHtml(relatedTrace.decision)}</div>
        </div>
      ` : '';

      return `
        <div class="timeline-item ${statusClass}">
          <div class="timeline-marker"></div>
          
          <div class="ag-tool-header">
            <div class="ag-tool-identity">
              <div class="ag-tool-action-line">
                <span class="ag-step-tag">#0${idx + 1}</span>
                <span class="ag-tool-action">${Utils.escapeHtml(meta.toolAction)}</span>
              </div>
              <div class="ag-tool-meta-line">
                <span class="ag-tool-summary-pill">${Utils.escapeHtml(meta.toolSummary)}</span>
                <span class="ag-system-tool-tag">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="7" width="20" height="14" rx="2" ry="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></svg>
                  ${Utils.escapeHtml(tool.tool_name)}
                </span>
                <span style="font-size:0.68rem; color:var(--text-subtle);">${Utils.escapeHtml(timeStr)}</span>
              </div>
            </div>

            <div class="ag-tool-status-group">
              ${durationBadge}
              ${statusBadge}
            </div>
          </div>

          ${thoughtHtml}

          <div class="timeline-summary" style="margin: 6px 0 10px;">${Utils.escapeHtml(tool.summary || 'Tool execution completed.')}</div>
          
          <button type="button" class="ag-drawer-toggle" onclick="AgentView.toggleDrawer('${drawerId}', this)">
            <span>Inspect Arguments & Observation</span>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
          </button>

          <div class="timeline-details-drawer" id="${drawerId}">
            <div class="timeline-drawer-grid">
              <div class="timeline-detail-col">
                <div class="timeline-detail-title">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
                  Parameters Passed
                </div>
                <pre>${Utils.escapeHtml(tool.inputs_summary || 'Standard parameters passed from agent state.')}</pre>
              </div>
              <div class="timeline-detail-col">
                <div class="timeline-detail-title">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
                  Observation Output
                </div>
                <pre>${Utils.escapeHtml(tool.summary || 'Completed successfully.')}</pre>
              </div>
            </div>
          </div>
        </div>
      `;
    });

    // If there is currently a tool running via SSE
    if (this.liveRunningTool) {
      const liveMeta = this.getAntigravityMetadata(this.liveRunningTool.tool_name);
      cardsHtml.push(`
        <div class="timeline-item running" id="ag-live-tool-card">
          <div class="timeline-marker"></div>
          
          <div class="ag-tool-header">
            <div class="ag-tool-identity">
              <div class="ag-tool-action-line">
                <span class="ag-step-tag">#0${tools.length + 1}</span>
                <span class="ag-tool-action">${Utils.escapeHtml(liveMeta.toolAction)}</span>
              </div>
              <div class="ag-tool-meta-line">
                <span class="ag-tool-summary-pill">${Utils.escapeHtml(liveMeta.toolSummary)}</span>
                <span class="ag-system-tool-tag">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="7" width="20" height="14" rx="2" ry="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></svg>
                  ${Utils.escapeHtml(this.liveRunningTool.tool_name)}
                </span>
              </div>
            </div>

            <div class="ag-tool-status-group">
              <span class="ag-duration-badge">
                <span class="ag-timer-live" id="ag-live-stopwatch">0.0s</span>
              </span>
              <span class="badge badge-processing">
                <span class="pulse-dot-running"></span>
                RUNNING
              </span>
            </div>
          </div>

          <div class="timeline-summary" style="margin: 6px 0 4px; color: var(--accent);">
            Executing autonomous capability in real-time...
          </div>
        </div>
      `);
    }

    container.innerHTML = cardsHtml.join('');
  },

  toggleDrawer(drawerId, btn) {
    const drawer = document.getElementById(drawerId);
    if (!drawer) return;
    const isOpen = drawer.classList.contains('open');
    if (isOpen) {
      drawer.classList.remove('open');
      btn.classList.remove('open');
      btn.innerHTML = `<span>Inspect Arguments & Observation</span> <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>`;
    } else {
      drawer.classList.add('open');
      btn.classList.add('open');
      btn.innerHTML = `<span>Hide Arguments & Observation</span> <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>`;
    }
  },

  /**
   * Start autonomous agent execution with SSE stream and polling fallback
   */
  async startExecution(claimId) {
    if (!claimId) return;

    try {
      Utils.showToast(`Launching InsureMate Agent for claim ${claimId}...`, 'info');
      AppState.setClaimRunning(claimId, true);

      // Trigger backend agent execution
      await API.startAgent(claimId, { background: true, offlineMode: true });

      // Connect SSE stream for instant real-time Antigravity events
      this.connectEventStream(claimId);

      // Start background polling as resilient sync
      this.startPolling(claimId);
    } catch (err) {
      console.error('Agent execution failed:', err);
      AppState.setClaimRunning(claimId, false);
      Utils.showToast(`Failed to start agent: ${err.message}`, 'error');
    }
  },

  /**
   * Connect to server-sent events stream (/api/claims/{id}/agent/stream)
   */
  connectEventStream(claimId) {
    if (this.activeStream) {
      try { this.activeStream.close(); } catch (_) {}
      this.activeStream = null;
    }

    this.activeStream = API.streamAgent(
      claimId,
      (data) => this.handleAgentEvent(claimId, data),
      (err) => {
        // SSE disconnected or closed - polling will continue smoothly
        if (this.activeStream) {
          try { this.activeStream.close(); } catch (_) {}
          this.activeStream = null;
        }
      }
    );
  },

  /**
   * Handle real-time agent lifecycle and tool events
   */
  handleAgentEvent(claimId, eventData) {
    if (!eventData || !eventData.event) return;

    const eventType = eventData.event;
    console.log(`[Agent Event: ${eventType}]`, eventData);

    if (eventType === 'tool_start') {
      const meta = this.getAntigravityMetadata(eventData.tool_name);
      this.liveRunningTool = {
        tool_name: eventData.tool_name,
        toolAction: eventData.toolAction || meta.toolAction,
        toolSummary: eventData.toolSummary || meta.toolSummary,
        startTime: Date.now()
      };

      // Start live stopwatch interval
      if (this.liveTimerInterval) clearInterval(this.liveTimerInterval);
      this.liveTimerInterval = setInterval(() => {
        const timerEl = document.getElementById('ag-live-stopwatch');
        if (timerEl && this.liveRunningTool) {
          const elapsedSec = ((Date.now() - this.liveRunningTool.startTime) / 1000).toFixed(1);
          timerEl.textContent = `${elapsedSec}s`;
        }
      }, 100);

      // Update current objective & next action
      const objEl = document.getElementById('agent-current-objective');
      if (objEl) objEl.textContent = `Invoking tool: ${meta.toolAction}`;

      const nextActionEl = document.getElementById('agent-next-action');
      if (nextActionEl) {
        nextActionEl.textContent = `${meta.toolAction} (${meta.friendlyName})`;
        nextActionEl.style.color = 'var(--accent)';
      }

      // Re-render bundle with live running card
      const bundle = AppState.get().activeClaimBundle;
      if (bundle) this.renderBundle(bundle);

    } else if (eventType === 'tool_finish') {
      // Clear live stopwatch
      if (this.liveTimerInterval) {
        clearInterval(this.liveTimerInterval);
        this.liveTimerInterval = null;
      }
      this.liveRunningTool = null;

      // Immediately refresh active claim bundle to fetch latest DB tool records
      AppState.refreshActiveClaim();

    } else if (eventType === 'decision') {
      const reasonEl = document.getElementById('agent-decision-reason');
      if (reasonEl && eventData.reason) {
        reasonEl.textContent = eventData.reason;
      }
      const nextActionEl = document.getElementById('agent-next-action');
      if (nextActionEl && eventData.next_action) {
        const meta = this.getAntigravityMetadata(eventData.next_action);
        nextActionEl.textContent = `${meta.toolAction} (${meta.friendlyName})`;
      }

    } else if (eventType === 'complete') {
      this.stopExecution(claimId);
      AppState.refreshActiveClaim();
      Utils.showToast(`Agent analysis completed for claim ${claimId}`, 'success');
    }
  },

  /**
   * Polling engine for live agent status and activity
   */
  startPolling(claimId) {
    if (this.isPolling) return;
    this.isPolling = true;

    if (this.pollInterval) clearInterval(this.pollInterval);

    this.pollInterval = setInterval(async () => {
      try {
        const statusData = await API.getAgentStatus(claimId);
        const isRunning = statusData.is_running || String(statusData.status).toLowerCase() === 'in_progress';

        // Check if server reported a live running tool
        if (statusData.live_running_tool && !this.liveRunningTool) {
          const live = statusData.live_running_tool;
          const meta = this.getAntigravityMetadata(live.tool_name);
          this.liveRunningTool = {
            tool_name: live.tool_name,
            toolAction: live.toolAction || meta.toolAction,
            toolSummary: live.toolSummary || meta.toolSummary,
            startTime: live.start_time ? new Date(live.start_time).getTime() : Date.now()
          };
        } else if (!statusData.live_running_tool && this.liveRunningTool && !this.activeStream) {
          this.liveRunningTool = null;
        }

        if (!isRunning || statusData.has_result) {
          this.stopExecution(claimId);
          await AppState.setActiveClaim(claimId);
          Utils.showToast(`Agent completed analysis for claim ${claimId}`, 'success');
          return;
        }

        // Live refresh activity and state while running
        await AppState.refreshActiveClaim();
      } catch (err) {
        console.warn('Agent status polling error:', err);
      }
    }, 1200);
  },

  stopPolling() {
    if (this.pollInterval) {
      clearInterval(this.pollInterval);
      this.pollInterval = null;
    }
    this.isPolling = false;
  },

  stopExecution(claimId) {
    this.stopPolling();
    if (this.activeStream) {
      try { this.activeStream.close(); } catch (_) {}
      this.activeStream = null;
    }
    if (this.liveTimerInterval) {
      clearInterval(this.liveTimerInterval);
      this.liveTimerInterval = null;
    }
    this.liveRunningTool = null;
    AppState.setClaimRunning(claimId, false);
  },

  resetAgentView() {
    this.stopExecution();
    const track = document.getElementById('stepper-track');
    if (track) {
      track.innerHTML = `
        <div class="stepper-empty-state">
          <span>Select an active claim session to inspect agent decisions and execution trace.</span>
        </div>
      `;
    }
    const timeline = document.getElementById('agent-timeline-container');
    if (timeline) {
      timeline.innerHTML = `<div class="empty-state"><p>No active claim selected.</p></div>`;
    }
  },

  formatFriendlyToolName(toolName) {
    return this.getAntigravityMetadata(toolName).friendlyName;
  },

  getStatusBadgeClass(status) {
    const s = String(status).toUpperCase();
    if (s.includes('READY')) return 'badge-ready';
    if (s.includes('MISSING')) return 'badge-warning';
    if (s.includes('INVALID') || s.includes('FAILED')) return 'badge-error';
    if (s.includes('PROGRESS') || s.includes('RUNNING')) return 'badge-processing';
    return 'badge-pending';
  }
};

window.AgentView = AgentView;
