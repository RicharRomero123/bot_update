import streamlit as st
import pandas as pd
import plotly.express as px
import os
import io
import time
import requests # IMPORTANTE: Asegúrate de tener esta librería instalada (pip install requests)
from datetime import datetime

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Tablero SARE", layout="wide", page_icon="📊")


# ¡No pongas una barra "/" al final de la URL!
URL_API = "http://127.0.0.1:8000/"

# --- FUNCIÓN DE ACTUALIZACIÓN (AHORA VÍA NGROK) ---
def ejecutar_actualizacion():
    """Llama a la PC local vía Ngrok para que ejecute el RPA y devuelva el Excel."""
    status_box = st.status("🚀 Conectando con la PC local vía Ngrok...", expanded=True)
    try:
        status_box.write("🤖 Solicitando ejecución del robot en la red interna...")
        
        # El header 'ngrok-skip-browser-warning' es crucial para cuentas Ngrok gratuitas
        headers = {"ngrok-skip-browser-warning": "true"}
        
        # Hacemos la llamada al endpoint de FastAPI que creaste en api_local.py
        # Le damos un timeout largo (5 minutos) porque el RPA toma tiempo en navegar y descargar
        respuesta = requests.get(f"{URL_API}/actualizar_datos", headers=headers, timeout=300)
        
        if respuesta.status_code == 200:
            status_box.write("⬇️ Recibiendo y guardando el Excel procesado...")
            
            # Guardamos el archivo Excel que nos envió la PC local
            with open("Reporte_General_Sare.xlsx", "wb") as f:
                f.write(respuesta.content)
                
            status_box.update(label="✅ ¡Actualización Exitosa desde tu PC!", state="complete", expanded=False)
            time.sleep(1)
            st.rerun() # Recarga la página para mostrar los datos nuevos
        else:
            status_box.write(f"Código de error del servidor: {respuesta.status_code}")
            status_box.update(label="❌ Error al procesar en el servidor local", state="error")
            
    except requests.exceptions.ConnectionError:
        status_box.write("No se pudo conectar al servidor. Verifica que Ngrok y Uvicorn estén corriendo en tu PC.")
        status_box.update(label="❌ Error de conexión", state="error")
    except Exception as e:
        status_box.write(f"Error crítico: {e}")
        status_box.update(label="❌ Fallo de comunicación", state="error")

# --- BARRA LATERAL ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2830/2830175.png", width=50)
    st.title("Panel de Control")
    st.write("Presiona para despertar al robot en la red interna y actualizar la data.")
    
    if st.button("🔄 ACTUALIZAR DATA (ROBOT)", type="primary"):
        ejecutar_actualizacion()

# --- TÍTULO PRINCIPAL ---
st.title("📊 Tablero de Control de Gestión")

FILE_PATH = "Reporte_General_Sare.xlsx"

# --- FUNCIONES AUXILIARES ---
def obtener_info_archivo(ruta):
    timestamp = os.path.getmtime(ruta)
    fecha_obj = datetime.fromtimestamp(timestamp)
    return fecha_obj.strftime("%d/%m/%Y"), fecha_obj.strftime("%H:%M:%S")

def generar_tabla_comparativa(df, col_responsable):
    if df.empty: return pd.DataFrame()
    resumen = df.groupby([col_responsable, 'Estado']).size().unstack(fill_value=0)
    if 'Dentro de fecha' not in resumen.columns: resumen['Dentro de fecha'] = 0
    if 'Vencido' not in resumen.columns: resumen['Vencido'] = 0
    resumen['TOTAL'] = resumen['Dentro de fecha'] + resumen['Vencido']
    resumen = resumen.sort_values(by=['Vencido', 'TOTAL'], ascending=False)
    return resumen

def convertir_df_a_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Resumen')
    return output.getvalue()

# --- LÓGICA DE VISUALIZACIÓN ---

