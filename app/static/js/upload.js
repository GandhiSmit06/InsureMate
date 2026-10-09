/**
 * frontend/js/upload.js
 * Claim Creation & File Upload Workflow.
 * Step progress tracker, drag-and-drop validation, multi-file support,
 * offline mode toggle, and agent execution trigger.
 */

const Upload = {
  policyFile: null,
  claimFiles: [],

  init() {
    this.setupDropzones();
    this.bindFormEvents();
    this.updateWizardSteps(1);
  },

  updateWizardSteps(activeStepNum) {
    for (let i = 1; i <= 4; i++) {
      const stepEl = document.getElementById(`wiz-step-${i}`);
      if (!stepEl) continue;
      stepEl.className = 'wizard-step';
      if (i < activeStepNum) {
        stepEl.classList.add('completed');
      } else if (i === activeStepNum) {
        stepEl.classList.add('active');
      }
    }
  },

  updateReviewCard() {
    const claimNum = document.getElementById('input-claim-number')?.value?.trim();
    const claimType = document.getElementById('select-claim-type')?.value;

    const refEl = document.getElementById('review-claim-ref');
    const typeEl = document.getElementById('review-claim-type');
    const policyEl = document.getElementById('review-policy-status');
    const countEl = document.getElementById('review-files-count');

    if (refEl) refEl.textContent = claimNum || 'Auto-Generated';
    if (typeEl) typeEl.textContent = claimType ? (claimType.charAt(0).toUpperCase() + claimType.slice(1)) : 'Health';
    if (policyEl) policyEl.textContent = this.policyFile ? `${this.policyFile.name} (Auto-OCR)` : 'None';
    if (countEl) countEl.textContent = `${this.claimFiles.length} file(s)`;
  },

  setupDropzones() {
    // Policy Dropzone
    const policyZone = document.getElementById('policy-dropzone');
    const policyInput = document.getElementById('policy-file-input');

    if (policyZone && policyInput) {
      this.attachDragEvents(policyZone, (files) => {
        if (files.length > 0) this.setPolicyFile(files[0]);
      });

      policyInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files[0]) {
          this.setPolicyFile(e.target.files[0]);
        }
      });
    }

    // Supporting Documents Dropzone (Multiple Files)
    const claimZone = document.getElementById('claim-dropzone');
    const claimInput = document.getElementById('claim-file-input');

    if (claimZone && claimInput) {
      this.attachDragEvents(claimZone, (files) => {
        Array.from(files).forEach(f => this.addClaimFile(f));
      });

      claimInput.addEventListener('change', (e) => {
        if (e.target.files) {
          Array.from(e.target.files).forEach(f => this.addClaimFile(f));
        }
      });
    }

    // Form inputs change listener to track step progress & update review card
    const inputs = ['input-claim-number', 'select-claim-type', 'input-incident-date', 'input-incident-notes', 'input-claim-goal'];
    inputs.forEach(id => {
      const el = document.getElementById(id);
      if (el) {
        el.addEventListener('input', () => {
          this.updateReviewCard();
          if (this.policyFile || this.claimFiles.length > 0) {
            this.updateWizardSteps(3);
          } else {
            this.updateWizardSteps(1);
          }
        });
        el.addEventListener('change', () => this.updateReviewCard());
      }
    });
  },

  attachDragEvents(element, onDropFiles) {
    ['dragenter', 'dragover'].forEach(name => {
      element.addEventListener(name, (e) => {
        e.preventDefault();
        element.classList.add('drag-over');
      });
    });

    ['dragleave', 'drop'].forEach(name => {
      element.addEventListener(name, (e) => {
        e.preventDefault();
        element.classList.remove('drag-over');
      });
    });

    element.addEventListener('drop', (e) => {
      if (e.dataTransfer && e.dataTransfer.files) {
        onDropFiles(e.dataTransfer.files);
      }
    });
  },

  setPolicyFile(file) {
    if (!this.validateFile(file)) return;
    this.policyFile = file;
    this.renderPolicyPreview();
    this.updateReviewCard();
    this.updateWizardSteps(2);
  },

  addClaimFile(file) {
    if (!this.validateFile(file)) return;
    if (this.claimFiles.some(f => f.name === file.name && f.size === file.size)) {
      Utils.showToast(`File "${file.name}" is already selected.`, 'warning');
      return;
    }
    this.claimFiles.push(file);
    this.renderClaimFilesPreview();
    this.updateReviewCard();
    this.updateWizardSteps(2);
  },

  validateFile(file) {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      Utils.showToast(`Unsupported format: "${file.name}". Only PDF files (.pdf) are supported.`, 'error');
      return false;
    }
    if (file.size > 50 * 1024 * 1024) {
      Utils.showToast(`File "${file.name}" exceeds 50 MB limit.`, 'error');
      return false;
    }
    return true;
  },

  renderPolicyPreview() {
    const container = document.getElementById('policy-files-list');
    if (!container) return;

    if (!this.policyFile) {
      container.innerHTML = '';
      return;
    }

    container.innerHTML = `
      <div class="file-chip">
        <div class="file-chip-info">
          <span class="file-chip-icon">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
          </span>
          <div>
            <div class="file-chip-name" title="${Utils.escapeHtml(this.policyFile.name)}">${Utils.escapeHtml(this.policyFile.name)}</div>
            <div class="file-chip-size">${Utils.formatFileSize(this.policyFile.size)} • PDF • Ready</div>
          </div>
        </div>
        <button type="button" class="file-chip-remove" title="Remove File" onclick="Upload.removePolicyFile()">&times;</button>
      </div>
    `;
  },

  removePolicyFile() {
    this.policyFile = null;
    const input = document.getElementById('policy-file-input');
    if (input) input.value = '';
    this.renderPolicyPreview();
    this.updateReviewCard();
    if (this.claimFiles.length === 0) this.updateWizardSteps(1);
  },

  renderClaimFilesPreview() {
    const container = document.getElementById('claim-files-list');
    if (!container) return;

    if (this.claimFiles.length === 0) {
      container.innerHTML = '';
      return;
    }

    container.innerHTML = this.claimFiles.map((file, idx) => `
      <div class="file-chip">
        <div class="file-chip-info">
          <span class="file-chip-icon">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
          </span>
          <div>
            <div class="file-chip-name" title="${Utils.escapeHtml(file.name)}">${Utils.escapeHtml(file.name)}</div>
            <div class="file-chip-size">${Utils.formatFileSize(file.size)} • PDF • Ready</div>
          </div>
        </div>
        <button type="button" class="file-chip-remove" title="Remove File" onclick="Upload.removeClaimFile(${idx})">&times;</button>
      </div>
    `).join('');
  },

  removeClaimFile(index) {
    this.claimFiles.splice(index, 1);
    const input = document.getElementById('claim-file-input');
    if (input && this.claimFiles.length === 0) input.value = '';
    this.renderClaimFilesPreview();
    this.updateReviewCard();
    if (!this.policyFile && this.claimFiles.length === 0) this.updateWizardSteps(1);
  },

  resetForm() {
    this.removePolicyFile();
    this.claimFiles = [];
    this.renderClaimFilesPreview();
    const form = document.getElementById('claim-create-form');
    if (form) form.reset();
    this.updateReviewCard();
    this.updateWizardSteps(1);
  },

  bindFormEvents() {
    const form = document.getElementById('claim-create-form');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
      e.preventDefault();

      if (!this.policyFile && this.claimFiles.length === 0) {
        Utils.showToast('Please upload at least a Policy or Supporting Document.', 'warning');
        return;
      }

      const submitBtn = document.getElementById('btn-submit-claim');
      const originalBtnText = submitBtn ? submitBtn.innerHTML : 'Start Claim Analysis';

      try {
        if (submitBtn) {
          submitBtn.disabled = true;
          submitBtn.innerHTML = `
            <span class="spinner" style="width: 14px; height: 14px; border: 2px solid #fff; border-top-color: transparent; border-radius: 50%; display: inline-block; animation: spin 1s linear infinite;"></span>
            Creating Claim...
          `;
        }

        const formData = new FormData();
        if (this.policyFile) {
          formData.append('policy_file', this.policyFile);
        }
        if (this.claimFiles.length > 0) {
          this.claimFiles.forEach(f => formData.append('claim_files', f));
          formData.append('claim_file', this.claimFiles[0]);
        }

        const claimNumber = document.getElementById('input-claim-number')?.value?.trim();
        const incidentDate = document.getElementById('input-incident-date')?.value?.trim();
        const incidentNotes = document.getElementById('input-incident-notes')?.value?.trim();
        const goalInput = document.getElementById('input-claim-goal');
        const claimTypeSelect = document.getElementById('select-claim-type');
        const toggleOffline = document.getElementById('toggle-offline-mode');
        const toggleAutoRun = document.getElementById('toggle-auto-run');

        const sessionName = claimNumber
          ? `Claim ${claimNumber}`
          : (this.policyFile ? `Policy: ${this.policyFile.name.replace(/\.[^/.]+$/, '')}` : null);
        if (sessionName) formData.append('session_name', sessionName);

        let finalGoal = goalInput ? goalInput.value.trim() : 'Determine claim readiness and identify missing evidence.';
        if (incidentDate) {
          finalGoal += ` Incident / admission date: ${incidentDate}.`;
        }
        if (incidentNotes) {
          finalGoal += ` Note: ${incidentNotes}.`;
        }

        formData.append('goal', finalGoal);
        formData.append('claim_type', claimTypeSelect ? claimTypeSelect.value : 'general');
        formData.append('offline_mode', toggleOffline ? toggleOffline.checked : true);
        formData.append('auto_run', false);

        this.updateWizardSteps(4);

        const res = await API.uploadClaim(formData);
        const claimId = res.claim_id;

        Utils.showToast(`Claim session ${claimId} registered.`, 'success');

        this.resetForm();
        Dashboard.refresh();

        await AppState.setActiveClaim(claimId);
        window.App.navigateTo('agent');

        const autoRunChecked = toggleAutoRun ? toggleAutoRun.checked : true;
        if (autoRunChecked) {
          window.AgentView.startExecution(claimId);
        }

      } catch (err) {
        Utils.showToast(`Upload failed: ${err.message}`, 'error');
        this.updateWizardSteps(2);
      } finally {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.innerHTML = originalBtnText;
        }
      }
    });

    const resetBtn = document.getElementById('btn-reset-form');
    if (resetBtn) {
      resetBtn.addEventListener('click', () => this.resetForm());
    }
  }
};

window.Upload = Upload;
