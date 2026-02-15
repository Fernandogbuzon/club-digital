#!/usr/bin/env python3
"""
Scraper Rápido de Resultados (reutilizable)
==========================================
Detecta partidos del equipo configurado en team_config.json que deberían
haber terminado (hora inicio + duración) pero aún no tienen resultado,
y scrapea SOLO esos grupos específicos.

Lógica de reintentos (max configurable):
  - Intento 1: hora_partido + duración
  - Intento 2: +10 min (llamado de nuevo por el disparador)
  - Intento 3: +10 min más
  - Si al último intento no hay resultado, se rinde (aplazado/no jugado)

Estado de intentos guardado en intentos_resultados.json

Uso:
  python scraper_resultados.py                # Una pasada (scraping)
  python scraper_resultados.py --check        # Solo mostrar pendientes (sin navegador)
  python scraper_resultados.py --headless     # Intentar headless
  python scraper_resultados.py --reset        # Limpiar estado de intentos
"""

import asyncio
import json
import re
import sys
import io
import argparse
import random
import logging
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# ─── Configuracion (desde team_config.json) ─────────────────────────────

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
DURACION_PARTIDO_HORAS = _CFG.get("match_duration_hours", 1)
MAX_INTENTOS = _CFG.get("max_retry_attempts", 5)
RETRY_INTERVAL_MIN = _CFG.get("retry_interval_minutes", 10)

DATA_BASE_DIR = SCRIPT_DIR / "src" / "data"
LOG_DIR = SCRIPT_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Fichero de estado de intentos
INTENTOS_FILE = SCRIPT_DIR / "intentos_resultados.json"

# Mapa carpeta → URL (generado por scraper_competicion.py)
COMP_URL_MAP_FILE = SCRIPT_DIR / "comp_url_map.json"

