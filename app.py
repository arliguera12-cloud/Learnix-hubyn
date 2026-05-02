# ═══════════════════════════════════════════════════════════════
# 6️⃣ DASHBOARD PRINCIPAL (CON SELECTOR DE CLIENTES)
# ═══════════════════════════════════════════════════════════════

def cargar_clientes_db() -> list:
    """Carga la lista de clientes desde el archivo del usuario."""
    archivo = f"{DATA_FOLDER}/usuarios.json"
    try:
        if not os.path.exists(archivo):
            return []
        with open(archivo, "r", encoding="utf-8") as f:
            usuarios = json.load(f)
        usuario = st.session_state.get("usuario_actual", "")
        return usuarios.get(usuario, {}).get("clientes", [])
    except Exception:
        return []


def guardar_clientes_db(lista_clientes: list) -> bool:
    """Guarda la lista de clientes del usuario activo."""
    archivo = f"{DATA_FOLDER}/usuarios.json"
    try:
        with open(archivo, "r", encoding="utf-8") as f:
            usuarios = json.load(f)
        usuario = st.session_state.get("usuario_actual", "")
        if usuario not in usuarios:
            return False
        usuarios[usuario]["clientes"] = lista_clientes
        with open(archivo, "w", encoding="utf-8") as f:
            json.dump(usuarios, f, indent=4, ensure_ascii=False)
        return True
    except Exception:
        return False


def mostrar_dashboard():
    """Renderiza el dashboard con selector de clientes."""
    st.markdown(
        "<h2 style='font-family:Courier New,monospace; color:#00E5FF; "
        "letter-spacing:2px; margin-bottom:0;'>YN</h2>",
        unsafe_allow_html=True
    )
    st.title("📊 Dashboard Principal")

    # Header
    col_user1, col_user2, col_user3 = st.columns([2, 1, 1])
    with col_user1:
        st.markdown(f"### 👤 **{st.session_state['usuario_actual']}**")
    with col_user2:
        st.caption(f"📅 {time.strftime('%d/%m/%Y')}")
    with col_user3:
        if st.button("🚪 Cerrar Sesión", use_container_width=True, key="btn_logout"):
            st.session_state["autenticado"] = False
            st.session_state["usuario_actual"] = None
            st.session_state["cliente_activo"] = None
            st.rerun()

    st.divider()

    # ══════════════════════════════════════════
    # SECCIÓN: CLIENTE ACTIVO
    # ══════════════════════════════════════════
    col_izq, col_der = st.columns([1, 1])

    with col_izq:
        st.markdown("### 🏢 Seleccionar Cliente Activo")

        clientes = cargar_clientes_db()

        if clientes:
            opciones = {f"{c.get('nombre', 'N/A')} — {c.get('nit', 'N/A')}": c for c in clientes}
            seleccion = st.selectbox(
                "Cliente registrado",
                list(opciones.keys()),
                key="sel_cliente_activo"
            )

            cliente_obj = opciones[seleccion]

            col_a, col_b = st.columns(2)
            with col_a:
                st.caption(f"**NIT:** {cliente_obj.get('nit', 'N/A')}")
                st.caption(f"**DUI:** {cliente_obj.get('dui', 'N/A')}")
            with col_b:
                st.caption(f"**Email:** {cliente_obj.get('email', 'N/A')}")
                st.caption(f"**Tel:** {cliente_obj.get('telefono', 'N/A')}")

            if st.button("✅ Activar este Cliente", type="primary", use_container_width=True, key="btn_activar"):
                st.session_state["cliente_activo"] = cliente_obj
                st.success(f"✅ Cliente activo: **{cliente_obj.get('nombre')}**")
                st.info("Ahora puedes acceder a los extractores desde el menú lateral.")
        else:
            st.warning("⚠️ No tienes clientes registrados aún.")
            st.info("Agrega tu primer cliente en la sección de abajo.")

        # Mostrar cliente activo actual
        if st.session_state.get("cliente_activo"):
            ca = st.session_state["cliente_activo"]
            st.markdown(
                f"""
                <div style='padding:10px; border-radius:6px; border-left:4px solid #00E5FF;
                            background-color:#0a1628; margin-top:10px;'>
                    <strong style='color:#00E5FF;'>ACTIVO:</strong><br>
                    <span>{ca.get('nombre', 'N/A')}</span><br>
                    <small>NIT: {ca.get('nit', 'N/A')}</small>
                </div>
                """,
                unsafe_allow_html=True
            )

    with col_der:
        st.markdown("### ➕ Agregar Nuevo Cliente")

        with st.form("form_nuevo_cliente", clear_on_submit=True):
            nombre_c = st.text_input("Nombre / Razón Social", placeholder="Empresa ABC S.A.")
            nit_c = st.text_input("NIT", placeholder="0614-123456-789-0")
            dui_c = st.text_input("DUI (opcional)", placeholder="12345678-9")
            email_c = st.text_input("Email", placeholder="empresa@correo.com")
            telefono_c = st.text_input("Teléfono", placeholder="+503 2234-5678")

            if st.form_submit_button("➕ Agregar Cliente", type="primary", use_container_width=True):
                if not nombre_c or not nit_c:
                    st.error("⚠️ Nombre y NIT son obligatorios.")
                else:
                    nuevo = {
                        "nombre": nombre_c.strip(),
                        "nit": nit_c.strip(),
                        "dui": dui_c.strip(),
                        "email": email_c.strip(),
                        "telefono": telefono_c.strip()
                    }
                    clientes_actualizados = clientes + [nuevo]
                    if guardar_clientes_db(clientes_actualizados):
                        st.success(f"✅ Cliente **{nombre_c}** agregado.")
                        st.rerun()
                    else:
                        st.error("❌ Error al guardar el cliente.")

    st.divider()

    # ══════════════════════════════════════════
    # SECCIÓN: MÓDULOS DISPONIBLES
    # ══════════════════════════════════════════
    st.markdown("### 📈 Módulos Disponibles")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(
            """<div style='padding:15px; border:1px solid #333; border-radius:8px;
                         background:#0a0a0a; text-align:center;'>
                <h4>📈 Ventas</h4>
                <p style='color:#888; font-size:12px;'>DTE 01, 03, 05, 06, 11</p>
            </div>""",
            unsafe_allow_html=True
        )
    with col2:
        st.markdown(
            """<div style='padding:15px; border:1px solid #333; border-radius:8px;
                         background:#0a0a0a; text-align:center;'>
                <h4>🛒 Compras</h4>
                <p style='color:#888; font-size:12px;'>DTE 03, 05, 06, 07</p>
            </div>""",
            unsafe_allow_html=True
        )
    with col3:
        st.markdown(
            """<div style='padding:15px; border:1px solid #333; border-radius:8px;
                         background:#0a0a0a; text-align:center;'>
                <h4>✂️ Retenciones</h4>
                <p style='color:#888; font-size:12px;'>DTE-07 (1%)</p>
            </div>""",
            unsafe_allow_html=True
        )
    with col4:
        st.markdown(
            """<div style='padding:15px; border:1px solid #333; border-radius:8px;
                         background:#0a0a0a; text-align:center;'>
                <h4>⚖️ Suj. Excluidos</h4>
                <p style='color:#888; font-size:12px;'>DTE-14 (10%)</p>
            </div>""",
            unsafe_allow_html=True
        )

    st.divider()
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        st.caption(f"👤 {st.session_state['usuario_actual']}")
    with col_f2:
        st.caption("🏢 Learnix Hub v2.0")
    with col_f3:
        st.caption(f"📅 {time.strftime('%d/%m/%Y')}")
