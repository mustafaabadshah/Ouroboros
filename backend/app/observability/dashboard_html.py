def get_phoenix_dashboard_html() -> str:
    return """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Arize Phoenix AI Observability | Project Ouroboros</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #09090b;
      --card-bg: #121215;
      --border: #27272a;
      --accent: #10b981;
      --accent-glow: rgba(16, 185, 129, 0.15);
      --text: #f4f4f5;
      --text-muted: #a1a1aa;
      --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      --font-mono: 'JetBrains Mono', monospace;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg);
      color: var(--text);
      font-family: var(--font-sans);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }
    header {
      background: rgba(18, 18, 21, 0.85);
      backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--border);
      padding: 1rem 1.5rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
      position: sticky;
      top: 0;
      z-index: 50;
    }
    .logo-area { display: flex; align-items: center; gap: 0.75rem; }
    .pulse-dot {
      width: 10px; height: 10px; border-radius: 50%;
      background: #10b981; box-shadow: 0 0 12px #10b981;
      animation: pulse 2s infinite;
    }
    @keyframes pulse { 0% { opacity: 1; transform: scale(1); } 50% { opacity: 0.4; transform: scale(0.9); } 100% { opacity: 1; transform: scale(1); } }
    .brand-title { font-family: var(--font-mono); font-weight: 700; font-size: 0.95rem; letter-spacing: -0.02em; }
    .badge {
      font-size: 0.65rem; font-family: var(--font-mono); font-weight: 700;
      padding: 0.2rem 0.5rem; border-radius: 9999px; text-transform: uppercase;
    }
    .badge-emerald { background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }
    .badge-purple { background: rgba(168, 85, 247, 0.15); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.3); }
    .badge-amber { background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }
    .badge-rose { background: rgba(244, 63, 94, 0.15); color: #fb7185; border: 1px solid rgba(244, 63, 94, 0.3); }
    
    .nav-actions { display: flex; align-items: center; gap: 0.75rem; }
    button.btn {
      background: #18181b; color: var(--text); border: 1px solid var(--border);
      padding: 0.4rem 0.75rem; border-radius: 6px; font-family: var(--font-mono);
      font-size: 0.75rem; cursor: pointer; display: flex; align-items: center; gap: 0.4rem;
      transition: all 0.15s ease;
    }
    button.btn:hover { background: #27272a; border-color: #3f3f46; }
    button.btn-primary { background: #10b981; color: #09090b; font-weight: 700; border-color: #10b981; }
    button.btn-primary:hover { background: #34d399; border-color: #34d399; }

    main { max-width: 1400px; width: 100%; margin: 0 auto; padding: 1.5rem; display: flex; flex-direction: column; gap: 1.5rem; flex: 1; }
    
    .metrics-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 1rem;
    }
    .metric-card {
      background: var(--card-bg); border: 1px solid var(--border);
      border-radius: 8px; padding: 1rem; font-family: var(--font-mono);
    }
    .metric-label { font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase; margin-bottom: 0.3rem; }
    .metric-val { font-size: 1.25rem; font-weight: 700; color: #ffffff; }
    .metric-sub { font-size: 0.68rem; color: var(--text-muted); margin-top: 0.2rem; }

    .tabs-bar {
      display: flex; gap: 0.5rem; border-bottom: 1px solid var(--border);
      padding-bottom: 0.5rem; align-items: center; justify-content: space-between;
    }
    .tab-btn-group { display: flex; gap: 0.5rem; }
    .tab-btn {
      background: transparent; color: var(--text-muted); border: none;
      padding: 0.4rem 0.8rem; font-family: var(--font-mono); font-size: 0.8rem;
      cursor: pointer; border-radius: 6px; font-weight: 600;
      transition: all 0.15s ease;
    }
    .tab-btn.active { background: #27272a; color: #ffffff; }

    .filter-chips { display: flex; gap: 0.4rem; font-family: var(--font-mono); }
    .chip {
      font-size: 0.7rem; padding: 0.2rem 0.5rem; border-radius: 4px;
      background: #18181b; border: 1px solid var(--border); color: var(--text-muted);
      cursor: pointer;
    }
    .chip.active { background: #3f3f46; color: #ffffff; border-color: #52525b; }

    .content-area {
      display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; flex: 1; min-height: 500px;
    }
    @media (max-width: 960px) { .content-area { grid-template-columns: 1fr; } }

    .panel {
      background: var(--card-bg); border: 1px solid var(--border); border-radius: 8px;
      display: flex; flex-direction: column; overflow: hidden;
    }
    .panel-header {
      padding: 0.75rem 1rem; border-bottom: 1px solid var(--border);
      background: #151518; font-family: var(--font-mono); font-size: 0.75rem;
      font-weight: 700; display: flex; justify-content: space-between; align-items: center;
    }
    .panel-body { flex: 1; overflow-y: auto; max-height: 600px; }

    /* Span Item */
    .span-item {
      padding: 0.75rem 1rem; border-bottom: 1px solid rgba(39, 39, 42, 0.5);
      cursor: pointer; transition: background 0.15s; font-family: var(--font-mono);
      font-size: 0.75rem; display: flex; flex-direction: column; gap: 0.35rem;
    }
    .span-item:hover { background: rgba(39, 39, 42, 0.4); }
    .span-item.selected { background: rgba(16, 185, 129, 0.08); border-left: 3px solid #10b981; }
    .span-title-row { display: flex; justify-content: space-between; align-items: center; }
    .span-name { font-weight: 700; color: #ffffff; display: flex; align-items: center; gap: 0.4rem; }
    .span-meta { font-size: 0.7rem; color: var(--text-muted); display: flex; gap: 0.75rem; }

    /* Logs Terminal */
    .terminal-body {
      background: #09090b; padding: 1rem; font-family: var(--font-mono);
      font-size: 0.72rem; line-height: 1.6; color: #d4d4d8; overflow-y: auto;
      max-height: 600px;
    }
    .log-line { display: flex; gap: 0.6rem; word-break: break-all; }
    .log-time { color: #71717a; flex-shrink: 0; }
    .log-lvl-INFO { color: #34d399; font-weight: 700; flex-shrink: 0; }
    .log-lvl-WARNING { color: #fbbf24; font-weight: 700; flex-shrink: 0; }
    .log-lvl-ERROR { color: #f87171; font-weight: 700; flex-shrink: 0; }

    /* Detail Inspector */
    .inspector-body { padding: 1.25rem; display: flex; flex-direction: column; gap: 1rem; font-family: var(--font-mono); }
    .inspector-grid {
      display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.75rem;
      background: #09090b; padding: 0.75rem; border-radius: 6px; border: 1px solid var(--border);
      font-size: 0.72rem;
    }
    .pre-box {
      background: #09090b; border: 1px solid var(--border); border-radius: 6px;
      padding: 0.75rem; font-size: 0.7rem; color: #e4e4e7; max-height: 250px;
      overflow-y: auto; white-space: pre-wrap; word-break: break-all;
    }
    .empty-state {
      padding: 3rem 1rem; text-align: center; color: var(--text-muted);
      font-family: var(--font-mono); font-size: 0.8rem;
    }
  </style>
</head>
<body>
  <header>
    <div class="logo-area">
      <div class="pulse-dot"></div>
      <h1 class="brand-title">PROJECT OUROBOROS</h1>
      <span class="badge badge-emerald">ARIZE PHOENIX AI OBSERVABILITY</span>
      <span class="badge badge-purple">LIVE CLOUD TELEMETRY</span>
    </div>
    <div class="nav-actions">
      <span id="autoRefreshNotice" style="font-size: 0.7rem; color: #a1a1aa; font-family: var(--font-mono);">
        Auto-syncing (3s)
      </span>
      <button class="btn btn-primary" onclick="fetchData()">
        <span>↻ Refresh Now</span>
      </button>
      <a href="https://ouroboros-frontend.vercel.app" class="btn" style="text-decoration: none;">
        <span>← Vercel Mission Control</span>
      </a>
    </div>
  </header>

  <main>
    <div class="metrics-grid">
      <div class="metric-card">
        <div class="metric-label">Recorded Spans</div>
        <div class="metric-val" id="metricSpans">15</div>
        <div class="metric-sub">OpenInference Spans in Buffer</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Tracing Project</div>
        <div class="metric-val" id="metricProject" style="font-size: 1rem;">ouroboros-swarm</div>
        <div class="metric-sub">OpenTelemetry Project</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Active Cloud Model</div>
        <div class="metric-val" style="font-size: 1rem; color: #34d399;">qwen/qwen3.8-27b</div>
        <div class="metric-sub">Groq Remote Inference Engine</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Instrumentation</div>
        <div class="metric-val" style="font-size: 1rem; color: #c084fc;">Root + Agent + Eval</div>
        <div class="metric-sub">Hierarchical Tracing Active</div>
      </div>
    </div>

    <div class="tabs-bar">
      <div class="tab-btn-group">
        <button class="tab-btn active" id="tabSpans" onclick="switchView('spans')">⚡ OpenInference Spans</button>
        <button class="tab-btn" id="tabLogs" onclick="switchView('logs')">📜 Live Server & Swarm Logs</button>
      </div>
      <div class="filter-chips" id="filterContainer">
        <span class="chip active" onclick="setFilter('ALL', this)">ALL</span>
        <span class="chip" onclick="setFilter('AGENT', this)">AGENT</span>
        <span class="chip" onclick="setFilter('EVALUATOR', this)">EVALUATOR</span>
        <span class="chip" onclick="setFilter('ERROR', this)">ERROR</span>
      </div>
    </div>

    <!-- Spans View -->
    <div class="content-area" id="spansView">
      <div class="panel">
        <div class="panel-header">
          <span id="spansCountHeader">Recorded Execution Spans (15)</span>
          <span style="font-size: 0.65rem; color: var(--text-muted);">Click span to inspect</span>
        </div>
        <div class="panel-body" id="spansList">
          <div class="empty-state">Loading Phoenix spans...</div>
        </div>
      </div>

      <div class="panel">
        <div class="panel-header">
          <span>Span Inspection & LLM I/O</span>
          <span id="selectedSpanId" style="color: #34d399;">Select a span</span>
        </div>
        <div class="panel-body" id="spanDetail">
          <div class="empty-state">Select any span from the list to inspect LLM prompts, tool execution, and AST evaluation outputs.</div>
        </div>
      </div>
    </div>

    <!-- Logs View -->
    <div class="panel" id="logsView" style="display: none; flex: 1;">
      <div class="panel-header">
        <span>Live Swarm & Process Logs Stream</span>
        <span style="font-size: 0.65rem; color: #34d399;" id="logsCountHeader">0 lines</span>
      </div>
      <div class="terminal-body" id="logsList">
        <div class="empty-state">Streaming server logs...</div>
      </div>
    </div>
  </main>

  <script>
    let spansData = [];
    let selectedSpan = null;
    let currentFilter = 'ALL';
    let currentView = 'spans';

    function switchView(view) {
      currentView = view;
      document.getElementById('tabSpans').classList.toggle('active', view === 'spans');
      document.getElementById('tabLogs').classList.toggle('active', view === 'logs');
      document.getElementById('spansView').style.display = view === 'spans' ? 'grid' : 'none';
      document.getElementById('logsView').style.display = view === 'logs' ? 'flex' : 'none';
      document.getElementById('filterContainer').style.display = view === 'spans' ? 'flex' : 'none';
      if (view === 'logs') fetchLogs();
    }

    function setFilter(filter, el) {
      currentFilter = filter;
      document.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
      el.classList.add('active');
      renderSpans();
    }

    async function fetchData() {
      try {
        const res = await fetch('/api/observability/phoenix/status');
        const data = await res.json();
        spansData = data.recent_spans || [];
        document.getElementById('metricSpans').innerText = data.total_recorded_spans || spansData.length;
        document.getElementById('metricProject').innerText = data.project_name || 'ouroboros-swarm';
        renderSpans();
        if (currentView === 'logs') fetchLogs();
      } catch (e) {
        console.error('Failed to fetch status:', e);
      }
    }

    async function fetchLogs() {
      try {
        const res = await fetch('/api/system/logs?limit=150');
        const data = await res.json();
        const logs = data.logs || [];
        document.getElementById('logsCountHeader').innerText = `${logs.length} lines`;
        const container = document.getElementById('logsList');
        if (logs.length === 0) {
          container.innerHTML = '<div class="empty-state">No recent server logs recorded yet.</div>';
          return;
        }
        container.innerHTML = logs.map(l => `
          <div class="log-line">
            <span class="log-time">${l.timestamp || ''}</span>
            <span class="log-lvl-${l.level}">${l.level}</span>
            <span>${escapeHtml(l.message || l.formatted || '')}</span>
          </div>
        `).join('');
      } catch (e) {
        console.error('Failed to fetch logs:', e);
      }
    }

    function renderSpans() {
      const container = document.getElementById('spansList');
      const filtered = spansData.filter(s => {
        if (currentFilter === 'ALL') return true;
        if (currentFilter === 'AGENT') return s.span_kind === 'AGENT';
        if (currentFilter === 'EVALUATOR') return s.span_kind === 'EVALUATOR';
        if (currentFilter === 'ERROR') return s.status !== 'OK';
        return true;
      });

      document.getElementById('spansCountHeader').innerText = `Recorded Execution Spans (${filtered.length})`;

      if (filtered.length === 0) {
        container.innerHTML = '<div class="empty-state">No spans matching selected filter.</div>';
        return;
      }

      container.innerHTML = filtered.map(s => `
        <div class="span-item ${selectedSpan?.id === s.id ? 'selected' : ''}" onclick="selectSpan('${s.id}')">
          <div class="span-title-row">
            <span class="span-name">
              <span class="badge ${s.span_kind === 'AGENT' ? 'badge-purple' : 'badge-amber'}">${s.span_kind || 'SPAN'}</span>
              ${escapeHtml(s.name)}
            </span>
            <span class="badge ${s.status === 'OK' ? 'badge-emerald' : 'badge-rose'}">${s.status}</span>
          </div>
          <div class="span-meta">
            <span>Model: ${escapeHtml(s.model_name || 'N/A')}</span>
            <span>Duration: ${s.duration_ms || 0}ms</span>
            ${s.total_tokens ? `<span>Tokens: ${s.total_tokens}</span>` : ''}
            <span>Time: ${s.timestamp ? s.timestamp.slice(11, 19) : ''}</span>
          </div>
        </div>
      `).join('');

      if (!selectedSpan && filtered.length > 0) {
        selectSpan(filtered[0].id);
      }
    }

    function selectSpan(id) {
      selectedSpan = spansData.find(s => s.id === id);
      renderSpans();
      const container = document.getElementById('spanDetail');
      if (!selectedSpan) return;

      document.getElementById('selectedSpanId').innerText = selectedSpan.id;
      container.innerHTML = `
        <div class="inspector-body">
          <div class="inspector-grid">
            <div><span style="color:#71717a">ROLE:</span> <b>${escapeHtml(selectedSpan.role || 'System')}</b></div>
            <div><span style="color:#71717a">MODEL:</span> <b>${escapeHtml(selectedSpan.model_name || 'N/A')}</b></div>
            <div><span style="color:#71717a">STATUS:</span> <b style="color:${selectedSpan.status === 'OK' ? '#34d399' : '#f87171'}">${selectedSpan.status}</b></div>
            <div><span style="color:#71717a">DURATION:</span> <b>${selectedSpan.duration_ms || 0} ms</b></div>
            <div><span style="color:#71717a">TOKENS:</span> <b>${selectedSpan.total_tokens || 0} (${selectedSpan.tokens_in || 0} in / ${selectedSpan.tokens_out || 0} out)</b></div>
            <div><span style="color:#71717a">RUN ID:</span> <b>${escapeHtml(selectedSpan.run_id || 'N/A')}</b></div>
          </div>

          ${selectedSpan.input ? `
            <div>
              <div style="font-size:0.7rem; color:#a1a1aa; margin-bottom:0.3rem;">INPUT / PROMPT:</div>
              <div class="pre-box">${escapeHtml(selectedSpan.input)}</div>
            </div>
          ` : ''}

          ${selectedSpan.output ? `
            <div>
              <div style="font-size:0.7rem; color:#a1a1aa; margin-bottom:0.3rem;">OUTPUT / CANDIDATE SYNTHESIS:</div>
              <div class="pre-box" style="border-color: rgba(16, 185, 129, 0.3);">${escapeHtml(selectedSpan.output)}</div>
            </div>
          ` : ''}

          ${selectedSpan.attributes && Object.keys(selectedSpan.attributes).length > 0 ? `
            <div>
              <div style="font-size:0.7rem; color:#a1a1aa; margin-bottom:0.3rem;">OPENINFERENCE ATTRIBUTES:</div>
              <div class="pre-box">${escapeHtml(JSON.stringify(selectedSpan.attributes, null, 2))}</div>
            </div>
          ` : ''}
        </div>
      `;
    }

    function escapeHtml(str) {
      if (!str) return '';
      return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    fetchData();
    setInterval(fetchData, 3000);
  </script>
</body>
</html>
"""
