import flet as ft
import asyncio
import json
import os
import re
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.units import cm
from datetime import datetime
from pathlib import Path


RUTA_DATOS = Path(os.environ.get("FLET_APP_STORAGE_DATA") or Path.home())
ARCHIVO_PROYECTOS = RUTA_DATOS / ".optimizer_tool" / "proyectos.json"


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


def nombre_material_general(nombre):
    nombre_original = nombre.strip()
    nombre_general = re.split(
        r"(?=\d|[½¼¾⅓⅔⅛])", nombre_original, maxsplit=1
    )[0].rstrip(' -xX/"\'').strip()
    return nombre_general or nombre_original


def etiqueta_total_material(nombre):
    etiquetas = {
        "tubo": "Total de tubos",
        "varilla": "Total de varillas",
        "perfil": "Total de perfiles",
    }
    return etiquetas.get(nombre.lower(), f"Total de {nombre.lower()}")


# --- ALGORITMO DE OPTIMIZACIÓN REALISTA (CON MARGEN DE FÁBRICA) ---


def optimizar_cortes(cortes, longitud_tubo_cm, espesor_disco_cm):
    longitud_real_cm = longitud_tubo_cm + 3.0
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


def configurar_footer(page):
    footer = ft.Container(
        height=56,
        alignment=ft.Alignment(0, 0),
        content=ft.Row(
            alignment=ft.MainAxisAlignment.CENTER,
            controls=[
                ft.Text("Optimizer Tool v2.0 | Desarrollado por ",
                        size=10, color=ft.Colors.WHITE70),
                ft.Text("Luis Andrés Cataño", size=10,
                        weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_ACCENT)
            ]
        )
    )
    page.bottom_appbar = ft.BottomAppBar(
        height=100,
        bgcolor=ft.Colors.GREY_900,
        content=footer,
    )


def mostrar_cargando(page):
    indicador = ft.Container(
        expand=True,
        bgcolor=ft.Colors.with_opacity(0.82, ft.Colors.BLACK),
        alignment=ft.Alignment(0, 0),
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=16,
            controls=[
                ft.ProgressRing(width=44, height=44),
                ft.Text("Optimizando...", size=18, weight=ft.FontWeight.BOLD),
            ],
        ),
    )
    page.overlay.append(indicador)
    page.update()
    return indicador


def ocultar_cargando(page, indicador):
    if indicador in page.overlay:
        page.overlay.remove(indicador)
        page.update()


