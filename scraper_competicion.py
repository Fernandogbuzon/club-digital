#!/usr/bin/env python3
"""
Scraper Competiciones – Federación Andaluza de Baloncesto (Cádiz)
================================================================
Extrae calendario completo + clasificaciones de TODAS las competiciones,
categorías, fases y grupos.

Estrategia:
  • Playwright en modo headed (necesario para que Cloudflare auto-resuelva
    sus challenges).
  • stealth para enmascarar la automatización.
  • __doPostBack nativo del ASP.NET para cambiar filtros.
  • Pausas aleatorias entre interacciones.

Carpetas de salida:
  src/data/<Competición>/<Categoría>/<Grupo>/<Fase>/
    ├── equipo-1.json
    ├── equipo-2.json
    └── clasificacion.json

Uso:
  python scraper_competicion.py                                   # Todas las competiciones
  python scraper_competicion.py --competicion "copa andalucia a"   # Filtrar competición
  python scraper_competicion.py --categoria "Senior Fem"           # Filtrar categoría
  python scraper_competicion.py --watch                            # Modo cron
  python scraper_competicion.py --headless                         # Intentar headless
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

# ─── Configuración (desde team_config.json) ─────────────────────────────────

SCRIPT_DIR = Path(__file__).parent
CONFIG_FILE = SCRIPT_DIR / "team_config.json"

def cargar_config() -> dict:
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(
            f"No se encontró {CONFIG_FILE}. "
            "Copia team_config.example.json → team_config.json y ajústalo a tu equipo."
        )
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))

_CFG = cargar_config()
TEAM_NAME = _CFG["team_name"]
TEAM_SLUG = _CFG["team_slug"]
COMPETICIONES = _CFG["competitions"]

# ASP.NET dropdown names (para __doPostBack)
DDL_CATEGORIAS = "ctl00$ctl00$contenedor_informacion$contenedor_informacion_con_lateral$DDLCategorias"
DDL_FASES = "ctl00$ctl00$contenedor_informacion$contenedor_informacion_con_lateral$DDLFases"
DDL_GRUPOS = "ctl00$ctl00$contenedor_informacion$contenedor_informacion_con_lateral$DDLGrupos"

# CSS selectors
SEL_CAT = f"select[name='{DDL_CATEGORIAS}']"
SEL_FASE = f"select[name='{DDL_FASES}']"
SEL_GRUPO = f"select[name='{DDL_GRUPOS}']"

DATA_BASE_DIR = SCRIPT_DIR / "src" / "data"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
]

# ─── Logging ─────────────────────────────────────────────────────────────────

LOG_DIR = SCRIPT_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "scraper_competicion.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


# ─── Utilidades ──────────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    text = unicodedata.normalize("NFD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    text = re.sub(r"[-\s]+", "-", text)
    return text


def normalizar_carpeta(nombre: str) -> str:
    nombre = re.sub(r"\s+", " ", nombre).strip()
    return re.sub(r"\s", "-", nombre)


def generar_id(fecha: str, local: str, visitante: str, categoria: str) -> str:
    return slugify(f"{fecha}_{local}_{visitante}_{categoria}")


def _fecha_sort(f: str) -> str:
    try:
        p = f.split("/")
        return f"{p[2]}{p[1]}{p[0]}" if len(p) == 3 else "00000000"
    except Exception:
        return "00000000"


async def pausa(lo: float = 0.8, hi: float = 2.5):
    await asyncio.sleep(random.uniform(lo, hi))


# ─── Browser helpers ─────────────────────────────────────────────────────────

async def crear_browser(headless: bool = False):
    from playwright.async_api import async_playwright
    from playwright_stealth import Stealth

    pw = await async_playwright().start()
    browser = await pw.chromium.launch(
        headless=headless,
        args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
        ],
    )
    stealth = Stealth()
    context = await browser.new_context(
        user_agent=random.choice(USER_AGENTS),
        viewport={"width": 1366, "height": 768},
        locale="es-ES",
        timezone_id="Europe/Madrid",
        extra_http_headers={
            "Accept-Language": "es-ES,es;q=0.9,en-US;q=0.8,en;q=0.7",
        },
    )
    await stealth.apply_stealth_async(context)
    page = await context.new_page()
    return pw, browser, context, page


async def esperar_pagina(page, timeout: int = 45000) -> bool:
    """Espera a que la página real cargue (selector de categoría visible)."""
    try:
        await page.wait_for_selector(SEL_CAT, timeout=timeout)
        return True
    except Exception:
        title = await page.title()
        if "moment" in title.lower() or "momento" in title.lower():
            logger.info("  ⏳ Challenge CF detectado, esperando resolución...")
            try:
                await page.wait_for_selector(SEL_CAT, timeout=90000)
                return True
            except Exception:
                logger.error("  ❌ CF challenge no se resolvió")
                return False
        return False


async def obtener_opciones(page, selector: str) -> list[dict]:
    """Lee las opciones de un <select> en la página."""
    return await page.eval_on_selector_all(
        selector + " option",
        "opts => opts.map(o => ({value: o.value, text: o.textContent.trim().replace(/\\s+/g, ' ')}))",
    )


async def seleccionar_dropdown(page, selector: str, ddl_name: str, value: str):
    """Selecciona valor en dropdown y espera la navegación del postback ASP.NET."""
    await page.evaluate("() => { window.__cFRLUnblockHandlers = true; }")
    try:
        async with page.expect_navigation(wait_until="domcontentloaded", timeout=60000):
            await page.select_option(selector, value)
    except Exception as e:
        logger.warning(f"  ⚠️ Navigation timeout/error: {e}")
    ok = await esperar_pagina(page, timeout=60000)
    if not ok:
        logger.error(f"  Error tras postback de {ddl_name}")
    await pausa(1.0, 2.5)
    return ok


# ─── Extracción de partidos ──────────────────────────────────────────────────

async def extraer_partidos(page, categoria: str, fase: str, grupo: str, competicion_nombre: str = "") -> list[dict]:
    """Extrae todos los partidos del calendario visible."""
    return await page.evaluate("""
        (params) => {
            const { categoria, fase, grupo, competicion } = params;
            const resultados = [];

            const calendarioTab = document.getElementById('calendario');
            if (!calendarioTab) return resultados;

            const headers = calendarioTab.querySelectorAll('header.nombre_tabla');

            headers.forEach(header => {
                const h5 = header.querySelector('h5');
                const jornadaText = h5 ? h5.textContent.trim().replace(/\\s+/g, ' ') : '';

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
                        jornada: jornadaText,
                        categoria_completa: `${categoria} - ${fase} - ${grupo}`,
                        fase, grupo, competicion
                    });
                });
            });

            return resultados;
        }
    """, {
        "categoria": categoria,
        "fase": fase,
        "grupo": grupo,
        "competicion": competicion_nombre,
    })


# ─── Agrupación y clasificación ──────────────────────────────────────────────

def agrupar_por_equipo(partidos: list[dict]) -> dict[str, list[dict]]:
    equipos: dict[str, list[dict]] = {}
    for p in partidos:
        loc, vis = p["local"], p["visitante"]
        if "DESCANSA" in loc or "DESCANSA" in vis:
            continue
        base = {
            "competicion": p["competicion"],
            "marcador_local": p["marcador_local"],
            "marcador_visitante": p["marcador_visitante"],
            "fecha": p["fecha"], "hora": p["hora"],
            "pabellon": p["pabellon"],
            "es_resultado": p["es_resultado"],
            "estado": "finalizado" if p["es_resultado"] else "proximo",
            "jornada": p["jornada"],
        }
        equipos.setdefault(loc, []).append({
            **base, "categoria": p["categoria_completa"],
            "equipo": loc, "rival": vis, "ubicacion": "Local",
            "id": generar_id(p["fecha"], loc, vis, p["categoria_completa"]),
        })
        equipos.setdefault(vis, []).append({
            **base, "categoria": p["categoria_completa"],
            "equipo": vis, "rival": loc, "ubicacion": "Visitante",
            "id": generar_id(p["fecha"], loc, vis, p["categoria_completa"]),
        })
    return equipos


def calcular_clasificacion(partidos: list[dict], cat: str, fase: str, grupo: str, competicion_nombre: str = "") -> dict:
    stats: dict[str, dict] = {}
    for p in partidos:
        if not p["es_resultado"]:
            continue
        loc, vis = p["local"], p["visitante"]
        if "DESCANSA" in loc or "DESCANSA" in vis:
            continue
        ml, mv = p["marcador_local"], p["marcador_visitante"]
        if ml is None or mv is None:
            continue

        for eq in (loc, vis):
            if eq not in stats:
                stats[eq] = {"equipo": eq, "partidos_jugados": 0, "partidos_ganados": 0,
                             "partidos_perdidos": 0, "puntos_favor": 0, "puntos_contra": 0,
                             "diferencia": 0, "puntos": 0}

        stats[loc]["partidos_jugados"] += 1
        stats[loc]["puntos_favor"] += ml
        stats[loc]["puntos_contra"] += mv
        stats[vis]["partidos_jugados"] += 1
        stats[vis]["puntos_favor"] += mv
        stats[vis]["puntos_contra"] += ml

        if ml > mv:
            stats[loc]["partidos_ganados"] += 1
            stats[loc]["puntos"] += 2
            stats[vis]["partidos_perdidos"] += 1
            stats[vis]["puntos"] += 1
        elif mv > ml:
            stats[vis]["partidos_ganados"] += 1
            stats[vis]["puntos"] += 2
            stats[loc]["partidos_perdidos"] += 1
            stats[loc]["puntos"] += 1

    clasificacion = list(stats.values())
    for eq in clasificacion:
        eq["diferencia"] = eq["puntos_favor"] - eq["puntos_contra"]
    clasificacion.sort(key=lambda x: (-x["puntos"], -x["diferencia"], -x["puntos_favor"]))
    for i, eq in enumerate(clasificacion, 1):
        eq["posicion"] = i

    return {
        "categoria": f"{cat} - {fase} - {grupo}",
        "competicion": competicion_nombre,
        "ultima_actualizacion": datetime.now().isoformat(),
        "clasificacion": clasificacion,
    }


# ─── Guardado ────────────────────────────────────────────────────────────────

def guardar(por_equipo: dict, clasif: dict, cat: str, grupo: str, fase: str, data_dir: Path = None):
    d = data_dir / normalizar_carpeta(cat) / normalizar_carpeta(grupo) / normalizar_carpeta(fase)
    d.mkdir(parents=True, exist_ok=True)

    for equipo, partidos in por_equipo.items():
        fn = slugify(equipo) + ".json"
        partidos.sort(key=lambda x: _fecha_sort(x.get("fecha", "")), reverse=True)
        (d / fn).write_text(json.dumps(partidos, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"      ✅ {fn}: {len(partidos)} partidos")

    (d / "clasificacion.json").write_text(
        json.dumps(clasif, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info(f"      📊 clasificacion.json: {len(clasif.get('clasificacion', []))} equipos")


# ─── Nombre de competición desde la página ──────────────────────────────────

def nombre_competicion_desde_url(url: str) -> str:
    """Extrae un nombre legible del slug de la URL como fallback."""
    from urllib.parse import unquote
    slug = unquote(url.rstrip("/").split("/")[-1])
    return slug.replace("-", " ").title()


async def obtener_nombre_competicion(page) -> str:
    """Lee el título de la competición del <h1> de la página."""
    try:
        h1 = await page.eval_on_selector(
            "h1, .titulo_seccion h2, .titulo_seccion h1",
            "el => el.textContent.trim().replace(/\\s+/g, ' ')"
        )
        if h1:
            return h1
    except Exception:
        pass
    return ""


def carpeta_competicion(nombre: str) -> str:
    """Convierte nombre de competición a nombre de carpeta."""
    nombre = re.sub(r"\s+", " ", nombre).strip()
    # Capitalizar palabras, reemplazar espacios por guiones
    return re.sub(r"\s", "-", nombre)


# ─── Scraper de una competición ──────────────────────────────────────────────

async def scrape_una_competicion(
    page, url: str, filtro_cat: Optional[str] = None
) -> tuple[int, int, str]:
    """Scrapea una competición completa. Devuelve (total_partidos, total_archivos, comp_carpeta)."""

    logger.info(f"📡 Navegando a {url}")
    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
    if not await esperar_pagina(page, timeout=60000):
        logger.error("❌ No se pudo cargar la página")
        return 0, 0
    await pausa(2.0, 4.0)

    # Obtener nombre real de la competición
    comp_nombre = await obtener_nombre_competicion(page)
    if not comp_nombre:
        comp_nombre = nombre_competicion_desde_url(url)
    comp_carpeta = carpeta_competicion(comp_nombre)
    data_dir = DATA_BASE_DIR / comp_carpeta

    logger.info(f"🏆 COMPETICIÓN: {comp_nombre}")
    logger.info(f"📂 Carpeta: {comp_carpeta}")

    # Leer categorías
    categorias = await obtener_opciones(page, SEL_CAT)
    categorias = [c for c in categorias if c["value"]]
    logger.info(f"📋 Categorías: {len(categorias)}")
    for c in categorias:
        logger.info(f"   - {c['text']}")

    if not categorias:
        logger.warning("⚠️ Sin categorías — puede que la página no tenga dropdowns")
        return 0, 0, comp_carpeta

    total_partidos = 0
    total_archivos = 0

    for cat_idx, cat in enumerate(categorias):
        cat_nombre = cat["text"]
        cat_value = cat["value"]

        if filtro_cat and filtro_cat.lower() not in cat_nombre.lower():
            continue

        logger.info(f"\n{'─' * 55}")
        logger.info(f"📂 CATEGORÍA: {cat_nombre}")

        ok = await seleccionar_dropdown(page, SEL_CAT, DDL_CATEGORIAS, cat_value)
        if not ok:
            logger.error(f"  ❌ No se pudo cambiar a {cat_nombre}")
            continue

        # Leer fases
        fases = await obtener_opciones(page, SEL_FASE)
        fases = [f for f in fases if f["value"]]
        logger.info(f"  📑 Fases: {[f['text'] for f in fases]}")

        if not fases:
            logger.warning(f"  ⚠️ Sin fases")
            continue

        for fase_idx, fase in enumerate(fases):
            fase_nombre = fase["text"]
            fase_value = fase["value"]
            logger.info(f"  📄 Fase: {fase_nombre}")

            ok = await seleccionar_dropdown(page, SEL_FASE, DDL_FASES, fase_value)
            if not ok:
                continue

            # Leer grupos
            grupos = await obtener_opciones(page, SEL_GRUPO)
            grupos = [g for g in grupos if g["value"]]
            logger.info(f"    📁 Grupos: {[g['text'] for g in grupos]}")

            if not grupos:
                logger.warning(f"    ⚠️ Sin grupos")
                continue

            for grupo_idx, grupo in enumerate(grupos):
                grupo_nombre = grupo["text"]
                grupo_value = grupo["value"]
                logger.info(f"    🏷️  Grupo: {grupo_nombre}")

                ok = await seleccionar_dropdown(page, SEL_GRUPO, DDL_GRUPOS, grupo_value)
                if not ok:
                    continue

                # Asegurar tab CALENDARIO activo
                try:
                    cal_tab = page.locator("#calendario-tab")
                    if await cal_tab.count() > 0:
                        aria = await cal_tab.get_attribute("aria-selected")
                        if aria != "true":
                            await cal_tab.click()
                            await pausa(0.5, 1.0)
                except Exception:
                    pass

                # Extraer partidos
                partidos = await extraer_partidos(
                    page, cat_nombre, fase_nombre, grupo_nombre, comp_nombre
                )
                if not partidos:
                    logger.warning(f"      ⚠️ Sin partidos")
                    continue

                logger.info(f"      📊 {len(partidos)} partidos")
                total_partidos += len(partidos)

                # Agrupar + clasificar + guardar
                por_equipo = agrupar_por_equipo(partidos)
                total_archivos += len(por_equipo)
                logger.info(f"      👥 {len(por_equipo)} equipos")

                clasif = calcular_clasificacion(
                    partidos, cat_nombre, fase_nombre, grupo_nombre, comp_nombre
                )
                guardar(por_equipo, clasif, cat_nombre, grupo_nombre, fase_nombre, data_dir)

                await pausa(0.8, 1.8)
            await pausa(1.0, 2.5)
        await pausa(2.0, 4.0)

    logger.info(f"\n  ✅ {comp_nombre}: {total_partidos} partidos, {total_archivos} archivos")
    return total_partidos, total_archivos, comp_carpeta


# ─── Scraper principal (todas las competiciones) ─────────────────────────────

async def scrape_todas(
    filtro_comp: Optional[str] = None,
    filtro_cat: Optional[str] = None,
    headless: bool = False,
):
    logger.info("=" * 60)
    logger.info(f"🏀 SCRAPER COMPETICIONES – {TEAM_NAME}")
    logger.info(f"📋 {len(COMPETICIONES)} competiciones registradas")
    logger.info("=" * 60)

    pw, browser, context, page = await crear_browser(headless=headless)

    gran_total_partidos = 0
    gran_total_archivos = 0
    resultados = []

    try:
        for comp_idx, url in enumerate(COMPETICIONES):
            # Filtrar por nombre de competición si se especificó
            if filtro_comp:
                slug = url.rstrip("/").split("/")[-1]
                from urllib.parse import unquote
                slug_decoded = unquote(slug).lower()
                if filtro_comp.lower() not in slug_decoded:
                    continue

            logger.info(f"\n{'═' * 60}")
            logger.info(f"🏆 [{comp_idx + 1}/{len(COMPETICIONES)}] {url}")
            logger.info(f"{'═' * 60}")

            try:
                tp, ta, comp_carpeta = await scrape_una_competicion(page, url, filtro_cat)
                gran_total_partidos += tp
                gran_total_archivos += ta
                resultados.append((url, tp, ta, "✅", comp_carpeta))
            except Exception as e:
                logger.error(f"❌ Error en competición: {e}", exc_info=True)
                resultados.append((url, 0, 0, f"❌ {e}", ""))
                # Renavegar a una página limpia para recuperar
                try:
                    await page.goto("about:blank")
                    await pausa(1.0, 2.0)
                except Exception:
                    pass

            await pausa(3.0, 6.0)

        # Resumen final
        logger.info(f"\n{'═' * 60}")
        logger.info("📊 RESUMEN FINAL")
        logger.info(f"{'═' * 60}")
        for url, tp, ta, status, _ in resultados:
            slug = url.rstrip("/").split("/")[-1]
            logger.info(f"  {status} {slug}: {tp} partidos, {ta} archivos")
        logger.info(f"{'─' * 60}")
        logger.info(f"  TOTAL: {gran_total_partidos} partidos, {gran_total_archivos} archivos")
        logger.info(f"  📂 {DATA_BASE_DIR}")
        logger.info(f"{'═' * 60}")

    except Exception as e:
        logger.error(f"❌ Error crítico: {e}", exc_info=True)
        raise
    finally:
        await browser.close()
        await pw.stop()

    # Generar comp_url_map.json (mapa carpeta → URL para el scraper de resultados)
    generar_comp_url_map(resultados)

    # Generar partidos_hoy.json para el disparador de resultados
    generar_partidos_hoy()


def generar_comp_url_map(resultados: list[tuple]):
    """
    Genera comp_url_map.json: mapea carpeta de competición → URL.
    Usado por scraper_resultados.py para saber qué URL abrir para cada grupo.
    """
    url_map = {}
    for url, tp, ta, status, comp_carpeta in resultados:
        if comp_carpeta:
            url_map[comp_carpeta] = url
    out = SCRIPT_DIR / "comp_url_map.json"
    out.write_text(json.dumps(url_map, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"🗺️ comp_url_map.json: {len(url_map)} competiciones mapeadas")


def generar_partidos_hoy():
    """
    Escanea todos los JSON del equipo (TEAM_SLUG) y genera partidos_hoy.json
    con los partidos de hoy que aún no tienen resultado.
    Usado por el workflow disparador para saber cuándo lanzar el scraper de resultados.
    """
    hoy = datetime.now().strftime("%d/%m/%Y")
    partidos_hoy = []
    glob_pattern = f"{TEAM_SLUG}*.json"

    for json_path in DATA_BASE_DIR.rglob(glob_pattern):
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                continue
        except Exception:
            continue

        rel = json_path.relative_to(DATA_BASE_DIR)
        parts = rel.parts
        if len(parts) < 5:
            continue

        for p in data:
            if p.get("es_resultado"):
                continue
            if p.get("fecha") == hoy:
                partidos_hoy.append({
                    "equipo": p.get("equipo", ""),
                    "rival": p.get("rival", ""),
                    "fecha": p.get("fecha", ""),
                    "hora": p.get("hora", ""),
                    "categoria": p.get("categoria", ""),
                    "ubicacion": p.get("ubicacion", ""),
                    "id": p.get("id", ""),
                    "comp_carpeta": parts[0],
                    "cat_carpeta": parts[1],
                    "grupo_carpeta": parts[2],
                    "fase_carpeta": parts[3],
                    "json_path": str(rel),
                })

    out = SCRIPT_DIR / "partidos_hoy.json"
    out.write_text(json.dumps(partidos_hoy, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"📅 partidos_hoy.json: {len(partidos_hoy)} partido(s) hoy ({hoy})")


# ─── Modo automático ─────────────────────────────────────────────────────────

async def modo_automatico(headless: bool = False, filtro_comp: Optional[str] = None):
    """
    Lun–Vie: cada 2 horas.
    Sáb–Dom 8:00–23:59: cada 30 minutos.
    """
    logger.info("🔄 Modo automático activado")
    while True:
        try:
            await scrape_todas(filtro_comp=filtro_comp, headless=headless)
        except Exception as e:
            logger.error(f"❌ Error: {e}")

        ahora = datetime.now()
        es_finde = ahora.weekday() in (5, 6)
        if es_finde and 8 <= ahora.hour < 24:
            intervalo = 30
        elif es_finde:
            proxima = ahora.replace(hour=8, minute=0, second=0)
            if proxima <= ahora:
                proxima += timedelta(days=1)
            intervalo = int((proxima - ahora).total_seconds() / 60)
        else:
            intervalo = 120

        logger.info(f"⏰ Próxima ejecución en {intervalo} min")
        await asyncio.sleep(intervalo * 60)


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Scraper Baloncesto Cádiz")
    parser.add_argument("--watch", action="store_true", help="Modo automático")
    parser.add_argument("--competicion", type=str, default=None,
                        help="Filtrar por nombre de competición (busca en el slug de la URL)")
    parser.add_argument("--categoria", type=str, default=None, help="Filtrar categoría")
    parser.add_argument("--headless", action="store_true", help="Modo headless (puede fallar con CF)")
    args = parser.parse_args()

    if args.watch:
        asyncio.run(modo_automatico(headless=args.headless, filtro_comp=args.competicion))
    else:
        asyncio.run(scrape_todas(
            filtro_comp=args.competicion,
            filtro_cat=args.categoria,
            headless=args.headless,
        ))


if __name__ == "__main__":
    main()
