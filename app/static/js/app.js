/**
 * frontend/js/app.js
 * Master Application Shell Orchestrator.
 * Handles SPA view switching, active claim synchronization, health check verification,
 * and mobile navigation drawers.
 */

const App = {
  views: ['dashboard', 'new-claim', 'claims', 'documents', 'agent', 'results'],
  currentView: 'dashboard',

  async init() {
    console.log('🚀 Initializing InsureMate Application Shell...');

    this.bindNavigation();
    this.bindMobileSidebar();

    // Initialize Sub-Modules
    if (window.Dashboard) await window.Dashboard.init();
    if (window.Upload) window.Upload.init();
    if (window.AgentView) window.AgentView.init();
    if (window.DocumentsView) window.DocumentsView.init();
    if (window.ClaimView) window.ClaimView.init();

    // Verify Backend Health & Catalog
    await this.checkSystemHealth();

    // Subscribe to state changes for header badges
    AppState.subscribe('activeClaimId', (claimId) => {
      this.updateActiveClaimHeader(claimId);
    });

    // Default to dashboard
    this.navigateTo('dashboard');
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

  navigateTo(viewName) {
    if (!this.views.includes(viewName)) return;

    this.currentView = viewName;
    AppState.set({ currentView: viewName });

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
        statusText.textContent = `${health.available_tools_count || 4} Tools Online`;
      }
      if (statusPill) {
        statusPill.style.display = 'inline-flex';
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