def modulo_barras(page: ft.Page, volver_menu=None):
    page.controls.clear()
    page.overlay.clear()
    page.services.clear()
    page.title = "Optimizer Tool"
    page.theme_mode = ft.ThemeMode.DARK
    page.scroll = ft.ScrollMode.AUTO
    page.window_width = 450
    page.window_height = 800
    page.padding = ft.Padding(top=16, left=24, right=24, bottom=0)

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
    dropdown_proyectos.visible = False
    input_nuevo_proyecto = ft.TextField(
        label="Nombre del nuevo proyecto", hint_text="Ej: Estructuras Metálicas",
        expand=True, visible=False)

    # 🛠️ CORRECCIÓN 1: El Combo Box ahora arranca vacío y limpio para obligar a seleccionar
    dropdown_materiales = ft.Dropdown(
        label="📦 Seleccione el material",
        options=[ft.dropdown.Option(m) for m in base_materiales],
        hint_text="⚠️ Selecciona un material...",
        value=None,  # Forzamos a que no haya nada seleccionado por defecto
    )

    input_nuevo_material = ft.TextField(
        label="Escribe el nombre del nuevo material", hint_text="Ej: Varilla Redonda de 1/2\"", visible=False)
    codigo_alt_material = []
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

        total_cortes = 0
        total_sobrante_cm = 0
        cantidades_por_categoria = {}
        cortes_por_categoria = {}

        resumen_materiales = {}
        for mat in materiales:
            nombre_material = mat["nombre"]
            unidades = optimizar_cortes(
                mat["cortes"][:], mat["largo_cm"], disco_cm)
            resumen = resumen_materiales.setdefault(nombre_material, {
                "despieces": 0,
                "piezas": 0,
                "barras": 0,
            })
            resumen["despieces"] += 1
            resumen["piezas"] += len(mat["cortes"])
            resumen["barras"] += len(unidades)

        elementos.append(Paragraph("MATERIALES UTILIZADOS", h2))
        tabla_materiales = [[
            "Material", "Despieces", "Piezas", "Cantidad"
        ]]
        for nombre_material, resumen in resumen_materiales.items():
            tabla_materiales.append([
                nombre_material,
                str(resumen["despieces"]),
                str(resumen["piezas"]),
                str(resumen["barras"]),
            ])

        t_materiales = Table(
            tabla_materiales, colWidths=[8*cm, 2.5*cm, 2.5*cm, 3*cm])
        t_materiales.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#34495e")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ALIGN", (1, 1), (-1, -1), "CENTER"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
        ]))
        elementos.append(t_materiales)
        elementos.append(Spacer(1, 15))

        for indice, mat in enumerate(materiales, 1):
            if indice > 1:
                elementos.append(PageBreak())
            unidades = optimizar_cortes(
                mat["cortes"][:], mat["largo_cm"], disco_cm)
            total_cortes += len(mat["cortes"])
            material_general = nombre_material_general(mat["nombre"])
            cantidades_por_categoria[material_general] = (
                cantidades_por_categoria.get(
                    material_general, 0) + len(unidades)
            )
            cortes_por_categoria[material_general] = (
                cortes_por_categoria.get(material_general, 0)
                + len(mat["cortes"])
            )
            medidas_unicas = sorted(set(mat["cortes"]), reverse=True)
            if len(medidas_unicas) == 1:
                titulo_material = (
                    f"{indice}. {mat['nombre']} — Medida de corte: "
                    f"{medidas_unicas[0]:.1f} cm"
                )
            else:
                titulo_material = f"{indice}. {mat['nombre']}"

            elementos.append(Paragraph(titulo_material, h2))

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

            tabla_despiece = [
                ["Material", "Cortes realizados", "Sobrante libre"]]

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
            ["Materiales diferentes", str(
                len({mat["nombre"] for mat in materiales}))],
            ["Total de piezas a cortar", str(total_cortes)],
        ]
        for material_general, cantidad in cantidades_por_categoria.items():
            resumen.append([
                etiqueta_total_material(material_general),
                str(cantidad),
            ])
        if len(cortes_por_categoria) > 1:
            for material_general, cantidad in cortes_por_categoria.items():
                resumen.append([
                    f"Total de cortes de {material_general.lower()}",
                    str(cantidad),
                ])
        resumen.append([
            "Sobrante libre estimado", f"{total_sobrante_cm / 100:.2f} m"
        ])

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

        def dibujar_pie(canvas, documento):
            canvas.saveState()
            canvas.setFont("Helvetica", 8)
            canvas.setFillColor(colors.grey)
            canvas.drawCentredString(
                A4[0] / 2,
                0.8 * cm,
                "Optimizer Tool | © 2026 v.2.0",
            )
            canvas.restoreState()

        doc.build(elementos, onFirstPage=dibujar_pie,
                  onLaterPages=dibujar_pie)

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
        valor_seleccionado = e.data or e.control.value
        dropdown_materiales.value = valor_seleccionado
        es_material_nuevo = (
            valor_seleccionado == "➕ Agregar material nuevo...")
        if es_material_nuevo:
            input_nuevo_material.value = ""
        input_nuevo_material.visible = es_material_nuevo
        page.update()
    dropdown_materiales.on_select = cambiar_material
    dropdown_materiales.on_change = cambiar_material

    def insertar_codigo_alt(e):
        if not input_nuevo_material.visible:
            return

        if e.alt:
            digito = re.search(r"(\d)$", e.key or "")
            if digito:
                codigo_alt_material.append(digito.group(1))
            return

        if (codigo_alt_material
                and (e.key or "").lower() in {"alt", "altleft", "altright"}):
            codigo = int("".join(codigo_alt_material))
            caracteres_alt = {171: "½", 189: "½"}
            caracter = caracteres_alt.get(codigo)
            if caracter:
                input_nuevo_material.value = (
                    input_nuevo_material.value or "") + caracter
                page.update()
            codigo_alt_material.clear()

    page.on_keyboard_event = insertar_codigo_alt

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

    async def guardar_y_calcular_material(e):
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

        indicador = mostrar_cargando(page)
        await asyncio.sleep(0.05)

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
        ocultar_cargando(page, indicador)

    def eliminar_despiece(nombre_proyecto, indice):
        materiales = proyectos.get(nombre_proyecto)
        if materiales is None or indice >= len(materiales):
            return
        del materiales[indice]
        guardar_proyectos(proyectos)
        actualizar_vista_proyecto(nombre_proyecto)

    def eliminar_material_catalogo(e):
        nombre_material = dropdown_materiales.value
        if (not nombre_material
                or nombre_material == "➕ Agregar material nuevo..."):
            snack = ft.SnackBar(ft.Text(
                "⚠️ Selecciona un material existente para eliminarlo."))
            page.overlay.append(snack)
            snack.open = True
            page.update()
            return

        def cancelar_eliminacion(e):
            dialogo.open = False
            page.update()

        def confirmar_eliminacion(e):
            dialogo.open = False
            if nombre_material in base_materiales:
                base_materiales.remove(nombre_material)
                dropdown_materiales.options = [
                    ft.dropdown.Option(material)
                    for material in base_materiales]
                dropdown_materiales.value = None
                input_nuevo_material.value = ""
                input_nuevo_material.visible = False
            page.update()

        dialogo = ft.AlertDialog(
            modal=True,
            title=ft.Text("Confirmar eliminación"),
            content=ft.Text(
                f"¿Seguro que deseas eliminar el material «{nombre_material}»?"),
            actions=[
                ft.TextButton("Cancelar", on_click=cancelar_eliminacion),
                ft.FilledButton("Eliminar", on_click=confirmar_eliminacion),
            ],
        )
        page.overlay.append(dialogo)
        dialogo.open = True
        page.update()

    def actualizar_vista_proyecto(nombre_proyecto=None):
        contenedor_resultados.controls.clear()
        if nombre_proyecto is None:
            nombre_proyecto = dropdown_proyectos.value
        materiales = proyectos.get(nombre_proyecto, [])
        page.scroll = ft.ScrollMode.AUTO
        try:
            disco_cm = float(input_disco.value)
        except (ValueError, TypeError):
            disco_cm = 0.3
        if materiales:
            contenedor_resultados.controls.append(ft.Text(
                f"📊 Despiece de: {nombre_proyecto}", size=18, weight=ft.FontWeight.BOLD))
            resumen_materiales = {}
            for mat in materiales:
                nombre_material = mat["nombre"]
                unidades = optimizar_cortes(
                    mat["cortes"][:], mat["largo_cm"], disco_cm)
                resumen = resumen_materiales.setdefault(nombre_material, {
                    "despieces": 0,
                    "piezas": 0,
                    "barras": 0,
                })
                resumen["despieces"] += 1
                resumen["piezas"] += len(mat["cortes"])
                resumen["barras"] += len(unidades)

            filas_resumen = []
            for nombre_material, resumen in resumen_materiales.items():
                filas_resumen.append(ft.DataRow(cells=[
                    ft.DataCell(ft.Text(nombre_material)),
                    ft.DataCell(ft.Text(str(resumen["despieces"]))),
                    ft.DataCell(ft.Text(str(resumen["piezas"]))),
                    ft.DataCell(ft.Text(str(resumen["barras"]))),
                ]))
            contenedor_resultados.controls.extend([
                ft.Text("Materiales utilizados", size=16,
                        weight=ft.FontWeight.BOLD),
                ft.DataTable(
                    columns=[
                        ft.DataColumn(label=ft.Text("Material")),
                        ft.DataColumn(label=ft.Text("Despieces")),
                        ft.DataColumn(label=ft.Text("Piezas")),
                        ft.DataColumn(label=ft.Text("Cantidad")),
                    ],
                    rows=filas_resumen,
                    heading_row_color=ft.Colors.BLUE_GREY_900,
                    column_spacing=18,
                ),
            ])
            for indice, mat in enumerate(materiales):
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
                titulo_despiece = (
                    f"📦 {mat['nombre']} | Medidas: {medidas_txt} "
                    f"➡️ Requieres: {len(unidades)} un."
                )
                titulo_con_eliminar = ft.Row([
                    ft.Text(titulo_despiece, expand=True),
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE,
                        tooltip="Eliminar este despiece",
                        icon_color=ft.Colors.RED_ACCENT,
                        on_click=lambda e, i=indice: eliminar_despiece(
                            nombre_proyecto, i),
                    ),
                ])
                contenedor_resultados.controls.append(ft.ExpansionTile(
                    title=titulo_con_eliminar, expanded=False,
                    controls=[ft.Container(content=contenido_pestana, padding=10)]))
        elif nombre_proyecto:
            contenedor_resultados.controls.append(ft.Text(
                f"📭 El proyecto {nombre_proyecto} no tiene materiales guardados.",
                color=ft.Colors.AMBER_ACCENT))
        page.update()

    def mostrar_proyecto(nombre_proyecto):
        if nombre_proyecto not in proyectos:
            return
        dropdown_proyectos.value = nombre_proyecto
        activar_formulario(True)
        dropdown_materiales.value = None
        input_nuevo_material.value = ""
        input_nuevo_material.visible = False
        filas_cortes.clear()
        contenedor_filas_cortes.controls.clear()
        primera_fila = crear_fila_corte(1)
        filas_cortes.append(primera_fila)
        contenedor_filas_cortes.controls.append(primera_fila)
        actualizar_vista_proyecto(nombre_proyecto)

    def cambiar_proyecto(e):
        mostrar_proyecto(e.control.value or e.data)

    def cargar_proyecto_seleccionado(e):
        nombre_proyecto = dropdown_proyectos.value
        if nombre_proyecto not in proyectos:
            snack = ft.SnackBar(ft.Text(
                "⚠️ Selecciona un proyecto para cargarlo."))
            page.overlay.append(snack)
            snack.open = True
            page.update()
            return
        mostrar_proyecto(nombre_proyecto)
        dropdown_proyectos.visible = False
        page.update()

    def preparar_nuevo_proyecto(e):
        dropdown_proyectos.value = None
        dropdown_proyectos.visible = False
        input_nuevo_proyecto.value = ""
        input_nuevo_proyecto.visible = True
        activar_formulario(True)
        dropdown_materiales.value = None
        input_nuevo_material.value = ""
        input_nuevo_material.visible = False
        input_largo_barra.value = "6.0"
        input_disco.value = "0.3"
        filas_cortes.clear()
        contenedor_filas_cortes.controls.clear()
        primera_fila = crear_fila_corte(1)
        filas_cortes.append(primera_fila)
        contenedor_filas_cortes.controls.append(primera_fila)
        contenedor_resultados.controls.clear()
        page.update()

    def preparar_carga_proyecto(e):
        input_nuevo_proyecto.visible = False
        dropdown_proyectos.visible = True
        dropdown_proyectos.value = None
        page.update()

    def activar_formulario(activar):
        for control in (
            dropdown_materiales, boton_eliminar_material,
            input_nuevo_material, input_largo_barra,
            input_disco, boton_agregar_medida, boton_guardar_material,
            boton_generar_pdf,
        ):
            control.disabled = not activar

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

    boton_agregar_medida = ft.ElevatedButton(
        "➕ Añadir otra medida a este material", on_click=agregar_fila_medida)
    boton_guardar_material = ft.FilledButton(
        "📥 Guardar y Calcular Material",
        on_click=guardar_y_calcular_material)
    boton_eliminar_material = ft.IconButton(
        icon=ft.Icons.DELETE_OUTLINE,
        tooltip="Eliminar material del catálogo",
        icon_color=ft.Colors.RED_ACCENT,
        on_click=eliminar_material_catalogo)
    boton_generar_pdf = ft.OutlinedButton(
        "📄 Generar reporte completo en PDF",
        on_click=generar_reporte_pdf)

    configurar_footer(page)

    # --- DISEÑO GENERAL EN PANTALLA ---
    activar_formulario(False)
    boton_volver_menu = ft.TextButton(
        "← Volver al menú principal",
        icon=ft.Icons.ARROW_BACK,
        on_click=lambda e: volver_menu(page) if volver_menu else None,
    )

    contenido_principal = ft.Column(
        controls=[
            boton_volver_menu,
            ft.Card(
                content=ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Image(src="icon.png", width=42, height=42),
                            ft.Text("Optimizer Tool", size=26,
                                    weight=ft.FontWeight.BOLD),
                        ], alignment=ft.MainAxisAlignment.CENTER),
                        ft.Row([
                            ft.ElevatedButton("Nuevo",
                                              on_click=preparar_nuevo_proyecto,
                                              expand=True),
                            ft.ElevatedButton("Cargar",
                                              on_click=preparar_carga_proyecto,
                                              expand=True),
                            ft.TextButton("Borrar", on_click=borrar_proyecto_actual,
                                          style=ft.ButtonStyle(
                                              color=ft.Colors.RED_ACCENT)),
                        ]),
                        ft.Row([
                            input_nuevo_proyecto,
                        ], expand=True),
                        ft.Row([
                            dropdown_proyectos,
                        ], expand=True),
                        ft.Row([
                            ft.ElevatedButton(
                                "Crear", on_click=inicializar_proyecto, expand=True),
                            ft.ElevatedButton("Cargar proyecto",
                                              on_click=cargar_proyecto_seleccionado,
                                              expand=True),
                        ]),
                    ]), padding=10
                )
            ),
            ft.Divider(),
            ft.Row([dropdown_materiales, boton_eliminar_material]),
            input_nuevo_material,
            ft.Row([input_largo_barra, input_disco]),
            ft.Text("📏 Medidas de corte requeridas:",
                    weight=ft.FontWeight.BOLD),
            contenedor_filas_cortes,
            boton_agregar_medida,
            ft.Container(height=10),
            boton_guardar_material,
            boton_generar_pdf,
            ft.Divider(),
            contenedor_resultados,
            ft.Container(height=56),
        ],
        expand=True,
    )
    page.add(contenido_principal)
    actualizar_vista_proyecto()


