import axios from 'axios';
import * as cheerio from 'cheerio';
import https from 'https';

const FAB_URL = 'https://www.andaluzabaloncesto.org/cadiz/resultados-club-196/adesa-80';

// User-Agent más realista para Chrome en Windows 11
const USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0';

// Headers completos para simular un navegador real
const HEADERS = {
  'User-Agent': USER_AGENT,
  'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
  'Accept-Encoding': 'gzip, deflate, br',
  'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
  'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="121", "Microsoft Edge";v="121"',
  'Sec-Ch-Ua-Mobile': '?0',
  'Sec-Ch-Ua-Platform': '"Windows"',
  'Sec-Fetch-Dest': 'document',
  'Sec-Fetch-Mode': 'navigate',
  'Sec-Fetch-Site': 'none',
  'Sec-Fetch-User': '?1',
  'Upgrade-Insecure-Requests': '1',
  'Referer': 'https://www.google.com/',
  'Cache-Control': 'max-age=0'
};

// Cliente HTTPS que ignora certificados autofirmados
const httpsAgent = new https.Agent({
  rejectUnauthorized: false,
  keepAlive: true,
  maxSockets: 50
});

/**
 * Pausa de espera para evitar bloqueos
 */
function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Realiza una petición GET con reintentos y manejo de errores
 */
async function fetchWithRetry(url, maxRetries = 3) {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      console.log(`Intentando descargar (intento ${attempt}/${maxRetries})...`);
      
      const response = await axios.get(url, {
        headers: HEADERS,
        httpsAgent: httpsAgent,
        timeout: 20000,
        maxRedirects: 5,
        validateStatus: function(status) {
          // Aceptar cualquier status para controlar el error nosotros
          return status < 500;
        }
      });

      if (response.status === 403) {
        console.warn(`Error 403 (intento ${attempt}/${maxRetries}). Esperando antes de reintentar...`);
        if (attempt < maxRetries) {
          // Esperar cada vez más tiempo
          await delay(2000 * attempt);
        }
        continue;
      }

      if (response.status === 404) {
        throw new Error(`URL no encontrada (404): ${url}`);
      }

      if (response.status >= 500) {
        throw new Error(`Error del servidor (${response.status})`);
      }

      if (response.status === 200) {
        console.log('✓ Descarga exitosa');
        return response;
      }

      console.warn(`Status ${response.status}. Reintentando...`);
      if (attempt < maxRetries) {
        await delay(1000 * attempt);
      }
    } catch (error) {
      console.error(`Error en intento ${attempt}: ${error.message}`);
      if (attempt < maxRetries) {
        await delay(2000 * attempt);
      } else {
        throw error;
      }
    }
  }

  throw new Error(`Fallo después de ${maxRetries} intentos`);
}

/**
 * Obtiene los próximos partidos del club ADESA 80
 * @returns {Promise<Array>} Array de objetos con próximos partidos
 */
