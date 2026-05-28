"""
Self-contained HTML upload page for RepairGraph OEM repair packet intake.

Produces a portable, self-contained HTML page with a file picker, drag-and-drop
zone, classify/report buttons, and a results area. The page uses vanilla JS/CSS
only — no CDN, no frameworks, no external dependencies.

The page interacts with:
  POST /internal/intake/classify  — returns JSON manifest
  POST /internal/intake/report    — returns HTML report (opened in new tab)

All outputs are advisory. RepairGraph processes OEM repair information supplied
by authorized users. It is not an OEM document distribution platform.
"""
from __future__ import annotations

_ADVISORY = (
    "RepairGraph processes OEM repair information supplied by authorized "
    "users/subscribers who have acquired the right to use that information. "
    "RepairGraph is not an OEM document distribution platform and does not "
    "redistribute OEM documentation. Intake classification is heuristic and "
    "does not certify document completeness, OEM authenticity, or normalization "
    "readiness. All outputs require qualified review."
)

_GENERATED_BY = "repairgraph.intake.upload_page"

_CSS = """\
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;font-size:14px;background:#f0f2f5;color:#1a1a2e;line-height:1.5}
header{background:#1a2332;color:#e8eaf0;padding:20px 32px;border-bottom:3px solid #2d5a8c}
header .title{font-size:22px;font-weight:700;letter-spacing:.5px}
header .subtitle{font-size:13px;color:#8899bb;margin-top:4px}
.advisory-banner{background:#fff3cd;border-left:4px solid #e6a817;color:#5a4000;padding:10px 32px;font-size:13px}
.advisory-banner strong{color:#b8860b}
main{padding:24px 32px;max-width:1400px}
.section{background:#fff;border-radius:6px;border:1px solid #dde1e8;margin-bottom:18px;overflow:hidden}
.section-header{background:#f8f9fc;border-bottom:1px solid #dde1e8;padding:10px 16px;font-weight:600;font-size:12px;color:#333;text-transform:uppercase;letter-spacing:.5px}
.section-body{padding:16px}
.drop-zone{border:2px dashed #2d5a8c;border-radius:6px;padding:28px 20px;text-align:center;cursor:pointer;color:#2d5a8c;background:#f8f9fc;transition:background .15s,border-color .15s}
.drop-zone.drag-over{background:#e8f0fb;border-color:#1a4070}
.drop-zone:hover{background:#eef2fa}
.drop-zone p{margin-top:6px;font-size:13px;color:#778}
.btn{display:inline-block;padding:9px 20px;border-radius:4px;font-size:13px;font-weight:600;border:none;cursor:pointer;transition:background .12s,opacity .12s}
.btn-primary{background:#2d5a8c;color:#fff}
.btn-primary:hover{background:#1e3f63}
.btn-secondary{background:#f0f2f5;color:#334;border:1px solid #ccc}
.btn-secondary:hover{background:#e4e6ea}
.btn:disabled{opacity:.55;cursor:not-allowed}
.btn-row{display:flex;gap:10px;margin-top:14px;flex-wrap:wrap}
.file-list{margin-top:12px;font-size:12px}
.file-item{padding:3px 0;color:#334;display:flex;gap:8px;border-bottom:1px solid #f0f2f5}
.file-item:last-child{border-bottom:none}
.file-size{color:#aaa}
.empty{color:#999;font-style:italic;font-size:13px}
.cards{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:0}
.card{background:#fff;border:1px solid #dde1e8;border-radius:6px;padding:14px 16px;min-width:100px;text-align:center;flex:1}
.card-value{font-size:24px;font-weight:700;color:#1a2332}
.card-label{font-size:11px;color:#778;text-transform:uppercase;letter-spacing:.5px;margin-top:3px}
.card.blue .card-value{color:#2d5a8c}
.card.amber .card-value{color:#c87800}
.card.red .card-value{color:#cc3333}
.card.green .card-value{color:#228844}
table{width:100%;border-collapse:collapse;font-size:13px}
th{background:#f0f2f5;text-align:left;padding:7px 10px;font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.4px;color:#556;border-bottom:1px solid #dde1e8}
td{padding:7px 10px;border-bottom:1px solid #eef0f3;vertical-align:top}
tr:last-child td{border-bottom:none}
tr:hover td{background:#f8f9fc}
.badge{display:inline-block;padding:2px 7px;border-radius:3px;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.3px;white-space:nowrap}
.r-ready{background:#d4edda;color:#155724}
.r-partial{background:#fff3cd;color:#7a5200}
.r-incomplete{background:#f8d7da;color:#721c24}
.r-unprocessable{background:#f5c6cb;color:#491217}
.r-unknown{background:#eee;color:#555}
.sev-info{background:#e3f2fd;color:#0d47a1}
.sev-warning{background:#fff3cd;color:#7a5200}
.sev-error{background:#f8d7da;color:#721c24}
.conf-high{background:#d4edda;color:#155724}
.conf-med{background:#fff3cd;color:#7a5200}
.conf-low{background:#f8d7da;color:#721c24}
.mono{font-family:monospace;font-size:12px}
.kv{display:flex;gap:8px;margin-bottom:5px}
.kv-key{color:#778;min-width:160px;flex-shrink:0;font-size:12px}
.kv-val{color:#1a1a2e;font-family:monospace;font-size:12px;word-break:break-all}
.progress-outer{background:#e9ecef;border-radius:4px;height:8px;overflow:hidden;width:80px;display:inline-block;vertical-align:middle;margin-left:6px}
.progress-inner{height:100%;border-radius:4px;background:#2d5a8c}
.role-found{background:#d4edda;color:#155724;border-radius:3px;padding:3px 9px;font-size:12px;font-weight:600;margin:2px;display:inline-block}
.role-found-supporting{background:#cce5ff;color:#004085;border-radius:3px;padding:3px 9px;font-size:12px;font-weight:600;margin:2px;display:inline-block}
.role-missing{background:#f8d7da;color:#721c24;border-radius:3px;padding:3px 9px;font-size:12px;font-weight:600;margin:2px;display:inline-block}
.error-box{background:#f8d7da;border-left:4px solid #cc3333;color:#721c24;padding:12px 16px;border-radius:4px;font-size:13px;white-space:pre-wrap;font-family:monospace}
.loading-msg{color:#2d5a8c;font-size:13px;padding:8px 0}
#results{display:none}
details{margin:4px 0}
details summary{cursor:pointer;font-size:12px;color:#2d5a8c;padding:2px 0;user-select:none}
details summary:hover{color:#1a3f6f}
.evidence-row{background:#f8f9fc;border-top:1px solid #eef0f3;padding:8px 10px;font-size:12px}
.evidence-label{font-size:11px;font-weight:600;color:#556;text-transform:uppercase;letter-spacing:.4px;margin-bottom:4px}
.text-quality-usable{color:#155724;font-weight:600}
.text-quality-sparse{color:#7a5200;font-weight:600}
.text-quality-none{color:#721c24;font-weight:600}
footer{margin-top:24px;padding:14px 32px;font-size:11px;color:#aaa;border-top:1px solid #dde1e8;text-align:center}
"""

