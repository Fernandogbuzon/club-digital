import puppeteer from 'puppeteer';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const FEDERACION_URL = 'https://www.andaluzabaloncesto.org/cadiz/resultados-club-196/adesa-80';
const JSON_PATH = path.join(__dirname, 'src', 'data', 'partidos.json');

/**
 * Parsea fecha en formato DD/MM/YYYY a objeto Date
 */
function parseFecha(fechaStr) {
  const [dia, mes, anio] = fechaStr.split('/').map(Number);
  return new Date(anio, mes - 1, dia);
}

/**
 * Formatea fecha para comparación
 */
function formatFecha(fecha) {
  const dia = String(fecha.getDate()).padStart(2, '0');
  const mes = String(fecha.getMonth() + 1).padStart(2, '0');
  const anio = fecha.getFullYear();
  return `${dia}/${mes}/${anio}`;
}

/**
 * Carga el JSON existente o retorna array vacío
 */
function cargarPartidosExistentes() {
  try {
    if (fs.existsSync(JSON_PATH)) {
      const data = fs.readFileSync(JSON_PATH, 'utf-8');
      return JSON.parse(data);
    }
  } catch (error) {
    console.log('⚠️  No se pudo cargar el JSON existente, creando uno nuevo...');
  }
  return [];
}

/**
 * Guarda los partidos en el JSON
 */
function guardarPartidos(partidos) {
  const dir = path.dirname(JSON_PATH);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  fs.writeFileSync(JSON_PATH, JSON.stringify(partidos, null, 2), 'utf-8');
  console.log(`✅ Guardados ${partidos.length} partidos en ${JSON_PATH}`);
}

/**
 * Genera ID único para un partido
 */
function generarId(partido) {
  const normalizado = `${partido.fecha}_${partido.local}_${partido.visitante}_${partido.categoria}`
    .replace(/\s+/g, '_')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase();
  return normalizado;
}

/**
 * Busca si un partido ya existe
 */
function buscarPartidoExistente(partidos, nuevoPartido) {
  const nuevoId = generarId(nuevoPartido);
  return partidos.findIndex(p => generarId(p) === nuevoId);
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
      
      // Buscar todas las secciones de categorías
      const categorias = document.querySelectorAll('.pestana-subdesplegable');
      
      console.log('Categorías encontradas:', categorias.length);
      
      categorias.forEach(categoriaHeader => {
        // Extraer nombre exacto de la categoría desde el h4
        const categoriaH4 = categoriaHeader.querySelector('h4');
        if (!categoriaH4) return;
        
        const categoriaNombre = categoriaH4.textContent
          .replace(/<span.*<\/span>/g, '')
          .trim();
        
        // Buscar el contenedor de partidos de esta categoría
        const contenedorId = categoriaHeader.id.replace('pestana_', 'capa_');
        const contenedor = document.getElementById(contenedorId);
        
        if (!contenedor) {
          console.log('No se encontró contenedor para:', contenedorId);
          return;
        }
        
        // Buscar todas las filas de partidos en las tablas
        const filas = contenedor.querySelectorAll('tbody tr');
        
        console.log(`Filas encontradas en ${categoriaNombre}:`, filas.length);
        
        filas.forEach(fila => {
          const celdas = fila.querySelectorAll('td');
          if (celdas.length < 6) return;
          
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
          
          // Extraer puntos
          const puntosLocalText = celdas[1].textContent.trim();
          const puntosVisitanteText = celdas[2].textContent.trim();
          
          const puntosLocal = puntosLocalText && !isNaN(parseInt(puntosLocalText)) 
            ? parseInt(puntosLocalText) 
            : null;
          const puntosVisitante = puntosVisitanteText && !isNaN(parseInt(puntosVisitanteText))
            ? parseInt(puntosVisitanteText) 
            : null;
          
          // Determinar marcadores para ADESA
          let marcadorLocal = null;
          let marcadorVisitante = null;
          
          if (puntosLocal !== null && puntosVisitante !== null) {
            if (adesaEsLocal) {
              marcadorLocal = puntosLocal;
              marcadorVisitante = puntosVisitante;
            } else {
              marcadorLocal = puntosVisitante;
              marcadorVisitante = puntosLocal;
            }
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
          
          resultados.push({
            categoria: categoriaNombre,
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
 * Función principal: Smart Merge
 */
async function main() {
  try {
    console.log('\n═══════════════════════════════════════════════');
    console.log('   🏀 SCRAPER ADESA 80 - Sistema Inteligente');
    console.log('═══════════════════════════════════════════════\n');
    
    // 1. Cargar partidos existentes
    const partidosExistentes = cargarPartidosExistentes();
    console.log(`📁 Partidos en base de datos: ${partidosExistentes.length}`);
    
    // 2. Scrape nuevos partidos
    const partidosNuevos = await scrapePartidos();
    
    if (partidosNuevos.length === 0) {
      console.log('⚠️  No se encontraron partidos. Verifica la URL o la estructura HTML.');
      return;
    }
    
    // 3. Smart Merge: actualizar o agregar
    let actualizados = 0;
    let agregados = 0;
    
    partidosNuevos.forEach(nuevoPartido => {
      const index = buscarPartidoExistente(partidosExistentes, nuevoPartido);
      
      if (index >= 0) {
        // Actualizar partido existente (mantener el ID original)
        nuevoPartido.id = partidosExistentes[index].id;
        partidosExistentes[index] = nuevoPartido;
        actualizados++;
      } else {
        // Agregar nuevo partido
        nuevoPartido.id = generarId(nuevoPartido);
        partidosExistentes.push(nuevoPartido);
        agregados++;
      }
    });
    
    console.log(`\n📈 ESTADÍSTICAS:`);
    console.log(`   ✏️  Actualizados: ${actualizados}`);
    console.log(`   ➕ Agregados: ${agregados}`);
    console.log(`   📊 Total: ${partidosExistentes.length}`);
    
    // 4. Ordenar por fecha (más recientes primero para resultados)
    partidosExistentes.sort((a, b) => {
      try {
        const fechaA = parseFecha(a.fecha);
        const fechaB = parseFecha(b.fecha);
        return fechaB - fechaA;
      } catch {
        return 0;
      }
    });
    
    // 5. Guardar
    guardarPartidos(partidosExistentes);
    
    console.log('\n🎉 Scraping completado con éxito!\n');
    console.log('═══════════════════════════════════════════════\n');
    
  } catch (error) {
    console.error('\n❌ ERROR CRÍTICO:', error.message);
    console.error(error.stack);
    process.exit(1);
  }
}

main();
