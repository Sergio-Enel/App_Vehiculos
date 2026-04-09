import streamlit as st
import pandas as pd
from sqlalchemy import text
from datetime import date
import urllib.parse

# ==========================================
# CONFIGURACIÓN DE PÁGINA Y BASE DE DATOS
# ==========================================
st.set_page_config(page_title="Gestión de Vehículos", layout="wide")

# Conexión directa con credenciales inyectadas (Sin depender de Secrets)
conn = st.connection(
    "supabase", 
    type="sql", 
    url="postgresql://postgres.prqgmsnglfvqyizfvaqm:Energia2026Master@aws-1-sa-east-1.pooler.supabase.com:5432/postgres"
)

# ==========================================
# FUNCIONES AUXILIARES
# ==========================================
def obtener_vehiculos():
    # Eliminamos el parámetro extra para evitar TypeError
    return conn.query("SELECT placa, conductor, celular FROM vehiculos", ttl=0)

def obtener_asignaciones(fecha):
    return conn.query(f"SELECT placa FROM asignaciones WHERE fecha='{fecha}'", ttl=0)

# ==========================================
# INTERFAZ DE USUARIO (LOGIN OBLIGATORIO)
# ==========================================
st.sidebar.title("🔐 Acceso al Sistema")

# Obtenemos los nombres y creamos una lista con una opción neutra
usuarios_df = conn.query("SELECT nombre, rol FROM usuarios", ttl=0)
lista_usuarios = ["-- Selecciona tu nombre --"] + usuarios_df['nombre'].tolist()

usuario_actual = st.sidebar.selectbox(
    "¿Quién está ingresando?", 
    options=lista_usuarios,
    index=0 
)

# Verificamos si ya seleccionó a alguien
if usuario_actual == "-- Selecciona tu nombre --":
    st.title("Bienvenido al Sistema de Vehículos")
    st.warning("👈 Por favor, selecciona tu nombre en el panel de la izquierda para continuar.")
    st.info("Esto asegura que las reservas y notificaciones queden a tu nombre.")
    st.stop() 
else:
    # Extraemos el rol del usuario seleccionado
    rol_actual = usuarios_df[usuarios_df['nombre'] == usuario_actual]['rol'].values[0]
    st.sidebar.success(f"Sesión iniciada: **{usuario_actual}**")
    st.sidebar.info(f"Rol activo: **{rol_actual}**")

# ==========================================
# VISTA GLOBAL: VEHÍCULOS EN RUTA SEGÚN FECHA
# ==========================================
st.markdown("### 🌐 Vehículos en Ruta")

# 1. Selector de fecha para filtrar la tabla global
col_fecha_filtro, _ = st.columns([0.3, 0.7])
with col_fecha_filtro:
    fecha_consulta = st.date_input("Filtrar por fecha:", value=date.today(), key="filtro_global")

fecha_str = str(fecha_consulta)

# 2. Consulta de vehículos activos
query_global = f"""
    SELECT r.placa as Placa, v.conductor as Conductor, r.usuario as Trabajador, r.destino as Destino, r.franja as Turno
    FROM reservas r
    JOIN vehiculos v ON r.placa = v.placa
    WHERE r.estado = 'Activa' AND r.fecha = '{fecha_str}'
"""
df_global = conn.query(query_global, ttl=0)

if not df_global.empty:
    st.dataframe(df_global, hide_index=True, use_container_width=True)
else:
    st.info(f"No hay vehículos en ruta para el día {fecha_str}.")

st.markdown("---")