def cargar_comp_url_map() -> dict:
    """Carga el mapa carpeta → URL generado por scraper_competicion.py"""
    if COMP_URL_MAP_FILE.exists():
        try:
            return json.loads(COMP_URL_MAP_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    logger.warning(f"No se encontró {COMP_URL_MAP_FILE}. Ejecuta primero scraper_competicion.py")
    return {}

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

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "scraper_resultados.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


# ─── Estado de intentos ──────────────────────────────────────────────────────

def cargar_intentos() -> dict:
    """Carga el fichero de intentos. Formato: { "partido_id": { "intentos": N, "ultimo": "ISO" } }"""
    if INTENTOS_FILE.exists():
        try:
            data = json.loads(INTENTOS_FILE.read_text(encoding="utf-8"))
            # Limpiar entradas de mas de 48h (partidos viejos)
            ahora = datetime.now()
            cleaned = {}
            for pid, info in data.items():
                ultimo = datetime.fromisoformat(info.get("ultimo", "2000-01-01"))
                if (ahora - ultimo).total_seconds() < 48 * 3600:
                    cleaned[pid] = info
            return cleaned
        except Exception:
            return {}
    return {}


def guardar_intentos(intentos: dict):
    INTENTOS_FILE.write_text(json.dumps(intentos, ensure_ascii=False, indent=2), encoding="utf-8")


def resetear_intentos():
    if INTENTOS_FILE.exists():
        INTENTOS_FILE.unlink()
    logger.info("Intentos reseteados")


# ─── Utilidades ──────────────────────────────────────────────────────────────

def parse_fecha(fecha_str: str, hora_str: str) -> datetime:
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


def normalizar_nombre(nombre: str) -> str:
    """Normaliza un nombre de equipo para comparación robusta.
    Quita acentos, pasa a minúsculas, elimina espacios extra."""
    s = unicodedata.normalize("NFD", nombre)
    s = s.encode("ascii", "ignore").decode("ascii")
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s


def nombres_coinciden(nombre_json: str, nombre_web: str) -> bool:
    """Compara nombres de equipos de forma flexible.
    Los patrocinadores rotan (ej: 'ISAVAL CBA' → 'NOATUM LOGISTIC CBA'),
    así que hacemos matching parcial inteligente."""
    a = normalizar_nombre(nombre_json)
    b = normalizar_nombre(nombre_web)

    # Exacto
    if a == b:
        return True

    # Uno contenido en el otro (ej: 'CBA' en 'ISAVAL CBA')
    if a in b or b in a:
        return True

    # Comparar últimas palabras (el "nombre base" del club suele ir al final)
    # Ej: "ISAVAL CBA" → "CBA", "NOATUM LOGISTIC CBA" → "CBA"
    palabras_a = a.split()
    palabras_b = b.split()
    if len(palabras_a) >= 1 and len(palabras_b) >= 1:
        # Última palabra igual (el nombre del club)
        if palabras_a[-1] == palabras_b[-1] and len(palabras_a[-1]) >= 3:
            return True
        # Últimas 2 palabras iguales
        if len(palabras_a) >= 2 and len(palabras_b) >= 2:
            if palabras_a[-2:] == palabras_b[-2:]:
                return True

    # Primeras palabras iguales (ej: "SD CANDRAY ..." → "SD CANDRAY")
    if len(palabras_a) >= 2 and len(palabras_b) >= 2:
        if palabras_a[:2] == palabras_b[:2]:
            return True

    # Ratio de similitud con SequenceMatcher
    from difflib import SequenceMatcher
    ratio = SequenceMatcher(None, a, b).ratio()
    if ratio >= 0.6:
        return True

    return False


# ─── Detectar partidos pendientes ────────────────────────────────────────────

def buscar_partidos_pendientes() -> list[dict]:
    """
    Escanea JSON del equipo (TEAM_SLUG). Devuelve partidos:
    - Sin resultado + hora+duración < ahora + intentos < MAX_INTENTOS
    """
    ahora = datetime.now()
    intentos = cargar_intentos()
    pendientes = []
    archivos_revisados = 0
    descartados = 0
    glob_pattern = f"{TEAM_SLUG}*.json"

    for json_path in DATA_BASE_DIR.rglob(glob_pattern):
        archivos_revisados += 1
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                continue
        except Exception:
            continue

        for partido in data:
            if partido.get("es_resultado"):
                continue

            fecha_str = partido.get("fecha", "")
            hora_str = partido.get("hora", "")
            if not fecha_str:
                continue

            dt_inicio = parse_fecha(fecha_str, hora_str)
            dt_fin_estimado = dt_inicio + timedelta(hours=DURACION_PARTIDO_HORAS)

            if dt_fin_estimado >= ahora:
                continue

            pid = partido.get("id", "")
            if not pid:
                continue

            info = intentos.get(pid, {})
            n_intentos = info.get("intentos", 0)
            if n_intentos >= MAX_INTENTOS:
                descartados += 1
                continue

            rel = json_path.relative_to(DATA_BASE_DIR)
            parts = rel.parts
            if len(parts) < 5:
                continue

            pendientes.append({
                "partido": partido,
                "json_path": str(json_path),
                "comp_carpeta": parts[0],
                "cat_carpeta": parts[1],
                "grupo_carpeta": parts[2],
                "fase_carpeta": parts[3],
                "dt_inicio": dt_inicio,
                "pid": pid,
                "intento": n_intentos + 1,
            })

    logger.info(f"Revisados {archivos_revisados} archivos de {TEAM_NAME}")
    if descartados:
        logger.info(f"  {descartados} descartado(s) (max {MAX_INTENTOS} intentos)")
    return pendientes


def agrupar_por_grupo(pendientes: list[dict]) -> dict[str, list[dict]]:
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
            logger.info("  CF challenge, esperando...")
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
        logger.warning(f"  Navigation: {e}")
    ok = await esperar_pagina(page, timeout=60000)
    await pausa(0.5, 1.2)
    return ok


async def extraer_partidos_pagina(page) -> list[dict]:
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


# ─── Match dropdown to folder ───────────────────────────────────────────────

def match_opcion_a_carpeta(opciones: list[dict], carpeta: str) -> Optional[str]:
    """Busca la opción del dropdown que mejor coincide con el nombre de carpeta.
    Prioriza exacto > exacto sin acentos > mejor substring."""
    def strip_accents(s):
        return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode("ascii").lower().strip()

    carpeta_norm = carpeta.replace("-", " ").lower().strip()
    carpeta_ascii = strip_accents(carpeta.replace("-", " "))

    # Paso 1: Match exacto (con y sin acentos)
    for opt in opciones:
        opt_norm = opt["text"].lower().strip()
        if opt_norm == carpeta_norm:
            return opt["value"]
    for opt in opciones:
        if strip_accents(opt["text"]) == carpeta_ascii:
            return opt["value"]

    # Paso 2: Substring match - buscar el MEJOR match (más largo overlap)
    best_match = None
    best_score = 0
    for opt in opciones:
        opt_ascii = strip_accents(opt["text"])
        # Solo match si la carpeta está contenida en la opción
        # (no al revés, para evitar 'grupo a' matcheando 'grupo ascenso')
        if carpeta_ascii == opt_ascii:
            return opt["value"]
        # Substring: carpeta contenida en opción, y la longitud es similar
        if carpeta_ascii in opt_ascii:
            score = len(carpeta_ascii) / max(len(opt_ascii), 1)
            if score > best_score:
                best_score = score
                best_match = opt["value"]
        elif opt_ascii in carpeta_ascii:
            score = len(opt_ascii) / max(len(carpeta_ascii), 1)
            if score > best_score:
                best_score = score
                best_match = opt["value"]

    if best_match and best_score >= 0.5:
        return best_match

    return None


# ─── Scraping dirigido de un grupo ──────────────────────────────────────────

async def scrape_grupo(page, comp_url, cat_carpeta, fase_carpeta, grupo_carpeta) -> list[dict]:
    page_url = page.url or ""
    comp_base = comp_url.split("/delegacion-competicion")[0] if "/delegacion-competicion" in comp_url else ""

    if comp_base not in page_url:
        logger.info(f"  Navegando a: {comp_url}")
        await page.goto(comp_url, wait_until="domcontentloaded", timeout=60000)
        if not await esperar_pagina(page, timeout=60000):
            logger.error("  No se pudo cargar la pagina")
            return []
        await pausa(1.5, 3.0)

    # Categoria
    cats = await obtener_opciones(page, SEL_CAT)
    cats = [c for c in cats if c["value"]]
    cat_value = match_opcion_a_carpeta(cats, cat_carpeta)
    if not cat_value:
        logger.error(f"  Categoria '{cat_carpeta}' no encontrada")
        return []

    logger.info(f"  Categoria: {cat_carpeta}")
    if not await seleccionar_dropdown(page, SEL_CAT, DDL_CATEGORIAS, cat_value):
        return []

    # Fase
    fases = await obtener_opciones(page, SEL_FASE)
    fases = [f for f in fases if f["value"]]
    fase_value = match_opcion_a_carpeta(fases, fase_carpeta)
    if not fase_value:
        fase_value = fases[0]["value"] if len(fases) == 1 else None
    if not fase_value:
        logger.error(f"  Fase '{fase_carpeta}' no encontrada")
        return []

    logger.info(f"  Fase: {fase_carpeta}")
    if not await seleccionar_dropdown(page, SEL_FASE, DDL_FASES, fase_value):
        return []

    # Grupo
    grupos = await obtener_opciones(page, SEL_GRUPO)
    grupos = [g for g in grupos if g["value"]]
    grupo_value = match_opcion_a_carpeta(grupos, grupo_carpeta)
    if not grupo_value:
        grupo_value = grupos[0]["value"] if len(grupos) == 1 else None
    if not grupo_value:
        logger.error(f"  Grupo '{grupo_carpeta}' no encontrado")
        return []

    logger.info(f"  Grupo: {grupo_carpeta}")
    if not await seleccionar_dropdown(page, SEL_GRUPO, DDL_GRUPOS, grupo_value):
        return []

    # Tab calendario
    try:
        cal_tab = page.locator("#calendario-tab")
        if await cal_tab.count() > 0:
            aria = await cal_tab.get_attribute("aria-selected")
            if aria != "true":
                await cal_tab.click()
                await pausa(0.5, 1.0)
    except Exception:
        pass

    partidos = await extraer_partidos_pagina(page)
    logger.info(f"  Extraidos {len(partidos)} partidos del grupo")
    return partidos


# ─── Actualizar JSON ─────────────────────────────────────────────────────────

def actualizar_json(json_path: str, partidos_web: list[dict]) -> list[str]:
    """Devuelve lista de IDs actualizados."""
    path = Path(json_path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"  Error leyendo {path}: {e}")
        return []

    if not isinstance(data, list):
        return []

    ids_actualizados = []

    for partido in data:
        if partido.get("es_resultado"):
            continue

        for pw in partidos_web:
            if not pw["es_resultado"]:
                continue
            if pw["fecha"] != partido.get("fecha"):
                continue

            p_equipo = partido.get("equipo", "")
            p_rival = partido.get("rival", "")
            p_ubi = partido.get("ubicacion", "")

            match = False
            if p_ubi == "Local":
                # Nuestro equipo es local → comparar local(web) con equipo, visitante(web) con rival
                if nombres_coinciden(p_equipo, pw["local"]) and nombres_coinciden(p_rival, pw["visitante"]):
                    match = True
                elif nombres_coinciden(p_equipo, pw["local"]):
                    logger.debug(f"  Equipo OK pero rival NO: JSON='{p_rival}' WEB='{pw['visitante']}'")
            elif p_ubi == "Visitante":
                # Nuestro equipo es visitante
                if nombres_coinciden(p_equipo, pw["visitante"]) and nombres_coinciden(p_rival, pw["local"]):
                    match = True
                elif nombres_coinciden(p_equipo, pw["visitante"]):
                    logger.debug(f"  Equipo OK pero rival NO: JSON='{p_rival}' WEB='{pw['local']}'")

            if not match and nombres_coinciden(p_equipo, pw["local"] if p_ubi == "Local" else pw["visitante"]):
                # Fallback: si nuestro equipo coincide + misma fecha + misma jornada → match
                pw_jornada = pw.get("jornada", "")
                p_jornada = partido.get("jornada", "")
                if pw_jornada and p_jornada and normalizar_nombre(pw_jornada) == normalizar_nombre(p_jornada):
                    logger.info(f"  MATCH por jornada: JSON rival='{p_rival}' WEB rival='{pw['local'] if p_ubi == 'Visitante' else pw['visitante']}' (jornada: {p_jornada})")
                    match = True

            if match:
                logger.info(f"  RESULTADO: {pw['local']} {pw['marcador_local']}-{pw['marcador_visitante']} {pw['visitante']}")
                partido["marcador_local"] = pw["marcador_local"]
                partido["marcador_visitante"] = pw["marcador_visitante"]
                partido["es_resultado"] = True
                partido["estado"] = "finalizado"
                if pw.get("hora"):
                    partido["hora"] = pw["hora"]
                if pw.get("pabellon"):
                    partido["pabellon"] = pw["pabellon"]
                ids_actualizados.append(partido.get("id", ""))
                break

    if ids_actualizados:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"  Guardado {path.name}: {len(ids_actualizados)} resultado(s)")

    return ids_actualizados


