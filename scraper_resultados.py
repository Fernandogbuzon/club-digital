#!/usr/bin/env python3
"""
Scraper Rápido de Resultados – ADESA 80
========================================
Detecta partidos de ADESA 80 que deberían haber terminado (hora inicio + 2.5h)
pero aún no tienen resultado, y scrapea SOLO esos grupos específicos para
actualizar el JSON correspondiente lo antes posible.

Uso:
  python scraper_resultados.py                # Una pasada
  python scraper_resultados.py --watch        # Loop cada 5 min en horario de partidos
  python scraper_resultados.py --headless     # Intentar headless
  python scraper_resultados.py --check        # Solo mostrar partidos pendientes (sin scraping)
"""

import asyncio
import json
import re
import sys
import argparse
import random
import logging
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# ─── Configuración ───────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent
DATA_BASE_DIR = SCRIPT_DIR / "src" / "data"
LOG_DIR = SCRIPT_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Mapa: carpeta de competición → URL
COMP_URL_MAP = {
    "Comp-Copa-Andalucia-A": "https://www.andaluzabaloncesto.org/cadiz/delegacion-competicion-2445/comp-copa-andalucia-a",
    "Comp-Copa-Andalucia-B": "https://www.andaluzabaloncesto.org/cadiz/delegacion-competicion-2446/comp-copa-andalucia-b",
    "Comp-1-Año": "https://www.andaluzabaloncesto.org/cadiz/delegacion-competicion-2447/comp-1-a%C3%B1o",
    "Liga-Pre-Minibasket": "https://www.andaluzabaloncesto.org/cadiz/delegacion-competicion-2448/liga-pre-minibasket",
    "Programa-Babybasket-20182019": "https://www.andaluzabaloncesto.org/cadiz/delegacion-competicion-2449/programa-babybasket-20182019",
    "Liga-Sierra-Cadiz": "https://www.andaluzabaloncesto.org/cadiz/delegacion-competicion-2542/liga-sierra-cadiz",
    "Copa-Diputacionmemorial-Carlos-Duque": "https://www.andaluzabaloncesto.org/cadiz/delegacion-competicion-2503/copa-diputacionmemorial-carlos-duque",
    "Iv-Torneo-Las-Cortes-Qv": "https://www.andaluzabaloncesto.org/cadiz/delegacion-competicion-2516/iv-torneo-las-cortes-qv",
    "Liga-Verano-El-Puerto": "https://www.andaluzabaloncesto.org/cadiz/delegacion-competicion-2381/liga-verano-el-puerto",
    "Torneo-Seleccion-Española": "https://www.andaluzabaloncesto.org/cadiz/delegacion-competicion-2386/torneo-seleccion-espa%C3%B1ola",
}

# ASP.NET dropdown names
DDL_CATEGORIAS = "ctl00$ctl00$contenedor_informacion$contenedor_informacion_con_lateral$DDLCategorias"
DDL_FASES = "ctl00$ctl00$contenedor_informacion$contenedor_informacion_con_lateral$DDLFases"
DDL_GRUPOS = "ctl00$ctl00$contenedor_informacion$contenedor_informacion_con_lateral$DDLGrupos"

SEL_CAT = f"select[name='{DDL_CATEGORIAS}']"
SEL_FASE = f"select[name='{DDL_FASES}']"
SEL_GRUPO = f"select[name='{DDL_GRUPOS}']"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
]

# Duración estimada de un partido (para saber cuándo debería haber terminado)
DURACION_PARTIDO_HORAS = 2.5

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "scraper_resultados.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


# ─── Utilidades ──────────────────────────────────────────────────────────────

def parse_fecha(fecha_str: str, hora_str: str) -> datetime:
    """Parsea fecha DD/MM/YYYY y hora HH:MM a datetime."""
    try:
        d, m, y = fecha_str.split("/")
        dt = datetime(int(y), int(m), int(d))
        if hora_str and ":" in hora_str:
            h, mi = hora_str.split(":")
            dt = dt.replace(hour=int(h), minute=int(mi))
        else:
            dt = dt.replace(hour=12, minute=0)
        return dt
    except Exception:
        return datetime(2000, 1, 1)


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    text = re.sub(r"[-\s]+", "-", text)
    return text


