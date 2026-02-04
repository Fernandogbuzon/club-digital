import puppeteer from 'puppeteer';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const FEDERACION_URL = 'https://www.andaluzabaloncesto.org/cadiz/resultados-club-196/adesa-80';
const EQUIPOS_DIR = path.join(__dirname, 'src', 'data', 'equipos');

/**
 * Parsea fecha en formato DD/MM/YYYY a objeto Date
 */
function parseFecha(fechaStr) {
  const [dia, mes, anio] = fechaStr.split('/').map(Number);
  return new Date(anio, mes - 1, dia);
}

/**
 * Normaliza el nombre del equipo para generar el nombre de archivo
 */
function normalizarNombreEquipo(equipo) {
  return equipo
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/\s+/g, '-')
    .replace(/[^a-z0-9-]/g, '');
}

/**
 * Genera el nombre del equipo combinando categoría y competición
 */
function generarNombreEquipo(categoria, competicion) {
  // Paso A: Toma el texto de la categoría antes del primer guion
  const categoriaPrincipal = categoria.split(' - ')[0].trim();
  
  // Paso B: Si la competición termina en 'A' o 'B', añade esa letra
  let sufijo = '';
  const matchSufijo = competicion.match(/\s([AB])\s*$/);
  if (matchSufijo) {
    sufijo = ` ${matchSufijo[1]}`;
  }
  
  return categoriaPrincipal + sufijo;
}

/**
 * Genera ID único para un partido, eliminando valores undefined
 */
function generarId(partido) {
  const fecha = partido.fecha || '';
  const local = partido.ubicacion === 'Local' ? 'adesa_80' : partido.rival;
  const visitante = partido.ubicacion === 'Visitante' ? 'adesa_80' : partido.rival;
  const categoria = partido.categoria || '';
  
  const normalizado = `${fecha}_${local}_${visitante}_${categoria}`
    .replace(/\s+/g, '_')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/undefined/g, '');
  
  return normalizado;
}

/**
 * Guarda los partidos agrupados por equipo en archivos individuales
 */
function guardarPartidosPorEquipo(partidos) {
  // Crear directorio si no existe
  if (!fs.existsSync(EQUIPOS_DIR)) {
    fs.mkdirSync(EQUIPOS_DIR, { recursive: true });
  }
  
  // Agrupar partidos por equipo
  const partidosPorEquipo = {};
  
  partidos.forEach(partido => {
    const nombreEquipo = partido.equipo || 'sin-equipo';
    if (!partidosPorEquipo[nombreEquipo]) {
      partidosPorEquipo[nombreEquipo] = [];
    }
    
    // Generar ID correcto sin undefined
    partido.id = generarId(partido);
    
    // Ajustar marcadores si el rival es DESCANSA
    if (partido.rival === 'DESCANSA') {
      partido.marcador_local = null;
      partido.marcador_visitante = null;
      partido.es_resultado = false;
    }
    
    partidosPorEquipo[nombreEquipo].push(partido);
  });
  
  // Guardar cada equipo en su archivo
  let archivosCreados = 0;
  
  Object.entries(partidosPorEquipo).forEach(([nombreEquipo, partidosEquipo]) => {
    const nombreArchivo = normalizarNombreEquipo(nombreEquipo) + '.json';
    const rutaArchivo = path.join(EQUIPOS_DIR, nombreArchivo);
    
    // Ordenar partidos por fecha
    partidosEquipo.sort((a, b) => {
      try {
        const fechaA = parseFecha(a.fecha);
        const fechaB = parseFecha(b.fecha);
        return fechaB - fechaA;
      } catch {
        return 0;
      }
    });
    
    fs.writeFileSync(rutaArchivo, JSON.stringify(partidosEquipo, null, 2), 'utf-8');
    console.log(`✅ ${nombreArchivo}: ${partidosEquipo.length} partidos`);
    archivosCreados++;
  });
  
  console.log(`\n📁 Total de archivos creados: ${archivosCreados}`);
}

/**
 * Extrae partidos de ADESA 80 de la página
 */
