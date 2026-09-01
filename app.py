import streamlit as st

# Configuración de la página para celulares con enfoque general
st.set_page_config(page_title="Optimero Taller", page_icon="🛠️", layout="centered")

def optimizar_cortes(cortes, longitud_tubo_cm, espesor_disco_cm):
    cortes.sort(reverse=True)
    tubos = []
    for corte in cortes:
        encontrado = False
        for i, (tubo, espacio) in enumerate(tubos):
            if espacio >= (corte + espesor_disco_cm):
                tubo.append(corte)
                tubos[i] = (tubo, espacio - corte - espesor_disco_cm)
                encontrado = True
                break
        if not encontrar:
            tubos.append(([corte], longitud_tubo_cm - corte - espesor_disco_cm))
    return tubos

# --- INTERFAZ GENERAL DE LA APLICACIÓN ---
st.title("🛠️ Optimizador de Cortes Profesional")
st.write("Calcula el despiece real para cualquier tipo de material lineal en tu taller, incluyendo la merma del disco.")

# Grosor del disco en la parte superior
espesor_disco_cm = st.number_input("Espesor del disco de corte (cm):", min_value=0.0, max_value=1.0, value=0.3, step=0.1)

# Inicializar la lista de materiales en la sesión de la app
if 'materiales' not in st.session_state:
    st.session_state.materiales = []

# Formulario para agregar un material
with st.form("Agregar Material"):
    st.subheader("➕ Agregar nuevo material o tubo")
    nombre = st.text_input("Nombre del material:", placeholder="Ej: Tubo Rectangular 1 1/2 x 3/4")
    largo_m = st.number_input("Longitud de la barra comercial (metros):", min_value=1.0, max_value=12.0, value=6.0, step=0.5)
    
    st.markdown("**Ingresa los cortes requeridos:**")
    # Campos para ingresar las medidas del material de forma limpia
    col1, col2 = st.columns(2)
    with col1:
        c1 = st.number_input("Medida Corte 1 (cm):", min_value=0.0, value=0.0)
        c2 = st.number_input("Medida Corte 2 (cm):", min_value=0.0, value=0.0)
    with col2:
        cant1 = st.number_input("Cantidad Corte 1:", min_value=0, value=0)
        cant2 = st.number_input("Cantidad Corte 2:", min_value=0, value=0)
        
    submit = st.form_submit_button("Guardar Material")
    
    if submit and nombre:
        lista_cortes = []
        if c1 > 0 and cant1 > 0: lista_cortes.extend([c1] * cant1)
        if c2 > 0 and cant2 > 0: lista_cortes.extend([c2] * cant2)
        
        if lista_cortes:
            st.session_state.materiales.append({
                "nombre": nombre,
                "largo_cm": largo_m * 100,
                "largo_m": largo_m,
                "cortes": lista_cortes
            })
            st.success(f"¡{nombre} agregado con éxito!")
        else:
            st.error("Debes ingresar al menos una medida y cantidad válida.")

# Mostrar resultados y calcular de manera estandarizada
if st.session_state.materiales:
    st.markdown("---")
    st.header("📊 Lista de Materiales y Despiece")
    
    if st.button("🗑️ Borrar todo y empezar de nuevo"):
        st.session_state.materiales = []
        st.rerun()
        
    for idx, mat in enumerate(st.session_state.materiales):
        with st.expander(f"📦 {mat['nombre']} (Barras de {mat['largo_m']}m)", expanded=True):
            tubos_calculados = optimizar_cortes(mat['cortes'], mat['largo_cm'], espesor_disco_cm)
            
            # Alerta principal con el total de barras en grande
            st.metric(label="Total de barras a comprar", value=f"{len(tubos_calculados)} unidades")
            
            # Tabla de despiece detallada
            for i, (tubo, sobrante) in enumerate(tubos_calculados, 1):
                sobrante_real = sobrante + espesor_disco_cm
                st.write(f"**Barra {i}:** {tubo} | *Sobrante libre:* {sobrante_real:.1f} cm")