export async function getUpcomingGames() {
  try {
    const response = await fetchWithRetry(FAB_URL);
    await delay(500); // Pequeño delay después de la respuesta

    const $ = cheerio.load(response.data);
    const upcomingGames = [];
    const seenGames = new Set();

    // Buscar en divs con id que contenga "capa_proximos"
    $('div[id^="capa_proximos"]').each((_, container) => {
      $(container)
        .find('tr.fila_color_tabla, tr.fila_sin_color')
        .each((_, element) => {
          try {
            const cells = $(element).find('td');

            if (cells.length >= 4) {
              // Estructura de próximos partidos:
              // td[0]: Categoría (puede tener <br>)
              // td[1]: Encuentro (nombres separados por <br>)
              // td[2]: Fecha (clase .centro)
              // td[3]: Campo

              // Extraer categoría (primera línea sin <br>)
              const categoryText = $(cells[0])
                .html()
                .split('<br')[0]
                .trim();

              // Extraer equipos del Encuentro (separados por <br>)
              const encounterHtml = $(cells[1]).html() || '';
              const teamParts = encounterHtml
                .split(/<br\s*\/?>/i)
                .map(p => {
                  // Limpiar HTML tags
                  return p
                    .replace(/<[^>]*>/g, '')
                    .trim();
                })
                .filter(p => p && p.length > 0);

              const localName = teamParts[0] || 'N/A';
              const visitorName = teamParts[1] || 'N/A';

              const fecha = $(cells[2]).text().trim();
              const campo = $(cells[3]).text().trim();

              // Crear clave única para evitar duplicados
              const gameKey = `${fecha}-${localName}-${visitorName}`;

              // Solo agregar si contiene ADESA 80 y no es duplicado
              if (
                !seenGames.has(gameKey) &&
                (localName.toUpperCase().includes('ADESA') ||
                  visitorName.toUpperCase().includes('ADESA'))
              ) {
                seenGames.add(gameKey);

                upcomingGames.push({
                  categoria: categoryText,
                  localName,
                  visitorName,
                  fecha,
                  campo,
                  isAdesaLocal: localName.toUpperCase().includes('ADESA')
                });
              }
            }
          } catch (err) {
            console.warn('Error procesando fila de próximos partidos:', err.message);
          }
        });
    });

    console.log(`Se obtuvieron ${upcomingGames.length} próximos partidos únicos`);
    return upcomingGames;
  } catch (error) {
    console.error('Error al scraping de próximos partidos:', error.message);
    return [];
  }
}

/**
 * Obtiene los últimos resultados del club ADESA 80
 * @returns {Promise<Array>} Array de objetos con resultados
 */
export async function getLastResults() {
  try {
    const response = await fetchWithRetry(FAB_URL);
    await delay(500); // Pequeño delay después de la respuesta

    const $ = cheerio.load(response.data);
    const results = [];
    const seenGames = new Set(); // Para evitar duplicados

    // Buscar en divs con id que contenga "capa_competicion" (resultados)
    // Estos contienen tablas con los resultados
    $('div[id^="capa_competicion_"]').each((_, mainContainer) => {
      // Dentro de cada capa_competicion hay sub-divs con id capa_XXXX_YYYYY
      $(mainContainer)
        .find('div[id^="capa_"]')
        .each((_, subContainer) => {
          // Buscar las tablas de resultados (primera tabla dentro del div)
          const firstTable = $(subContainer).find('table.table.table-striped.table-bordered').first();
          
          firstTable.find('tbody tr.fila_color_tabla').each((_, element) => {
            try {
              const cells = $(element).find('td');

              if (cells.length >= 5) {
                // Estructura de resultados:
                // td[0] (clase .centro): Fecha
                // td[1] (clase .valor_tabla_grande): Puntos Local
                // td[2]: Nombre Local
                // td[3]: Nombre Visitante
                // td[4] (clase .valor_tabla_grande): Puntos Visitante

                const fecha = $(cells[0]).text().trim();
                const localPoints = $(cells[1]).text().trim();
                const localName = $(cells[2]).text().trim();
                const visitorName = $(cells[3]).text().trim();
                const visitorPoints = $(cells[4]).text().trim();

                // Solo procesar si tiene puntos (puede estar vacío en partidos pendientes)
                if (localPoints && visitorPoints) {
                  // Crear clave única para evitar duplicados
                  const gameKey = `${fecha}-${localName}-${visitorName}`;
                  
                  if (!seenGames.has(gameKey)) {
                    seenGames.add(gameKey);

                    // Detectar si ADESA 80 ganó
                    const isAdesaLocal = localName.toUpperCase().includes('ADESA');
                    const localWon = $(cells[1]).hasClass('ganador');
                    const visitorWon = $(cells[4]).hasClass('ganador');

                    const isAdesaWinner = isAdesaLocal ? localWon : visitorWon;

                    // Solo agregar si ADESA 80 está involucrado
                    if (isAdesaLocal || visitorName.toUpperCase().includes('ADESA')) {
                      results.push({
                        fecha,
                        localName,
                        localPoints,
                        visitorName,
                        visitorPoints,
                        isAdesaWinner,
                        isAdesaLocal
                      });
                    }
                  }
                }
              }
            } catch (err) {
              console.warn('Error procesando fila de resultados:', err.message);
            }
          });
        });
    });

    console.log(`Se obtuvieron ${results.length} resultados únicos`);
    return results;
  } catch (error) {
    console.error('Error al scraping de resultados:', error.message);
    return [];
  }
}

