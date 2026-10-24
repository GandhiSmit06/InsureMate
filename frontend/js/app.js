/**
 * frontend/js/app.js
 * Master Application Shell Orchestrator.
 * Handles SPA view switching, hash routing, active claim synchronization,
 * health check verification, and mobile navigation drawers.
 */

const App = {
  views: ['dashboard', 'new-claim', 'claims', 'documents', 'agent', 'results'],
  currentView: 'dashboard',

  async init() {
    console.log('🚀 Initializing InsureMate Dynamic AI Platform Shell...');

    this.initTheme();
    this.bindNavigation();
    this.bindMobileSidebar();
    this.bindActiveClaimClear();

    // Initialize Sub-Modules
    if (window.Dashboard) await window.Dashboard.init();
    if (window.Upload) window.Upload.init();
    if (window.AgentView) await window.AgentView.init();
    if (window.DocumentsView) window.DocumentsView.init();
    if (window.ClaimView) window.ClaimView.init();

    // Verify Backend Health & Catalog
    await this.checkSystemHealth();

    // Subscribe to state changes for header badges
    AppState.subscribe('activeClaimId', (claimId) => {
      this.updateActiveClaimHeader(claimId);
    });

    // Restore active claim from localStorage or auto-load latest claim from backend
    const savedClaimId = localStorage.getItem('insuremate_active_claim_id');
    let loadedBundle = null;
    if (savedClaimId) {
      try {
        loadedBundle = await AppState.setActiveClaim(savedClaimId);
      } catch (_) {}
    }

    if (!loadedBundle) {
      try {
        const claimsRes = await API.listClaims(1, 0);
        const list = claimsRes?.claims || (Array.isArray(claimsRes) ? claimsRes : []);
        if (list.length > 0 && list[0].claim_id) {
          loadedBundle = await AppState.setActiveClaim(list[0].claim_id);
        }
      } catch (err) {
        console.warn('Initial claims list fallback failed:', err);
      }
    }

    // Hash-based initial route or default to dashboard
    const rawInitial = window.location.hash.replace(/^#\/?/, '');
    const initialHash = (rawInitial === 'archive' || rawInitial === 'history') ? 'claims' : rawInitial;
    if (this.views.includes(initialHash)) {
      this.navigateTo(initialHash, false);
    } else {
      this.navigateTo('dashboard', false);
    }

    // Handle browser back/forward
    window.addEventListener('popstate', () => {
      const rawHash = window.location.hash.replace(/^#\/?/, '');
      const hash = (rawHash === 'archive' || rawHash === 'history') ? 'claims' : rawHash;
      if (this.views.includes(hash) && hash !== this.currentView) {
        this.navigateTo(hash, false);
      }
    });
  },

  bindNavigation() {
    const navLinks = document.querySelectorAll('.nav-link[data-view]');
    navLinks.forEach(link => {
      link.addEventListener('click', (e) => {
        e.preventDefault();
        const targetView = link.getAttribute('data-view');
        this.navigateTo(targetView);

        // Close mobile drawer on navigation
        document.querySelector('.app-sidebar')?.classList.remove('mobile-open');
      });
    });

    // Quick New Claim buttons throughout UI
    document.querySelectorAll('[data-action="new-claim"]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        this.navigateTo('new-claim');
      });
    });
  },

  bindMobileSidebar() {
    const toggleBtn = document.getElementById('btn-mobile-sidebar-toggle');
    const sidebar = document.querySelector('.app-sidebar');

    if (toggleBtn && sidebar) {
      toggleBtn.addEventListener('click', () => {
        sidebar.classList.toggle('mobile-open');
      });
    }
  },

  bindActiveClaimClear() {
    const clearBtn = document.getElementById('btn-clear-active-claim');
    if (clearBtn) {
      clearBtn.addEventListener('click', () => {
        AppState.setActiveClaim(null);
        Utils.showToast('Active claim deselected.', 'info', 1000);
      });
    }
  },

  initTheme() {
    const saved = localStorage.getItem('insuremate_theme');
    const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    const initial = saved || (prefersDark ? 'dark' : 'dark');
    this.setTheme(initial, false);

    const toggleBtn = document.getElementById('btn-theme-toggle');
    if (toggleBtn) {
      toggleBtn.addEventListener('click', () => {
        const current = document.documentElement.getAttribute('data-theme') || 'dark';
        const next = current === 'dark' ? 'light' : 'dark';
        this.setTheme(next, true);
        Utils.showToast(`Theme switched to ${next === 'dark' ? 'Obsidian Dark' : 'Enterprise Light'}`, 'info', 1200);
      });
    }
  },

  setTheme(theme, save = true) {
    document.documentElement.setAttribute('data-theme', theme);
    if (save) {
      localStorage.setItem('insuremate_theme', theme);
    }
    const label = document.getElementById('theme-mode-label');
    if (label) {
      label.textContent = theme === 'dark' ? 'Dark' : 'Light';
    }
  },

  navigateTo(viewName, updateHistory = true) {
    if (viewName === 'archive' || viewName === 'history') {
      viewName = 'claims';
    }
    if (!this.views.includes(viewName)) return;

    this.currentView = viewName;
    AppState.set({ currentView: viewName });

    if (updateHistory) {
      window.history.pushState(null, '', `#/${viewName}`);
    }

    // Update Sidebar active link
    document.querySelectorAll('.nav-link[data-view]').forEach(link => {
      if (link.getAttribute('data-view') === viewName) {
        link.classList.add('active');
      } else {
        link.classList.remove('active');
      }
    });

    // Toggle Section visibility
    this.views.forEach(v => {
      const el = document.getElementById(`view-${v}`);
      if (el) {
        if (v === viewName) {
          el.classList.add('active');
        } else {
          el.classList.remove('active');
        }
      }
    });

    // Update Header View Title
    const titleEl = document.getElementById('header-view-title');
    if (titleEl) {
      const titles = {
        'dashboard': 'Dashboard',
        'new-claim': 'New Claim Registration',
        'claims': 'Claims Archive',
        'documents': 'Claim Documents',
        'agent': 'Agent Operations Console',
        'results': 'Claim Assessment & Results'
      };
      titleEl.textContent = titles[viewName] || 'Operations';
    }

    // Refresh view data when navigating to specific screens
    if (viewName === 'agent' && window.AgentView) {
      window.AgentView.fetchAndRenderToolRegistry();
    } else if (viewName === 'claims' && window.Dashboard) {
      window.Dashboard.refresh();
    } else if (viewName === 'documents' && window.DocumentsView) {
      const activeBundle = AppState.get().activeClaimBundle;
      if (activeBundle) {
        window.DocumentsView.renderDocumentsTable(activeBundle);
      }
    } else if (viewName === 'results' && window.ClaimView) {
      const activeBundle = AppState.get().activeClaimBundle;
      if (activeBundle) {
        window.ClaimView.renderClaimResults(activeBundle);
      } else {
        const activeId = AppState.get().activeClaimId || localStorage.getItem('insuremate_active_claim_id');
        if (activeId) {
          AppState.setActiveClaim(activeId).then(b => {
            if (b && window.ClaimView) {
              window.ClaimView.renderClaimResults(b);
            } else {
              // Stale claim fallback to latest existing claim in DB
              API.listClaims(1, 0).then(cr => {
                const l = cr?.claims || (Array.isArray(cr) ? cr : []);
                if (l.length > 0) {
                  AppState.setActiveClaim(l[0].claim_id).then(nb => {
                    if (nb && window.ClaimView) window.ClaimView.renderClaimResults(nb);
                  });
                } else if (window.ClaimView) {
                  window.ClaimView.renderEmptyState();
                }
              });
            }
          }).catch(() => {
            if (window.ClaimView) window.ClaimView.renderEmptyState();
          });
        } else {
          API.listClaims(1, 0).then(cr => {
            const l = cr?.claims || (Array.isArray(cr) ? cr : []);
            if (l.length > 0 && l[0].claim_id) {
              AppState.setActiveClaim(l[0].claim_id).then(nb => {
                if (nb && window.ClaimView) window.ClaimView.renderClaimResults(nb);
              });
            } else if (window.ClaimView) {
              window.ClaimView.renderEmptyState();
            }
          }).catch(() => {
            if (window.ClaimView) window.ClaimView.renderEmptyState();
          });
        }
      }
    }

    window.scrollTo({ top: 0, behavior: 'smooth' });
  },

  updateActiveClaimHeader(claimId) {
    const pill = document.getElementById('header-active-claim-pill');
    const label = document.getElementById('header-active-claim-label');

    if (pill && label) {
      if (claimId) {
        label.textContent = claimId;
        pill.style.display = 'inline-flex';
      } else {
        label.textContent = 'None';
        pill.style.display = 'none';
      }
    }
  },

  async checkSystemHealth() {
    try {
      const health = await API.getHealth();
      const statusText = document.getElementById('header-system-status-text');
      const statusPill = document.getElementById('header-system-status-pill');

      if (statusText) {
        statusText.textContent = `${health.available_tools_count || 6} Tools Online`;
      }
      if (statusPill) {
        statusPill.style.display = 'inline-flex';
      }

      const sidebarToolsCount = document.getElementById('sidebar-tools-count');
      if (sidebarToolsCount) {
        sidebarToolsCount.textContent = `${health.available_tools_count || 6} tools available`;
      }

      const heroStatTools = document.getElementById('hero-stat-tools');
      if (heroStatTools) {
        heroStatTools.textContent = String(health.available_tools_count || 6).padStart(2, '0');
      }
    } catch (err) {
      console.warn('Backend health check returned warning:', err);
      const statusText = document.getElementById('header-system-status-text');
      if (statusText) {
        statusText.textContent = 'Offline / Connecting';
      }
    }
  }
};

window.App = App;

// Start on DOM ready
document.addEventListener('DOMContentLoaded', () => {
  App.init();
});
