import * as cheerio from 'cheerio';
import { writeFileSync, readFileSync, existsSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import puppeteer from 'puppeteer';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Configuración
const CONFIG = {
  url: 'https://www.andaluzabaloncesto.org/cadiz/resultados-club-196/adesa-80',
  timeout: 30000,
  retries: 1,
  outputPath: join(__dirname, '..', 'data', 'partidos.json'),
};

// Tipos
interface Partido {
  id: string;
  categoria: string;
  competicion: string;
  equipoLocal: string;
  equipoVisitante: string;
  fecha: string;
  hora?: string;
  pabellon: string;
  resultadoLocal?: number;
  resultadoVisitante?: number;
  estado: 'proximo' | 'en_curso' | 'finalizado';
  fechaActualizacion: string;
}

interface PartidosData {
  ultima_actualizacion: string;
  total_partidos: number;
  partidos: Partido[];
}

/**
 * Genera un ID único para el partido
 */
function generarIdPartido(partido: Omit<Partido, 'id' | 'estado' | 'fechaActualizacion'>): string {
  const base = `${partido.fecha}_${partido.categoria}_${partido.equipoLocal}_${partido.equipoVisitante}`
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/\s+/g, '_')
    .replace(/[^a-z0-9_]/g, '');
  
  return base;
}

/**
 * Determina el estado del partido basado en la información disponible
 */
function determinarEstado(
  fecha: string,
  hora: string | undefined,
  resultado: { local?: number; visitante?: number }
): 'proximo' | 'en_curso' | 'finalizado' {
  // Si tiene resultado, está finalizado
  if (resultado.local !== undefined && resultado.visitante !== undefined) {
    return 'finalizado';
  }

  // Si no tiene hora, es próximo
  if (!hora) {
    return 'proximo';
  }

  // Comparar con fecha actual
  try {
    const [dia, mes, anio] = fecha.split('/').map(Number);
    const [horas, minutos] = hora.split(':').map(Number);
    const fechaPartido = new Date(anio, mes - 1, dia, horas || 0, minutos || 0);
    const ahora = new Date();

    if (fechaPartido < ahora) {
      return 'finalizado';
    }
  } catch (error) {
    console.warn(`Error al parsear fecha/hora: ${fecha} ${hora}`);
  }

  return 'proximo';
}

/**
 * Extrae el resultado de una celda de partido
 */
function extraerResultado(texto: string): { local?: number; visitante?: number } {
  // Buscar patrón tipo "75-68" o "75 - 68"
  const match = texto.match(/(\d+)\s*-\s*(\d+)/);
  if (match) {
    return {
      local: parseInt(match[1], 10),
      visitante: parseInt(match[2], 10),
    };
  }
  return {};
}

/**
 * Determina qué equipo es local y cuál visitante
 */
function determinarEquipos(textoEquipos: string): { local: string; visitante: string } {
  // La web muestra: "EQUIPO_LOCAL EQUIPO_VISITANTE"
  // ADESA 80 suele estar en una de las posiciones
  const equipos = textoEquipos.split(/\s{2,}/).map(e => e.trim()).filter(e => e);
  
  if (equipos.length >= 2) {
    return {
      local: equipos[0],
      visitante: equipos[1],
    };
  }
  
  // Si solo hay un equipo visible, intentar separar por ADESA 80
  const partes = textoEquipos.split('ADESA 80');
  if (partes.length === 2) {
    const primerEquipo = partes[0].trim();
    const segundoEquipo = partes[1].trim();
    
    if (primerEquipo) {
      return { local: primerEquipo, visitante: 'ADESA 80' };
    } else {
      return { local: 'ADESA 80', visitante: segundoEquipo };
    }
  }
  
  // Fallback
  return {
    local: equipos[0] || 'Desconocido',
    visitante: equipos[1] || 'Desconocido',
  };
}

/**
 * Fetch con Puppeteer (para sitios con protección anti-bot)
 */
async function fetchConPuppeteer(url: string, timeout: number): Promise<string> {
  console.log('🤖 Usando Puppeteer para evitar protección anti-bot...');
  
  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });
  
  try {
    const page = await browser.newPage();
    
    // Configurar timeout
    page.setDefaultTimeout(timeout);
    
    // Simular navegador real
    await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36');
    await page.setViewport({ width: 1920, height: 1080 });
    
    // Navegar a la URL
    await page.goto(url, { waitUntil: 'networkidle2' });
    
    // Obtener HTML
    const html = await page.content();
    
    return html;
  } finally {
    await browser.close();
  }
}