async def pausa(lo: float = 0.5, hi: float = 1.5):
    await asyncio.sleep(random.uniform(lo, hi))


# ─── Detectar partidos pendientes ────────────────────────────────────────────

def buscar_partidos_pendientes() -> list[dict]:
    """
    Escanea todos los JSON de ADESA 80 y devuelve partidos que:
    - No tienen resultado (es_resultado == False)
    - Ya deberían haber terminado (hora_partido + DURACION_PARTIDO > ahora)
    
    Devuelve lista con info del partido y la ruta del archivo JSON.
    """
    ahora = datetime.now()
    pendientes = []
    archivos_revisados = 0

    for json_path in DATA_BASE_DIR.rglob("adesa-80*.json"):
        archivos_revisados += 1
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                continue
        except Exception as e:
            logger.warning(f"⚠️ Error leyendo {json_path}: {e}")
            continue

        for partido in data:
            if partido.get("es_resultado"):
                continue  # Ya tiene resultado
            
            fecha_str = partido.get("fecha", "")
            hora_str = partido.get("hora", "")
            if not fecha_str:
                continue

            dt_inicio = parse_fecha(fecha_str, hora_str)
            dt_fin_estimado = dt_inicio + timedelta(hours=DURACION_PARTIDO_HORAS)

            if dt_fin_estimado < ahora:
                # ¡Este partido debería haber terminado!
                # Extraer info de la ruta del archivo para saber a qué grupo pertenece
                rel = json_path.relative_to(DATA_BASE_DIR)
                parts = rel.parts  # ej: ('Comp-Copa-Andalucia-A', 'Cadete-Femenino', 'ÚNICO', 'REGULAR', 'adesa-80.json')
                
                if len(parts) >= 5:
                    comp_carpeta = parts[0]
                    cat_carpeta = parts[1]
                    grupo_carpeta = parts[2]
                    fase_carpeta = parts[3]
                else:
                    continue

                pendientes.append({
                    "partido": partido,
                    "json_path": str(json_path),
                    "comp_carpeta": comp_carpeta,
                    "cat_carpeta": cat_carpeta,
                    "grupo_carpeta": grupo_carpeta,
                    "fase_carpeta": fase_carpeta,
                    "dt_inicio": dt_inicio,
                    "dt_fin_estimado": dt_fin_estimado,
                    "categoria": partido.get("categoria", ""),
                })

    logger.info(f"📂 Revisados {archivos_revisados} archivos ADESA 80")
    return pendientes


def agrupar_por_grupo(pendientes: list[dict]) -> dict[str, list[dict]]:
    """Agrupa partidos pendientes por competición/categoría/grupo/fase (para scraping eficiente)."""
    grupos = {}
    for p in pendientes:
        key = f"{p['comp_carpeta']}|{p['cat_carpeta']}|{p['grupo_carpeta']}|{p['fase_carpeta']}"
        grupos.setdefault(key, []).append(p)
    return grupos


# ─── Browser helpers ─────────────────────────────────────────────────────────

async def crear_browser(headless: bool = False):
    from playwright.async_api import async_playwright
    from playwright_stealth import Stealth

    pw = await async_playwright().start()
    browser = await pw.chromium.launch(
        headless=headless,
        args=["--no-sandbox", "--disable-setuid-sandbox",
              "--disable-blink-features=AutomationControlled",
              "--disable-dev-shm-usage"],
    )
    stealth = Stealth()
    context = await browser.new_context(
        user_agent=random.choice(USER_AGENTS),
        viewport={"width": 1366, "height": 768},
        locale="es-ES",
        timezone_id="Europe/Madrid",
        extra_http_headers={"Accept-Language": "es-ES,es;q=0.9"},
    )
    await stealth.apply_stealth_async(context)
    page = await context.new_page()
    return pw, browser, context, page