_JS = """\
(function() {
  var _files = [];

  function esc(s) {
    return String(s)
      .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
      .replace(/"/g,'&quot;');
  }

  function formatBytes(n) {
    if (n < 1024) return n + ' B';
    if (n < 1048576) return (n/1024).toFixed(1) + ' KB';
    return (n/1048576).toFixed(1) + ' MB';
  }

  function badge(cls, label) {
    return '<span class="badge ' + esc(cls) + '">' + esc(label) + '</span>';
  }

  function confDisplay(conf) {
    var pct = Math.round(conf * 100);
    var cls = conf >= 0.65 ? 'conf-high' : conf >= 0.35 ? 'conf-med' : 'conf-low';
    var bar = '<div class="progress-outer"><div class="progress-inner" style="width:' + pct + '%"></div></div>';
    return '<span class="badge ' + cls + '">' + pct + '%</span>' + bar;
  }

  function kv(key, val) {
    return '<div class="kv"><span class="kv-key">' + esc(key) + '</span><span class="kv-val">' + esc(String(val ?? '—')) + '</span></div>';
  }

  function section(title, content) {
    return '<div class="section"><div class="section-header">' + esc(title) + '</div><div class="section-body">' + content + '</div></div>';
  }

  function table(headers, rows) {
    var th = headers.map(function(h){ return '<th>' + esc(h) + '</th>'; }).join('');
    var body = rows.length === 0
      ? '<tr><td colspan="' + headers.length + '" class="empty" style="padding:12px 10px">No entries.</td></tr>'
      : rows.map(function(r){ return '<tr>' + r.map(function(c){ return '<td>' + c + '</td>'; }).join('') + '</tr>'; }).join('');
    return '<table><thead><tr>' + th + '</tr></thead><tbody>' + body + '</tbody></table>';
  }

  function renderFileList() {
    var el = document.getElementById('file-list');
    if (_files.length === 0) {
      el.innerHTML = '<span class="empty">No files selected.</span>';
      return;
    }
    el.innerHTML = _files.map(function(f) {
      return '<div class="file-item"><span>' + esc(f.name) + '</span><span class="file-size">' + formatBytes(f.size) + '</span></div>';
    }).join('');
  }

  function setLoading(on) {
    var msg = document.getElementById('loading-msg');
    document.getElementById('btn-analyze').disabled = on;
    document.getElementById('btn-report').disabled = on;
    msg.style.display = on ? '' : 'none';
  }

  function showError(msg) {
    var el = document.getElementById('error-area');
    el.innerHTML = '<div class="error-box">' + esc(msg) + '</div>';
    el.style.display = '';
    document.getElementById('results').style.display = 'none';
  }

  function clearError() {
    var el = document.getElementById('error-area');
    el.innerHTML = '';
    el.style.display = 'none';
  }

  function buildRoleCoverage(files, foundRoles) {
    // Compute role coverage from both primary and supporting roles
    var allRoles = ['repair_procedure','sectioning','welding','corrosion_protection','materials','dimensions','calibration','precautions'];
    var primaryFound = {};
    var supportingFound = {};
    foundRoles.forEach(function(r){ primaryFound[r] = true; });
    files.forEach(function(f) {
      if (f.errors && f.errors.length) return;
      (f.supporting_roles || []).forEach(function(r){ supportingFound[r] = true; });
    });
    var allFound = {};
    Object.keys(primaryFound).forEach(function(r){ allFound[r] = 'primary'; });
    Object.keys(supportingFound).forEach(function(r){ if (!allFound[r]) allFound[r] = 'supporting'; });
    return {allRoles: allRoles, allFound: allFound, primaryFound: primaryFound, supportingFound: supportingFound};
  }

  function renderRoleCoverage(coverage) {
    var foundCount = Object.keys(coverage.allFound).length;
    var totalCount = coverage.allRoles.length;
    var supportingOnlyCount = Object.keys(coverage.supportingFound).filter(function(r){ return !coverage.primaryFound[r]; }).length;
    var rolesHtml = coverage.allRoles.map(function(r) {
      if (coverage.allFound[r] === 'primary') {
        return '<span class="role-found">' + esc(r) + '</span>';
      } else if (coverage.allFound[r] === 'supporting') {
        return '<span class="role-found-supporting" title="Found as supporting role">' + esc(r) + ' (supporting)</span>';
      } else {
        return '<span class="role-missing">' + esc(r) + ' ✗</span>';
      }
    }).join('');
    rolesHtml += '<p style="margin-top:8px;font-size:12px;color:#666">Found ' + foundCount + ' of ' + totalCount + ' tracked roles.';
    if (supportingOnlyCount > 0) {
      rolesHtml += ' ' + supportingOnlyCount + ' role(s) covered via supporting roles only (blue).';
    }
    rolesHtml += '</p>';
    return rolesHtml;
  }

  function renderEvidenceSection(files) {
    if (!files || files.length === 0) return '';
    var blocks = files.map(function(f) {
      var roleBadge = badge('r-' + (f.document_role || 'unknown'), f.document_role || 'unknown');
      var conf = f.confidence || 0;
      var confPct = Math.round(conf * 100);
      var confCls = conf >= 0.65 ? 'conf-high' : conf >= 0.35 ? 'conf-med' : 'conf-low';
      var confBadge = '<span class="badge ' + confCls + '">' + confPct + '%</span>';

      var supporting = (f.supporting_roles || []);
      var roleScores = f.role_scores || {};
      var roleEvidence = f.role_evidence || [];
      var warnings = f.warnings || [];
      var errors = f.errors || [];

      // Text quality
      var warnJoined = warnings.join(' ').toLowerCase();
      var errJoined = errors.join(' ').toLowerCase();
      var textQuality = 'usable';
      if (errors.length || errJoined.indexOf('could not') >= 0) {
        textQuality = 'none';
      } else if (warnJoined.indexOf('minimal content') >= 0 || warnJoined.indexOf('empty') >= 0) {
        textQuality = warnJoined.indexOf('minimal content') >= 0 ? 'sparse' : 'none';
      } else if (Object.keys(roleScores).length === 0 && roleEvidence.length === 0) {
        textQuality = 'sparse';
      }

      // Role scores list
      var scoreEntries = Object.keys(roleScores).sort(function(a,b){ return roleScores[b]-roleScores[a]; });
      var scoresHtml = scoreEntries.length > 0
        ? scoreEntries.map(function(r) {
            var pct = Math.round(roleScores[r] * 100);
            var cls = roleScores[r] >= 0.65 ? 'conf-high' : roleScores[r] >= 0.35 ? 'conf-med' : 'conf-low';
            return '<div class="kv"><span class="kv-key">' + esc(r) + '</span>'
              + '<span class="kv-val"><span class="badge ' + cls + '">' + pct + '%</span></span></div>';
          }).join('')
        : '<span class="empty">No role scores.</span>';

      // Evidence phrases
      var bcItems = roleEvidence.filter(function(e){ return e.indexOf('[bc]') === 0; });
      var phraseItems = roleEvidence.filter(function(e){ return e.indexOf('[bc]') !== 0; });
      var evidenceHtml = '';
      if (phraseItems.length) {
        evidenceHtml += '<div class="evidence-label" style="margin-top:8px">Keyword/Ontology Evidence</div>'
          + phraseItems.map(function(p){ return '<div class="expl-item"><code>' + esc(p) + '</code></div>'; }).join('');
      }
      if (bcItems.length) {
        evidenceHtml += '<div class="evidence-label" style="margin-top:8px">Breadcrumb Evidence</div>'
          + bcItems.map(function(b){ return '<div class="expl-item"><code>' + esc(b.replace('[bc] ','')) + '</code></div>'; }).join('');
      }

      // Filename tokens
      var stem = f.filename.replace(/\.[^.]+$/, '');
      var tokens = stem.split(/[\s_\(\)\[\]\.]+/).filter(function(t){ return t; });

      var qualityCls = 'text-quality-' + textQuality;

      var innerHtml =
        '<details><summary>Role Scores &amp; Evidence</summary>'
        + '<div class="evidence-row"><div class="evidence-label">Role Scores</div>' + scoresHtml
        + (evidenceHtml ? evidenceHtml : '')
        + '</div></details>'
        + '<details><summary>Text Quality: <span class="' + qualityCls + '">' + textQuality + '</span></summary>'
        + '<div class="evidence-row">'
        + '<div class="kv"><span class="kv-key">Quality</span><span class="kv-val ' + qualityCls + '">' + textQuality + '</span></div>'
        + (Object.keys(roleScores).length ? '<div class="kv"><span class="kv-key">Roles Scored</span><span class="kv-val">' + Object.keys(roleScores).length + '</span></div>' : '')
        + (warnings.length ? '<div class="kv"><span class="kv-key">Warnings</span><span class="kv-val">' + warnings.length + '</span></div>' : '')
        + '</div></details>'
        + '<details><summary>Filename Evidence</summary>'
        + '<div class="evidence-row">'
        + '<div class="kv"><span class="kv-key">Tokens</span><span class="kv-val">' + esc(tokens.join(' | ') || '—') + '</span></div>'
        + '<div class="kv"><span class="kv-key">OEM</span><span class="kv-val">' + esc(f.detected_oem || '—') + '</span></div>'
        + '<div class="kv"><span class="kv-key">Model</span><span class="kv-val">' + esc(f.detected_model || '—') + '</span></div>'
        + '<div class="kv"><span class="kv-key">Year</span><span class="kv-val">' + esc(f.detected_year ? String(f.detected_year) : '—') + '</span></div>'
        + '</div></details>';

      if (warnings.length || errors.length) {
        innerHtml += '<details><summary>Warnings &amp; Errors (' + (warnings.length + errors.length) + ')</summary>'
          + '<div class="evidence-row">'
          + errors.map(function(e){ return '<div class="expl-item">' + badge('sev-error','error') + ' ' + esc(e) + '</div>'; }).join('')
          + warnings.map(function(w){ return '<div class="expl-item">' + badge('sev-warning','warning') + ' ' + esc(w) + '</div>'; }).join('')
          + '</div></details>';
      }

      return '<details style="margin-bottom:8px;border:1px solid #dde1e8;border-radius:4px;padding:8px 12px">'
        + '<summary style="font-size:13px;font-weight:600"><span class="mono">' + esc(f.filename) + '</span>&nbsp;&nbsp;'
        + roleBadge
        + (supporting.length ? '&nbsp;<span style="font-size:10px;color:#778">+ ' + esc(supporting.join(', ')) + '</span>' : '')
        + '&nbsp;&nbsp;' + confBadge + '</summary>'
        + '<div style="margin-top:10px">' + innerHtml + '</div>'
        + '</details>';
    });

    return section('Evidence Inspector',
      '<p style="font-size:12px;color:#666;margin-bottom:12px">Click a file to inspect classification evidence, role scores, text quality, and filename parsing.</p>'
      + blocks.join(''));
  }

  function displayResults(data) {
    clearError();
    var html = '';
    var pkt = data.detected_packet || {};
    var files = data.files || [];
    var diags = data.diagnostics || [];
    var missingRoles = data.missing_roles || [];
    var foundRoles = (pkt.detected_roles || []);

    // Compute corrected role coverage (primary + supporting)
    var coverage = buildRoleCoverage(files, foundRoles);
    var allFoundCount = Object.keys(coverage.allFound).length;
    var allMissingCount = coverage.allRoles.length - allFoundCount;

    // Summary cards
    var errCount = diags.filter(function(d){ return d.severity === 'error'; }).length;
    var warnCount = diags.filter(function(d){ return d.severity === 'warning'; }).length;
    var readable = files.filter(function(f){ return !f.errors || f.errors.length === 0; }).length;
    var cards = [
      {value: String(files.length), label: 'Files', accent: 'blue'},
      {value: String(readable), label: 'Readable', accent: readable === files.length ? 'green' : 'amber'},
      {value: String(allFoundCount), label: 'Roles Found', accent: 'blue'},
      {value: String(allMissingCount), label: 'Roles Missing', accent: allMissingCount > 0 ? 'amber' : 'green'},
      {value: String(errCount), label: 'Errors', accent: errCount > 0 ? 'red' : 'green'},
      {value: String(warnCount), label: 'Warnings', accent: warnCount > 0 ? 'amber' : 'green'},
    ];
    var cardsHtml = '<div class="cards">' + cards.map(function(c) {
      return '<div class="card ' + esc(c.accent) + '"><div class="card-value">' + esc(c.value) + '</div><div class="card-label">' + esc(c.label) + '</div></div>';
    }).join('') + '</div>';
    html += section('Intake Summary', cardsHtml);

    // Readiness + packet metadata
    var readiness = data.readiness || 'unknown';
    var readinessBadge = badge('r-' + readiness, readiness.toUpperCase());
    var metaHtml = kv('Intake ID', data.intake_id || '—')
      + kv('Readiness', '') + '<div style="margin:-22px 0 5px 168px">' + readinessBadge + '</div>'
      + kv('Detected OEM', pkt.detected_oem || 'Not detected')
      + kv('Detected Model', pkt.detected_model || 'Not detected')
      + kv('Detected Year', pkt.detected_year || 'Not detected')
      + kv('Detected Operation', pkt.detected_operation || 'Not detected')
      + '<div class="kv"><span class="kv-key">OEM Confidence</span><span class="kv-val">' + confDisplay(pkt.oem_confidence || 0) + '</span></div>';
    html += section('Detected Packet', metaHtml);

    // Role coverage (corrected: primary + supporting)
    html += section('Document Role Coverage', renderRoleCoverage(coverage));

    // File classifications
    var fileRows = files.map(function(f) {
      var status = (f.errors && f.errors.length) ? badge('sev-error','Error')
                 : (f.warnings && f.warnings.length) ? badge('sev-warning','Warning')
                 : badge('r-ready','OK');
      var roleCell = badge('r-' + (f.document_role || 'unknown'), f.document_role || '—');
      var supporting = (f.supporting_roles || []);
      if (supporting.length > 0) {
        roleCell += ' <span style="font-size:10px;color:#778">+ ' + esc(supporting.join(', ')) + '</span>';
      }
      // Text quality indicator
      var warnJoined = (f.warnings || []).join(' ').toLowerCase();
      var tq = (f.errors && f.errors.length) ? 'none'
              : (warnJoined.indexOf('minimal content') >= 0) ? 'sparse'
              : (warnJoined.indexOf('empty') >= 0) ? 'none'
              : (Object.keys(f.role_scores || {}).length === 0) ? 'sparse'
              : 'usable';
      var tqHtml = '<span class="text-quality-' + tq + '">' + tq + '</span>';
      return [
        '<span class="mono">' + esc(f.filename || '—') + '</span>',
        esc(f.extension || '—'),
        roleCell,
        esc(f.detected_oem || '—'),
        esc(f.detected_model || '—'),
        esc(f.detected_year ? String(f.detected_year) : '—'),
        confDisplay(f.confidence || 0),
        tqHtml,
        status,
      ];
    });
    html += section('File Classifications', table(['Filename','Ext','Role','OEM','Model','Year','Confidence','Text Quality','Status'], fileRows));

    // Diagnostics
    if (diags.length > 0) {
      var diagRows = diags.map(function(d) {
        return [
          badge('sev-' + d.severity, d.severity),
          '<span class="mono">' + esc(d.code) + '</span>',
          esc(d.message || '—'),
          esc(d.detail || '—'),
        ];
      });
      html += section('Diagnostics (' + diags.length + ')', table(['Severity','Code','Message','Detail'], diagRows));
    } else {
      html += section('Diagnostics', '<span class="empty">No diagnostics.</span>');
    }

    // Evidence Inspector
    html += renderEvidenceSection(files);

    document.getElementById('results').innerHTML = html;
    document.getElementById('results').style.display = '';
    document.getElementById('results').scrollIntoView({behavior:'smooth', block:'start'});
  }

  function buildFormData() {
    var fd = new FormData();
    _files.forEach(function(f){ fd.append('files', f); });
    return fd;
  }

  window.analyzeFiles = function() {
    if (_files.length === 0) { alert('Please select at least one file.'); return; }
    clearError();
    setLoading(true);
    fetch('/internal/intake/classify', {method: 'POST', body: buildFormData()})
      .then(function(r) {
        if (!r.ok) return r.text().then(function(t){ throw new Error('HTTP ' + r.status + ': ' + t); });
        return r.json();
      })
      .then(function(data) { displayResults(data); })
      .catch(function(e) { showError('Analysis failed: ' + e.message); })
      .finally(function() { setLoading(false); });
  };

  window.viewReport = function() {
    if (_files.length === 0) { alert('Please select at least one file.'); return; }
    clearError();
    setLoading(true);
    fetch('/internal/intake/report', {method: 'POST', body: buildFormData()})
      .then(function(r) {
        if (!r.ok) return r.text().then(function(t){ throw new Error('HTTP ' + r.status + ': ' + t); });
        return r.text();
      })
      .then(function(htmlContent) {
        var blob = new Blob([htmlContent], {type: 'text/html'});
        var url = URL.createObjectURL(blob);
        window.open(url, '_blank');
      })
      .catch(function(e) { showError('Report failed: ' + e.message); })
      .finally(function() { setLoading(false); });
  };

  document.addEventListener('DOMContentLoaded', function() {
    var input = document.getElementById('file-input');
    var dropZone = document.getElementById('drop-zone');

    input.addEventListener('change', function() {
      _files = Array.from(input.files || []);
      renderFileList();
    });

    dropZone.addEventListener('click', function() { input.click(); });

    dropZone.addEventListener('dragover', function(e) {
      e.preventDefault();
      dropZone.classList.add('drag-over');
    });
    dropZone.addEventListener('dragleave', function() {
      dropZone.classList.remove('drag-over');
    });
    dropZone.addEventListener('drop', function(e) {
      e.preventDefault();
      dropZone.classList.remove('drag-over');
      _files = Array.from(e.dataTransfer.files || []);
      renderFileList();
    });

    renderFileList();
  });
})();
"""