def marcar_estado_sin_resultado(json_path: str, pid: str, partidos_web: list[dict]):
    """
    Marca un partido sin resultado tras agotar los {MAX_INTENTOS} intentos.
    
    Lógica para diferenciar Aplazado vs Esperando resultado:
    - Si otros partidos de la MISMA fecha en la web SÍ tienen resultado
      → nuestro partido probablemente fue aplazado/suspendido → "Aplazado"
    - Si la mayoría de partidos de esa fecha tampoco tienen resultado
      → probablemente aún no lo han publicado → "Esperando resultado"
    """
    path = Path(json_path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return

    if not isinstance(data, list):
        return

    modified = False
    for partido in data:
        if partido.get("id") != pid:
            continue
        if partido.get("es_resultado"):
            break

        fecha_partido = partido.get("fecha", "")

        # Buscar cuántos partidos de la misma fecha tienen resultado en la web
        misma_fecha = [p for p in partidos_web if p.get("fecha") == fecha_partido]
        con_resultado = [p for p in misma_fecha if p.get("es_resultado")]

        if len(misma_fecha) > 0 and len(con_resultado) >= len(misma_fecha) * 0.5:
            # La mayoría de partidos de esa fecha tienen resultado → aplazado
            partido["estado"] = "aplazado"
            logger.info(f"  APLAZADO: {partido.get('equipo','?')} vs {partido.get('rival','?')} "
                       f"({len(con_resultado)}/{len(misma_fecha)} partidos de esa fecha con resultado)")
        else:
            # Pocos o ningún resultado publicado → esperando
            partido["estado"] = "esperando_resultado"
            logger.info(f"  ESPERANDO RESULTADO: {partido.get('equipo','?')} vs {partido.get('rival','?')} "
                       f"({len(con_resultado)}/{len(misma_fecha)} partidos con resultado)")
        modified = True
        break

    if modified:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ─── Pipeline principal ──────────────────────────────────────────────────────

async def actualizar_resultados(headless: bool = False, check_only: bool = False) -> int:
    logger.info("=" * 60)
    logger.info(f"SCRAPER RAPIDO DE RESULTADOS -- {TEAM_NAME}")
    logger.info(f"{datetime.now().strftime('%d/%m/%Y %H:%M')}")
    logger.info("=" * 60)

    pendientes = buscar_partidos_pendientes()

    if not pendientes:
        logger.info("No hay partidos pendientes de resultado.")
        return 0

    logger.info(f"\n{len(pendientes)} partido(s) pendiente(s):")
    for p in pendientes:
        pt = p["partido"]
        logger.info(f"  [{p['intento']}/{MAX_INTENTOS}] {pt.get('equipo','?')} vs {pt.get('rival','?')} "
                     f"({pt.get('fecha','?')} {pt.get('hora','?')}) -- {p['cat_carpeta']}")

    if check_only:
        logger.info("\n(modo --check: no se realiza scraping)")
        return len(pendientes)

    grupos = agrupar_por_grupo(pendientes)
    logger.info(f"\n{len(grupos)} grupo(s) a scrapear")

    pw_inst, browser, context, page = await crear_browser(headless=headless)
    total_actualizados = 0
    intentos = cargar_intentos()
    comp_url_map = cargar_comp_url_map()

    try:
        for key, partidos_grupo in grupos.items():
            comp_carpeta, cat_carpeta, grupo_carpeta, fase_carpeta = key.split("|")

            comp_url = comp_url_map.get(comp_carpeta)
            if not comp_url:
                logger.warning(f"  Competicion '{comp_carpeta}' sin URL. Saltando.")
                continue

            logger.info(f"\n{'─' * 50}")
            logger.info(f"  {comp_carpeta} / {cat_carpeta} / {grupo_carpeta}")

            try:
                partidos_web = await scrape_grupo(
                    page, comp_url, cat_carpeta, fase_carpeta, grupo_carpeta
                )
            except Exception as e:
                logger.error(f"  Error scraping: {e}")
                try:
                    await page.goto("about:blank")
                    await pausa(1.0, 2.0)
                except Exception:
                    pass
                for p in partidos_grupo:
                    info = intentos.get(p["pid"], {"intentos": 0})
                    info["intentos"] = info.get("intentos", 0) + 1
                    info["ultimo"] = datetime.now().isoformat()
                    intentos[p["pid"]] = info
                continue

            if not partidos_web:
                for p in partidos_grupo:
                    info = intentos.get(p["pid"], {"intentos": 0})
                    info["intentos"] = info.get("intentos", 0) + 1
                    info["ultimo"] = datetime.now().isoformat()
                    intentos[p["pid"]] = info
                continue

            con_resultado = [p for p in partidos_web if p["es_resultado"]]
            logger.info(f"  Web: {len(partidos_web)} partidos ({len(con_resultado)} con resultado)")

            json_paths_vistos = set()
            ids_encontrados = set()
            for p in partidos_grupo:
                jp = p["json_path"]
                if jp not in json_paths_vistos:
                    json_paths_vistos.add(jp)
                    ids = actualizar_json(jp, partidos_web)
                    ids_encontrados.update(ids)
                    total_actualizados += len(ids)

            for p in partidos_grupo:
                pid = p["pid"]
                if pid in ids_encontrados:
                    intentos.pop(pid, None)
                else:
                    info = intentos.get(pid, {"intentos": 0})
                    info["intentos"] = info.get("intentos", 0) + 1
                    info["ultimo"] = datetime.now().isoformat()
                    intentos[pid] = info
                    n = info["intentos"]
                    pt = p["partido"]
                    if n >= MAX_INTENTOS:
                        logger.info(f"  RENDIDO ({n}/{MAX_INTENTOS}): {pt.get('equipo','?')} vs {pt.get('rival','?')}")
                        # Marcar como Aplazado o Esperando resultado según contexto
                        marcar_estado_sin_resultado(p["json_path"], pid, partidos_web)
                    else:
                        logger.info(f"  Sin resultado ({n}/{MAX_INTENTOS}). Se reintentara en ~{RETRY_INTERVAL_MIN}min.")

            await pausa(1.0, 2.0)

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
    finally:
        await browser.close()
        await pw_inst.stop()
        guardar_intentos(intentos)

    logger.info(f"\n{'=' * 60}")
    logger.info(f"RESUMEN: {total_actualizados} resultado(s) de {len(pendientes)} pendiente(s)")
    logger.info(f"{'=' * 60}")
    return total_actualizados


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=f"Scraper rapido de resultados {TEAM_NAME} (max {MAX_INTENTOS} intentos)"
    )
    parser.add_argument("--check", action="store_true",
                        help="Solo mostrar pendientes (sin scraping)")
    parser.add_argument("--headless", action="store_true",
                        help="Modo headless")
    parser.add_argument("--reset", action="store_true",
                        help="Limpiar estado de intentos")
    args = parser.parse_args()

    if args.reset:
        resetear_intentos()
        return

    asyncio.run(actualizar_resultados(headless=args.headless, check_only=args.check))


if __name__ == "__main__":
    main()
