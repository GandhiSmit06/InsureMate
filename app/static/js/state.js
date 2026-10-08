/**
 * frontend/js/state.js
 * Central Application State Management for InsureMate Frontend.
 * Maintains context, active claim bundle, document lists, and reactive subscribers.
 */

const AppState = {
  data: {
    activeClaimId: null,
    activeClaimBundle: null, // { claim, tool_executions, final_report, verdict, latest_state }
    claimsList: [],
    currentView: 'dashboard',
    isExecuting: false,
    pollTimer: null,
    // Form upload pending files
    policyFile: null,
    claimFiles: [],
    // Tool catalog
    availableTools: []
  },

  listeners: {},

  /**
   * Get current state object snapshot.
   */
  get() {
    return this.data;
  },

  /**
   * Update partial state and notify subscribers for changed keys.
   */
  set(partial) {
    const changedKeys = [];
    for (const key of Object.keys(partial)) {
      if (this.data[key] !== partial[key]) {
        this.data[key] = partial[key];
        changedKeys.push(key);
      }
    }

    // Trigger specific listeners
    for (const key of changedKeys) {
      if (this.listeners[key]) {
        for (const cb of this.listeners[key]) {
          try {
            cb(this.data[key], this.data);
          } catch (e) {
            console.error(`[STATE LISTENER ERROR] key=${key}:`, e);
          }
        }
      }
    }

    // Trigger wildcard listeners
    if (changedKeys.length > 0 && this.listeners['*']) {
      for (const cb of this.listeners['*']) {
        try {
          cb(this.data, changedKeys);
        } catch (e) {
          console.error('[STATE WILDCARD LISTENER ERROR]:', e);
        }
      }
    }
  },

  /**
   * Subscribe to state property changes.
   */
  subscribe(key, callback) {
    if (!this.listeners[key]) {
      this.listeners[key] = [];
    }
    this.listeners[key].push(callback);
    return () => {
      this.listeners[key] = this.listeners[key].filter(cb => cb !== callback);
    };
  },

  /**
   * Set active claim by ID and fetch complete bundle from backend.
   */
  async setActiveClaim(claimId) {
    if (!claimId) {
      this.set({ activeClaimId: null, activeClaimBundle: null });
      return;
    }

    try {
      const bundle = await API.getClaim(claimId);
      this.set({
        activeClaimId: claimId,
        activeClaimBundle: bundle
      });
      return bundle;
    } catch (err) {
      console.error(`Failed to load claim ${claimId}:`, err);
      Utils.showToast(`Failed to load claim ${claimId}`, 'error');
      throw err;
    }
  }
};

window.AppState = AppState;
