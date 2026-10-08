/**
 * frontend/js/dashboard.js
 * Dashboard logic: KPI metrics calculations, recent claims list rendering,
 * search/filter controls, and demo quick launchers.
 */

const Dashboard = {
  async init() {
    this.bindEvents();
    await this.refresh();
  },

  bindEvents() {
    // Quick Demo Buttons
    const btnDemoHealth = document.getElementById('btn-dash-demo-health');
    if (btnDemoHealth) {
      btnDemoHealth.addEventListener('click', () => this.launchDemo('health'));
    }

    const btnDemoTravel = document.getElementById('btn-dash-demo-travel');
    if (btnDemoTravel) {
      btnDemoTravel.addEventListener('click', () => this.launchDemo('travel'));
    }

    // Dashboard Search Input
    const searchInput = document.getElementById('dash-claims-search');
    if (searchInput) {
      searchInput.addEventListener('input', (e) => this.filterClaims(e.target.value));
    }

    // Status Filter
    const filterSelect = document.getElementById('dash-claims-filter');
    if (filterSelect) {
      filterSelect.addEventListener('change', () => this.filterClaims());
    }

    // Subscribe to state claim list changes
    AppState.subscribe('claimsList', (list) => {
      this.renderKPIs(list);
      this.renderClaimsTable(list);
    });
  },

  async refresh() {
    try {
      const res = await API.listClaims(100, 0);
      const claims = res.claims || [];
      AppState.set({ claimsList: claims });
    } catch (err) {
      console.error('Failed to load dashboard claims:', err);
      Utils.showToast('Could not fetch claims history', 'error');
    }
  },

  renderKPIs(claims = []) {
    const totalClaimsEl = document.getElementById('kpi-total-claims');
    const totalDocsEl = document.getElementById('kpi-total-docs');
    const missingDocsEl = document.getElementById('kpi-missing-docs');
    const readyClaimsEl = document.getElementById('kpi-ready-claims');

    let totalDocsCount = 0;
    let missingDocsCount = 0;
    let readyClaimsCount = 0;

    claims.forEach(c => {
      // Approximate document count from filenames
      const cFiles = c.claim_filenames || [];
      const hasPolicy = !!c.policy_filename;
      totalDocsCount += (hasPolicy ? 1 : 0) + (Array.isArray(cFiles) ? cFiles.length : (cFiles ? 1 : 0));

      if (c.missing_count) {
        missingDocsCount += Number(c.missing_count);
      }

      const st = String(c.verdict || c.status || '').toUpperCase();
      if (st.includes('READY') || st.includes('CLAIM_READY')) {
        readyClaimsCount += 1;
      }
    });

    if (totalClaimsEl) totalClaimsEl.textContent = claims.length;
    if (totalDocsEl) totalDocsEl.textContent = totalDocsCount;
    if (missingDocsEl) missingDocsEl.textContent = missingDocsCount;
    if (readyClaimsEl) readyClaimsEl.textContent = readyClaimsCount;
  },

  filterClaims() {
    const searchVal = (document.getElementById('dash-claims-search')?.value || '').toLowerCase().trim();
    const filterVal = (document.getElementById('dash-claims-filter')?.value || 'ALL').toUpperCase();
    const allClaims = AppState.get().claimsList || [];

    const filtered = allClaims.filter(c => {
      const matchSearch = !searchVal || 
        c.claim_id.toLowerCase().includes(searchVal) ||
        (c.session_name && c.session_name.toLowerCase().includes(searchVal)) ||
        (c.claim_type && c.claim_type.toLowerCase().includes(searchVal));

      let matchFilter = true;
      if (filterVal !== 'ALL') {
        const st = String(c.verdict || c.status || '').toUpperCase();
        if (filterVal === 'READY') matchFilter = st.includes('READY');
        else if (filterVal === 'MISSING') matchFilter = st.includes('MISSING');
        else if (filterVal === 'PENDING') matchFilter = st.includes('PENDING');
        else if (filterVal === 'FAILED') matchFilter = st.includes('FAILED');
      }

      return matchSearch && matchFilter;
    });

    this.renderClaimsTable(filtered);
  },

  renderClaimsTable(claims = []) {
    const tbody = document.getElementById('dash-claims-tbody');
    if (!tbody) return;

    if (!claims || claims.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="6" class="empty-state" style="padding: 40px;">
            <div class="empty-state-icon">📋</div>
            <h4>No Claims Found</h4>
            <p>Create a new claim session or run a quick demo.</p>
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = claims.map(c => {
      const verdict = c.verdict || c.status || 'pending';
      const badgeClass = this.getStatusBadgeClass(verdict);
      const docsCount = (c.policy_filename ? 1 : 0) + (Array.isArray(c.claim_filenames) ? c.claim_filenames.length : (c.claim_filename ? 1 : 0));

      return `
        <tr>
          <td>
            <a href="#" class="text-mono" style="font-weight: 600; color: var(--cyan-primary);" onclick="Dashboard.openClaim('${Utils.escapeHtml(c.claim_id)}'); return false;">
              ${Utils.escapeHtml(c.claim_id)}
            </a>
            <div style="font-size: 0.76rem; color: var(--text-muted);">${Utils.escapeHtml(c.session_name || 'General Claim')}</div>
          </td>
          <td style="font-size: 0.82rem;">${Utils.formatDate(c.created_at)}</td>
          <td>
            <span style="font-size: 0.82rem; text-transform: capitalize; color: var(--text-secondary);">
              ${Utils.escapeHtml(c.claim_type || 'General')}
            </span>
          </td>
          <td>
            <span class="badge" style="background: var(--bg-elevated); color: var(--text-secondary);">
              📄 ${docsCount} doc(s)
            </span>
          </td>
          <td>
            <span class="badge ${badgeClass}">
              ${this.getStatusIcon(verdict)} ${Utils.escapeHtml(verdict.replace(/_/g, ' '))}
            </span>
          </td>
          <td>
            <div style="display: flex; gap: 6px;">
              <button class="btn btn-secondary btn-sm" onclick="Dashboard.openClaim('${Utils.escapeHtml(c.claim_id)}')">
                Open
              </button>
              ${String(c.status).toLowerCase() === 'pending' ? `
                <button class="btn btn-primary btn-sm" onclick="Dashboard.runClaim('${Utils.escapeHtml(c.claim_id)}')">
                  Run Agent
                </button>
              ` : ''}
              <button class="btn btn-icon btn-sm" title="Delete Claim" onclick="Dashboard.deleteClaim('${Utils.escapeHtml(c.claim_id)}')">
                🗑️
              </button>
            </div>
          </td>
        </tr>
      `;
    }).join('');
  },

  getStatusBadgeClass(status) {
    const s = String(status).toUpperCase();
    if (s.includes('READY') || s.includes('CLAIM_READY')) return 'badge-ready';
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
      Utils.showToast(`Loading claim ${claimId}...`, 'info', 1500);
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

  async runClaim(claimId) {
    try {
      Utils.showToast(`Launching InsureMate Agent for ${claimId}...`, 'info');
      await AppState.setActiveClaim(claimId);
      window.App.navigateTo('agent');
      window.AgentView.startExecution(claimId);
    } catch (err) {
      Utils.showToast(`Error running agent: ${err.message}`, 'error');
    }
  },

  async deleteClaim(claimId) {
    if (!confirm(`Are you sure you want to delete claim session ${claimId}?`)) return;
    try {
      await API.deleteClaim(claimId);
      Utils.showToast(`Deleted claim ${claimId}`, 'success');
      if (AppState.get().activeClaimId === claimId) {
        AppState.setActiveClaim(null);
      }
      await this.refresh();
    } catch (err) {
      Utils.showToast(`Failed to delete claim: ${err.message}`, 'error');
    }
  },

  async launchDemo(preset) {
    try {
      Utils.showToast(`Creating ${preset} demo claim...`, 'info', 2000);
      const res = await API.createDemoClaim(preset, false, true);
      const claimId = res.claim_id;
      Utils.showToast(`Demo created: ${claimId}`, 'success');
      await this.refresh();
      await AppState.setActiveClaim(claimId);
      window.App.navigateTo('agent');
      // Automatically prompt or start agent
      window.AgentView.startExecution(claimId);
    } catch (err) {
      Utils.showToast(`Demo failed: ${err.message}`, 'error');
    }
  }
};

window.Dashboard = Dashboard;