async def esperar_pagina(page, timeout: int = 45000) -> bool:
    try:
        await page.wait_for_selector(SEL_CAT, timeout=timeout)
        return True
    except Exception:
        title = await page.title()
        if "moment" in title.lower() or "momento" in title.lower():
            logger.info("  ⏳ Challenge CF, esperando...")
            try:
                await page.wait_for_selector(SEL_CAT, timeout=90000)
                return True
            except Exception:
                return False
        return False


async def obtener_opciones(page, selector: str) -> list[dict]:
    return await page.eval_on_selector_all(
        selector + " option",
        "opts => opts.map(o => ({value: o.value, text: o.textContent.trim().replace(/\\s+/g, ' ')}))",
    )


async def seleccionar_dropdown(page, selector: str, ddl_name: str, value: str):
    await page.evaluate("() => { window.__cFRLUnblockHandlers = true; }")
    try:
        async with page.expect_navigation(wait_until="domcontentloaded", timeout=60000):
            await page.select_option(selector, value)
    except Exception as e:
        logger.warning(f"  ⚠️ Navigation: {e}")
    ok = await esperar_pagina(page, timeout=60000)
    await pausa(0.5, 1.2)
    return ok


async def extraer_partidos_pagina(page) -> list[dict]:
    """Extrae TODOS los partidos del calendario visible (de un grupo ya seleccionado)."""
    return await page.evaluate("""
        () => {
            const resultados = [];
            const cal = document.getElementById('calendario');
            if (!cal) return resultados;

            cal.querySelectorAll('header.nombre_tabla').forEach(header => {
                const h5 = header.querySelector('h5');
                const jornada = h5 ? h5.textContent.trim().replace(/\\s+/g, ' ') : '';

                let tc = header.nextElementSibling;
                while (tc && !tc.classList.contains('table-responsive')) tc = tc.nextElementSibling;
                if (!tc) return;

                const tabla = tc.querySelector('table');
                if (!tabla) return;

                tabla.querySelectorAll('tbody tr').forEach(fila => {
                    const c = fila.querySelectorAll('td');
                    if (c.length < 6) return;

                    const local = c[0].textContent.trim();
                    const ptL = c[1].textContent.trim();
                    const ptV = c[2].textContent.trim();
                    const visitante = c[3].textContent.trim();
                    if (!local || !visitante) return;

                    const strong = c[4].querySelector('strong');
                    let fecha = '', hora = '';
                    if (strong) {
                        const parts = strong.innerHTML.split(/<br\\s*\\/?>/);
                        fecha = (parts[0] || '').replace(/"/g, '').trim();
                        if (parts[1]) hora = parts[1].replace(/"/g, '').trim();
                    }

                    const pabellon = c[5] ? c[5].textContent.trim() : '';
                    const ml = ptL && !isNaN(parseInt(ptL)) ? parseInt(ptL) : null;
                    const mv = ptV && !isNaN(parseInt(ptV)) ? parseInt(ptV) : null;

                    resultados.push({
                        local, visitante,
                        marcador_local: ml, marcador_visitante: mv,
                        fecha, hora, pabellon,
                        es_resultado: ml !== null && mv !== null,
                        jornada,
                    });
                });
            });
            return resultados;
        }
    """)


# ─── Buscar valor en dropdown que coincida con carpeta ──────────────────────

def match_opcion_a_carpeta(opciones: list[dict], carpeta: str) -> Optional[str]:
    """
    Dado un nombre de carpeta (ej: 'Cadete-Femenino') y las opciones del dropdown,
    encuentra el value cuyo texto coincida.
    """
    # Normalizar carpeta: quitar guiones, minúsculas
    carpeta_norm = carpeta.replace("-", " ").lower().strip()
    
    for opt in opciones:
        opt_norm = opt["text"].lower().strip()
        # Coincidencia exacta
        if opt_norm == carpeta_norm:
            return opt["value"]
        # Coincidencia parcial (la carpeta es un subconjunto del texto o viceversa)
        if carpeta_norm in opt_norm or opt_norm in carpeta_norm:
            return opt["value"]
    
    # Intentar con match más flexible: quitar tildes
    def strip_accents(s):
        return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode("ascii").lower()
    
    carpeta_ascii = strip_accents(carpeta.replace("-", " "))
    for opt in opciones:
        if strip_accents(opt["text"]) == carpeta_ascii:
            return opt["value"]
        if carpeta_ascii in strip_accents(opt["text"]):
            return opt["value"]
    
    return None


