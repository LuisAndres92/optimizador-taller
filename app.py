import flet as ft
import json
import re
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.units import cm
from datetime import datetime
from pathlib import Path


ARCHIVO_PROYECTOS = Path.home() / ".optimizer_tool" / "proyectos.json"


def cargar_proyectos():
    proyectos_predeterminados = {"Proyecto Demo": []}
    if not ARCHIVO_PROYECTOS.exists():
        return proyectos_predeterminados

    try:
        datos = json.loads(ARCHIVO_PROYECTOS.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return proyectos_predeterminados

    if not isinstance(datos, dict):
        return proyectos_predeterminados

    proyectos = {
        nombre: materiales
        for nombre, materiales in datos.items()
        if isinstance(nombre, str) and nombre.strip()
        and isinstance(materiales, list)
    }
    return proyectos or proyectos_predeterminados


def guardar_proyectos(proyectos):
    ARCHIVO_PROYECTOS.parent.mkdir(parents=True, exist_ok=True)
    archivo_temporal = ARCHIVO_PROYECTOS.with_suffix(".tmp")
    archivo_temporal.write_text(
        json.dumps(proyectos, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    archivo_temporal.replace(ARCHIVO_PROYECTOS)


# --- ALGORITMO DE OPTIMIZACIÓN REALISTA (CON MARGEN DE FÁBRICA) ---


def optimizar_cortes(cortes, longitud_tubo_cm, espesor_disco_cm):
    longitud_real_cm = longitud_tubo_cm + 4.0
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
            tubos.append(([corte], longitud_real_cm -
                         corte - espesor_disco_cm))
    return tubos


def main(page: ft.Page):
    page.title = "Optimizer Tool"
    page.theme_mode = ft.ThemeMode.DARK
    page.scroll = ft.ScrollMode.AUTO
    page.window_width = 450
    page.window_height = 800
    page.padding = ft.Padding(top=60, left=24, right=24, bottom=30)

    proyectos = cargar_proyectos()
    guardar_proyectos(proyectos)

    # Catálogo limpio con las pulgadas exactas de tu taller
    base_materiales = [
        'Tubo 3/4" x 3/4"', 'Tubo 1½" x 3/4"', 'Tubo ½" x ½"',
        'Tubo 1" x 1"', 'Tubo 2" x 1"', 'Tubo 1½" x 1½"',
        'Tubo 3" x 1½"', "➕ Agregar material nuevo..."
    ]
    filas_cortes = []

    # --- CONTROLES VISUALES ---
    dropdown_proyectos = ft.Dropdown(label="📁 Buscar / Seleccionar Proyecto", options=[
                                     ft.dropdown.Option(p) for p in proyectos.keys()],
                                     hint_text="Selecciona un proyecto...", value=None, expand=True)
    input_nuevo_proyecto = ft.TextField(
        label="Nombre del nuevo proyecto", hint_text="Ej: Estructuras Metálicas", expand=True)

    # 🛠️ CORRECCIÓN 1: El Combo Box ahora arranca vacío y limpio para obligar a seleccionar
    dropdown_materiales = ft.Dropdown(
        label="📦 Seleccione el material",
        options=[ft.dropdown.Option(m) for m in base_materiales],
        hint_text="⚠️ Selecciona un material...",
        value=None,  # Forzamos a que no haya nada seleccionado por defecto
        expand=True
    )

    input_nuevo_material = ft.TextField(
        label="Escribe el nombre del nuevo material", hint_text="Ej: Varilla Redonda de 1/2\"", visible=False)
    input_largo_barra = ft.TextField(
        label="Longitud comercial (m)", value="6.0", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
    input_disco = ft.TextField(label="Espesor disco (cm)", value="0.3",
                               keyboard_type=ft.KeyboardType.NUMBER, expand=True)
    contenedor_filas_cortes = ft.Column()
    contenedor_resultados = ft.Column()

    # --- VARIABLES PARA GUARDAR PDF CON RUTA PERSONALIZADA ---
    datos_pdf = {"proyecto": None, "materiales": None, "disco_cm": 0.3}

    # --- FILE PICKER PARA ELEGIR CARPETA ---
    file_picker = ft.FilePicker()
    page.services.append(file_picker)

    def generar_pdf_archivo(archivo, proyecto, materiales, disco_cm):
        """Función que genera el PDF en la ruta especificada"""
        estilos = getSampleStyleSheet()
        titulo = ParagraphStyle(
            "TituloReporte", parent=estilos["Title"], alignment=TA_CENTER,
            fontSize=18, leading=22, spaceAfter=12
        )
        subtitulo = ParagraphStyle(
            "Subtitulo", parent=estilos["Normal"], alignment=TA_CENTER,
            fontSize=9, textColor=colors.grey, spaceAfter=15
        )
        h2 = ParagraphStyle(
            "H2", parent=estilos["Heading2"], fontSize=13,
            spaceBefore=10, spaceAfter=7
        )
        normal = ParagraphStyle(
            "NormalReporte", parent=estilos["Normal"], fontSize=9, leading=12
        )
        cortes_tabla = ParagraphStyle(
            "CortesTabla", parent=normal, fontSize=8, leading=10
        )

        doc = SimpleDocTemplate(
            str(archivo), pagesize=A4,
            rightMargin=1.3*cm, leftMargin=1.3*cm,
            topMargin=1.3*cm, bottomMargin=1.3*cm
        )

        elementos = []
        fecha = datetime.now()

        elementos.append(
            Paragraph("REPORTE DE OPTIMIZACIÓN DE CORTES", titulo))
        elementos.append(Paragraph(
            f"<b>Proyecto:</b> {proyecto}<br/>"
            f"<b>Fecha:</b> {fecha.strftime('%d/%m/%Y %H:%M')}<br/>"
            f"<b>Espesor del disco:</b> {disco_cm:.2f} cm",
            subtitulo
        ))

        total_tubos = 0
        total_cortes = 0
        total_material_cm = 0
        total_sobrante_cm = 0

        for indice, mat in enumerate(materiales, 1):
            unidades = optimizar_cortes(
                mat["cortes"][:], mat["largo_cm"], disco_cm)
            total_tubos += len(unidades)
            total_cortes += len(mat["cortes"])
            total_material_cm += len(unidades) * mat["largo_cm"]

            elementos.append(Paragraph(
                f"{indice}. {mat['nombre']} — Barra comercial: {mat['largo_m']} m",
                h2
            ))

            cantidades = {}
            for corte in mat["cortes"]:
                cantidades[corte] = cantidades.get(corte, 0) + 1

            tabla_cortes = [["Medida de corte", "Cantidad"]]
            for medida, cantidad in sorted(cantidades.items(), reverse=True):
                tabla_cortes.append([f"{medida:.1f} cm", str(cantidad)])

            t = Table(tabla_cortes, colWidths=[8*cm, 4*cm])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#34495e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ALIGN", (1, 1), (-1, -1), "CENTER"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
            ]))
            elementos.append(t)
            elementos.append(Spacer(1, 8))

            tabla_despiece = [["Barra", "Cortes realizados", "Sobrante libre"]]

            for i, (tubo, sobrante) in enumerate(unidades, 1):
                sobrante_real = sobrante + disco_cm
                total_sobrante_cm += sobrante_real
                grupos_cortes = [
                    tubo[indice:indice + 8]
                    for indice in range(0, len(tubo), 8)
                ]
                cortes_txt = "<br/>".join(
                    " + ".join(f"{c:.1f}" for c in grupo) + " cm"
                    for grupo in grupos_cortes
                )
                tabla_despiece.append([
                    f"Tubo {i}",
                    Paragraph(cortes_txt, cortes_tabla),
                    f"{sobrante_real:.1f} cm"
                ])

            t2 = Table(tabla_despiece, colWidths=[
                       2.5*cm, 11*cm, 3.2*cm], repeatRows=1)
            t2.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
            ]))
            elementos.append(Paragraph("Despiece optimizado", h2))
            elementos.append(t2)
            elementos.append(Spacer(1, 12))

        elementos.append(PageBreak())
        elementos.append(Paragraph("RESUMEN GENERAL", titulo))

        resumen = [
            ["Concepto", "Resultado"],
            ["Materiales registrados", str(len(materiales))],
            ["Total de piezas a cortar", str(total_cortes)],
            ["Total de barras a comprar", str(total_tubos)],
            ["Material comprado", f"{total_material_cm / 100:.2f} m"],
            ["Sobrante libre estimado", f"{total_sobrante_cm / 100:.2f} m"],
        ]

        tr = Table(resumen, colWidths=[10*cm, 6*cm])
        tr.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#34495e")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
        ]))
        elementos.append(tr)
        elementos.append(Spacer(1, 20))
        elementos.append(Paragraph(
            "Este reporte corresponde a la optimización calculada por Optimizer Tool. "
            "Las longitudes están expresadas en centímetros y metros según corresponda.",
            normal
        ))

        doc.build(elementos)

    def guardar_pdf_en_carpeta(carpeta, proyecto, materiales, disco_cm):
        nombre_seguro = re.sub(
            r'[^A-Za-z0-9_-]+', '_', proyecto).strip("_") or "Proyecto"
        archivo = Path(carpeta) / (
            f"Reporte_Cortes_{nombre_seguro}_"
            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        )
        generar_pdf_archivo(archivo, proyecto, materiales, disco_cm)
        return archivo

    def cambiar_material(e):
        input_nuevo_material.visible = (
            dropdown_materiales.value == "➕ Agregar material nuevo...")
        page.update()
    dropdown_materiales.on_change = cambiar_material

    def crear_fila_corte(num):
        return ft.Row([
            ft.TextField(label=f"Tamaño de Corte {num} en (cm)", hint_text="0.0",
                         keyboard_type=ft.KeyboardType.NUMBER, expand=True),
            ft.TextField(label=f"Cantidad", hint_text="0",
                         keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        ])

    def agregar_fila_medida(e):
        nueva_fila = crear_fila_corte(len(filas_cortes) + 1)
        filas_cortes.append(nueva_fila)
        contenedor_filas_cortes.controls.append(nueva_fila)
        page.update()

    def inicializar_proyecto(e):
        nombre = input_nuevo_proyecto.value.strip()
        if nombre and nombre not in proyectos:
            proyectos[nombre] = []
            guardar_proyectos(proyectos)
            dropdown_proyectos.options.append(ft.dropdown.Option(nombre))
            dropdown_proyectos.value = nombre
            input_nuevo_proyecto.value = ""
            actualizar_vista_proyecto()
            snack = ft.SnackBar(ft.Text(f"Proyecto '{nombre}' creado"))
            page.overlay.append(snack)
            snack.open = True
            page.update()

    def borrar_proyecto_actual(e):
        nombre_actual = dropdown_proyectos.value
        if not nombre_actual:
            snack = ft.SnackBar(ft.Text(
                "⚠️ Primero selecciona un proyecto para borrarlo."))
            page.overlay.append(snack)
            snack.open = True
            page.update()
            return
        if len(proyectos) > 1:
            del proyectos[nombre_actual]
            guardar_proyectos(proyectos)
            lista_restante = list(proyectos.keys())
            dropdown_proyectos.options = [
                ft.dropdown.Option(p) for p in lista_restante]
            dropdown_proyectos.value = lista_restante[0]
        else:
            proyectos[nombre_actual] = []
            guardar_proyectos(proyectos)
        actualizar_vista_proyecto()
        page.update()

    def guardar_y_calcular_material(e):
        proyecto_actual = dropdown_proyectos.value
        if not proyecto_actual or proyecto_actual not in proyectos:
            snack = ft.SnackBar(ft.Text(
                "❌ Primero selecciona o crea un proyecto."),
                bgcolor=ft.Colors.RED_ACCENT)
            page.overlay.append(snack)
            snack.open = True
            page.update()
            return

        # 🛠️ MEJORA DE RESTRICCIÓN: Si el usuario no ha elegido nada en el combo, se activa el freno de mano
        if dropdown_materiales.value is None:
            snack = ft.SnackBar(ft.Text(
                "❌ ERROR: Debes seleccionar un tipo de material antes de calcular."), bgcolor=ft.Colors.RED_ACCENT)
            page.overlay.append(snack)
            snack.open = True
            page.update()
            return  # Detiene la ejecución por completo

        if dropdown_materiales.value == "➕ Agregar material nuevo...":
            nombre_mat = input_nuevo_material.value.strip()
            if nombre_mat and nombre_mat not in base_materiales:
                base_materiales.insert(-1, nombre_mat)
                dropdown_materiales.options = [
                    ft.dropdown.Option(m) for m in base_materiales]
                dropdown_materiales.value = nombre_mat
                input_nuevo_material.visible = False
        else:
            nombre_mat = dropdown_materiales.value

        if not nombre_mat:
            return

        cortes_expandidos = []
        for fila in filas_cortes:
            try:
                med_val = fila.controls[0].value
                cant_val = fila.controls[1].value

                med = float(med_val) if med_val else 0.0
                cant = int(cant_val) if cant_val else 0

                if med > 0 and cant > 0:
                    cortes_expandidos.extend([med] * cant)
            except (ValueError, IndexError):
                continue

        if cortes_expandidos:
            largo_cm = float(input_largo_barra.value) * 100
            proyectos[proyecto_actual].append({
                "nombre": nombre_mat, "largo_cm": largo_cm, "largo_m": input_largo_barra.value, "cortes": cortes_expandidos
            })
            guardar_proyectos(proyectos)

            filas_cortes.clear()
            contenedor_filas_cortes.controls.clear()
            primera_fila = crear_fila_corte(1)
            filas_cortes.append(primera_fila)
            contenedor_filas_cortes.controls.append(primera_fila)

            # Reseteamos el combo box a vacío para el siguiente material
            dropdown_materiales.value = None

            actualizar_vista_proyecto()
            snack = ft.SnackBar(
                ft.Text(f"✅ {nombre_mat} calculado y guardado."))
            page.overlay.append(snack)
            snack.open = True
        page.update()

    def actualizar_vista_proyecto(nombre_proyecto=None):
        contenedor_resultados.controls.clear()
        nombre_proyecto = nombre_proyecto or dropdown_proyectos.value
        materiales = proyectos.get(nombre_proyecto, [])
        try:
            disco_cm = float(input_disco.value)
        except (ValueError, TypeError):
            disco_cm = 0.3
        if materiales:
            contenedor_resultados.controls.append(ft.Text(
                f"📊 Despiece de: {nombre_proyecto}", size=18, weight=ft.FontWeight.BOLD))
            for mat in materiales:
                unidades = optimizar_cortes(
                    mat['cortes'], mat['largo_cm'], disco_cm)
                contenido_pestana = ft.Column()
                cantidades = {}
                for corte in mat['cortes']:
                    cantidades[corte] = cantidades.get(corte, 0) + 1
                medidas_txt = ", ".join(
                    f"{medida:.1f} cm x {cantidad}"
                    for medida, cantidad in sorted(cantidades.items(), reverse=True)
                )
                contenido_pestana.controls.append(ft.Text(
                    f"Medidas ingresadas: {medidas_txt}", size=13))
                contenido_pestana.controls.append(ft.Text(
                    f"Total a comprar: {len(unidades)} unidades", color=ft.Colors.GREEN_ACCENT, size=16, weight=ft.FontWeight.BOLD))
                for i, (tubo, sobrante) in enumerate(unidades, 1):
                    sobrante_real = sobrante + disco_cm
                    contenido_pestana.controls.append(
                        ft.Text(f"Tubo {i}: {tubo} | Sobrante libre: {sobrante_real:.1f} cm"))
                contenedor_resultados.controls.append(ft.ExpansionTile(title=ft.Text(
                    f"📦 {mat['nombre']} ({mat['largo_m']}m) ➡️ Requieres: {len(unidades)} un."), controls=[ft.Container(content=contenido_pestana, padding=10)]))
        elif nombre_proyecto:
            contenedor_resultados.controls.append(ft.Text(
                f"📭 El proyecto {nombre_proyecto} no tiene materiales guardados.",
                color=ft.Colors.AMBER_ACCENT))
        page.update()

    def cambiar_proyecto(e):
        nombre_proyecto = dropdown_proyectos.value
        dropdown_materiales.value = None
        input_nuevo_material.value = ""
        input_nuevo_material.visible = False
        actualizar_vista_proyecto(nombre_proyecto)

    dropdown_proyectos.on_change = cambiar_proyecto
    primera_fila = crear_fila_corte(1)
    filas_cortes.append(primera_fila)
    contenedor_filas_cortes.controls.append(primera_fila)

    async def generar_reporte_pdf(e):
        proyecto = dropdown_proyectos.value
        materiales = proyectos.get(proyecto, [])

        if not materiales:
            snack = ft.SnackBar(
                ft.Text(
                    "⚠️ No hay materiales guardados en este proyecto para generar el reporte.")
            )
            page.overlay.append(snack)
            snack.open = True
            page.update()
            return

        try:
            disco_cm = float(input_disco.value)
        except (ValueError, TypeError):
            disco_cm = 0.3

        # Guardar datos en variables globales
        datos_pdf["proyecto"] = proyecto
        datos_pdf["materiales"] = materiales
        datos_pdf["disco_cm"] = disco_cm

        try:
            carpeta = await file_picker.get_directory_path(
                dialog_title="Selecciona la carpeta donde guardar el PDF"
            )
            if not carpeta:
                return

            archivo = guardar_pdf_en_carpeta(
                carpeta, proyecto, materiales, disco_cm)
            snack = ft.SnackBar(ft.Text(f"✅ PDF guardado: {archivo.name}"))
        except Exception as ex:
            snack = ft.SnackBar(ft.Text(f"❌ Error al guardar el PDF: {ex}"))

        page.overlay.append(snack)
        snack.open = True
        page.update()

    page.bottom_appbar = ft.BottomAppBar(
        height=38,
        content=ft.Row(
            alignment=ft.MainAxisAlignment.CENTER,
            controls=[
                ft.Text("Optimizer Tool v2.0 | Desarrollado por ",
                        size=10, color=ft.Colors.WHITE30),
                ft.Text("Luis Andrés Cataño", size=10,
                        weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_ACCENT)
            ]
        )
    )

    # --- DISEÑO GENERAL EN PANTALLA ---
    page.add(
        ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Row([dropdown_proyectos, ft.TextButton(
                        "Borrar", on_click=borrar_proyecto_actual, style=ft.ButtonStyle(color=ft.Colors.RED_ACCENT))]),
                    ft.Row([input_nuevo_proyecto, ft.ElevatedButton(
                        "Nuevo Proy.", on_click=inicializar_proyecto)])
                ]), padding=10
            )
        ),
        ft.Divider(),
        dropdown_materiales, input_nuevo_material,
        ft.Row([input_largo_barra, input_disco]),
        ft.Text("📏 Medidas de corte requeridas:", weight=ft.FontWeight.BOLD),
        contenedor_filas_cortes,
        ft.ElevatedButton("➕ Añadir otra medida a este material",
                          on_click=agregar_fila_medida),
        ft.Container(height=10),
        ft.FilledButton("📥 Guardar y Calcular Material",
                        on_click=guardar_y_calcular_material, expand=True),
        ft.OutlinedButton("📄 Generar reporte completo en PDF",
                          on_click=generar_reporte_pdf, expand=True),
        ft.Divider(),
        contenedor_resultados,
        ft.Container(height=20)
    )
    actualizar_vista_proyecto()


ft.app(target=main)