# ================================================================
# MÓDULO 2D: OPTIMIZACIÓN DE LÁMINAS
# ================================================================
ARCHIVO_PROYECTOS_LAMINAS = RUTA_DATOS / \
    ".optimizer_tool" / "proyectos_laminas.json"


def cargar_proyectos_laminas():
    if not ARCHIVO_PROYECTOS_LAMINAS.exists():
        return {}
    try:
        datos = json.loads(
            ARCHIVO_PROYECTOS_LAMINAS.read_text(encoding="utf-8"))
        return datos if isinstance(datos, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def guardar_proyectos_laminas(proyectos):
    ARCHIVO_PROYECTOS_LAMINAS.parent.mkdir(parents=True, exist_ok=True)
    tmp = ARCHIVO_PROYECTOS_LAMINAS.with_suffix(".tmp")
    tmp.write_text(json.dumps(proyectos, ensure_ascii=False,
                   indent=2), encoding="utf-8")
    tmp.replace(ARCHIVO_PROYECTOS_LAMINAS)


def _rect_intersect(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by


def _split_free_rect(free, used):
    fx, fy, fw, fh = free
    ux, uy, uw, uh = used
    if not _rect_intersect(free, used):
        return [free]
    result = []
    if uy > fy:
        result.append((fx, fy, fw, uy - fy))
    if uy + uh < fy + fh:
        result.append((fx, uy + uh, fw, fy + fh - (uy + uh)))
    if ux > fx:
        result.append((fx, fy, ux - fx, fh))
    if ux + uw < fx + fw:
        result.append((ux + uw, fy, fx + fw - (ux + uw), fh))
    return [r for r in result if r[2] > 0 and r[3] > 0]


def _prune_free_rects(rects):
    clean = []
    for i, a in enumerate(rects):
        ax, ay, aw, ah = a
        contained = False
        for j, b in enumerate(rects):
            if i == j:
                continue
            bx, by, bw, bh = b
            if (ax >= bx and ay >= by and ax + aw <= bx + bw and
                    ay + ah <= by + bh):
                contained = True
                break
        if not contained:
            clean.append(a)
    # Evita duplicados
    return list(dict.fromkeys(clean))


def _puede_colocar(placements, x, y, w, h, ancho, alto):
    if x < 0 or y < 0 or x + w > ancho or y + h > alto:
        return False
    nuevo = (x, y, w, h)
    return not any(_rect_intersect(nuevo, (px, py, pw, ph))
                   for _, px, py, pw, ph in placements)


def colocar_patron(piezas, ancho, alto):
    """Busca una distribución válida de un patrón pequeño de rectángulos."""
    piezas = sorted(piezas, key=lambda p: p[1] * p[2], reverse=True)
    placements = []

    def rec(indice):
        if indice >= len(piezas):
            return [dict(x=x, y=y, w=w, h=h, nombre=nombre)
                    for nombre, x, y, w, h in placements]

        nombre, w, h = piezas[indice]
        candidatos = {(0, 0)}
        for _, x, y, pw, ph in placements:
            candidatos.add((x + pw, y))
            candidatos.add((x, y + ph))

        opciones = [(w, h, False)]
        if w != h:
            opciones.append((h, w, True))

        for rw, rh, _rotada in opciones:
            for x, y in sorted(candidatos, key=lambda p: (p[1], p[0])):
                if _puede_colocar(placements, x, y, rw, rh, ancho, alto):
                    placements.append((nombre, x, y, rw, rh))
                    resultado = rec(indice + 1)
                    if resultado:
                        return resultado
                    placements.pop()
        return None

    return rec(0)


def generar_patrones_factibles(piezas, ancho, alto, limite_combinaciones=4500):
    """Genera patrones factibles para hasta 3 tipos de pieza.
    Se limita deliberadamente para mantener la app rápida en equipos modestos.
    """
    if not piezas or len(piezas) > 3:
        return []

    limites = []
    combinaciones = 1
    area_lamina = ancho * alto
    for p in piezas:
        max_area = max(1, area_lamina // (p["ancho"] * p["alto"]))
        limite = min(int(p["cantidad"]), int(max_area), 12)
        limites.append(limite)
        combinaciones *= (limite + 1)
    if combinaciones > limite_combinaciones:
        return []

    patrones = []
    rangos = [range(l + 1) for l in limites]
    import itertools
    for combo in itertools.product(*rangos):
        if not any(combo):
            continue
        area = sum(c * p["ancho"] * p["alto"] for c, p in zip(combo, piezas))
        if area > area_lamina:
            continue
        # Los patrones con muy poco llenado rara vez ayudan a minimizar hojas;
        # se reservan para el respaldo MaxRects.
        if area / area_lamina < 0.75:
            continue
        rects = []
        for c, p in zip(combo, piezas):
            rects.extend([(p["nombre"], p["ancho"], p["alto"])] * c)
        if colocar_patron(rects, ancho, alto):
            patrones.append(combo)
    return patrones


def optimizar_laminas_2d(piezas, ancho, alto):
    """Optimización híbrida: patrones exactos pequeños + MaxRects como respaldo."""
    from functools import lru_cache

    nombres = [p["nombre"] for p in piezas]
    demandas = tuple(int(p["cantidad"]) for p in piezas)
    patrones = generar_patrones_factibles(piezas, ancho, alto)

    if patrones:
        # Conserva patrones útiles y resuelve exactamente las cantidades solicitadas.
        patrones = list(set(patrones))
        # Reducimos el conjunto a patrones no dominados para mantener la búsqueda rápida.
        # Esto conserva los patrones con mayor carga por tipo y evita millones de estados.
        patrones = [
            p for p in patrones
            if not any(q != p and all(q[i] >= p[i] for i in range(len(p))) for q in patrones)
        ]
        patrones.sort(
            key=lambda p: (sum(p), sum(p[i] * piezas[i]["ancho"] * piezas[i]["alto"]
                                       for i in range(len(p))), p),
            reverse=True,
        )

        @lru_cache(maxsize=None)
        def resolver(restantes):
            if not any(restantes):
                return (0, ())
            mejor = (10**9, ())
            for patron in patrones:
                if all(patron[i] <= restantes[i] for i in range(len(piezas))):
                    nuevo = tuple(restantes[i] - patron[i]
                                  for i in range(len(piezas)))
                    sub = resolver(nuevo)
                    if sub[0] + 1 < mejor[0]:
                        mejor = (sub[0] + 1, (patron,) + sub[1])
            return mejor

        try:
            cantidad_hojas, secuencia = resolver(demandas)
        except RecursionError:
            cantidad_hojas, secuencia = 0, ()

        if cantidad_hojas < 10**9 and secuencia:
            hojas = []
            for patron in secuencia:
                rects = []
                for i, cantidad in enumerate(patron):
                    rects.extend(
                        [(piezas[i]["nombre"], piezas[i]["ancho"], piezas[i]["alto"])] * cantidad)
                colocaciones = colocar_patron(rects, ancho, alto)
                hojas.append(
                    {"placements": colocaciones or [], "patron": patron})
            if sum(len(h["placements"]) for h in hojas) == sum(demandas):
                return hojas, "Patrones 2D exactos"

    # Respaldo general MaxRects / Best Short Side Fit.
    items = []
    for i, p in enumerate(piezas):
        for n in range(int(p["cantidad"])):
            items.append((p["nombre"], p["ancho"], p["alto"], i, n))
    items.sort(key=lambda x: x[1] * x[2], reverse=True)

    hojas = []
    for nombre, pw, ph, tipo, numero in items:
        mejor = None
        for si, hoja in enumerate(hojas):
            for fi, free in enumerate(hoja["free"]):
                fx, fy, fw, fh = free
                for rw, rh in ((pw, ph), (ph, pw)) if pw != ph else ((pw, ph),):
                    if rw <= fw and rh <= fh:
                        short = min(fw - rw, fh - rh)
                        long_side = max(fw - rw, fh - rh)
                        score = (short, long_side, si, fi)
                        if mejor is None or score < mejor[0]:
                            mejor = (score, si, rw, rh, fx, fy)
        if mejor is None:
            hoja = {"free": [(0, 0, ancho, alto)],
                    "placements": [], "patron": None}
            hojas.append(hoja)
            si = len(hojas) - 1
            fx = fy = 0
            rw, rh = (pw, ph)
            if rw > ancho or rh > alto:
                if ph <= ancho and pw <= alto:
                    rw, rh = ph, pw
                else:
                    raise ValueError(
                        f"La pieza {nombre} ({pw} x {ph} mm) no cabe en la lámina.")
        else:
            _, si, rw, rh, fx, fy = mejor
            hoja = hojas[si]

        usado = (fx, fy, rw, rh)
        nuevos = []
        for free in hoja["free"]:
            nuevos.extend(_split_free_rect(free, usado))
        hoja["free"] = _prune_free_rects(nuevos)
        hoja["placements"].append(
            {"x": fx, "y": fy, "w": rw, "h": rh, "nombre": nombre})

    return hojas, "MaxRects heurístico"


def calcular_espacios_libres(placements, ancho, alto):
    libres = [(0, 0, ancho, alto)]
    for p in placements:
        usados = (p["x"], p["y"], p["w"], p["h"])
        nuevos = []
        for libre in libres:
            nuevos.extend(_split_free_rect(libre, usados))
        libres = _prune_free_rects(nuevos)
    return sorted(libres, key=lambda r: (r[1], r[0]))


def resumen_laminas(hojas, piezas, ancho, alto):
    area_total = ancho * alto * len(hojas)
    area_usada = sum(p["w"] * p["h"] for h in hojas for p in h["placements"])
    return {
        "hojas": len(hojas),
        "area_usada": area_usada,
        "area_total": area_total,
        "aprovechamiento": (area_usada / area_total * 100) if area_total else 0,
        "sobrante": area_total - area_usada,
        "piezas": sum(len(h["placements"]) for h in hojas),
    }


def generar_pdf_laminas(archivo, proyecto, datos, hojas, metodo):
    from reportlab.graphics.shapes import Drawing, Rect, String
    from reportlab.lib.pagesizes import A4
    estilos = getSampleStyleSheet()
    titulo = ParagraphStyle(
        "LT", parent=estilos["Title"], alignment=TA_CENTER, fontSize=18, leading=22)
    subtitulo = ParagraphStyle(
        "LS", parent=estilos["Normal"], alignment=TA_CENTER, fontSize=9, textColor=colors.grey)
    h2 = ParagraphStyle(
        "LH2", parent=estilos["Heading2"], fontSize=13, spaceBefore=10, spaceAfter=7)
    normal = ParagraphStyle(
        "LN", parent=estilos["Normal"], fontSize=8.5, leading=11)

    doc = SimpleDocTemplate(str(archivo), pagesize=A4,
                            rightMargin=1.2*cm, leftMargin=1.2*cm,
                            topMargin=1.2*cm, bottomMargin=1.2*cm)
    elementos = [
        Paragraph("REPORTE DE OPTIMIZACIÓN DE LÁMINAS", titulo), Spacer(1, 5)]
    fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
    proceso = datos["proceso"]
    kerf = datos.get("kerf", 0)
    elementos.append(Paragraph(
        f"<b>Proyecto:</b> {proyecto}<br/>"
        f"<b>Fecha:</b> {fecha}<br/>"
        f"<b>Lámina:</b> {datos['ancho']} × {datos['alto']} mm — Calibre {datos['calibre']}<br/>"
        f"<b>Proceso:</b> {proceso} — <b>Kerf:</b> {kerf:.2f} mm<br/>"
        f"<b>Método:</b> {metodo}", subtitulo))

    res = resumen_laminas(
        hojas, datos["piezas"], datos["ancho"], datos["alto"])
    elementos.append(Paragraph("RESUMEN DE PRODUCCIÓN", h2))
    tabla = [["Concepto", "Resultado"],
             ["Láminas requeridas", str(res["hojas"])],
             ["Piezas a producir", str(res["piezas"])],
             ["Aprovechamiento global", f"{res['aprovechamiento']:.2f}%"],
             ["Área sobrante total", f"{res['sobrante']/1_000_000:.3f} m²"]]
    t = Table(tabla, colWidths=[8*cm, 7*cm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#34495e")),
                           ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                           ("GRID", (0, 0), (-1, -1), .5, colors.grey),
                           ("ALIGN", (1, 1), (-1, -1), "CENTER"),
                           ("FONTSIZE", (0, 0), (-1, -1), 9)]))
    elementos += [t, Spacer(1, 10), Paragraph("PIEZAS", h2)]
    piezas_tabla = [["Pieza", "Ancho", "Largo", "Cantidad"]]
    for p in datos["piezas"]:
        piezas_tabla.append(
            [p["nombre"], f"{p['ancho']} mm", f"{p['alto']} mm", str(p["cantidad"])])
    pt = Table(piezas_tabla, colWidths=[6*cm, 3*cm, 3*cm, 3*cm])
    pt.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#34495e")),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                            ("GRID", (0, 0), (-1, -1), .5, colors.grey),
                            ("ALIGN", (1, 1), (-1, -1), "CENTER"),
                            ("FONTSIZE", (0, 0), (-1, -1), 8.5)]))
    elementos.append(pt)

    # Agrupar hojas por patrón para reducir páginas repetidas.
    grupos = {}
    for h in hojas:
        patron = tuple(h.get("patron") or ())
        if not patron:
            patron = tuple(sorted((p["nombre"] for p in h["placements"])))
        grupos.setdefault(patron, []).append(h)

    elementos.append(PageBreak())
    elementos.append(Paragraph("PATRONES DE CORTE", titulo))
    for indice, (patron, grupo) in enumerate(grupos.items(), 1):
        h = grupo[0]
        elementos.append(Paragraph(
            f"Patrón {indice} — {len(grupo)} lámina(s) — "
            f"Piezas: {', '.join(f'{n}×{c}' for n, c in _contar_placements(h['placements']).items())}", h2))
        elementos.append(_dibujar_lamina_pdf(
            h["placements"], datos["ancho"], datos["alto"]))
        libres = calcular_espacios_libres(
            h["placements"], datos["ancho"], datos["alto"])
        area_sobrante = sum(w*h for _, _, w, h in libres)
        elementos.append(Paragraph(
            f"Área libre aproximada: {area_sobrante/1_000_000:.3f} m². "
            f"Espacios rectangulares detectados: {len(libres)}.", normal))
        if indice < len(grupos):
            elementos.append(PageBreak())

    def pie(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.grey)
        canvas.drawCentredString(
            A4[0] / 2, 0.7*cm, "Optimizer Tool | © 2026 v2.0")
        canvas.restoreState()
    doc.build(elementos, onFirstPage=pie, onLaterPages=pie)


