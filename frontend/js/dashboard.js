/**
 * frontend/js/dashboard.js
 * Operations Dashboard & Claims Archive Controller.
 * Computes real KPI metrics from backend claims records, handles 1-click demos,
 * provides live table search/filtering, and manages claim deletions via confirmation modal.
 */

const Dashboard = {
  pendingDeleteClaimId: null,
  pollTimer: null,

  async init() {
    this.bindEvents();
    await this.refresh();
  },

  bindEvents() {
    // 1-Click Demo Scenarios
    const btnDemoHealth = document.getElementById('btn-dash-demo-health');
    if (btnDemoHealth) {
      btnDemoHealth.addEventListener('click', () => this.launchDemo('health'));
    }

    const btnDemoTravel = document.getElementById('btn-dash-demo-travel');
    if (btnDemoTravel) {
      btnDemoTravel.addEventListener('click', () => this.launchDemo('travel'));
    }

    // Hero Quick Action Buttons
    const btnHeroNew = document.getElementById('btn-hero-new-claim');
    if (btnHeroNew) {
      btnHeroNew.addEventListener('click', () => window.App.navigateTo('new-claim'));
    }

    const btnHeroClaims = document.getElementById('btn-hero-view-claims');
    if (btnHeroClaims) {
      btnHeroClaims.addEventListener('click', () => window.App.navigateTo('claims'));
    }

    // Refresh Archive Button
    const btnRefreshClaims = document.getElementById('btn-refresh-claims');
    if (btnRefreshClaims) {
      btnRefreshClaims.addEventListener('click', async () => {
        Utils.showToast('Refreshing claims archive...', 'info', 1000);
        await this.refresh(true);
      });
    }

    // Dashboard Search & Filters
    const dashSearch = document.getElementById('dash-claims-search');
    if (dashSearch) {
      dashSearch.addEventListener('input', (e) => this.filterClaims(e.target.value, 'dash'));
    }

    const dashFilter = document.getElementById('dash-claims-filter');
    if (dashFilter) {
      dashFilter.addEventListener('change', () => this.filterClaims(null, 'dash'));
    }

    // Claims Archive Page Search & Filters
    const claimsSearch = document.getElementById('claims-page-search');
    if (claimsSearch) {
      claimsSearch.addEventListener('input', (e) => this.filterClaims(e.target.value, 'claims'));
    }

    const claimsFilter = document.getElementById('claims-page-filter');
    if (claimsFilter) {
      claimsFilter.addEventListener('change', () => this.filterClaims(null, 'claims'));
    }

    // Delete Confirmation Modal Events
    const btnCancelDelete = document.getElementById('btn-cancel-delete');
    if (btnCancelDelete) {
      btnCancelDelete.addEventListener('click', () => Utils.closeModal('delete-confirm-modal'));
    }

    const btnCloseDelete = document.getElementById('btn-close-delete-modal');
    if (btnCloseDelete) {
      btnCloseDelete.addEventListener('click', () => Utils.closeModal('delete-confirm-modal'));
    }

    const btnConfirmDelete = document.getElementById('btn-confirm-delete');
    if (btnConfirmDelete) {
      btnConfirmDelete.addEventListener('click', async () => {
        if (this.pendingDeleteClaimId) {
          await this.executeDelete(this.pendingDeleteClaimId);
        }
      });
    }

    // Subscribe to state claim list changes
    AppState.subscribe('claimsList', (list) => {
      this.renderKPIs(list);
      this.renderClaimsTable(list, 'dash-claims-tbody');
      this.renderClaimsTable(list, 'all-claims-tbody');
    });
  },

  startPolling() {
    if (this.pollTimer) return;
    this.pollTimer = setInterval(async () => {
      const claims = AppState.get().claimsList || [];
      const hasRunning = claims.some(c => c.is_running || String(c.status).toLowerCase().includes('progress') || String(c.status).toLowerCase().includes('running') || AppState.isClaimRunning(c.claim_id));
      if (hasRunning || AppState.runningClaimIds.size > 0) {
        await this.refresh(false);
      } else {
        this.stopPolling();
      }
    }, 2000);
  },

  stopPolling() {
    if (this.pollTimer) {
      clearInterval(this.pollTimer);
      this.pollTimer = null;
    }
  },

  async refresh(showError = false) {
    try {
      const res = await API.listClaims(100, 0);
      const claims = res.claims || [];

      // Check running status from backend
      claims.forEach(c => {
        const isRunning = c.is_running || String(c.status).toLowerCase() === 'in_progress' || String(c.status).toLowerCase() === 'running';
        if (isRunning) {
          AppState.runningClaimIds.add(c.claim_id);
          c.is_running = true;
          c.status = 'in_progress';
        } else if (c.verdict || c.final_report || c.status === 'completed' || c.status === 'failed') {
          AppState.runningClaimIds.delete(c.claim_id);
          c.is_running = false;
        } else if (AppState.isClaimRunning(c.claim_id)) {
          c.is_running = true;
          c.status = 'in_progress';
        }
      });

      AppState.set({ claimsList: claims });

      this.renderKPIs(claims);
      this.renderClaimsTable(claims, 'dash-claims-tbody');
      this.renderClaimsTable(claims, 'all-claims-tbody');

      if (AppState.runningClaimIds.size > 0) {
        this.startPolling();
      }
    } catch (err) {
      if (showError) {
        Utils.showToast(`Failed to load claims: ${err.message}`, 'error');
      }
      console.warn('Claims fetch failed:', err);
    }
  },

  renderKPIs(claims = []) {
    const totalClaims = claims.length;

    // Approximate total documents analyzed
    let totalDocs = 0;
    claims.forEach(c => {
      const cFiles = c.claim_filenames || [];
      totalDocs += (c.policy_filename ? 1 : 0) + (Array.isArray(cFiles) ? cFiles.length : (c.claim_filename ? 1 : 0));
    });

    // Count missing evidence findings
    const missingDocs = claims.filter(c => {
      const s = String(c.status || '').toLowerCase();
      return s.includes('missing') || s.includes('action_required');
    }).length;

    // Count ready for review
    const readyClaims = claims.filter(c => {
      const s = String(c.status || '').toLowerCase();
      return s.includes('ready');
    }).length;

    // Update DOM
    const kpiTotal = document.getElementById('kpi-total-claims');
    const kpiDocs = document.getElementById('kpi-total-docs');
    const kpiMissing = document.getElementById('kpi-missing-docs');
    const kpiReady = document.getElementById('kpi-ready-claims');
    const heroStatClaims = document.getElementById('hero-stat-claims');
    const heroStatTools = document.getElementById('hero-stat-tools');

    if (kpiTotal) kpiTotal.textContent = totalClaims;
    if (kpiDocs) kpiDocs.textContent = totalDocs;
    if (kpiMissing) kpiMissing.textContent = missingDocs;
    if (kpiReady) kpiReady.textContent = readyClaims;
    if (heroStatClaims) heroStatClaims.textContent = totalClaims;

    const availableTools = AppState.get().availableTools || [];
    if (heroStatTools) heroStatTools.textContent = availableTools.length > 0 ? String(availableTools.length).padStart(2, '0') : '06';
  },

  filterClaims(query = null, context = 'dash') {
    const list = AppState.get().claimsList || [];
    const searchId = context === 'dash' ? 'dash-claims-search' : 'claims-page-search';
    const filterId = context === 'dash' ? 'dash-claims-filter' : 'claims-page-filter';
    const tbodyId = context === 'dash' ? 'dash-claims-tbody' : 'all-claims-tbody';

    const searchVal = query !== null ? query.toLowerCase() : (document.getElementById(searchId)?.value.toLowerCase() || '');
    const filterVal = document.getElementById(filterId)?.value || 'ALL';

    const filtered = list.filter(c => {
      const matchSearch = !searchVal ||
        String(c.claim_id || '').toLowerCase().includes(searchVal) ||
        String(c.claim_type || '').toLowerCase().includes(searchVal) ||
        String(c.session_name || '').toLowerCase().includes(searchVal) ||
        String(c.policy_filename || '').toLowerCase().includes(searchVal);

      if (!matchSearch) return false;

      const s = String(c.status || '').toUpperCase();
      if (filterVal === 'ALL') return true;
      if (filterVal === 'RUNNING') return c.is_running || s.includes('PROGRESS') || s.includes('RUNNING') || AppState.isClaimRunning(c.claim_id);
      if (filterVal === 'READY') return s.includes('READY');
      if (filterVal === 'MISSING') return s.includes('MISSING') || s.includes('ACTION_REQUIRED');
      if (filterVal === 'PENDING') return s === 'PENDING';
      if (filterVal === 'FAILED') return s.includes('FAILED') || s.includes('INVALID');
      return true;
    });

    this.renderClaimsTable(filtered, tbodyId);
  },

  renderClaimsTable(claims = [], tbodyId) {
    const tbody = document.getElementById(tbodyId);
    if (!tbody) return;

    if (!claims || claims.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="7" class="empty-state">
            <div class="empty-state-icon">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="10"/><line x1="8" y1="12" x2="16" y2="12"/></svg>
            </div>
            <h4>No Claims Found</h4>
            <p>No insurance claims match your search filter.</p>
          </td>
        </tr>
      `;
      return;
    }

    const displayList = tbodyId === 'dash-claims-tbody' ? claims.slice(0, 8) : claims;

    tbody.innerHTML = displayList.map(claim => {
      const cid = claim.claim_id;
      const isRunning = claim.is_running || AppState.isClaimRunning(cid) || String(claim.status).toLowerCase() === 'in_progress';
      const statusText = isRunning ? 'IN PROGRESS' : (claim.status || 'PENDING');
      const badgeClass = isRunning ? 'badge-processing' : this.getStatusBadgeClass(statusText);
      const icon = isRunning ? '●' : this.getStatusIcon(statusText);

      const policyRef = claim.policy_filename || claim.session_name || '--';
      const claimType = claim.claim_type ? (claim.claim_type.charAt(0).toUpperCase() + claim.claim_type.slice(1)) : 'General';
      const dateStr = Utils.formatDate(claim.created_at);

      const cFiles = claim.claim_filenames || [];
      const docCount = (claim.policy_filename ? 1 : 0) + (Array.isArray(cFiles) ? cFiles.length : (claim.claim_filename ? 1 : 0));

      const runBtnHtml = isRunning ? `
        <button class="btn btn-secondary btn-sm" onclick="Dashboard.trackAgent('${cid}')" style="color: var(--accent); border-color: var(--accent);">
          <span class="spinner-sm" style="width: 10px; height: 10px; border: 1.5px solid var(--accent); border-top-color: transparent; border-radius: 50%; display: inline-block; animation: spin 1s linear infinite;"></span>
          <span>Tracking</span>
        </button>
      ` : `
        <button class="btn btn-secondary btn-sm" onclick="Dashboard.runClaim('${cid}', this)" title="Execute Agent Analysis">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
          <span>Run</span>
        </button>
      `;

      return `
        <tr>
          <td>
            <a href="#" class="claim-id-link" onclick="Dashboard.openClaim('${cid}'); return false;" title="Inspect Claim">
              ${Utils.escapeHtml(cid)}
            </a>
          </td>
          <td>
            <span style="font-weight: 500; color: #FFFFFF;" title="${Utils.escapeHtml(policyRef)}">
              ${Utils.escapeHtml(policyRef.length > 24 ? policyRef.substring(0, 24) + '...' : policyRef)}
            </span>
          </td>
          <td>
            <span class="badge badge-neutral" style="font-size: 0.7rem;">${Utils.escapeHtml(claimType)}</span>
          </td>
          <td style="font-size: 0.74rem; color: var(--text-muted); font-family: var(--font-mono);">
            ${Utils.escapeHtml(dateStr)}
          </td>
          <td>
            <span style="font-family: var(--font-mono); font-size: 0.76rem; color: var(--text-secondary);">
              ${docCount} file(s)
            </span>
          </td>
          <td>
            <span class="badge ${badgeClass}">
              <span style="font-size: 0.65rem;">${icon}</span>
              <span>${Utils.escapeHtml(statusText.replace(/_/g, ' '))}</span>
            </span>
          </td>
          <td>
            <div style="display: flex; align-items: center; gap: 6px;">
              <button class="btn btn-secondary btn-sm" onclick="Dashboard.openClaim('${cid}')" title="Open Claim Results & Details">
                Open
              </button>
              ${runBtnHtml}
              <button class="btn btn-icon btn-sm" onclick="Dashboard.promptDeleteClaim('${cid}')" title="Delete Claim Session" style="color: var(--rose);">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
              </button>
            </div>
          </td>
        </tr>
      `;
    }).join('');
  },

  getStatusBadgeClass(status) {
    const s = String(status).toUpperCase();
    if (s.includes('READY')) return 'badge-ready';
    if (s.includes('MISSING')) return 'badge-warning';
    if (s.includes('INVALID') || s.includes('FAILED')) return 'badge-error';
    if (s.includes('PROGRESS') || s.includes('RUNNING')) return 'badge-processing';
    return 'badge-pending';
  },

  getStatusIcon(status) {
    const s = String(status).toUpperCase();
    if (s.includes('READY')) return '✓';
    if (s.includes('MISSING')) return '⚠';
    if (s.includes('INVALID') || s.includes('FAILED')) return '✕';
    if (s.includes('PROGRESS') || s.includes('RUNNING')) return '●';
    return '○';
  },

  async openClaim(claimId) {
    try {
      Utils.showToast(`Loading claim ${claimId}...`, 'info', 1200);
      const bundle = await AppState.setActiveClaim(claimId);
      if (bundle && bundle.final_report) {
        window.App.navigateTo('results');
      } else {
        window.App.navigateTo('agent');
      }
    } catch {
      Utils.showToast(`Failed to open claim ${claimId}`, 'error');
    }
  },

  async trackAgent(claimId) {
    if (!claimId) return;
    try {
      await AppState.setActiveClaim(claimId);
      window.App.navigateTo('agent');
      if (window.AgentView && (AppState.isClaimRunning(claimId) || AppState.get().activeClaimBundle?.is_running)) {
        window.AgentView.startPolling(claimId);
      }
    } catch (err) {
      console.error('Failed to open Agent Activity:', err);
      window.App.navigateTo('agent');
    }
  },

  async runClaim(claimId, btnEl = null) {
    if (!claimId) return;

    if (AppState.isClaimRunning(claimId)) {
      Utils.showToast(`Agent is already running for claim ${claimId}`, 'info');
      await this.trackAgent(claimId);
      return;
    }

    AppState.setClaimRunning(claimId, true);
    this.startPolling();

    Utils.showToast(`Launching InsureMate Agent for ${claimId}...`, 'info');
    await this.trackAgent(claimId);

    if (window.AgentView) {
      window.AgentView.startExecution(claimId);
    } else {
      API.startAgent(claimId, { background: true }).catch(err => {
        console.error('Failed to start agent:', err);
        AppState.setClaimRunning(claimId, false);
      });
    }
  },

  promptDeleteClaim(claimId) {
    this.pendingDeleteClaimId = claimId;
    const label = document.getElementById('delete-claim-id-label');
    if (label) label.textContent = claimId;
    Utils.openModal('delete-confirm-modal');
  },

  async executeDelete(claimId) {
    try {
      Utils.closeModal('delete-confirm-modal');
      Utils.showToast(`Deleting claim ${claimId}...`, 'info');
      await API.deleteClaim(claimId);
      Utils.showToast(`Deleted claim ${claimId}`, 'success');
      AppState.setClaimRunning(claimId, false);
      if (AppState.get().activeClaimId === claimId) {
        AppState.setActiveClaim(null);
      }
      this.pendingDeleteClaimId = null;
      await this.refresh();
    } catch (err) {
      Utils.showToast(`Failed to delete claim: ${err.message}`, 'error');
    }
  },

  async launchDemo(preset) {
    try {
      Utils.showToast(`Creating ${preset} demo claim...`, 'info', 1800);
      const res = await API.createDemoClaim(preset, false, true);
      const claimId = res.claim_id;
      Utils.showToast(`Demo claim created: ${claimId}`, 'success');
      await this.refresh();
      await AppState.setActiveClaim(claimId);
      window.App.navigateTo('agent');
      if (window.AgentView) {
        window.AgentView.startExecution(claimId);
      }
    } catch (err) {
      Utils.showToast(`Demo creation failed: ${err.message}`, 'error');
    }
  }
};

window.Dashboard = Dashboard;