# ==========================================
# VISTA: COORDINADOR
# ==========================================
if rol_actual == 'Coordinador':
    st.title("⚙️ Gestión y Asignación de Vehículos")
    st.write("Selecciona los 7 vehículos que estarán disponibles para la fecha.")
    
    fecha_sel = st.date_input("Fecha de asignación:", min_value=date.today())
    vehiculos_totales = obtener_vehiculos()['placa'].tolist()
    asignados_actuales = obtener_asignaciones(fecha_sel)['placa'].tolist()
    
    # Filtro de seguridad
    asignados_validos = [placa for placa in asignados_actuales if placa in vehiculos_totales]
    
    # Formulario de asignación diaria
    with st.form("form_asignacion"):
        seleccionados = st.multiselect(
            "Vehículos habilitados (Máximo 7):", 
            options=vehiculos_totales, 
            default=asignados_validos, 
            max_selections=7
        )
        guardar = st.form_submit_button("Guardar Asignación Diaria")
        
        if guardar:
            with conn.session as s:
                s.execute(text("DELETE FROM asignaciones WHERE fecha = :f"), {"f": str(fecha_sel)})
                for placa in seleccionados:
                    s.execute(text("INSERT INTO asignaciones (fecha, placa) VALUES (:f, :p)"), 
                               {"f": str(fecha_sel), "p": placa})
                s.commit()
            st.success(f"Se habilitaron {len(seleccionados)} vehículos para el {fecha_sel}.")
            st.rerun()

    # Monitoreo de estado
    st.subheader("📊 Estado de Reservas")
    df_reservas_dia = conn.query(f"SELECT placa, usuario, franja, estado FROM reservas WHERE fecha='{fecha_sel}'", ttl=0)
    if not df_reservas_dia.empty:
        st.dataframe(df_reservas_dia, use_container_width=True)
    else:
        st.info("No hay reservas registradas para esta fecha.")

    # PANEL DE CONFIGURACIÓN MAESTRA
    st.markdown("---")
    with st.expander("🛠️ Panel de Control: Usuarios y Vehículos"):
        tab_veh, tab_usu = st.tabs(["Listado de Vehículos", "Listado de Usuarios"])

        with tab_veh:
            st.subheader("Modificar o Agregar Vehículos")
            with st.form("form_gestion_veh"):
                col_p, col_c, col_t = st.columns(3)
                p_nueva = col_p.text_input("Placa")
                c_nuevo = col_c.text_input("Nombre Conductor")
                t_nuevo = col_t.text_input("Celular/Contacto")
                
                if st.form_submit_button("Guardar / Actualizar"):
                    if p_nueva and c_nuevo:
                        p_limpia = p_nueva.upper().strip()
                        # Verificamos si la placa ya existe
                        existe_v = conn.query(f"SELECT placa FROM vehiculos WHERE placa = '{p_limpia}'", ttl=0)
                        
                        with conn.session as s:
                            if not existe_v.empty:
                                s.execute(text("UPDATE vehiculos SET conductor=:c, celular=:t WHERE placa=:p"), 
                                          {"p": p_limpia, "c": c_nuevo, "t": t_nuevo})
                            else:
                                s.execute(text("INSERT INTO vehiculos (placa, conductor, celular) VALUES (:p, :c, :t)"), 
                                          {"p": p_limpia, "c": c_nuevo, "t": t_nuevo})
                            s.commit()
                        st.success(f"Vehículo {p_limpia} procesado correctamente.")
                        st.rerun()
                    else:
                        st.error("La placa y el conductor son obligatorios.")

            st.write("---")
            st.write("**Eliminar Vehículos:**")
            df_v = conn.query("SELECT * FROM vehiculos", ttl=0)
            for _, row in df_v.iterrows():
                col_i, col_b = st.columns([0.8, 0.2])
                col_i.write(f"🚗 **{row['placa']}** - {row['conductor']}")
                if col_b.button("🗑️ Borrar", key=f"del_v_{row['placa']}"):
                    with conn.session as s:
                        s.execute(text("DELETE FROM vehiculos WHERE placa=:p"), {"p": row['placa']})
                        s.commit()
                    st.rerun()

        with tab_usu:
            st.subheader("Gestión de Personal")
            with st.form("form_nuevo_usuario"):
                n_usuario = st.text_input("Nombre completo")
                r_usuario = st.selectbox("Rol", ["Trabajador", "Coordinador"])
                if st.form_submit_button("Registrar / Modificar"):
                    if n_usuario:
                        n_limpio = n_usuario.strip()
                        # Verificamos si el usuario ya existe
                        existe_u = conn.query(f"SELECT nombre FROM usuarios WHERE nombre = '{n_limpio}'", ttl=0)
                        
                        with conn.session as s:
                            if not existe_u.empty:
                                s.execute(text("UPDATE usuarios SET rol = :r WHERE nombre = :n"), 
                                          {"n": n_limpio, "r": r_usuario})
                            else:
                                s.execute(text("INSERT INTO usuarios (nombre, rol) VALUES (:n, :r)"), 
                                          {"n": n_limpio, "r": r_usuario})
                            s.commit()
                        st.success(f"Usuario {n_limpio} procesado correctamente.")
                        st.rerun()

            st.write("---")
            st.write("**Eliminar Usuarios:**")
            df_u = conn.query("SELECT id, nombre, rol FROM usuarios", ttl=0)
            for _, row in df_u.iterrows():
                if row['nombre'] != usuario_actual:
                    col_u, col_b = st.columns([0.8, 0.2])
                    col_u.write(f"👤 {row['nombre']} ({row['rol']})")
                    if col_b.button("🗑️ Quitar", key=f"del_u_{row['id']}"):
                        with conn.session as s:
                            s.execute(text("DELETE FROM usuarios WHERE id=:id"), {"id": row['id']})
                            s.commit()
                        st.rerun()

