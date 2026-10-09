/**
 * frontend/js/dashboard.js
 * Dashboard logic: KPI metrics calculations, claims table rendering,
 * search/filter controls, and demo launchers.
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

    // Hero Section Buttons
    const btnHeroNew = document.getElementById('btn-hero-new-claim');
    if (btnHeroNew) {
      btnHeroNew.addEventListener('click', () => window.App.navigateTo('new-claim'));
    }

    const btnHeroClaims = document.getElementById('btn-hero-view-claims');
    if (btnHeroClaims) {
      btnHeroClaims.addEventListener('click', () => window.App.navigateTo('claims'));
    }

    // Dashboard Search & Filter
    const searchInput = document.getElementById('dash-claims-search');
    if (searchInput) {
      searchInput.addEventListener('input', (e) => this.filterClaims(e.target.value, 'dash'));
    }

    const filterSelect = document.getElementById('dash-claims-filter');
    if (filterSelect) {
      filterSelect.addEventListener('change', () => this.filterClaims(null, 'dash'));
    }

    // Claims Page Search & Filter
    const claimsSearchInput = document.getElementById('claims-page-search');
    if (claimsSearchInput) {
      claimsSearchInput.addEventListener('input', (e) => this.filterClaims(e.target.value, 'claims'));
    }

    const claimsFilterSelect = document.getElementById('claims-page-filter');
    if (claimsFilterSelect) {
      claimsFilterSelect.addEventListener('change', () => this.filterClaims(null, 'claims'));
    }

    // Subscribe to state claim list changes
    AppState.subscribe('claimsList', (list) => {
      this.renderKPIs(list);
      this.renderClaimsTable(list, 'dash-claims-tbody');
      this.renderClaimsTable(list, 'all-claims-tbody');
    });
  },

  async refresh() {
    try {
      const res = await API.listClaims(100, 0);
      const claims = res.claims || [];
      AppState.set({ claimsList: claims });
    } catch (err) {
      console.error('Failed to load claims history:', err);
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

    const heroClaimsEl = document.getElementById('hero-stat-claims');
    if (heroClaimsEl) heroClaimsEl.textContent = String(claims.length).padStart(2, '0');
  },

  filterClaims(queryVal, source = 'dash') {
    const searchId = source === 'dash' ? 'dash-claims-search' : 'claims-page-search';
    const filterId = source === 'dash' ? 'dash-claims-filter' : 'claims-page-filter';
    const tbodyId = source === 'dash' ? 'dash-claims-tbody' : 'all-claims-tbody';

    const searchVal = (queryVal !== null && queryVal !== undefined ? queryVal : document.getElementById(searchId)?.value || '').toLowerCase().trim();
    const filterVal = (document.getElementById(filterId)?.value || 'ALL').toUpperCase();
    const allClaims = AppState.get().claimsList || [];

    const filtered = allClaims.filter(c => {
      const matchSearch = !searchVal || 
        c.claim_id.toLowerCase().includes(searchVal) ||
        (c.session_name && c.session_name.toLowerCase().includes(searchVal)) ||
        (c.claim_type && c.claim_type.toLowerCase().includes(searchVal)) ||
        (c.policy_filename && c.policy_filename.toLowerCase().includes(searchVal));

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

    this.renderClaimsTable(filtered, tbodyId);
  },

  renderClaimsTable(claims = [], tbodyId = 'dash-claims-tbody') {
    const tbody = document.getElementById(tbodyId);
    if (!tbody) return;

    if (!claims || claims.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="7" class="empty-state" style="padding: 32px 16px;">
            <div class="empty-state-icon">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
            </div>
            <h4>No Claims Found</h4>
            <p>No insurance claim records match your current criteria.</p>
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = claims.map(c => {
      const verdict = c.verdict || c.status || 'pending';
      const badgeClass = this.getStatusBadgeClass(verdict);
      const docsCount = (c.policy_filename ? 1 : 0) + (Array.isArray(c.claim_filenames) ? c.claim_filenames.length : (c.claim_filename ? 1 : 0));
      const policyDisplay = c.policy_filename ? c.policy_filename.replace(/\.pdf$/i, '') : 'POL-AUTO';

      return `
        <tr>
          <td>
            <a href="#" class="text-mono" style="font-weight: 600; color: var(--primary);" onclick="Dashboard.openClaim('${Utils.escapeHtml(c.claim_id)}'); return false;">
              ${Utils.escapeHtml(c.claim_id)}
            </a>
            <div style="font-size: 0.74rem; color: var(--text-muted);">${Utils.escapeHtml(c.session_name || 'General Claim')}</div>
          </td>
          <td style="font-size: 0.82rem; font-family: var(--font-mono); color: var(--text-secondary);">
            ${Utils.escapeHtml(policyDisplay)}
          </td>
          <td>
            <span style="font-size: 0.82rem; text-transform: capitalize; color: var(--text-secondary); font-weight: 500;">
              ${Utils.escapeHtml(c.claim_type || 'General')}
            </span>
          </td>
          <td style="font-size: 0.82rem;">${Utils.formatDate(c.created_at)}</td>
          <td>
            <span class="badge" style="background: var(--bg-elevated); color: var(--text-secondary); font-weight: 500;">
              ${docsCount} doc(s)
            </span>
          </td>
          <td>
            <span class="badge ${badgeClass}">
              ${this.getStatusIcon(verdict)} ${Utils.escapeHtml(verdict.replace(/_/g, ' '))}
            </span>
          </td>
          <td>
            <div style="display: flex; gap: 6px; align-items: center;">
              <button class="btn btn-secondary btn-sm" onclick="Dashboard.openClaim('${Utils.escapeHtml(c.claim_id)}')">
                View
              </button>
              ${(c.is_running || String(c.status).toLowerCase() === 'in_progress') ? `
                <button class="btn btn-secondary btn-sm" disabled style="opacity: 0.75; cursor: not-allowed; display: inline-flex; align-items: center; gap: 6px;">
                  <span class="spinner-sm" style="width: 12px; height: 12px; border: 2px solid currentColor; border-top-color: transparent; border-radius: 50%; display: inline-block; animation: spin 1s linear infinite;"></span>
                  Agent Running…
                </button>
              ` : (String(c.status).toLowerCase() === 'pending' ? `
                <button class="btn btn-primary btn-sm btn-run-agent" id="btn-run-${Utils.escapeHtml(c.claim_id)}" onclick="Dashboard.runClaim('${Utils.escapeHtml(c.claim_id)}', this)">
                  Run Agent
                </button>
              ` : (c.final_report || c.verdict ? `
                <button class="btn btn-secondary btn-sm" onclick="Dashboard.openClaim('${Utils.escapeHtml(c.claim_id)}')">
                  Results
                </button>
              ` : ''))}
              <button class="btn btn-icon btn-sm" title="Delete Claim" onclick="Dashboard.deleteClaim('${Utils.escapeHtml(c.claim_id)}')">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
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

  async runClaim(claimId, btnEl = null) {
    const btn = btnEl || document.getElementById(`btn-run-${claimId}`);
    if (btn) {
      btn.disabled = true;
      btn.style.opacity = '0.75';
      btn.style.cursor = 'not-allowed';
      btn.innerHTML = `
        <span class="spinner-sm" style="width: 12px; height: 12px; border: 2px solid currentColor; border-top-color: transparent; border-radius: 50%; display: inline-block; animation: spin 1s linear infinite;"></span>
        Agent Running…
      `;
    }

    // Mark as running in local AppState to prevent any duplicate trigger
    const claims = AppState.get().claimsList || [];
    const updated = claims.map(c => c.claim_id === claimId ? { ...c, status: 'in_progress', is_running: true } : c);
    AppState.set({ claimsList: updated });

    try {
      Utils.showToast(`Launching InsureMate Agent for ${claimId}...`, 'info');
      await AppState.setActiveClaim(claimId);
      window.App.navigateTo('agent');
      await window.AgentView.startExecution(claimId);
    } catch (err) {
      Utils.showToast(`Error running agent: ${err.message}`, 'error');
    } finally {
      await this.refresh();
    }
  },

  async deleteClaim(claimId) {
    if (!confirm(`Are you sure you want to delete claim ${claimId}? This action cannot be undone.`)) return;
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
      Utils.showToast(`Creating ${preset} demo claim...`, 'info', 1800);
      const res = await API.createDemoClaim(preset, false, true);
      const claimId = res.claim_id;
      Utils.showToast(`Demo claim created: ${claimId}`, 'success');
      await this.refresh();
      await AppState.setActiveClaim(claimId);
      window.App.navigateTo('agent');
      // Execute the agent on the demo claim
      window.AgentView.startExecution(claimId);
    } catch (err) {
      Utils.showToast(`Demo creation failed: ${err.message}`, 'error');
    }
  }
};

window.Dashboard = Dashboard;