/**
 * Obtiene TODOS los partidos del club ADESA 80 de la página de calendario
 * Estructura: Busca categorías (h4) y luego sus tablas de partidos
 * @returns {Promise<Array>} Array con todos los partidos en formato uniforme
 */
export async function getAllGames() {
  try {
    const response = await fetchWithRetry(FAB_URL);
    await delay(500);

    const $ = cheerio.load(response.data);
    const allGames = [];
    const seenGames = new Set();

    // Buscar todos los headers que tienen categorías (h4)
    $('header.pestana-subdesplegable h4').each((_, headerElem) => {
      const categoryText = $(headerElem).text().trim();
      
      if (!categoryText) return; // Saltar si no hay texto
      
      // Encontrar la próxima tabla después de este header
      const container = $(headerElem).closest('header').next('div');
      const tables = container.find('table.table.table-striped.table-bordered');
      
      if (tables.length === 0) return; // Sin tablas, pasar al siguiente
      
      tables.each((_, table) => {
        $(table)
          .find('tbody tr')
          .each((_, row) => {
            try {
              const cells = $(row).find('td');
              
              // Estructura esperada:
              // Col 0: Local
              // Col 1-2: Marcador (números si resultado, vacío si próximo)
              // Col 3: Visitante
              // Col 4: Fecha/Hora (con <br>)
              // Col 5: Pabellón
              
              if (cells.length < 5) return; // Filas incompletas
              
              const local = $(cells[0]).text().trim();
              const visitante = $(cells[3]).text().trim();
              
              // Filtrar solo ADESA 80
              if (!local.toUpperCase().includes('ADESA') && 
                  !visitante.toUpperCase().includes('ADESA')) {
                return;
              }
              
              // Extraer marcador (columnas 1-2)
              const marcadorLocal = $(cells[1]).text().trim();
              const marcadorVisitante = $(cells[2]).text().trim();
              
              // Extraer fecha y hora (columna 4)
              const fechaHoraHtml = $(cells[4]).html() || '';
              const fechaHoraParts = fechaHoraHtml
                .split(/<br\s*\/?>/i)
                .map(p => p.replace(/<[^>]*>/g, '').trim())
                .filter(p => p && p.length > 0);
              
              const fecha = fechaHoraParts[0] || '';
              const hora = fechaHoraParts[1] || '';
              
              // Extraer pabellón (columna 5)
              const pabellon = $(cells[5])?.text().trim() || '';
              
              // Crear clave única para evitar duplicados
              const gameKey = `${categoryText}-${local}-${visitante}-${fecha}`;
              
              if (seenGames.has(gameKey)) return;
              seenGames.add(gameKey);
              
              // Agregar partido
              allGames.push({
                categoria: categoryText,
                local,
                visitante,
                marcadorLocal: marcadorLocal || null,
                marcadorVisitante: marcadorVisitante || null,
                fecha,
                hora,
                pabellon,
                isAdesaLocal: local.toUpperCase().includes('ADESA')
              });
            } catch (err) {
              console.warn('Error procesando fila:', err.message);
            }
          });
      });
    });

    console.log(`✓ Se obtuvieron ${allGames.length} partidos de ADESA 80`);
    return allGames;
  } catch (error) {
    console.error('Error al scraping de calendario:', error.message);
    return [];
  }
}

export default { getUpcomingGames, getLastResults, getAllGames };
