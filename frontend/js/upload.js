/**
 * frontend/js/upload.js
 * Claim Creation & File Upload Experience.
 * Drag-and-drop file upload, file validation, multiple supporting files,
 * offline mode toggle, and automatic agent triggering.
 */

const Upload = {
  policyFile: null,
  claimFiles: [],

  init() {
    this.setupDropzones();
    this.bindFormEvents();
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

    // Supporting Documents Dropzone (Supports Multiple Files)
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
  },

  addClaimFile(file) {
    if (!this.validateFile(file)) return;
    // Prevent duplicate files with same name
    if (this.claimFiles.some(f => f.name === file.name && f.size === file.size)) {
      Utils.showToast(`File "${file.name}" is already added.`, 'warning');
      return;
    }
    this.claimFiles.push(file);
    this.renderClaimFilesPreview();
  },

  validateFile(file) {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      Utils.showToast(`Invalid file type: "${file.name}". Only PDF files (.pdf) are supported.`, 'error');
      return false;
    }
    // Max 50MB check
    if (file.size > 50 * 1024 * 1024) {
      Utils.showToast(`File "${file.name}" exceeds the maximum allowed size of 50 MB.`, 'error');
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
          <span class="file-chip-icon">📄</span>
          <div>
            <div class="file-chip-name" title="${Utils.escapeHtml(this.policyFile.name)}">${Utils.escapeHtml(this.policyFile.name)}</div>
            <div class="file-chip-size">${Utils.formatFileSize(this.policyFile.size)} • PDF</div>
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
          <span class="file-chip-icon">📑</span>
          <div>
            <div class="file-chip-name" title="${Utils.escapeHtml(file.name)}">${Utils.escapeHtml(file.name)}</div>
            <div class="file-chip-size">${Utils.formatFileSize(file.size)} • PDF</div>
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
  },

  resetForm() {
    this.removePolicyFile();
    this.claimFiles = [];
    this.renderClaimFilesPreview();
    const form = document.getElementById('claim-create-form');
    if (form) form.reset();
  },

  bindFormEvents() {
    const form = document.getElementById('claim-create-form');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
      e.preventDefault();

      if (!this.policyFile && this.claimFiles.length === 0) {
        Utils.showToast('Please upload at least an Insurance Policy or a Supporting Document.', 'warning');
        return;
      }

      const submitBtn = document.getElementById('btn-submit-claim');
      const originalBtnText = submitBtn ? submitBtn.innerHTML : 'Launch Agent';

      try {
        if (submitBtn) {
          submitBtn.disabled = true;
          submitBtn.innerHTML = `
            <span class="spinner" style="width: 16px; height: 16px; border: 2px solid #fff; border-top-color: transparent; border-radius: 50%; display: inline-block; animation: spin 1s linear infinite;"></span>
            Creating Claim Session...
          `;
        }

        const formData = new FormData();
        if (this.policyFile) {
          formData.append('policy_file', this.policyFile);
        }
        if (this.claimFiles.length > 0) {
          this.claimFiles.forEach(f => formData.append('claim_files', f));
          formData.append('claim_file', this.claimFiles[0]); // Primary backward compat
        }

        const goalInput = document.getElementById('input-claim-goal');
        const sessionNameInput = document.getElementById('input-session-name');
        const claimTypeSelect = document.getElementById('select-claim-type');
        const toggleOffline = document.getElementById('toggle-offline-mode');
        const toggleAutoRun = document.getElementById('toggle-auto-run');

        formData.append('goal', goalInput ? goalInput.value : 'Determine claim readiness and identify missing evidence.');
        if (sessionNameInput && sessionNameInput.value.trim()) {
          formData.append('session_name', sessionNameInput.value.trim());
        }
        formData.append('claim_type', claimTypeSelect ? claimTypeSelect.value : 'general');
        formData.append('offline_mode', toggleOffline ? toggleOffline.checked : true);
        formData.append('auto_run', false); // We handle execution explicitly in AgentView

        const res = await API.uploadClaim(formData);
        const claimId = res.claim_id;

        Utils.showToast(`Claim session ${claimId} created successfully!`, 'success');

        // Reset inputs
        this.resetForm();

        // Refresh dashboard list
        Dashboard.refresh();

        // Set active claim and switch view
        await AppState.setActiveClaim(claimId);
        window.App.navigateTo('agent');

        // Start agent execution
        const autoRunChecked = toggleAutoRun ? toggleAutoRun.checked : true;
        if (autoRunChecked) {
          window.AgentView.startExecution(claimId);
        }

      } catch (err) {
        Utils.showToast(`Upload failed: ${err.message}`, 'error');
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
