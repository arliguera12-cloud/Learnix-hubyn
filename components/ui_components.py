"""
Learnix DTE Hub — Componentes UI Personalizados v3.0
Componentes HTML/JS embebidos via st.components.v1.html()
y st.markdown(unsafe_allow_html=True)
"""
import streamlit as st
import streamlit.components.v1 as components


# ─────────────────────────────────────────────────────────
# ENCABEZADO DE PÁGINA
# ─────────────────────────────────────────────────────────
def page_header(icon: str, title: str, subtitle: str, badge: str = "") -> None:
    badge_html = (
        f'<span class="version-badge">{badge}</span>'
        if badge else ""
    )
    st.markdown(
        f"""
        <div class="page-header animate-fade-in-up">
          <div class="page-header-icon">{icon}</div>
          <div style="flex:1; min-width:0;">
            <div class="page-header-title">{title}</div>
            <div class="page-header-sub">{subtitle}</div>
          </div>
          {badge_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────
# ETIQUETA DE SECCIÓN
# ─────────────────────────────────────────────────────────
def section_label(text: str, icon: str = "") -> None:
    prefix = f"{icon}&nbsp;&nbsp;" if icon else ""
    st.markdown(
        f'<div class="section-label animate-fade-in">{prefix}{text}</div>',
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────
# TARJETA KPI
# ─────────────────────────────────────────────────────────
def kpi_card(
    value: str,
    label: str,
    sub: str = "",
    icon: str = "",
    accent: str = "teal",          # teal | green | blue | amber | purple | rose
    animate_delay: int = 0,
) -> None:
    accent_map = {
        "teal":   "",
        "green":  "accent-green",
        "blue":   "accent-blue",
        "amber":  "accent-amber",
        "purple": "accent-purple",
        "rose":   "accent-rose",
    }
    accent_class = accent_map.get(accent, "")
    delay_class  = f"animate-delay-{animate_delay}" if animate_delay else ""
    icon_html    = (
        f'<div class="kpi-icon">{icon}</div>' if icon else ""
    )
    st.markdown(
        f"""
        <div class="kpi-pro {accent_class} animate-fade-in-up {delay_class}">
          {icon_html}
          <div class="value">{value}</div>
          <div class="label">{label}</div>
          {"" if not sub else f'<div class="sub">{sub}</div>'}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────
# ZONA DRAG & DROP MEJORADA (HTML/JS puro, sin frameborder)
# Se usa JUNTO al st.file_uploader nativo de Streamlit.
# Esta zona visual mejorada no reemplaza la lógica de upload.
# ─────────────────────────────────────────────────────────
def dropzone_header(accepted_formats: list[str] | None = None, max_mb: int = 500) -> None:
    if accepted_formats is None:
        accepted_formats = ["PDF", "XML", "JSON"]
    chips = "".join(
        f'<span class="format-chip">{fmt}</span>' for fmt in accepted_formats
    )
    st.markdown(
        f"""
        <div class="dropzone-wrap animate-fade-in-up" id="lx-dropzone">
          <span class="dropzone-icon">📂</span>
          <div class="dropzone-title">Arrastra tus archivos aquí</div>
          <div class="dropzone-sub">o usa el botón de carga — máx. {max_mb} MB por lote</div>
          <div class="dropzone-formats">{chips}</div>
        </div>
        <script>
          (function(){{
            var dz = document.getElementById('lx-dropzone');
            if (!dz) return;
            ['dragenter','dragover'].forEach(function(ev){{
              dz.addEventListener(ev, function(e){{
                e.preventDefault();
                dz.classList.add('drag-over');
              }});
            }});
            ['dragleave','drop'].forEach(function(ev){{
              dz.addEventListener(ev, function(){{
                dz.classList.remove('drag-over');
              }});
            }});
          }})();
        </script>
        """,
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────
# ESTADO VACÍO
# ─────────────────────────────────────────────────────────
def empty_state(
    icon: str,
    title: str,
    subtitle: str,
    action_hint: str = "",
) -> None:
    hint_html = (
        f'<div style="margin-top:14px; font-size:0.78rem; color:var(--accent);">{action_hint}</div>'
        if action_hint else ""
    )
    st.markdown(
        f"""
        <div class="empty-state animate-fade-in">
          <span class="empty-state-icon">{icon}</span>
          <div class="empty-state-title">{title}</div>
          <div class="empty-state-sub">{subtitle}</div>
          {hint_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────
# BADGE DE ESTADO DTE
# ─────────────────────────────────────────────────────────
def status_badge(
    text: str,
    kind: str = "ok",    # ok | warn | error | vision | manual
    icon: str = "",
) -> str:
    icon_html = f"{icon}&nbsp;" if icon else ""
    return (
        f'<span class="status-badge {kind}">{icon_html}{text}</span>'
    )


# ─────────────────────────────────────────────────────────
# TABLA MEJORADA CON FILTRO JS (sin recargar página)
# ─────────────────────────────────────────────────────────
def filterable_table(df, height: int = 420, key: str = "tbl") -> None:
    """
    Renderiza un DataFrame Pandas como tabla HTML filtrable en JS.
    No altera ni depende de la lógica de extracción.
    """
    import pandas as pd

    if df is None or df.empty:
        empty_state("📭", "Sin resultados", "No hay datos que mostrar para los filtros aplicados.")
        return

    cols = list(df.columns)
    header_cells = "".join(
        f'<th onclick="lxSort(\'{key}\',{i})" title="Ordenar">{c}</th>'
        for i, c in enumerate(cols)
    )

    def _cell(v) -> str:
        s = str(v) if v is not None else ""
        # Resaltar montos con formato
        if s.startswith("$"):
            return f'<td class="lx-amount">{s}</td>'
        # Colorear tipos DTE
        if s.upper() in {"DTE-01","DTE-02","DTE-03","DTE-05","DTE-06","DTE-07","DTE-10","DTE-11","DTE-14",
                          "01","02","03","05","06","07","10","11","14"}:
            return f'<td><span class="format-chip" style="font-size:0.7rem">{s}</span></td>'
        return f'<td>{s}</td>'

    rows_html = ""
    for _, row in df.iterrows():
        cells = "".join(_cell(row[c]) for c in cols)
        rows_html += f"<tr>{cells}</tr>"

    n = len(df)
    table_html = f"""
<div class="lx-table-wrap" id="wrap-{key}">
  <div class="results-toolbar">
    <div class="results-count" id="count-{key}">{n} registros</div>
    <div style="position:relative;flex:1;min-width:180px;">
      <svg style="position:absolute;left:10px;top:50%;transform:translateY(-50%);
                  width:14px;height:14px;color:#94A3B8;pointer-events:none;"
           fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/>
      </svg>
      <input class="filter-input" id="filter-{key}"
             placeholder="Filtrar por cualquier columna..."
             oninput="lxFilter('{key}')" autocomplete="off"/>
    </div>
  </div>
  <div style="overflow:auto;max-height:{height}px;border-radius:10px;
              border:1px solid var(--border);box-shadow:var(--shadow-sm);">
    <table class="lx-table" id="table-{key}">
      <thead><tr>{header_cells}</tr></thead>
      <tbody id="tbody-{key}">{rows_html}</tbody>
    </table>
  </div>
</div>

<style>
.lx-table {{
  width:100%; border-collapse:collapse; font-family:var(--font);
  font-size:0.855rem; background:var(--bg-surface);
}}
.lx-table thead th {{
  background:var(--bg-elevated); color:var(--text-secondary);
  font-weight:700; font-size:0.72rem; text-transform:uppercase;
  letter-spacing:0.07em; padding:10px 14px; border-bottom:2px solid var(--border);
  white-space:nowrap; cursor:pointer; user-select:none;
  position:sticky; top:0; z-index:1;
  transition:background 0.15s;
}}
.lx-table thead th:hover {{ background:var(--accent-light); color:var(--accent-dark); }}
.lx-table tbody tr {{ transition:background 0.12s; }}
.lx-table tbody tr:nth-child(even) {{ background:var(--bg-elevated); }}
.lx-table tbody tr:hover {{ background:var(--accent-light); }}
.lx-table tbody td {{
  padding:9px 14px; color:var(--text-primary);
  border-bottom:1px solid var(--border-muted);
  max-width:260px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
}}
.lx-amount {{ font-variant-numeric:tabular-nums; font-weight:600; color:var(--navy) !important; }}
</style>

<script>
(function(){{
  var _sortDir = {{}};

  window.lxFilter = function(key) {{
    var q = (document.getElementById('filter-' + key).value || '').toLowerCase();
    var rows = document.getElementById('tbody-' + key).querySelectorAll('tr');
    var shown = 0;
    rows.forEach(function(r) {{
      var match = r.textContent.toLowerCase().includes(q);
      r.style.display = match ? '' : 'none';
      if (match) shown++;
    }});
    var cnt = document.getElementById('count-' + key);
    if (cnt) cnt.textContent = shown + ' registros';
  }};

  window.lxSort = function(key, col) {{
    var tbody = document.getElementById('tbody-' + key);
    if (!tbody) return;
    var rows = Array.from(tbody.querySelectorAll('tr'));
    var asc = !_sortDir[key + col];
    _sortDir[key + col] = asc;
    rows.sort(function(a, b) {{
      var av = (a.cells[col] ? a.cells[col].textContent : '').trim();
      var bv = (b.cells[col] ? b.cells[col].textContent : '').trim();
      var na = parseFloat(av.replace(/[$,]/g,''));
      var nb = parseFloat(bv.replace(/[$,]/g,''));
      if (!isNaN(na) && !isNaN(nb)) return asc ? na - nb : nb - na;
      return asc ? av.localeCompare(bv) : bv.localeCompare(av);
    }});
    rows.forEach(function(r) {{ tbody.appendChild(r); }});
  }};
}})();
</script>
"""
    st.markdown(table_html, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────
# CARD CLIENTE ACTIVO (en página de extractor)
# ─────────────────────────────────────────────────────────
def cliente_activo_banner(cliente: dict) -> None:
    nombre = cliente.get("nombre", "—")
    nit    = cliente.get("nit", "—")
    nrc    = cliente.get("nrc", "")
    st.markdown(
        f"""
        <div style="background:var(--bg-surface);border:1px solid var(--border);
                    border-radius:var(--radius);padding:12px 18px;
                    display:flex;align-items:center;gap:14px;
                    box-shadow:var(--shadow-xs);margin-bottom:4px;">
          <div style="width:40px;height:40px;background:var(--accent-light);
                      border-radius:10px;display:flex;align-items:center;
                      justify-content:center;font-size:1.3rem;flex-shrink:0;">🏢</div>
          <div style="flex:1;min-width:0;">
            <div style="font-size:0.60rem;font-weight:700;color:var(--text-muted);
                        letter-spacing:2px;text-transform:uppercase;margin-bottom:2px;">
              Cliente Activo
            </div>
            <div style="font-size:0.95rem;font-weight:700;color:var(--navy);
                        white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
              {nombre}
            </div>
            <div style="font-size:0.72rem;color:var(--text-secondary);
                        font-family:'Courier New',monospace;">
              NIT: {nit}{f" &nbsp;·&nbsp; NRC: {nrc}" if nrc else ""}
            </div>
          </div>
          <span class="status-badge ok" style="flex-shrink:0;">&#x25CF;&nbsp;Activo</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────
# RESUMEN DE PROCESAMIENTO (después de extraer DTEs)
# ─────────────────────────────────────────────────────────
def processing_summary(total: int, ok: int, warn: int, error: int) -> None:
    pct_ok   = int(ok   / total * 100) if total else 0
    pct_warn = int(warn / total * 100) if total else 0
    pct_err  = int(error/ total * 100) if total else 0
    st.markdown(
        f"""
        <div style="background:var(--bg-surface);border:1px solid var(--border);
                    border-radius:var(--radius-lg);padding:16px 20px;
                    box-shadow:var(--shadow-sm);margin-bottom:16px;">
          <div style="font-size:0.68rem;font-weight:700;color:var(--text-muted);
                      letter-spacing:2px;text-transform:uppercase;margin-bottom:12px;">
            Resumen del Procesamiento
          </div>
          <div style="display:flex;gap:20px;flex-wrap:wrap;margin-bottom:12px;">
            <div style="text-align:center;">
              <div style="font-size:1.5rem;font-weight:800;color:var(--navy);">{total}</div>
              <div style="font-size:0.70rem;color:var(--text-muted);font-weight:600;">Total</div>
            </div>
            <div style="text-align:center;">
              <div style="font-size:1.5rem;font-weight:800;color:var(--success);">{ok}</div>
              <div style="font-size:0.70rem;color:var(--text-muted);font-weight:600;">OK ({pct_ok}%)</div>
            </div>
            <div style="text-align:center;">
              <div style="font-size:1.5rem;font-weight:800;color:var(--warning);">{warn}</div>
              <div style="font-size:0.70rem;color:var(--text-muted);font-weight:600;">Revisar ({pct_warn}%)</div>
            </div>
            <div style="text-align:center;">
              <div style="font-size:1.5rem;font-weight:800;color:var(--error);">{error}</div>
              <div style="font-size:0.70rem;color:var(--text-muted);font-weight:600;">Error ({pct_err}%)</div>
            </div>
          </div>
          <div style="display:flex;height:6px;border-radius:99px;overflow:hidden;gap:2px;">
            <div style="flex:{ok};background:var(--success);border-radius:99px 0 0 99px;
                        transition:flex 0.5s ease;"></div>
            <div style="flex:{warn};background:var(--warning);transition:flex 0.5s ease;"></div>
            <div style="flex:{error};background:var(--error);border-radius:0 99px 99px 0;
                        transition:flex 0.5s ease;"></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────
# LOGO & SIDEBAR HEADER (usado en app.py)
# ─────────────────────────────────────────────────────────
def sidebar_logo() -> None:
    st.markdown(
        """
        <div class="sidebar-logo-wrap">
          <div class="sidebar-logo-mark">YN</div>
          <span class="sidebar-logo-name">Learnix · DTE Hub</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────
# CARD CLIENTE ACTIVO SIDEBAR
# ─────────────────────────────────────────────────────────
def sidebar_cliente_card(cliente: dict) -> None:
    nombre = cliente.get("nombre", "—")
    nit    = cliente.get("nit", "—")
    st.markdown(
        f"""
        <div class="card-cliente-activo">
          <span class="label">Cliente Activo</span>
          <span class="nombre">{nombre}</span>
          <span class="nit">NIT: {nit}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────
# PERIODO FISCAL BADGE
# ─────────────────────────────────────────────────────────
def periodo_badge(mes: str, anno: str) -> None:
    st.markdown(
        f"""
        <div class="periodo-card animate-fade-in">
          <div class="periodo-icon">📅</div>
          <div>
            <span class="periodo-label">Período Fiscal</span>
            <span class="periodo-value">{mes} {anno}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