def _contar_placements(placements):
    from collections import Counter
    return Counter(p["nombre"] for p in placements)


def _dibujar_lamina_pdf(placements, ancho, alto):
    from reportlab.graphics.shapes import Drawing, Rect, String
    max_w, max_h = 7.0*cm, 14.0*cm
    escala = min(max_w / ancho, max_h / alto)
    d = Drawing(ancho*escala, alto*escala)
    d.add(Rect(0, 0, ancho*escala, alto*escala,
               fillColor=colors.whitesmoke, strokeColor=colors.black, strokeWidth=1))
    palette = [colors.HexColor("#d6eaf8"), colors.HexColor("#d5f5e3"),
               colors.HexColor("#fcf3cf"), colors.HexColor("#f5eef8"),
               colors.HexColor("#fadbd8")]
    nombres = []
    for p in placements:
        if p["nombre"] not in nombres:
            nombres.append(p["nombre"])
        color = palette[nombres.index(p["nombre"]) % len(palette)]
        x = p["x"] * escala
        y = p["y"] * escala
        w = p["w"] * escala
        h = p["h"] * escala
        d.add(Rect(x, y, w, h, fillColor=color,
              strokeColor=colors.black, strokeWidth=.6))
        if w > 28 and h > 14:
            centro_x = x + w / 2
            centro_y = y + h / 2
            d.add(String(centro_x, centro_y + 4, p["nombre"], fontSize=7,
                         textAnchor="middle", fillColor=colors.black))
            d.add(String(
                centro_x, centro_y - 6,
                f"{p['w']} × {p['h']} mm", fontSize=6,
                textAnchor="middle", fillColor=colors.black))
    return d