if os.path.exists(FILE_PATH):
    try:
        fecha_arch, hora_arch = obtener_info_archivo(FILE_PATH)
        st.info(f"📅 Fecha de Corte: **{fecha_arch}** | 🕒 Hora: **{hora_arch}**")
        st.markdown("---")

        xls = pd.ExcelFile(FILE_PATH)
        df_reclamos = pd.read_excel(xls, 'Data_Reclamos') if 'Data_Reclamos' in xls.sheet_names else pd.DataFrame()
        df_reqs = pd.read_excel(xls, 'Data_Requerimientos') if 'Data_Requerimientos' in xls.sheet_names else pd.DataFrame()
        color_map = {'Vencido': '#FF4B4B', 'Dentro de fecha': '#00CC96'}

        col_izq, separador, col_der = st.columns([1, 0.1, 1])

        # RECLAMOS
        with col_izq:
            st.header("RECLAMOS")
            st.markdown("---")
            if not df_reclamos.empty:
                total_rec = len(df_reclamos)
                vencidos_rec = len(df_reclamos[df_reclamos['Estado'] == 'Vencido'])
                k1, k2 = st.columns(2)
                k1.metric("Total General", total_rec)
                k2.metric("Vencidos", vencidos_rec, delta="-Crítico", delta_color="inverse")
                
                st.subheader("Carga por Responsable")
                tabla_rec = generar_tabla_comparativa(df_reclamos, 'Asignado a:')
                st.dataframe(tabla_rec.style.highlight_max(axis=0, color='#ffcccc', subset=['Vencido']), use_container_width=True)
                
                st.download_button("📥 Descargar Tabla Reclamos", data=convertir_df_a_excel(tabla_rec), file_name=f"Resumen_Reclamos_{fecha_arch.replace('/','-')}.xlsx")
                
                st.divider()
                st.subheader("Porcentaje de Cumplimiento")
                fig_rec = px.pie(df_reclamos, names='Estado', color='Estado', color_discrete_map=color_map, hole=0.5)
                fig_rec.update_traces(textinfo='percent+value')
                st.plotly_chart(fig_rec, use_container_width=True)
            else:
                st.warning("Sin datos de Reclamos.")

        # REQUERIMIENTOS
        with col_der:
            st.header("REQUERIMIENTOS")
            st.markdown("---")
            if not df_reqs.empty:
                total_req = len(df_reqs)
                vencidos_req = len(df_reqs[df_reqs['Estado'] == 'Vencido'])
                r1, r2 = st.columns(2)
                r1.metric("Total General", total_req)
                r2.metric("Vencidos", vencidos_req, delta="-Crítico", delta_color="inverse")
                
                st.subheader("Carga por Responsable")
                tabla_req = generar_tabla_comparativa(df_reqs, 'Asignado a:')
                st.dataframe(tabla_req.style.highlight_max(axis=0, color='#ffcccc', subset=['Vencido']), use_container_width=True)
                
                st.download_button("📥 Descargar Tabla Requerimientos", data=convertir_df_a_excel(tabla_req), file_name=f"Resumen_Requerimientos_{fecha_arch.replace('/','-')}.xlsx")
                
                st.divider()
                st.subheader("Porcentaje de Cumplimiento")
                fig_req = px.pie(df_reqs, names='Estado', color='Estado', color_discrete_map=color_map, hole=0.5)
                fig_req.update_traces(textinfo='percent+value')
                st.plotly_chart(fig_req, use_container_width=True)
            else:
                st.warning("Sin datos de Requerimientos.")

        # DATA RAW
        st.markdown("---")
        with st.expander("📂 Ver Base de Datos Completa"):
            t1, t2 = st.tabs(["RECLAMOS (Detalle)", "REQUERIMIENTOS (Detalle)"])
            with t1: st.dataframe(df_reclamos, use_container_width=True)
            with t2: st.dataframe(df_reqs, use_container_width=True)

    except Exception as e:
        st.error(f"Error al cargar: {e}")

else:
    st.error("⚠️ No se encontró el reporte 'Reporte_General_Sare.xlsx'. Presiona el botón para solicitar a tu PC que lo genere.")

# --- BOTÓN DE FETCH AL FINAL ---
st.markdown("---")
st.markdown("### ¿Necesitas datos más recientes?")
if st.button("🔄 ACTUALIZAR DATA AHORA (FINAL)", type="secondary", use_container_width=True):
    ejecutar_actualizacion()