def build_intake_upload_page() -> str:
    """Build a self-contained HTML upload page for OEM repair packet intake.

    The page includes a file picker, drag-and-drop zone, Analyze and View Report
    buttons, and a dynamic results area populated via fetch() from the classify
    and report endpoints. No external CDN, no frameworks, vanilla JS/CSS only.

    Returns deterministic, self-contained HTML.
    """
    body = (
        f'<header>'
        f'<div class="title">RepairGraph — OEM Intake</div>'
        f'<div class="subtitle">Upload OEM repair documents for classification and diagnostics</div>'
        f'</header>'
        f'<div class="advisory-banner">'
        f'<strong>Advisory:</strong> {_ADVISORY}'
        f'</div>'
        f'<main>'
        f'<div class="section">'
        f'<div class="section-header">Upload OEM Repair Documents</div>'
        f'<div class="section-body">'
        f'<div id="drop-zone" class="drop-zone">'
        f'<strong>Click to select files</strong> or drag and drop here'
        f'<p>Supported: .txt, .pdf, .md, .json, .csv &bull; Multiple files accepted</p>'
        f'</div>'
        f'<input type="file" id="file-input" multiple style="display:none"'
        f' accept=".txt,.pdf,.md,.json,.csv">'
        f'<div id="file-list" class="file-list">'
        f'<span class="empty">No files selected.</span>'
        f'</div>'
        f'<div class="btn-row">'
        f'<button id="btn-analyze" class="btn btn-primary" onclick="analyzeFiles()">Analyze Packet</button>'
        f'<button id="btn-report" class="btn btn-secondary" onclick="viewReport()">View Full Report</button>'
        f'</div>'
        f'<div id="loading-msg" class="loading-msg" style="display:none">Processing&hellip;</div>'
        f'</div>'
        f'</div>'
        f'<div id="error-area" style="display:none;margin-bottom:18px"></div>'
        f'<div id="results"></div>'
        f'</main>'
        f'<footer>Generated by {_GENERATED_BY} &bull; RepairGraph OEM intake intelligence &bull; Local/internal use only</footer>'
        f'<script>\n{_JS}\n</script>'
    )

    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        "<title>RepairGraph OEM Intake</title>\n"
        f"<style>\n{_CSS}\n</style>\n"
        "</head>\n"
        "<body>\n"
        f"{body}\n"
        "</body>\n"
        "</html>"
    )
