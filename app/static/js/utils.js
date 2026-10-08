/**
 * frontend/js/utils.js
 * Utility helpers: HTML sanitization, Date/Currency/Size formatters,
 * Toast notification system, and Modal dialog managers.
 */

const Utils = {
  /**
   * Escape potentially malicious HTML characters to prevent XSS.
   */
  escapeHtml(str) {
    if (str === null || str === undefined) return '';
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
  },

  /**
   * Format ISO date string into human-readable timestamp.
   */
  formatDate(isoStr) {
    if (!isoStr) return '--';
    try {
      const d = new Date(isoStr);
      if (isNaN(d.getTime())) return isoStr;
      return d.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return isoStr;
    }
  },

  /**
   * Format bytes into readable KB/MB string.
   */
  formatFileSize(bytes) {
    if (!bytes || isNaN(bytes)) return '0 B';
    const num = Number(bytes);
    if (num < 1024) return `${num} B`;
    if (num < 1024 * 1024) return `${(num / 1024).toFixed(1)} KB`;
    return `${(num / (1024 * 1024)).toFixed(2)} MB`;
  },

  /**
   * Format currency values.
   */
  formatCurrency(val) {
    if (val === null || val === undefined) return '--';
    const num = typeof val === 'number' ? val : parseFloat(String(val).replace(/[^0-9.-]+/g, ''));
    if (isNaN(num)) return String(val);
    return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(num);
  },

  /**
   * Display non-blocking toast notifications.
   */
  showToast(message, type = 'info', duration = 3500) {
    let container = document.getElementById('toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'toast-container';
      container.className = 'toast-container';
      document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    let icon = 'ℹ️';
    if (type === 'success') icon = '✓';
    else if (type === 'error') icon = '✕';
    else if (type === 'warning') icon = '⚠';

    toast.innerHTML = `
      <span style="font-weight: 700; font-size: 1.1rem;">${icon}</span>
      <div style="flex: 1; word-break: break-word;">${this.escapeHtml(message)}</div>
      <button style="background: none; border: none; color: inherit; opacity: 0.6; cursor: pointer; font-size: 1.1rem;" onclick="this.parentElement.remove()">&times;</button>
    `;

    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(100%)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, duration);
  },

  /**
   * Open modal dialog by element ID.
   */
  openModal(modalId) {
    const el = document.getElementById(modalId);
    if (el) {
      el.classList.add('active');
      document.body.style.overflow = 'hidden';
    }
  },

  /**
   * Close modal dialog by element ID.
   */
  closeModal(modalId) {
    const el = document.getElementById(modalId);
    if (el) {
      el.classList.remove('active');
      document.body.style.overflow = '';
    }
  },

  /**
   * Copy plain text to clipboard with fallback.
   */
  async copyToClipboard(text) {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
        this.showToast('Copied to clipboard!', 'success');
        return true;
      }
    } catch (e) {
      console.warn('Clipboard write failed, using textarea fallback', e);
    }

    const textArea = document.createElement('textarea');
    textArea.value = text;
    textArea.style.position = 'fixed';
    textArea.style.left = '-9999px';
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    try {
      document.execCommand('copy');
      this.showToast('Copied to clipboard!', 'success');
      return true;
    } catch {
      this.showToast('Failed to copy to clipboard', 'error');
      return false;
    } finally {
      textArea.remove();
    }
  }
};

window.Utils = Utils;