# ─── Scraping dirigido de un grupo específico ────────────────────────────────

async def scrape_grupo(
    page,
    comp_url: str,
    cat_carpeta: str,
    fase_carpeta: str,
    grupo_carpeta: str,
    current_page_url: str = "",
) -> list[dict]:
    """
    Navega a una competición y selecciona categoría/fase/grupo específicos.
    Devuelve la lista de partidos scrapeados de ese grupo.
    """
    # Solo navegar si no estamos ya en la URL de esta competición
    page_url = page.url or ""
    comp_base = comp_url.split("/delegacion-competicion")[0] if "/delegacion-competicion" in comp_url else ""
    
    if comp_base not in page_url:
        logger.info(f"  📡 Navegando a competición: {comp_url}")
        await page.goto(comp_url, wait_until="domcontentloaded", timeout=60000)
        if not await esperar_pagina(page, timeout=60000):
            logger.error("  ❌ No se pudo cargar la página")
            return []
        await pausa(1.5, 3.0)

    # 1) Seleccionar categoría
    cats = await obtener_opciones(page, SEL_CAT)
    cats = [c for c in cats if c["value"]]
    cat_value = match_opcion_a_carpeta(cats, cat_carpeta)
    if not cat_value:
        logger.error(f"  ❌ No encontré categoría '{cat_carpeta}' en dropdown. Opciones: {[c['text'] for c in cats]}")
        return []
    
    logger.info(f"  📂 Seleccionando categoría: {cat_carpeta}")
    if not await seleccionar_dropdown(page, SEL_CAT, DDL_CATEGORIAS, cat_value):
        return []

    # 2) Seleccionar fase
    fases = await obtener_opciones(page, SEL_FASE)
    fases = [f for f in fases if f["value"]]
    fase_value = match_opcion_a_carpeta(fases, fase_carpeta)
    if not fase_value:
        # Si solo hay una fase, usarla
        if len(fases) == 1:
            fase_value = fases[0]["value"]
        else:
            logger.error(f"  ❌ No encontré fase '{fase_carpeta}'. Opciones: {[f['text'] for f in fases]}")
            return []

    logger.info(f"  📄 Seleccionando fase: {fase_carpeta}")
    if not await seleccionar_dropdown(page, SEL_FASE, DDL_FASES, fase_value):
        return []

    # 3) Seleccionar grupo
    grupos = await obtener_opciones(page, SEL_GRUPO)
    grupos = [g for g in grupos if g["value"]]
    grupo_value = match_opcion_a_carpeta(grupos, grupo_carpeta)
    if not grupo_value:
        if len(grupos) == 1:
            grupo_value = grupos[0]["value"]
        else:
            logger.error(f"  ❌ No encontré grupo '{grupo_carpeta}'. Opciones: {[g['text'] for g in grupos]}")
            return []

    logger.info(f"  🏷️ Seleccionando grupo: {grupo_carpeta}")
    if not await seleccionar_dropdown(page, SEL_GRUPO, DDL_GRUPOS, grupo_value):
        return []

    # 4) Asegurar tab calendario
    try:
        cal_tab = page.locator("#calendario-tab")
        if await cal_tab.count() > 0:
            aria = await cal_tab.get_attribute("aria-selected")
            if aria != "true":
                await cal_tab.click()
                await pausa(0.5, 1.0)
    except Exception:
        pass

    # 5) Extraer
    partidos = await extraer_partidos_pagina(page)
    logger.info(f"  📊 Extraídos {len(partidos)} partidos del grupo")
    return partidos


# ─── Actualizar JSON con nuevos resultados ───────────────────────────────────