async function scrapePartidos() {
  console.log('🚀 Iniciando scraper de ADESA 80...');
  
  const browser = await puppeteer.launch({ 
    headless: 'new',
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-blink-features=AutomationControlled',
      '--disable-web-security',
      '--disable-features=IsolateOrigins,site-per-process'
    ]
  });
  
  try {
    const page = await browser.newPage();
    
    // Configurar User-Agent real
    await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36');
    
    // Configurar viewport
    await page.setViewport({ width: 1920, height: 1080 });
    
    // Ocultar que estamos usando Puppeteer
    await page.evaluateOnNewDocument(() => {
      Object.defineProperty(navigator, 'webdriver', {
        get: () => false,
      });
      
      // Agregar lenguajes
      Object.defineProperty(navigator, 'languages', {
        get: () => ['es-ES', 'es', 'en-US', 'en'],
      });
      
      // Chrome
      window.chrome = {
        runtime: {},
      };
      
      // Permisos
      const originalQuery = window.navigator.permissions.query;
      window.navigator.permissions.query = (parameters) => (
        parameters.name === 'notifications' ?
          Promise.resolve({ state: Notification.permission }) :
          originalQuery(parameters)
      );
    });
    
    console.log(`📡 Navegando a ${FEDERACION_URL}...`);
    
    await page.goto(FEDERACION_URL, { 
      waitUntil: 'domcontentloaded', 
      timeout: 60000 
    });
    
    // Esperar un poco para que cargue el contenido dinámico
    await new Promise(resolve => setTimeout(resolve, 3000));
    
    // Esperar a que cargue el contenido
    await page.waitForSelector('.pestana-subdesplegable, table', { timeout: 15000 });
    
    console.log('🔍 Extrayendo partidos de ADESA 80...');
    
    const partidos = await page.evaluate(() => {
      const resultados = [];
      
      // Buscar todas las competiciones principales (nivel superior)
      const competicionesPrincipales = document.querySelectorAll('.pestana-desplegable');
      
      console.log('Competiciones principales encontradas:', competicionesPrincipales.length);
      
      competicionesPrincipales.forEach(competicionHeader => {
        // Extraer el nombre de la competición principal
        const competicionH4 = competicionHeader.querySelector('h4');
        if (!competicionH4) {
          console.log('⚠️ Competición sin H4 encontrada, saltando...');
          return;
        }
        
        const competicionNombre = competicionH4.textContent
          .replace(/<span.*<\/span>/g, '')
          .trim();
        
        if (!competicionNombre) {
          console.log('⚠️ Competición con nombre vacío, saltando...');
          return;
        }
        
        // Determinar sufijo (A, B, etc.) desde el nombre de la competición
        let sufijoCompeticion = '';
        const matchSufijo = competicionNombre.match(/\s([AB])\s*$/);
        if (matchSufijo) {
          sufijoCompeticion = ` ${matchSufijo[1]}`;
        }
        
        console.log(`Procesando competición: ${competicionNombre}, sufijo: "${sufijoCompeticion}"`);
        
        // Obtener el contenedor de esta competición
        const competicionId = competicionHeader.id.replace('pestana_', 'capa_');
        const competicionContenedor = document.getElementById(competicionId);
        
        if (!competicionContenedor) {
          console.log('⚠️ No se encontró contenedor para:', competicionId);
          return;
        }
        
        // Buscar todas las subcategorías dentro de esta competición
        const categorias = competicionContenedor.querySelectorAll('.pestana-subdesplegable');
        
        console.log(`Categorías encontradas en ${competicionNombre}:`, categorias.length);
        
        // REFUERZO: Variable persistente para categoría actual
        let categoriaActual = null;
        let categoriaLimpiaActual = null;
        let equipoActual = null;
        
        categorias.forEach(categoriaHeader => {
          // Extraer nombre de la categoría
          const categoriaH4 = categoriaHeader.querySelector('h4');
          if (!categoriaH4) {
            console.log('⚠️ Categoría sin H4 encontrada, saltando...');
            return;
          }
          
          let categoriaNombre = categoriaH4.textContent
            .replace(/<span.*<\/span>/g, '')
            .trim();
          
          if (!categoriaNombre) {
            console.log('⚠️ Categoría con nombre vacío, saltando...');
            return;
          }
          
          // Añadir sufijo si existe y no está ya en el nombre
          if (sufijoCompeticion && !categoriaNombre.includes(sufijoCompeticion.trim())) {
            categoriaNombre = categoriaNombre + sufijoCompeticion;
          }
          
          // REFUERZO: Actualizar variables persistentes
          categoriaActual = categoriaNombre;
          
          // Generar nombre del equipo: categoría antes del primer guion + sufijo A/B
          const categoriaPrincipal = categoriaNombre.split(' - ')[0].trim();
          equipoActual = categoriaPrincipal + sufijoCompeticion;
          
          console.log(`📋 Categoría actual: ${categoriaActual}`);
          console.log(`🏀 Equipo generado: ${equipoActual}`);
          
          // Buscar el contenedor de partidos de esta categoría
          const contenedorId = categoriaHeader.id.replace('pestana_', 'capa_');
          const contenedor = document.getElementById(contenedorId);
          
          if (!contenedor) {
            console.log('⚠️ No se encontró contenedor para:', contenedorId);
            return;
          }
          
          // Buscar todas las filas de partidos en las tablas
          const filas = contenedor.querySelectorAll('tbody tr');
          
          console.log(`Filas encontradas en ${categoriaActual}:`, filas.length);
          
          filas.forEach((fila, index) => {
            const celdas = fila.querySelectorAll('td');
            if (celdas.length < 6) {
              console.log(`⚠️ Fila ${index} con menos de 6 celdas, saltando...`);
              return;
            }
            
            const localText = celdas[0].textContent.trim();
            const visitanteText = celdas[3].textContent.trim();
            
            // Filtrar solo partidos de ADESA 80
            if (!localText.includes('ADESA 80') && !visitanteText.includes('ADESA 80')) {
              return;
            }
            
            // Determinar si ADESA es local o visitante
            const adesaEsLocal = localText.includes('ADESA 80');
            const rival = adesaEsLocal ? visitanteText : localText;
            const ubicacion = adesaEsLocal ? 'Local' : 'Visitante';
            
            // Extraer puntos DIRECTAMENTE de la tabla (SIN inversión)
            const puntosLocalText = celdas[1].textContent.trim();
            const puntosVisitanteText = celdas[2].textContent.trim();
            
            // CORRECCIÓN CRÍTICA: Los marcadores reflejan la posición en la tabla web
            // marcador_local = puntos del equipo que jugó en casa
            // marcador_visitante = puntos del equipo que jugó fuera
            // NO importa si ADESA es local o visitante, los campos son POSICIONALES
            const marcadorLocal = puntosLocalText && !isNaN(parseInt(puntosLocalText)) 
              ? String(parseInt(puntosLocalText))
              : null;
            const marcadorVisitante = puntosVisitanteText && !isNaN(parseInt(puntosVisitanteText))
              ? String(parseInt(puntosVisitanteText))
              : null;
            
            // LOG DE DEPURACIÓN
            if (marcadorLocal && marcadorVisitante) {
              console.log(`🔍 ${localText} (${marcadorLocal}) vs ${visitanteText} (${marcadorVisitante}) - Ubicación ADESA: ${ubicacion}`);
            }
            
            // Extraer fecha y hora
            const fechaHoraElement = celdas[4].querySelector('strong');
            let fecha = '';
            let hora = '';
            
            if (fechaHoraElement) {
              const fechaHoraHTML = fechaHoraElement.innerHTML;
              const partes = fechaHoraHTML.split('<br>');
              
              fecha = partes[0].trim();
              
              if (partes.length > 1 && partes[1].trim()) {
                hora = partes[1].trim();
              }
            }
            
            const pabellon = celdas[5].textContent.trim();
            
            const esResultado = marcadorLocal !== null && marcadorVisitante !== null;
            
            // VALIDACIÓN CRÍTICA: Usar variables persistentes
            const categoriaFinal = categoriaActual || 'Categoría por definir';
            const competicionFinal = competicionNombre || 'Competición por definir';
            const equipoFinal = equipoActual || 'Equipo por definir';
            
            // DEPURACIÓN: Log del partido procesado
            console.log(`✅ Procesando partido para el equipo: ${equipoFinal} (${categoriaFinal})`);
            
            // VALIDACIÓN ANTES DE GUARDAR
            if (!equipoFinal || equipoFinal === 'Equipo por definir') {
              console.log(`⚠️ ADVERTENCIA: Partido sin equipo válido. Rival: ${rival}, Fecha: ${fecha}`);
            }
            
            resultados.push({
              categoria: categoriaFinal,
              competicion: competicionFinal,
              equipo: equipoFinal,
              rival: rival,
              ubicacion: ubicacion,
              marcador_local: marcadorLocal ? String(marcadorLocal) : null,
              marcador_visitante: marcadorVisitante ? String(marcadorVisitante) : null,
              fecha: fecha,
              hora: hora,
              pabellon: pabellon,
              es_resultado: esResultado
            });
          });
        });
      });
      
      return resultados;
    });
    
    console.log(`📊 Encontrados ${partidos.length} partidos de ADESA 80`);
    
    return partidos;
    
  } catch (error) {
    console.error('❌ Error durante el scraping:', error.message);
    throw error;
  } finally {
    await browser.close();
  }
}

/**
 * Función principal: Scrape y generación de archivos por equipo
 */
async function main() {
  try {
    console.log('\n═══════════════════════════════════════════════');
    console.log('   🏀 SCRAPER ADESA 80 - Archivos por Equipo');
    console.log('═══════════════════════════════════════════════\n');
    
    // 1. Scrape partidos
    const partidos = await scrapePartidos();
    
    if (partidos.length === 0) {
      console.log('⚠️  No se encontraron partidos. Verifica la URL o la estructura HTML.');
      return;
    }
    
    console.log(`\n📊 Total partidos extraídos: ${partidos.length}`);
    
    // 2. Guardar partidos por equipo
    guardarPartidosPorEquipo(partidos);
    
    console.log('\n🎉 Scraping completado con éxito!\n');
    console.log('═══════════════════════════════════════════════\n');
    
  } catch (error) {
    console.error('\n❌ ERROR CRÍTICO:', error.message);
    console.error(error.stack);
    process.exit(1);
  }
}

main();