# ==========================================
# VISTA: USUARIO (TRABAJADOR)
# ==========================================
elif rol_actual == 'Trabajador':
    st.title("🚗 Reserva Ágil de Vehículos")
    tab_reserva, tab_mis_reservas = st.tabs(["Nueva Reserva", "Mis Reservas Activas"])
    
    with tab_reserva:
        col1, col2 = st.columns(2)
        with col1:
            fecha_res = st.date_input("¿Qué día necesitas el vehículo?", min_value=date.today())
        with col2:
            franja_res = st.selectbox("Franja Horaria:", ["Mañana", "Tarde", "Todo el día"])
            
        st.markdown("### Vehículos Disponibles")
        query_disponibles = f"""
            SELECT v.placa, v.conductor, v.celular FROM asignaciones a
            JOIN vehiculos v ON a.placa = v.placa
            WHERE a.fecha = '{fecha_res}' AND a.placa NOT IN (
                SELECT placa FROM reservas WHERE fecha = '{fecha_res}' AND estado = 'Activa'
                AND (franja = '{franja_res}' OR franja = 'Todo el día' OR '{franja_res}' = 'Todo el día')
            )
        """
        df_disp = conn.query(query_disponibles, ttl=0)
        
        if df_disp.empty:
            st.warning("No hay vehículos disponibles para esta selección.")
        else:
            st.dataframe(df_disp, hide_index=True, use_container_width=True)
            with st.form("form_reserva"):
                placa_elegida = st.selectbox("Selecciona la placa:", df_disp['placa'])
                destino_res = st.text_input("Destino:")
                if st.form_submit_button("Confirmar Reserva"):
                    if not destino_res:
                        st.error("⚠️ Ingresa el destino.")
                    else:
                        with conn.session as s:
                            s.execute(text("""
                                INSERT INTO reservas (fecha, placa, usuario, franja, estado, destino) 
                                VALUES (:f, :p, :u, :fr, :e, :d)
                            """), {"f": str(fecha_res), "p": placa_elegida, "u": usuario_actual, "fr": franja_res, "e": 'Activa', "d": destino_res})
                            s.commit()
                        
                        # Datos para WhatsApp
                        datos_cond = conn.query(f"SELECT conductor, celular FROM vehiculos WHERE placa='{placa_elegida}'", ttl=0)
                        if not datos_cond.empty:
                            n_cond = datos_cond.iloc[0]['conductor']
                            c_cond = "".join(filter(str.isdigit, str(datos_cond.iloc[0]['celular'])))
                            if len(c_cond) == 10: c_cond = "57" + c_cond
                            
                            mensaje = f"Hola {n_cond}, soy {usuario_actual}. Reservé el vehículo {placa_elegida} para el {fecha_res} ({franja_res}). Destino: {destino_res}."
                            wa_url = f"https://wa.me/{c_cond}?text={urllib.parse.quote(mensaje)}"
                            
                            st.success(f"✅ Reservado: {placa_elegida}")
                            st.markdown(f'[📱 Notificar a {n_cond} por WhatsApp]({wa_url})')

    with tab_mis_reservas:
        query_mis = f"SELECT id, fecha, placa, franja FROM reservas WHERE usuario='{usuario_actual}' AND estado='Activa'"
        df_mis = conn.query(query_mis, ttl=0)
        
        if df_mis.empty:
            st.info("No tienes reservas activas.")
        else:
            for _, row in df_mis.iterrows():
                st.write(f"🚗 **{row['placa']}** | {row['fecha']} | {row['franja']}")
                if st.button(f"🗑️ Liberar {row['placa']}", key=f"lib_{row['id']}"):
                    with conn.session as s:
                        s.execute(text("UPDATE reservas SET estado = 'Liberada' WHERE id = :id"), {"id": row['id']})
                        s.commit()
                    st.rerun()