def modulo_laminas(page: ft.Page, volver_menu=None):
    page.controls.clear()
    page.overlay.clear()
    page.services.clear()
    page.title = "Optimizer Tool — Láminas"
    page.theme_mode = ft.ThemeMode.DARK
    page.scroll = ft.ScrollMode.AUTO
    page.padding = ft.Padding(top=16, left=24, right=24, bottom=0)
    configurar_footer(page)

    proyectos = cargar_proyectos_laminas()
    base_proceso = ["Cizalla", "Plasma", "Láser"]
    filas = []
    resultado_actual = {"hojas": [], "datos": None, "metodo": ""}

    dd_proyecto = ft.Dropdown(label="📁 Proyecto", options=[
                              ft.dropdown.Option(x) for x in proyectos], expand=True)
    nuevo_proyecto = ft.TextField(
        label="Nombre del nuevo proyecto", expand=True, visible=False)
    dd_proceso = ft.Dropdown(label="✂️ Proceso de corte", options=[
                             ft.dropdown.Option(x) for x in base_proceso], value="Cizalla", expand=True)
    in_ancho = ft.TextField(label="Ancho lámina (mm)", value="1220",
                            keyboard_type=ft.KeyboardType.NUMBER, expand=True)
    in_alto = ft.TextField(label="Largo lámina (mm)", value="2440",
                           keyboard_type=ft.KeyboardType.NUMBER, expand=True)
    in_calibre = ft.TextField(label="Calibre", value="22", expand=True)
    in_kerf = ft.TextField(label="Kerf / ancho de corte (mm)", value="0",
                           keyboard_type=ft.KeyboardType.NUMBER, expand=True, disabled=True)
    contenedor_piezas = ft.Column()
    contenedor_resultado = ft.Column()

    def toast(msg, error=False):
        s = ft.SnackBar(
            ft.Text(msg), bgcolor=ft.Colors.RED_ACCENT if error else None)
        page.overlay.append(s)
        s.open = True
        page.update()

    def cambiar_proceso(e):
        in_kerf.disabled = dd_proceso.value == "Cizalla"
        if dd_proceso.value == "Cizalla":
            in_kerf.value = "0"
        page.update()

    dd_proceso.on_change = cambiar_proceso

    def crear_fila(num):
        nombre = ft.TextField(
            label=f"Pieza {num}", hint_text="Ej: Bandeja A", expand=True)
        ancho = ft.TextField(label="Ancho útil (mm)",
                             keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        alto = ft.TextField(label="Largo útil (mm)",
                            keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        pestaña = ft.TextField(label="Pestaña por lado (mm)", value="",
                               keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        cantidad = ft.TextField(
            label="Cantidad", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        fila = ft.Column([
            ft.Row([nombre, ancho, alto]),
            ft.Row([pestaña, cantidad]),
        ])
        fila._campos_optimizer = (nombre, ancho, alto, pestaña, cantidad)
        return fila

    def agregar_fila(e=None):
        f = crear_fila(len(filas) + 1)
        filas.append(f)
        contenedor_piezas.controls.append(f)
        page.update()

    def leer_piezas():
        piezas = []
        for f in filas:
            nombre, ancho, alto, pestaña, cantidad = f._campos_optimizer
            try:
                n = (nombre.value or "").strip() or f"Pieza {len(piezas)+1}"
                w = float(str(ancho.value or "0").replace(",", "."))
                h = float(str(alto.value or "0").replace(",", "."))
                tab = float(str(pestaña.value or "0").replace(",", "."))
                q = int(float(str(cantidad.value or "0").replace(",", ".")))
                if w <= 0 or h <= 0 or q <= 0:
                    continue
                piezas.append({"nombre": n, "ancho": int(round(w + 2*tab)),
                               "alto": int(round(h + 2*tab)), "cantidad": q,
                               "util_ancho": w, "util_alto": h, "pestana": tab})
            except (ValueError, TypeError):
                continue
        return piezas

    def guardar_proyecto_actual(e=None):
        nombre = dd_proyecto.value or nuevo_proyecto.value.strip()
        if not nombre:
            toast("❌ Indica un nombre de proyecto.", True)
            return
        try:
            ancho = int(float(in_ancho.value))
            alto = int(float(in_alto.value))
            kerf = float(in_kerf.value or 0)
        except ValueError:
            toast("❌ Revisa las dimensiones de la lámina y el kerf.", True)
            return
        piezas = leer_piezas()
        if not piezas:
            toast("❌ Agrega al menos una pieza válida.", True)
            return
        datos = {"ancho": ancho, "alto": alto, "calibre": in_calibre.value.strip(),
                 "proceso": dd_proceso.value, "kerf": 0 if dd_proceso.value == "Cizalla" else kerf,
                 "piezas": piezas}
        proyectos[nombre] = datos
        guardar_proyectos_laminas(proyectos)
        dd_proyecto.options = [ft.dropdown.Option(x) for x in proyectos]
        dd_proyecto.value = nombre
        nuevo_proyecto.visible = False
        toast(f"✅ Proyecto '{nombre}' guardado.")

    def cargar_proyecto(e=None):
        nombre = dd_proyecto.value
        datos = proyectos.get(nombre)
        if not isinstance(datos, dict):
            toast("❌ Selecciona un proyecto de láminas.", True)
            return
        in_ancho.value = str(datos.get("ancho", 1220))
        in_alto.value = str(datos.get("alto", 2440))
        in_calibre.value = str(datos.get("calibre", ""))
        dd_proceso.value = datos.get("proceso", "Cizalla")
        in_kerf.value = str(datos.get("kerf", 0))
        in_kerf.disabled = dd_proceso.value == "Cizalla"
        filas.clear()
        contenedor_piezas.controls.clear()
        for p in datos.get("piezas", []):
            f = crear_fila(len(filas)+1)
            filas.append(f)
            contenedor_piezas.controls.append(f)
            n, w, h, tab, q = f._campos_optimizer
            n.value = p.get("nombre", "")
            w.value = str(p.get("util_ancho", p.get("ancho", "")))
            h.value = str(p.get("util_alto", p.get("alto", "")))
            tab.value = "" if not p.get("pestana", 0) else str(p["pestana"])
            q.value = str(p.get("cantidad", ""))
        page.update()

    def nuevo(e=None):
        nuevo_proyecto.value = ""
        nuevo_proyecto.visible = True
        dd_proyecto.value = None
        resultado_actual.update({"hojas": [], "datos": None, "metodo": ""})
        contenedor_resultado.controls.clear()
        filas.clear()
        contenedor_piezas.controls.clear()
        agregar_fila()
        page.update()

    def vista_patron(hoja, datos):
        """Construye una vista proporcional de la distribución de una lámina."""
        ancho_lamina = datos["ancho"]
        alto_lamina = datos["alto"]
        max_ancho = 350
        max_alto = 270
        escala = min(max_ancho / ancho_lamina, max_alto / alto_lamina)
        ancho_vista = max(80, ancho_lamina * escala)
        alto_vista = max(80, alto_lamina * escala)
        colores = [
            ft.Colors.BLUE_200, ft.Colors.GREEN_200, ft.Colors.AMBER_200,
            ft.Colors.PURPLE_200, ft.Colors.RED_200, ft.Colors.CYAN_200,
        ]
        nombres = []
        piezas_vista = []
        for pieza in hoja["placements"]:
            nombre = pieza["nombre"]
            if nombre not in nombres:
                nombres.append(nombre)
            color = colores[nombres.index(nombre) % len(colores)]
            piezas_vista.append(ft.Container(
                left=pieza["x"] * escala,
                top=pieza["y"] * escala,
                width=max(2, pieza["w"] * escala),
                height=max(2, pieza["h"] * escala),
                bgcolor=color,
                border=ft.Border.all(1, ft.Colors.BLUE_GREY_700),
                content=ft.Text(
                    f"{nombre}\n{pieza['w']} × {pieza['h']} mm",
                    size=8, text_align=ft.TextAlign.CENTER,
                    color=ft.Colors.BLACK,
                ),
            ))

        return ft.Column([
            ft.Row([
                ft.Text(
                    f"Distribución de referencia: {ancho_lamina} × {alto_lamina} mm",
                    size=12, weight=ft.FontWeight.BOLD,
                ),
            ], alignment=ft.MainAxisAlignment.CENTER),
            ft.Row([
                ft.Container(
                    width=ancho_vista,
                    height=alto_vista,
                    bgcolor=ft.Colors.GREY_100,
                    border=ft.Border.all(2, ft.Colors.BLUE_GREY_700),
                    content=ft.Stack(
                        controls=piezas_vista,
                        width=ancho_vista,
                        height=alto_vista,
                    ),
                ),
            ], alignment=ft.MainAxisAlignment.CENTER),
            ft.Text(
                "La posición y el giro de cada pieza corresponden a la optimización calculada.",
                size=10, color=ft.Colors.WHITE70, italic=True,
            ),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8)

    async def optimizar(e=None):
        try:
            ancho = int(float(in_ancho.value))
            alto = int(float(in_alto.value))
            kerf = float(in_kerf.value or 0)
        except ValueError:
            toast("❌ Dimensiones inválidas.", True)
            return
        piezas = leer_piezas()
        if not piezas:
            toast("❌ Agrega piezas válidas.", True)
            return
        if any(p["ancho"] > ancho and p["alto"] > ancho and p["ancho"] > alto and p["alto"] > alto for p in piezas):
            toast("❌ Hay una pieza que no cabe en la lámina.", True)
            return
        indicador = mostrar_cargando(page)
        await asyncio.sleep(0.05)
        # Para procesos con kerf, se aplica como separación conservadora.
        if dd_proceso.value != "Cizalla" and kerf > 0:
            for p in piezas:
                p["ancho"] += kerf
                p["alto"] += kerf
                p["ancho"] = int(round(p["ancho"]))
                p["alto"] = int(round(p["alto"]))
        try:
            hojas, metodo = await asyncio.to_thread(optimizar_laminas_2d, piezas, ancho, alto)
        except Exception as ex:
            ocultar_cargando(page, indicador)
            toast(f"❌ No se pudo optimizar: {ex}", True)
            return
        resultado_actual.update({"hojas": hojas, "datos": {"ancho": ancho, "alto": alto, "calibre": in_calibre.value,
                                                           "proceso": dd_proceso.value, "kerf": 0 if dd_proceso.value == "Cizalla" else kerf, "piezas": piezas}, "metodo": metodo})
        res = resumen_laminas(hojas, piezas, ancho, alto)
        contenedor_resultado.controls.clear()
        contenedor_resultado.controls.append(ft.Text(
            f"📊 Resultado: {res['hojas']} láminas | {res['piezas']} piezas | Aprovechamiento: {res['aprovechamiento']:.2f}%",
            size=17, weight=ft.FontWeight.BOLD))
        contenedor_resultado.controls.append(ft.Text(f"Método: {metodo}"))
        # Resumen por patrón
        grupos = {}
        for h in hojas:
            patron = tuple(h.get("patron") or sorted(
                _contar_placements(h["placements"]).items()))
            if patron not in grupos:
                grupos[patron] = {"cantidad": 0, "hoja": h}
            grupos[patron]["cantidad"] += 1
        for i, (pat, grupo) in enumerate(grupos.items(), 1):
            cant = grupo["cantidad"]
            desc = ", ".join(f"{x}×{y}" for x, y in pat) if pat and isinstance(
                pat[0], tuple) else ", ".join(f"{piezas[j]['nombre']}×{v}" for j, v in enumerate(pat))
            contenedor_resultado.controls.append(ft.ExpansionTile(
                title=ft.Text(f"Patrón {i}: {cant} lámina(s) — {desc}"),
                subtitle=ft.Text("Pulsa para ver el esquema de distribución"),
                controls=[vista_patron(
                    grupo["hoja"], resultado_actual["datos"])],
            ))
            ocultar_cargando(page, indicador)
        page.update()

    async def generar_pdf(e=None):
        if not resultado_actual["hojas"]:
            toast("⚠️ Primero ejecuta una optimización.", True)
            return
        picker = ft.FilePicker()
        page.services.append(picker)
        try:
            carpeta = await picker.get_directory_path(dialog_title="Selecciona la carpeta donde guardar el PDF")
            if not carpeta:
                return
            proyecto = dd_proyecto.value or nuevo_proyecto.value.strip() or "Proyecto_Laminas"
            seguro = re.sub(r'[^A-Za-z0-9_-]+', '_',
                            proyecto).strip('_') or 'Proyecto_Laminas'
            archivo = Path(
                carpeta) / f"Reporte_Laminas_{seguro}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            generar_pdf_laminas(
                archivo, proyecto, resultado_actual["datos"], resultado_actual["hojas"], resultado_actual["metodo"])
            toast(f"✅ PDF guardado: {archivo.name}")
        except Exception as ex:
            toast(f"❌ Error al generar PDF: {ex}", True)

    if not filas:
        agregar_fila()

    header = ft.Row([ft.Text("▦", size=30), ft.Text("OPTIMIZER TOOL — LÁMINAS",
                    size=23, weight=ft.FontWeight.BOLD)], alignment=ft.MainAxisAlignment.CENTER)
    menu = ft.Row([
        ft.ElevatedButton("Nuevo", on_click=nuevo, expand=True),
        ft.ElevatedButton("Cargar", on_click=cargar_proyecto, expand=True),
        ft.OutlinedButton(
            "Guardar", on_click=guardar_proyecto_actual, expand=True),
    ])
    contenedor = ft.Column([
        ft.TextButton("← Volver al menú principal", icon=ft.Icons.ARROW_BACK,
                      on_click=lambda e: volver_menu(page) if volver_menu else None),
        header,
        menu,
        nuevo_proyecto,
        dd_proyecto,
        ft.Text("CONFIGURACIÓN DE LA LÁMINA", weight=ft.FontWeight.BOLD),
        ft.Row([in_ancho, in_alto]),
        ft.Row([in_calibre, dd_proceso]),
        in_kerf,
        ft.Divider(),
        ft.Row([ft.Text("PIEZAS A CORTAR", weight=ft.FontWeight.BOLD, size=16),
               ft.ElevatedButton("➕ Agregar pieza", on_click=agregar_fila)]),
        contenedor_piezas,
        ft.FilledButton("⚙️ Optimizar láminas", on_click=optimizar),
        ft.OutlinedButton("📄 Generar reporte completo en PDF",
                          on_click=generar_pdf),
        ft.Divider(),
        contenedor_resultado,
        ft.Container(height=50),
    ], expand=True)
    page.add(contenedor)
    page.update()


def mostrar_menu_principal(page):
    page.controls.clear()
    page.overlay.clear()
    page.services.clear()
    page.on_keyboard_event = None
    page.title = "Optimizer Tool"
    page.theme_mode = ft.ThemeMode.DARK
    page.scroll = ft.ScrollMode.AUTO
    page.padding = ft.Padding(top=16, left=24, right=24, bottom=0)

    def abrir_barras(e=None):
        modulo_barras(page, mostrar_menu_principal)

    def abrir_laminas(e=None):
        modulo_laminas(page, mostrar_menu_principal)

    page.add(ft.Column([
        ft.Container(height=50),
        ft.Image(src="icon.png", width=110, height=110),
        ft.Text("Optimizer Tool", size=30, weight=ft.FontWeight.BOLD),
        ft.Text("¿Qué deseas optimizar?", size=18),
        ft.Container(height=20),
        ft.ElevatedButton("🪚  TUBOS / VARILLAS / PERFILES",
                          on_click=abrir_barras, width=330, height=55),
        ft.ElevatedButton("▦  LÁMINAS", on_click=abrir_laminas,
                          width=330, height=55),
        ft.Container(height=30),
        ft.Text("Optimización de cortes para fabricación",
                size=11, color=ft.Colors.WHITE70),
    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER, expand=True))
    page.update()


def mostrar_splash_inicial(page):
    splash = ft.Container(
        expand=True,
        bgcolor=ft.Colors.BLACK,
        opacity=1,
        animate_opacity=ft.Animation(700, ft.AnimationCurve.EASE_IN_OUT),
        alignment=ft.Alignment(0, 0),
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            controls=[
                ft.Image(src="icon.png", width=130, height=130),
                ft.Text("Optimizer Tool", size=30,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.WHITE),
            ],
        ),
    )
    page.overlay.append(splash)
    page.update()

    async def ocultar_splash():
        await asyncio.sleep(0.8)
        if splash not in page.overlay:
            return
        splash.opacity = 0
        page.update()
        await asyncio.sleep(0.8)
        if splash in page.overlay:
            page.overlay.remove(splash)
            page.update()

    page.run_task(ocultar_splash)


def main(page: ft.Page):
    page.window_width = 450
    page.window_height = 800
    mostrar_menu_principal(page)
    mostrar_splash_inicial(page)


ft.app(target=main)