def actualizar_json(json_path: str, partidos_web: list[dict]) -> int:
    """
    Compara los partidos del JSON local con los scrapeados de la web.
    Actualiza los que ahora tienen resultado. Devuelve nº de actualizados.
    """
    path = Path(json_path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"  ❌ Error leyendo {path}: {e}")
        return 0

    if not isinstance(data, list):
        return 0

    actualizados = 0

    for partido in data:
        if partido.get("es_resultado"):
            continue  # Ya tiene resultado

        # Buscar este partido en los datos web
        for pw in partidos_web:
            if not pw["es_resultado"]:
                continue  # Tampoco tiene resultado en la web

            # Coincidir por fecha + equipos
            if pw["fecha"] != partido.get("fecha"):
                continue

            # Verificar equipos (local/visitante o viceversa en el JSON por equipo)
            p_equipo = partido.get("equipo", "")
            p_rival = partido.get("rival", "")
            p_ubicacion = partido.get("ubicacion", "")

            match = False
            if p_ubicacion == "Local" and pw["local"] == p_equipo and pw["visitante"] == p_rival:
                match = True
            elif p_ubicacion == "Visitante" and pw["visitante"] == p_equipo and pw["local"] == p_rival:
                match = True

            if match:
                logger.info(f"  ✅ RESULTADO ENCONTRADO: {pw['local']} {pw['marcador_local']}-{pw['marcador_visitante']} {pw['visitante']} ({pw['fecha']})")
                partido["marcador_local"] = pw["marcador_local"]
                partido["marcador_visitante"] = pw["marcador_visitante"]
                partido["es_resultado"] = True
                # Actualizar hora y pabellón si cambiaron
                if pw.get("hora"):
                    partido["hora"] = pw["hora"]
                if pw.get("pabellon"):
                    partido["pabellon"] = pw["pabellon"]
                actualizados += 1
                break

    if actualizados > 0:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"  💾 Guardado {path.name}: {actualizados} resultado(s) actualizado(s)")

    return actualizados


# ─── Pipeline principal ──────────────────────────────────────────────────────