/**
 * Fetch con timeout y retry
 */
async function fetchConTimeout(url: string, timeout: number, retries: number = 1): Promise<string> {
  let ultimoError: Error | null = null;
  let usoPuppeteer = false;
  
  for (let intento = 0; intento <= retries; intento++) {
    try {
      if (intento > 0) {
        console.log(`🔄 Reintento ${intento}/${retries}...`);
        await new Promise(resolve => setTimeout(resolve, 2000)); // Esperar 2s entre reintentos
      }
      
      // Si ya detectamos 403, usar Puppeteer directamente
      if (usoPuppeteer) {
        return await fetchConPuppeteer(url, timeout);
      }
      
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), timeout);
      
      const response = await fetch(url, {
        signal: controller.signal,
        headers: {
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
          'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
          'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
          'Accept-Encoding': 'gzip, deflate, br',
          'Connection': 'keep-alive',
          'Upgrade-Insecure-Requests': '1',
          'Sec-Fetch-Dest': 'document',
          'Sec-Fetch-Mode': 'navigate',
          'Sec-Fetch-Site': 'none',
          'Sec-Fetch-User': '?1',
          'Cache-Control': 'max-age=0',
        },
      });
      
      clearTimeout(timeoutId);
      
      if (!response.ok) {
        // Si es 403, cambiar a Puppeteer para el siguiente intento
        if (response.status === 403) {
          console.log('⚠️  Detectado HTTP 403, cambiando a Puppeteer...');
          usoPuppeteer = true;
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      return await response.text();
    } catch (error) {
      ultimoError = error as Error;
      console.error(`❌ Intento ${intento + 1} fallido:`, error instanceof Error ? error.message : error);
    }
  }
  
  // Si todos los intentos con fetch fallaron, intentar con Puppeteer una vez más
  if (!usoPuppeteer) {
    console.log('🔄 Último intento con Puppeteer...');
    try {
      return await fetchConPuppeteer(url, timeout);
    } catch (error) {
      console.error('❌ Puppeteer también falló:', error instanceof Error ? error.message : error);
    }
  }
  
  throw new Error(`Falló después de ${retries + 1} intentos: ${ultimoError?.message}`);
}

/**
 * Parsea el HTML y extrae los partidos
 */
function parsearPartidos(html: string): Partido[] {
  const $ = cheerio.load(html);
  const partidos: Partido[] = [];
  let competicionActual = '';
  
  // La web organiza los partidos en secciones por competición
  $('h4, table tbody tr').each((_, elem) => {
    const element = $(elem);
    
    // Detectar headers de competición
    if (elem.tagName === 'h4') {
      competicionActual = element.text().trim();
      return;
    }
    
    // Procesar filas de partidos (tr)
    const celdas = element.find('td');
    if (celdas.length < 3) return; // Saltar filas vacías o inválidas
    
    try {
      // Estructura típica: | Categoría | Equipos | Fecha [Hora] | Pabellón |
      const categoria = $(celdas[0]).text().trim();
      const textoEquipos = $(celdas[1]).text().trim();
      const textoFechaHora = $(celdas[2]).text().trim();
      const pabellon = $(celdas[3])?.text().trim() || 'Por determinar';
      
      if (!categoria || !textoEquipos || !textoFechaHora) return;
      
      // Separar fecha y hora
      const partesFechaHora = textoFechaHora.split(/\s+/);
      const fecha = partesFechaHora[0]; // DD/MM/YYYY
      const hora = partesFechaHora[1]; // HH:MM (opcional)
      
      // Validar formato de fecha
      if (!/\d{2}\/\d{2}\/\d{4}/.test(fecha)) {
        return;
      }
      
      // Determinar equipos
      const { local, visitante } = determinarEquipos(textoEquipos);
      
      // Extraer posible resultado
      const resultado = extraerResultado(textoEquipos);
      
      const partido: Partido = {
        id: '',
        categoria,
        competicion: competicionActual,
        equipoLocal: local,
        equipoVisitante: visitante,
        fecha,
        hora: hora && /\d{2}:\d{2}/.test(hora) ? hora : undefined,
        pabellon,
        resultadoLocal: resultado.local,
        resultadoVisitante: resultado.visitante,
        estado: determinarEstado(fecha, hora, resultado),
        fechaActualizacion: new Date().toISOString(),
      };
      
      partido.id = generarIdPartido(partido);
      partidos.push(partido);
    } catch (error) {
      console.warn('⚠️  Error procesando fila:', error);
    }
  });
  
  return partidos;
}

