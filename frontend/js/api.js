/**
 * frontend/js/api.js
 * InsureMate Centralized API Client & Normalization Layer.
 * Connects the new frontend to InsureMate's FastAPI backend endpoints:
 * - /api/claims, /api/claims/upload, /api/claims/demo
 * - /api/claims/{id}/agent/start, /api/claims/{id}/agent/status, /api/claims/{id}/agent/stream
 * - /api/claims/{id}/result, /api/claims/{id}/missing-documents, /api/claims/{id}/validity
 * - /api/claims/{id}/assistant, /api/claims/{id}/report
 */
(function () {
  const baseUrl = (
    window.INSUREMATE_API_BASE_URL ||
    document.querySelector('meta[name="insuremate-api-base-url"]')?.content ||
    (typeof window !== "undefined" && window.location.protocol === "file:" ? "http://localhost:8000" : "")
  ).replace(/\/$/, "");

  async function request(path, options = {}) {
    const url = `${baseUrl}${path}`;
    const defaultHeaders = {};
    if (!(options.body instanceof FormData)) {
      defaultHeaders["Content-Type"] = "application/json";
    }

    const response = await fetch(url, {
      ...options,
      headers: {
        ...defaultHeaders,
        ...(options.headers || {})
      }
    });

    if (!response.ok) {
      let detail = "";
      try {
        const errorJson = await response.json();
        detail = errorJson.detail || errorJson.error || errorJson.message || "";
      } catch (_) {
        detail = response.statusText || "";
      }
      throw new Error(detail || `Request failed (${response.status})`);
    }

    if (response.status === 204) return null;
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      return response.json();
    }
    return response.text();
  }

  function jsonRequest(method, body) {
    return {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    };
  }

  /**
   * Transforms raw backend claim bundle into normalized analysis schema
   * expected by the new frontend UI.
   */
  function normalizeClaimToAnalysis(data) {
    if (!data) return null;
    const claim = data.claim || data;
    const report = data.final_report || {};
    const latestState = data.latest_state || {};
    const toolExecs = data.tool_executions || [];
    const claimId = claim.claim_id || data.claim_id || data.id || "CLM-ACTIVE";

    const isRunning = Boolean(
      data.is_running ||
      ["in_progress", "running", "processing"].includes(String(claim.status).toLowerCase())
    );

    // Build standard pipeline step progress
    const stepDefs = [
      { name: "Document ingestion and preprocessing", description: "Preparing document pages and structure." },
      { name: "OCR and visual understanding", description: "Reading text, tables, and visual layout." },
      { name: "Structured extraction and validation", description: "Turning evidence into structured fields." },
      { name: "Reasoning", description: "Connecting extracted facts across documents." },
      { name: "Insurance analysis", description: "Reviewing policy coverage and exclusions." },
      { name: "Evidence and confidence checks", description: "Linking findings back to source pages." }
    ];

    let steps = [];
    if (!isRunning && (report.status || report.verdict || claim.status === "completed" || data.verdict)) {
      steps = stepDefs.map(s => ({ ...s, status: "done", state: "done" }));
    } else if (String(claim.status).toUpperCase() === "FAILED") {
      steps = stepDefs.map((s, idx) => ({ ...s, status: idx === 0 ? "failed" : "pending", state: idx === 0 ? "failed" : "pending" }));
    } else {
      const activeIdx = Math.min(stepDefs.length - 1, Math.max(0, toolExecs.length));
      steps = stepDefs.map((s, idx) => {
        if (idx < activeIdx) return { ...s, status: "done", state: "done" };
        if (idx === activeIdx) return { ...s, status: "in_progress", state: "in_progress" };
        return { ...s, status: "pending", state: "pending" };
      });
    }

    // Verdict formatting
    const rawVerdict = data.verdict || report.status || report.verdict || claim.status || "INITIALIZED";
    const statusUpper = String(rawVerdict).toUpperCase();
    const isReady = statusUpper === "CLAIM_READY_FOR_SUBMISSION";
    const isMissing = statusUpper.includes("MISSING");
    const isDiscrepancy = statusUpper.includes("INVALID") || statusUpper.includes("DISCREPANCY") || statusUpper.includes("BREACH");

    let verdictSeverity = "success";
    let verdictBadge = "Ready For Submission";
    let verdictTitle = "Claim Ready For Submission";

    if (isRunning) {
      verdictSeverity = "warning";
      verdictBadge = "Analysis In Progress";
      verdictTitle = "Analyzing Claim Documents…";
    } else if (isReady) {
      verdictSeverity = "success";
      verdictBadge = "Ready For Submission";
      verdictTitle = "Claim Ready For Submission";
    } else if (isMissing) {
      verdictSeverity = "warning";
      verdictBadge = "Missing Required Evidence";
      verdictTitle = "Action Required: Missing Documents";
    } else if (isDiscrepancy) {
      verdictSeverity = "danger";
      verdictBadge = "Discrepancy Detected";
      verdictTitle = "Action Required: Discrepancy Detected";
    } else {
      verdictSeverity = "success";
      verdictBadge = "Assessment Completed";
      verdictTitle = String(rawVerdict).replace(/_/g, " ");
    }

    const verdict = {
      status: rawVerdict,
      is_ready: isReady,
      severity: verdictSeverity,
      badge: verdictBadge,
      title: verdictTitle,
      summary: (/tool requires/i.test(report.decision_summary || "") || /Action=\w+/i.test(report.decision_summary || ""))
        ? (isMissing ? "Required mandatory policy evidence is missing from the submitted claim documents. Please review the checklist below."
          : (isDiscrepancy ? "Discrepancy detected across submitted claim documents. Please resolve the conflicting records before submission."
            : (isReady ? "All documents validated, coverage dates verified, entities consistent, and all required evidence present."
              : "Policy conditions and submitted claim records have been analyzed for claim admissibility.")))
        : (report.decision_summary || "Policy conditions and submitted claim records have been analyzed for claim admissibility.")
    };

    // Missing Documents & Summary
    const rawMissing = latestState.missing_documents || report.missing_documents || {};
    let missingList = [];
    if (Array.isArray(rawMissing)) {
      missingList = rawMissing;
    } else if (Array.isArray(rawMissing.document_results)) {
      missingList = rawMissing.document_results;
    } else if (Array.isArray(rawMissing.missing_documents)) {
      missingList = rawMissing.missing_documents;
    } else if (Array.isArray(rawMissing.required_documents)) {
      missingList = rawMissing.required_documents;
    } else if (Array.isArray(rawMissing.items)) {
      missingList = rawMissing.items;
    }

    const missing_documents = missingList.map((doc, idx) => ({
      sr_no: doc.sr_no || (idx + 1),
      title: doc.document_title || doc.title || doc.document_name || "Required Document",
      missing: Boolean(doc.missing),
      page_number: doc.page_number || doc.page_no || doc.page || null,
      reason: doc.reason || doc.details || (doc.missing ? "Mandated by policy schedule" : "Verified in submission")
    }));

    const missingCount = missing_documents.filter(d => Boolean(d.missing)).length;
    const totalCount = missing_documents.length;
    const summaryMissing = rawMissing.summary?.missing ?? rawMissing.summary?.total_missing ?? rawMissing.summary?.missing_count;
    const summaryTotal = rawMissing.summary?.total_required ?? rawMissing.summary?.total_count;
    const summaryPresent = rawMissing.summary?.present ?? rawMissing.summary?.total_found ?? rawMissing.summary?.present_count;

    const missing_summary = {
      total_required: summaryTotal !== undefined ? summaryTotal : totalCount,
      present_count: summaryPresent !== undefined ? summaryPresent : Math.max(0, totalCount - missingCount),
      missing_count: summaryMissing !== undefined ? summaryMissing : missingCount
    };

    // Validity & Dates
    const valRes = latestState.validity_result || report.validity_check || {};
    let pStart = valRes.policy_start_date;
    let pEnd = valRes.policy_end_date;

    const extracted = latestState.extracted_data || data.extracted_data || data.extracted_pages || [];
    if (!pStart || !pEnd || pStart === "Not specified") {
      for (const p of extracted) {
        if (!pStart || pStart === "Not specified") {
          pStart = p.policy_start_date || p.policy_inception_date || p.inception_date || p.coverage_start_date || p.effective_date || p.start_date || p.from_date;
        }
        if (!pEnd || pEnd === "Not specified") {
          pEnd = p.policy_end_date || p.policy_expiry_date || p.expiry_date || p.coverage_end_date || p.expiration_date || p.end_date || p.to_date;
        }
        if (pStart && pEnd && pStart !== "Not specified" && pEnd !== "Not specified") break;
      }
    }

    let dates = [];
    if (Array.isArray(valRes.dates)) {
      dates = valRes.dates.map(d => {
        let pageNum = d.page_number || d.page_no || d.page;
        const reasonText = d.details || d.reason || "";
        const m = String(reasonText).match(/\b(?:Page|page)\s*(\d+)\b/);
        if (m && (!pageNum || pageNum === 1 || pageNum === "1")) {
          pageNum = parseInt(m[1], 10);
        }
        return {
          ...d,
          page: pageNum || d.page || 1,
          page_number: pageNum || d.page_number || 1
        };
      });
    } else if (Array.isArray(valRes.checks)) {
      dates = valRes.checks.map(c => {
        let pageNum = c.page_number || c.page_no || c.page;
        const reasonText = c.reason || c.details || "";
        const m = String(reasonText).match(/\b(?:Page|page)\s*(\d+)\b/);
        if (m && (!pageNum || pageNum === 1 || pageNum === "1")) {
          pageNum = parseInt(m[1], 10);
        }
        return {
          type: c.document_type || "Claim Document",
          date: c.normalized_date || c.raw_date || "—",
          page: pageNum || 1,
          page_number: pageNum || 1,
          valid: c.valid !== false,
          status: c.status || (c.valid !== false ? "Within Coverage" : "Outside Period"),
          details: c.reason || (c.valid !== false ? "Document event falls within policy effective dates." : "Date outside active policy window")
        };
      });
    }

    const validity = {
      valid: valRes.valid !== false,
      policy_start_date: pStart || "Not specified",
      policy_end_date: pEnd || "Not specified",
      dates: dates,
      reasons: Array.isArray(valRes.reasons) ? valRes.reasons : (valRes.reason ? [valRes.reason] : ["Coverage dates verified against policy period."])
    };

    // Extracted Fields with Page-Level Attribution and Provenance
    const fields = [];
    if (Array.isArray(extracted)) {
      extracted.forEach((doc, idx) => {
        const docType = doc.document_type || "document";
        const pageNum = doc.page_number || (idx + 1);
        const sourceDoc = doc.source_file || doc.document_name || "Document";
        const pageTitle = doc.document_title || (docType === "insurance_policy" ? `Policy Document (Page ${pageNum})` : `Claim Document (Page ${pageNum})`);
        const source = pageTitle;
        const provMap = doc.field_provenance || {};

        const pageFields = [];

        if (doc.fields && typeof doc.fields === "object") {
          for (const [k, v] of Object.entries(doc.fields)) {
            const val = typeof v === "object" && v !== null ? v.value : v;
            const conf = typeof v === "object" && v !== null ? (v.confidence || 0.95) : 0.95;
            if (val !== undefined && val !== null && String(val).trim() !== "") {
              const fieldProv = provMap[k] || {};
              pageFields.push({
                source,
                name: k.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase()),
                value: String(val),
                confidence: conf,
                page_number: pageNum,
                page: pageNum,
                source_document: sourceDoc,
                evidence: fieldProv.evidence || "",
                is_document_level: Boolean(fieldProv.is_document_level)
              });
            }
          }
        } else {
          const skip = new Set([
            "document_type",
            "document_name",
            "document_title",
            "page_number",
            "raw_text",
            "raw_response",
            "status",
            "success",
            "error",
            "source_file",
            "file_path",
            "slot",
            "extracted_text_summary",
            "policy_clauses",
            "policy_relevant_text",
            "relevant_conditions",
            "field_provenance"
          ]);

          for (const [k, v] of Object.entries(doc)) {
            if (!skip.has(k) && v !== null && v !== undefined) {
              const strVal = Array.isArray(v) ? (v.length > 0 ? v.join(", ") : "") : String(v).trim();
              if (strVal !== "") {
                const fieldProv = provMap[k] || {};
                const fieldName = k.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
                pageFields.push({
                  source,
                  name: fieldName,
                  value: strVal,
                  confidence: fieldProv.confidence || 0.95,
                  page_number: pageNum,
                  page: pageNum,
                  source_document: sourceDoc,
                  evidence: fieldProv.evidence || "",
                  is_document_level: Boolean(fieldProv.is_document_level)
                });
              }
            }
          }
        }

        if (pageFields.length > 0) {
          fields.push(...pageFields);
        } else {
          // If page has no schedule fields (e.g. general exclusions/definitions page), indicate clearly
          fields.push({
            source,
            name: "Page Content",
            value: "General policy terms, clauses & exclusions (no page-specific schedule limits)",
            confidence: 1.0,
            page_number: pageNum,
            page: pageNum,
            source_document: sourceDoc,
            evidence: `Verified from Page ${pageNum}`,
            is_document_level: false
          });
        }
      });
    }

    if (latestState.verified_facts && typeof latestState.verified_facts === "object") {
      for (const [k, v] of Object.entries(latestState.verified_facts)) {
        const name = k.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
        if (!fields.some(f => f.name.toLowerCase() === name.toLowerCase())) {
          fields.push({
            source: "Verified Facts",
            name,
            value: typeof v === "object" ? JSON.stringify(v) : String(v),
            confidence: 0.98
          });
        }
      }
    }

    // Exclusions
    let exclusions = [];
    if (Array.isArray(report.exclusions)) {
      exclusions = report.exclusions;
    } else if (report.coverage_evaluation && Array.isArray(report.coverage_evaluation.exclusions)) {
      exclusions = report.coverage_evaluation.exclusions;
    } else if (latestState.clause_search_results && Array.isArray(latestState.clause_search_results.exclusions)) {
      exclusions = latestState.clause_search_results.exclusions;
    }
    const normalizedExclusions = exclusions.map(item => typeof item === "string" ? { text: item } : item);

    // Warnings & Discrepancies
    const warnings = [];
    const valDoc = latestState.validation_result || {};
    if (Array.isArray(valDoc.discrepancies)) {
      valDoc.discrepancies.forEach(d => {
        warnings.push({
          title: d.title || d.field || "Document Discrepancy",
          message: d.message || d.details || String(d)
        });
      });
    }
    if (latestState.consistency_results && Array.isArray(latestState.consistency_results.contradictions)) {
      latestState.consistency_results.contradictions.forEach(c => {
        warnings.push({
          title: c.entity_type ? `Contradiction: ${c.entity_type}` : "Entity Contradiction Detected",
          message: c.description || c.details || String(c)
        });
      });
    }
    if (valRes.valid === false && Array.isArray(valRes.reasons)) {
      valRes.reasons.forEach(r => {
        warnings.push({
          title: "Coverage Window Violation",
          message: r
        });
      });
    }

    // Supporting Evidence
    const evidence = [];
    if (latestState.verified_facts && typeof latestState.verified_facts === "object") {
      for (const [k, v] of Object.entries(latestState.verified_facts)) {
        const prov = (latestState.evidence_provenance && latestState.evidence_provenance[k]) || "Submission Documents";
        const pageMatch = String(prov).match(/page\s*(\d+)/i);
        evidence.push({
          kind: "Fact",
          title: k.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase()),
          detail: String(v),
          source: prov,
          page: pageMatch ? pageMatch[1] : null,
          text: `Extracted & verified from source: ${k} = ${String(v)}.`
        });
      }
    }

    // Review state recall from localStorage
    let review = {};
    try {
      review = JSON.parse(localStorage.getItem(`insuremate_review_${claimId}`) || "{}");
    } catch (_) {}

    return {
      id: claimId,
      analysis_id: claimId,
      name: claim.session_name || claim.policy_filename || claimId,
      title: claim.session_name || claim.policy_filename || "Insurance Claim Assessment",
      created_at: claim.created_at || new Date().toISOString(),
      status: isRunning ? "in_progress" : (claim.status || "completed"),
      is_running: isRunning,
      steps,
      verdict,
      decision_summary: verdict.summary,
      missing_documents,
      missing_summary,
      validity,
      fields,
      extracted_fields: fields,
      coverage_summary: report.coverage_evaluation?.summary || report.decision_summary || "Policy coverage terms and clauses verified.",
      exclusions: normalizedExclusions,
      warnings,
      discrepancies: warnings,
      evidence,
      findings: evidence,
      supporting_evidence: evidence,
      review
    };
  }

  const InsureMateAPI = {
    baseUrl,

    async validateDocumentSlot(file, slot) {
      if (!file) return { valid: false, error: "No file provided" };
      const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
      const allowed = [".pdf", ".jpg", ".jpeg", ".png", ".webp"];
      if (!allowed.includes(ext)) {
        return {
          valid: false,
          error: `Unsupported file type '${ext}'. Please choose a PDF or scanned image.`
        };
      }
      if (file.size > 25 * 1024 * 1024) {
        return {
          valid: false,
          error: "File size exceeds 25 MB limit."
        };
      }

      try {
        const formData = new FormData();
        formData.append("file", file);
        formData.append("slot", slot);
        const url = `${baseUrl}/api/documents/validate-slot`;
        const response = await fetch(url, {
          method: "POST",
          body: formData
        });
        const data = await response.json().catch(() => null);
        if (!response.ok || (data && data.valid === false)) {
          const errMsg = data?.error || data?.detail || data?.message || (slot === "policy" ? "Please upload a valid insurance policy PDF." : "Invalid document uploaded.");
          return {
            valid: false,
            error: errMsg
          };
        }
        return data || { valid: true, slot };
      } catch (err) {
        return {
          valid: false,
          error: err.message || (slot === "policy" ? "Please upload a valid insurance policy PDF." : "Failed to validate document.")
        };
      }
    },

    validateDocumentPair(policyDocument, hospitalDocument) {
      if (!policyDocument || !hospitalDocument) {
        return Promise.resolve({ valid: false, error: "Both policy and claim documents are required." });
      }
      return Promise.resolve({ valid: true });
    },

    async uploadAndAnalyze(policyDocument, hospitalDocument) {
      const body = new FormData();
      body.append("policy_file", policyDocument);
      body.append("claim_file", hospitalDocument);
      body.append("session_name", `${policyDocument.name.replace(/\.[^/.]+$/, "")} Assessment`);
      body.append("goal", "Determine claim readiness, validate policy coverage dates, and identify any missing evidence.");
      body.append("offline_mode", "false");
      body.append("auto_run", "false");

      const res = await request("/api/claims/upload", { method: "POST", body });
      const claimId = res.claim_id || res.id;

      // Start agent in background
      await request(`/api/claims/${encodeURIComponent(claimId)}/agent/start`, jsonRequest("POST", {
        background: true,
        offline_mode: false
      }));

      return normalizeClaimToAnalysis(res);
    },

    async createDemoAnalysis() {
      const res = await request("/api/claims/demo", jsonRequest("POST", {
        preset: "health",
        offline_mode: false,
        auto_run: false
      }));
      const claimId = res.claim_id || res.id;

      await request(`/api/claims/${encodeURIComponent(claimId)}/agent/start`, jsonRequest("POST", {
        background: true,
        offline_mode: false
      }));

      return normalizeClaimToAnalysis(res);
    },

    async getAnalysis(analysisId) {
      const data = await request(`/api/claims/${encodeURIComponent(analysisId)}`);
      return normalizeClaimToAnalysis(data);
    },

    async listHistory() {
      const res = await request("/api/claims?limit=200");
      const list = res.claims || [];
      return list.map(c => ({
        id: c.claim_id,
        analysis_id: c.claim_id,
        name: c.session_name || c.policy_filename || c.claim_id,
        title: c.session_name || c.policy_filename || c.claim_id,
        created_at: c.created_at,
        date: c.created_at,
        status: c.verdict || c.status || "COMPLETED"
      }));
    },

    getHistoryItem(analysisId) {
      return this.getAnalysis(analysisId);
    },

    deleteHistoryItem(analysisId) {
      return request(`/api/claims/${encodeURIComponent(analysisId)}`, { method: "DELETE" });
    },

    askAssistant(analysisId, question) {
      return request(`/api/claims/${encodeURIComponent(analysisId)}/assistant`, jsonRequest("POST", { question }));
    },

    downloadReport(analysisId) {
      return fetch(`${baseUrl}/api/claims/${encodeURIComponent(analysisId)}/report`, { method: "GET" })
        .then(response => {
          if (!response.ok) throw new Error(`Report download failed (${response.status})`);
          return response.blob();
        });
    },

    saveReview(analysisId, review) {
      try {
        localStorage.setItem(`insuremate_review_${analysisId}`, JSON.stringify(review));
      } catch (_) {}
      return request(`/analyses/${encodeURIComponent(analysisId)}/review`, jsonRequest("PUT", review))
        .catch(() => review);
    },

    // SSE agent live feed
    streamAgent(analysisId, onEvent, onError) {
      const url = `${baseUrl}/api/claims/${encodeURIComponent(analysisId)}/agent/stream`;
      try {
        const es = new EventSource(url);
        es.onmessage = (e) => {
          if (!e.data || e.data.trim() === ": keepalive") return;
          try {
            const data = JSON.parse(e.data);
            if (onEvent) onEvent(data);
            if (data.type === "complete") es.close();
          } catch (_) {}
        };
        es.onerror = (err) => {
          if (onError) onError(err);
          es.close();
        };
        return es;
      } catch (err) {
        if (onError) onError(err);
        return null;
      }
    },

    normalizeClaimToAnalysis(data) {
      return normalizeClaimToAnalysis(data);
    },

    normalizeAnalysisResponse(data) {
      return normalizeClaimToAnalysis(data);
    }
  };

  window.InsureMateAPI = InsureMateAPI;
  window.API = InsureMateAPI; // Backwards compatibility
})();
