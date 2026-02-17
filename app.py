import streamlit as st
import pandas as pd
import plotly.express as px
import os
import io
import time
import requests 
from datetime import datetime, timezone, timedelta

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Tablero SARE - Filtros Reclamos", layout="wide", page_icon="📊")

# --- VARIABLES GLOBALES ---
URL_API = "https://unbased-pallidly-donn.ngrok-free.dev"
FILE_PATH = "Reporte_General_Sare.xlsx"

# --- FUNCIONES AUXILIARES ---
def ejecutar_actualizacion():
    """Llama a la PC local vía Ngrok para ejecutar el RPA."""
    status_box = st.status("🚀 Conectando con la PC local...", expanded=True)
    try:
        headers = {"ngrok-skip-browser-warning": "true"}
        respuesta = requests.get(f"{URL_API}/actualizar_datos", headers=headers, timeout=300)
        
        if respuesta.status_code == 200:
            with open(FILE_PATH, "wb") as f:
                f.write(respuesta.content)
            status_box.update(label="✅ ¡Actualización Exitosa!", state="complete", expanded=False)
            time.sleep(1)
            st.rerun()
        else:
            st.error(f"Error del servidor: {respuesta.status_code}")
    except Exception as e:
        st.error(f"Error de conexión: {e}")

def obtener_info_archivo(ruta):
    """Calcula la fecha y hora de modificación del archivo en zona horaria Perú."""
    timestamp = os.path.getmtime(ruta)
    dt_utc = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    tz_peru = timezone(timedelta(hours=-5))
    fecha_obj = dt_utc.astimezone(tz_peru)
    return fecha_obj.strftime("%d/%m/%Y"), fecha_obj.strftime("%H:%M:%S")

def generar_tabla_comparativa(df, col_responsable):
    """Genera el resumen de Dentro de fecha vs Vencido por responsable."""
    if df.empty: return pd.DataFrame()
    resumen = df.groupby([col_responsable, 'Estado']).size().unstack(fill_value=0)
    if 'Dentro de fecha' not in resumen.columns: resumen['Dentro de fecha'] = 0
    if 'Vencido' not in resumen.columns: resumen['Vencido'] = 0
    resumen['TOTAL'] = resumen['Dentro de fecha'] + resumen['Vencido']
    return resumen.sort_values(by=['Vencido', 'TOTAL'], ascending=False)

# --- BARRA LATERAL ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2830/2830175.png", width=50)
    st.title("Panel de Control")
    
    if st.button("🔄 ACTUALIZAR DATA (ROBOT)", type="primary", use_container_width=True):
        ejecutar_actualizacion()
    
    st.divider()
    st.header("🎯 Filtros Especiales")
    
    # Filtro de Días Dinámico
    dias_limite = st.slider("Umbral de Vencimiento (Días)", 1, 45, 15)
    st.caption(f"Configurado: >= {dias_limite} días es Vencido.")

# --- CUERPO PRINCIPAL ---
st.title("📊 Tablero de Control de Gestión")

if os.path.exists(FILE_PATH):
    try:
        fecha_arch, hora_arch = obtener_info_archivo(FILE_PATH)
        st.info(f"📅 Corte: **{fecha_arch}** | 🕒 Actualización: **{hora_arch}**")

        # Cargar Dataframes
        xls = pd.ExcelFile(FILE_PATH)
        df_rec = pd.read_excel(xls, 'Data_Reclamos') if 'Data_Reclamos' in xls.sheet_names else pd.DataFrame()
        df_req = pd.read_excel(xls, 'Data_Requerimientos') if 'Data_Requerimientos' in xls.sheet_names else pd.DataFrame()

        # --- FILTRO POR PRODUCTO (SOLO PARA RECLAMOS) ---
        col_producto = "Producto/Servicio - Proced./Admin."
        
        if not df_rec.empty:
            # Verificamos si la columna existe para evitar el error que mencionaste
            if col_producto in df_rec.columns:
                opciones = sorted(df_rec[col_producto].unique().tolist())
                seleccion = st.sidebar.multiselect("Filtrar Reclamos por Producto:", opciones, default=opciones)
                
                # Aplicamos el filtro de Producto
                df_rec = df_rec[df_rec[col_producto].isin(seleccion)]
            else:
                st.sidebar.warning(f"⚠️ No se halló la columna '{col_producto}' en Reclamos.")

            # --- RECALCULAR ESTADO SEGÚN SLIDER (SOLO PARA RECLAMOS) ---
            if 'Días Demora' in df_rec.columns:
                df_rec['Estado'] = df_rec['Días Demora'].apply(
                    lambda x: 'Vencido' if pd.notnull(x) and x >= dias_limite else 'Dentro de fecha'
                )

        # --- VISUALIZACIÓN ---
        col1, col2 = st.columns(2)

        with col1:
            st.header("SECCIÓN RECLAMOS")
            if not df_rec.empty:
                vencidos = len(df_rec[df_rec['Estado'] == 'Vencido'])
                st.metric("Total (Filtrado)", len(df_rec), f"{vencidos} Vencidos", delta_color="inverse")
                
                tabla_rec = generar_tabla_comparativa(df_rec, 'Asignado a:')
                st.dataframe(tabla_rec.style.highlight_max(axis=0, color='#ffcccc', subset=['Vencido']), use_container_width=True)
                
                fig_rec = px.pie(df_rec, names='Estado', hole=0.5, 
                                 color='Estado', color_discrete_map={'Vencido': '#FF4B4B', 'Dentro de fecha': '#00CC96'})
                st.plotly_chart(fig_rec, use_container_width=True)
            else:
                st.warning("No hay datos de Reclamos para mostrar con estos filtros.")

        with col2:
            st.header("REQUERIMIENTOS")
            if not df_req.empty:
                # Requerimientos se mantiene con la regla estándar de 15 días
                st.metric("Total General", len(df_req))
                tabla_req = generar_tabla_comparativa(df_req, 'Asignado a:')
                st.dataframe(tabla_req, use_container_width=True)
                
                fig_req = px.pie(df_req, names='Estado', hole=0.5,
                                 color='Estado', color_discrete_map={'Vencido': '#FF4B4B', 'Dentro de fecha': '#00CC96'})
                st.plotly_chart(fig_req, use_container_width=True)

        st.divider()
        with st.expander("📂 Ver Detalle de Reclamos Filtrados"):
            st.dataframe(df_rec, use_container_width=True)

    except Exception as e:
        st.error(f"Error crítico al procesar: {e}")
else:
    st.error("⚠️ Archivo no encontrado. Ejecuta el Robot desde el panel lateral.")