async def actualizar_resultados(headless: bool = False, check_only: bool = False):
    """Busca partidos pendientes → scrapea solo los grupos necesarios → actualiza JSONs."""
    
    logger.info("=" * 60)
    logger.info("⚡ SCRAPER RÁPIDO DE RESULTADOS — ADESA 80")
    logger.info(f"🕐 {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    logger.info("=" * 60)

    # 1) Buscar pendientes
    pendientes = buscar_partidos_pendientes()
    
    if not pendientes:
        logger.info("✅ No hay partidos pendientes de resultado. Todo al día.")
        return 0

    logger.info(f"\n⚠️ {len(pendientes)} partido(s) pendiente(s) de resultado:")
    for p in pendientes:
        pt = p["partido"]
        logger.info(f"  >> {pt.get('equipo', '?')} vs {pt.get('rival', '?')} "
                     f"({pt.get('fecha', '?')} {pt.get('hora', '?')}) "
                     f"-- {p['cat_carpeta']} [{p['comp_carpeta']}]")

    if check_only:
        logger.info("\n(modo --check: no se realiza scraping)")
        return len(pendientes)

    # 2) Agrupar por grupo (para no repetir navegaciones)
    grupos = agrupar_por_grupo(pendientes)
    logger.info(f"\n📋 {len(grupos)} grupo(s) a scrapear:")
    for key in grupos:
        comp, cat, grupo, fase = key.split("|")
        logger.info(f"  → {comp} / {cat} / {grupo} / {fase} ({len(grupos[key])} partido(s))")

    # 3) Scraping dirigido
    pw_inst, browser, context, page = await crear_browser(headless=headless)
    total_actualizados = 0

    try:
        for key, partidos_grupo in grupos.items():
            comp_carpeta, cat_carpeta, grupo_carpeta, fase_carpeta = key.split("|")
            
            comp_url = COMP_URL_MAP.get(comp_carpeta)
            if not comp_url:
                logger.warning(f"  ⚠️ Competición '{comp_carpeta}' no tiene URL mapeada. Saltando.")
                continue

            logger.info(f"\n{'─' * 50}")
            logger.info(f"🎯 {comp_carpeta} / {cat_carpeta} / {grupo_carpeta} / {fase_carpeta}")
            
            try:
                partidos_web = await scrape_grupo(
                    page, comp_url, cat_carpeta, fase_carpeta, grupo_carpeta
                )
            except Exception as e:
                logger.error(f"  ❌ Error scraping: {e}")
                try:
                    await page.goto("about:blank")
                    await pausa(1.0, 2.0)
                except Exception:
                    pass
                continue

            if not partidos_web:
                logger.warning("  ⚠️ No se obtuvieron partidos de la web")
                continue

            # Contar cuántos tienen resultado en la web
            con_resultado = [p for p in partidos_web if p["es_resultado"]]
            logger.info(f"  📊 Web: {len(partidos_web)} partidos ({len(con_resultado)} con resultado)")

            # 4) Actualizar los JSON afectados
            json_paths_vistos = set()
            for p in partidos_grupo:
                jp = p["json_path"]
                if jp not in json_paths_vistos:
                    json_paths_vistos.add(jp)
                    n = actualizar_json(jp, partidos_web)
                    total_actualizados += n

            await pausa(1.0, 2.0)

    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
    finally:
        await browser.close()
        await pw_inst.stop()

    logger.info(f"\n{'═' * 60}")
    logger.info(f"📊 RESUMEN: {total_actualizados} resultado(s) actualizado(s) de {len(pendientes)} pendiente(s)")
    logger.info(f"{'═' * 60}")
    return total_actualizados


# ─── Modo watch ──────────────────────────────────────────────────────────────

async def modo_watch(headless: bool = False):
    """
    Loop inteligente:
    - Sáb-Dom de 9:00 a 22:00: cada 5 min
    - Vie de 18:00 a 23:00: cada 5 min
    - Resto: cada 30 min (solo comprueba, no scrapea si no hay pendientes)
    """
    logger.info("🔄 Modo watch activado — buscando resultados automáticamente")
    
    while True:
        ahora = datetime.now()
        es_finde = ahora.weekday() in (5, 6)    # Sáb, Dom
        es_viernes = ahora.weekday() == 4         # Viernes
        hora = ahora.hour

        # Determinar si estamos en horario de partidos
        en_horario = False
        if es_finde and 9 <= hora <= 22:
            en_horario = True
        elif es_viernes and 18 <= hora <= 23:
            en_horario = True
        elif hora >= 18 and hora <= 22:
            en_horario = True  # Entre semana por la tarde

        if en_horario:
            # Scraping activo
            try:
                actualizados = await actualizar_resultados(headless=headless)
                if actualizados > 0:
                    logger.info(f"🔔 ¡{actualizados} resultado(s) nuevo(s)!")
            except Exception as e:
                logger.error(f"❌ Error: {e}")
            intervalo = 5  # 5 minutos
        else:
            # Solo comprobar (sin abrir navegador)
            pendientes = buscar_partidos_pendientes()
            if pendientes:
                logger.info(f"⏳ {len(pendientes)} pendiente(s), pero fuera de horario. Esperando...")
                intervalo = 30
            else:
                logger.info("✅ Sin partidos pendientes")
                intervalo = 30

        logger.info(f"⏰ Próxima comprobación en {intervalo} min")
        await asyncio.sleep(intervalo * 60)


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="⚡ Scraper rápido de resultados ADESA 80 — actualiza solo partidos terminados"
    )
    parser.add_argument("--watch", action="store_true",
                        help="Modo automático: loop cada 5 min en horario de partidos")
    parser.add_argument("--check", action="store_true",
                        help="Solo mostrar partidos pendientes (sin scraping)")
    parser.add_argument("--headless", action="store_true",
                        help="Modo headless (puede fallar con Cloudflare)")
    args = parser.parse_args()

    if args.watch:
        asyncio.run(modo_watch(headless=args.headless))
    else:
        asyncio.run(actualizar_resultados(headless=args.headless, check_only=args.check))


if __name__ == "__main__":
    main()
