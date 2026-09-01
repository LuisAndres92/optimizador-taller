import streamlit as st

# Configuración de la página para celulares con enfoque general e ilimitado
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
        if not encontrado:
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

# Formulario para agregar un material con ingresos ilimitados
with st.form("Agregar Material"):
    st.subheader("➕ Agregar nuevo material (Medidas Ilimitadas)")
    nombre = st.text_input("Nombre del material:", placeholder="Ej: Tubo Rectangular 1 1/2 x 3/4")
    largo_m = st.number_input("Longitud de la barra comercial (metros):", min_value=1.0, max_value=12.0, value=6.0, step=0.5)
    
    st.markdown("---")
    st.markdown("**📌 Ingresa las medidas y cantidades separadas por comas:**")
    
    medidas_input = st.text_area("Lista de Medidas (en cm):", placeholder="Ej: 46, 44, 88, 96, 100, 78")
    cantidades_input = st.text_area("Lista de Cantidades para cada medida:", placeholder="Ej: 300, 200, 200, 100, 100, 100")
    
    submit = st.form_submit_button("⚡ Calcular y Guardar Material")
    
    if submit and nombre:
        try:
            # Convertir los textos de entrada en listas de números limpias
            lista_medidas = [float(x.strip()) for x in medidas_input.split(",") if x.strip()]
            lista_cantidades = [int(x.strip()) for x in cantidades_input.split(",") if x.strip()]
            
            if len(lista_medidas) != len(lista_cantidades):
                st.error("⚠️ La cantidad de medidas no coincide con la cantidad de respuestas. Revisa las comas.")
            elif not lista_medidas:
                st.error("⚠️ Debes ingresar al menos una medida y su cantidad.")
            else:
                # Construir la lista expandida igual que hacías en Python puro
                cortes_expandidos = []
                for med, cant in zip(lista_medidas, lista_cantidades):
                    cortes_expandidos.extend([med] * cant)
                
                st.session_state.materiales.append({
                    "nombre": nombre,
                    "largo_cm": largo_m * 100,
                    "largo_m": largo_m,
                    "cortes": cortes_expandidos
                })
                st.success(f"¡{nombre} procesado con éxito!")
        except ValueError:
            st.error("⚠️ Formato incorrecto. Asegúrate de usar solo números separados por comas.")

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
