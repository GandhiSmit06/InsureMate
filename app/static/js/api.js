/**
 * frontend/js/api.js
 * Centralized InsureMate REST API Client Layer.
 * Handles base URLs, error encapsulation, JSON parsing, and network timeouts.
 */

const API = {
  BASE_URL: '', // Relative path to support same-origin deployment

  /**
   * Internal generic request helper with JSON parsing and timeout handling.
   */
  async request(endpoint, options = {}) {
    const url = `${this.BASE_URL}${endpoint}`;
    const defaultHeaders = {};

    // Only set Content-Type to JSON if not uploading FormData
    if (!(options.body instanceof FormData)) {
      defaultHeaders['Content-Type'] = 'application/json';
    }

    const config = {
      ...options,
      headers: {
        ...defaultHeaders,
        ...(options.headers || {})
      }
    };

    try {
      const response = await fetch(url, config);

      let data;
      const contentType = response.headers.get('content-type') || '';
      if (contentType.includes('application/json')) {
        data = await response.json();
      } else {
        data = await response.text();
      }

      if (!response.ok) {
        const errorDetail = (data && data.detail) || (data && data.message) || response.statusText || 'Unknown server error';
        throw new Error(typeof errorDetail === 'string' ? errorDetail : JSON.stringify(errorDetail));
      }

      return data;
    } catch (err) {
      console.error(`[API ERROR] ${options.method || 'GET'} ${url}:`, err);
      throw err;
    }
  },

  /**
   * System health check.
   */
  async getHealth() {
    return this.request('/api/health');
  },

  /**
   * Catalog of agent-callable tools.
   */
  async listTools() {
    return this.request('/api/tools');
  },

  /**
   * List historical claim sessions.
   */
  async listClaims(limit = 50, offset = 0) {
    return this.request(`/api/claims?limit=${limit}&offset=${offset}`);
  },

  /**
   * Retrieve full claim memory bundle by claim ID.
   */
  async getClaim(claimId) {
    return this.request(`/api/claims/${encodeURIComponent(claimId)}`);
  },

  /**
   * Create claim session and upload files via FormData.
   */
  async uploadClaim(formData) {
    return this.request('/api/claims/upload', {
      method: 'POST',
      body: formData
    });
  },

  /**
   * Alias for createClaim.
   */
  async createClaim(formData) {
    return this.uploadClaim(formData);
  },

  /**
   * Quick-launch preconfigured demo claim.
   */
  async createDemoClaim(preset = 'health', autoRun = false, offlineMode = true) {
    return this.request('/api/claims/demo', {
      method: 'POST',
      body: JSON.stringify({
        preset,
        auto_run: autoRun,
        offline_mode: offlineMode
      })
    });
  },

  /**
   * Trigger autonomous agent run for a claim.
   */
  async startAgent(claimId, { maxPages = 3, offlineMode = null, background = false } = {}) {
    return this.request(`/api/claims/${encodeURIComponent(claimId)}/agent/start`, {
      method: 'POST',
      body: JSON.stringify({
        max_pages: maxPages,
        offline_mode: offlineMode,
        background: background
      })
    });
  },

  /**
   * Polling endpoint for active agent status.
   */
  async getAgentStatus(claimId) {
    return this.request(`/api/claims/${encodeURIComponent(claimId)}/agent/status`);
  },

  /**
   * Chronological tool execution activity and decisions.
   */
  async getAgentActivity(claimId) {
    return this.request(`/api/claims/${encodeURIComponent(claimId)}/agent/activity`);
  },

  /**
   * Document list and extracted structured entities.
   */
  async getDocuments(claimId) {
    return this.request(`/api/claims/${encodeURIComponent(claimId)}/documents`);
  },

  /**
   * Add supporting documents to existing claim session.
   */
  async addDocuments(claimId, files) {
    const formData = new FormData();
    for (const f of files) {
      formData.append('files', f);
    }
    return this.request(`/api/claims/${encodeURIComponent(claimId)}/documents`, {
      method: 'POST',
      body: formData
    });
  },

  /**
   * Retrieve final claim readiness verdict and report.
   */
  async getClaimResult(claimId) {
    return this.request(`/api/claims/${encodeURIComponent(claimId)}/result`);
  },

  /**
   * Missing evidence detection report.
   */
  async getMissingDocuments(claimId) {
    return this.request(`/api/claims/${encodeURIComponent(claimId)}/missing-documents`);
  },

  /**
   * Coverage validity and date checks.
   */
  async getValidity(claimId) {
    return this.request(`/api/claims/${encodeURIComponent(claimId)}/validity`);
  },

  /**
   * Document completeness and validation checks.
   */
  async getValidation(claimId) {
    return this.request(`/api/claims/${encodeURIComponent(claimId)}/validation`);
  },

  /**
   * Delete claim session and purge memory records.
   */
  async deleteClaim(claimId) {
    return this.request(`/api/claims/${encodeURIComponent(claimId)}`, {
      method: 'DELETE'
    });
  }
};

window.API = API;