/**
 * Compara dos arrays de partidos y devuelve true si son diferentes
 */
function hanCambiado(partidosNuevos: Partido[], partidosAntiguos: Partido[]): boolean {
  if (partidosNuevos.length !== partidosAntiguos.length) {
    return true;
  }
  
  // Comparar por ID y estado
  const mapaNuevos = new Map(partidosNuevos.map(p => [p.id, p]));
  
  for (const partidoAntiguo of partidosAntiguos) {
    const partidoNuevo = mapaNuevos.get(partidoAntiguo.id);
    
    if (!partidoNuevo) return true;
    
    // Comparar campos relevantes
    if (
      partidoNuevo.estado !== partidoAntiguo.estado ||
      partidoNuevo.hora !== partidoAntiguo.hora ||
      partidoNuevo.resultadoLocal !== partidoAntiguo.resultadoLocal ||
      partidoNuevo.resultadoVisitante !== partidoAntiguo.resultadoVisitante
    ) {
      return true;
    }
  }
  
  return false;
}

/**
 * Carga los partidos existentes desde el archivo JSON
 */
function cargarPartidosExistentes(): Partido[] {
  try {
    if (existsSync(CONFIG.outputPath)) {
      const contenido = readFileSync(CONFIG.outputPath, 'utf-8');
      const data: PartidosData = JSON.parse(contenido);
      return data.partidos || [];
    }
  } catch (error) {
    console.warn('⚠️  No se pudieron cargar partidos existentes:', error);
  }
  return [];
}

/**
 * Guarda los partidos en el archivo JSON
 */
function guardarPartidos(partidos: Partido[]): void {
  const data: PartidosData = {
    ultima_actualizacion: new Date().toISOString(),
    total_partidos: partidos.length,
    partidos,
  };
  
  writeFileSync(CONFIG.outputPath, JSON.stringify(data, null, 2), 'utf-8');
}

/**
 * Función principal del scraper
 */
async function main() {
  const inicio = Date.now();
  console.log('🏀 Iniciando scraper de partidos ADESA 80...\n');
  
  try {
    // 1. Fetch del HTML
    console.log(`📡 Obteniendo datos de: ${CONFIG.url}`);
    const html = await fetchConTimeout(CONFIG.url, CONFIG.timeout, CONFIG.retries);
    console.log(`✅ HTML descargado (${(html.length / 1024).toFixed(2)} KB)\n`);
    
    // 2. Parsear partidos
    console.log('🔍 Parseando partidos...');
    const partidosNuevos = parsearPartidos(html);
    console.log(`✅ ${partidosNuevos.length} partidos encontrados\n`);
    
    if (partidosNuevos.length === 0) {
      console.warn('⚠️  No se encontraron partidos. Verifica la estructura de la web.');
      process.exit(1);
    }
    
    // 3. Comparar con datos existentes
    const partidosAntiguos = cargarPartidosExistentes();
    const hubocambios = hanCambiado(partidosNuevos, partidosAntiguos);
    
    if (!hubocambios && partidosAntiguos.length > 0) {
      console.log('ℹ️  No hay cambios desde la última actualización');
      console.log(`⏱️  Completado en ${((Date.now() - inicio) / 1000).toFixed(2)}s`);
      process.exit(0);
    }
    
    // 4. Guardar datos
    console.log('💾 Guardando partidos...');
    guardarPartidos(partidosNuevos);
    console.log(`✅ Datos guardados en: ${CONFIG.outputPath}\n`);
    
    // 5. Resumen
    const proximos = partidosNuevos.filter(p => p.estado === 'proximo').length;
    const finalizados = partidosNuevos.filter(p => p.estado === 'finalizado').length;
    const enCurso = partidosNuevos.filter(p => p.estado === 'en_curso').length;
    
    console.log('📊 Resumen:');
    console.log(`   - Total: ${partidosNuevos.length} partidos`);
    console.log(`   - Próximos: ${proximos}`);
    console.log(`   - En curso: ${enCurso}`);
    console.log(`   - Finalizados: ${finalizados}`);
    console.log(`   - Cambios detectados: ${hubocambios ? 'Sí' : 'No'}`);
    console.log(`\n⏱️  Completado en ${((Date.now() - inicio) / 1000).toFixed(2)}s`);
    
    process.exit(0);
  } catch (error) {
    console.error('\n❌ Error fatal:', error instanceof Error ? error.message : error);
    process.exit(1);
  }
}

// Ejecutar
main();
