# 🏀 Scraper Automático de Partidos ADESA 80

Sistema automatizado para obtener y actualizar los calendarios de partidos desde la Federación Andaluza de Baloncesto.

## 📋 Características

- ✅ **Scraping eficiente** con Cheerio (más rápido que Puppeteer)
- ✅ **Actualización inteligente** según el día de la semana
- ✅ **Detección de cambios** para evitar commits innecesarios
- ✅ **Retry automático** en caso de fallo
- ✅ **TypeScript** con tipos estrictos
- ✅ **GitHub Actions** totalmente integrado

## 🕐 Frecuencia de Actualización

### Lunes a Viernes
**Cada 4 horas** (0:00, 4:00, 8:00, 12:00, 16:00, 20:00)
- Los horarios y fechas se actualizan entre semana

### Sábado y Domingo
**Cada 30 minutos**
- Máxima frescura durante los días de partidos

### Manual
Puedes ejecutar el scraper manualmente desde:
- **GitHub**: Actions → "🤖 Actualizar Partidos" → Run workflow
- **Local**: `npm run scrape:partidos`

## 🚀 Uso Local

### Instalación
```bash
npm install
```

### Ejecutar scraper
```bash
# Ejecución única
npm run scrape:partidos

# Modo desarrollo (con watch)
npm run scrape:dev
```

### Build con scraping automático
```bash
npm run build
```
El comando build ejecuta automáticamente el scraper antes de compilar.

## 📁 Estructura de Datos

Los partidos se guardan en `src/data/partidos.json`:

```json
{
  "ultima_actualizacion": "2026-02-09T12:00:00.000Z",
  "total_partidos": 42,
  "partidos": [
    {
      "id": "2026-02-15_cadete_masculino_adesa_80_isaval_cba",
      "categoria": "Cadete Masculino",
      "competicion": "Comp. Copa Andalucía A",
      "equipoLocal": "ADESA 80",
      "equipoVisitante": "ISAVAL CBA",
      "fecha": "14/02/2026",
      "hora": "18:30",
      "pabellon": "PDVO. MUNICIPAL",
      "estado": "proximo",
      "fechaActualizacion": "2026-02-09T12:00:00.000Z"
    }
  ]
}
```

### Estados de Partidos

- `proximo`: Partido aún no jugado
- `en_curso`: Partido en desarrollo (detectado por fecha/hora)
- `finalizado`: Partido completado (con resultado)

## 🔧 Configuración

### URL de origen
En `src/scripts/scraper.ts`:
```typescript
const CONFIG = {
  url: 'https://www.andaluzabaloncesto.org/cadiz/resultados-club-196/adesa-80',
  timeout: 30000,
  retries: 1,
  outputPath: join(__dirname, '..', 'data', 'partidos.json'),
};
```

### Personalizar frecuencia
Edita `.github/workflows/scraper.yml`:
```yaml
schedule:
  - cron: '0 0,4,8,12,16,20 * * 1-5'  # Lunes-Viernes
  - cron: '*/30 * * * 0,6'             # Sábado-Domingo
```

## 📊 Logs y Monitoreo

### Ver logs de GitHub Actions
1. Ve a la pestaña **Actions**
2. Selecciona el workflow "🤖 Actualizar Partidos"
3. Revisa los logs de cada ejecución

### Logs locales
El scraper muestra logs detallados:
```
🏀 Iniciando scraper de partidos ADESA 80...

📡 Obteniendo datos de: https://www.andaluzabaloncesto.org/...
✅ HTML descargado (45.23 KB)

🔍 Parseando partidos...
✅ 42 partidos encontrados

💾 Guardando partidos...
✅ Datos guardados en: src/data/partidos.json

📊 Resumen:
   - Total: 42 partidos
   - Próximos: 38
   - En curso: 0
   - Finalizados: 4
   - Cambios detectados: Sí

⏱️  Completado en 2.45s
```

## 🛠️ Troubleshooting

### El scraper no encuentra partidos
- Verifica que la URL sea correcta
- La estructura HTML de la web puede haber cambiado
- Revisa los selectores en la función `parsearPartidos()`

### GitHub Actions no se ejecuta
- Verifica que el workflow esté habilitado
- Los cron jobs pueden tener hasta 15 minutos de retraso
- Ejecuta manualmente para verificar

### Errores de tipos TypeScript
```bash
npm install --save-dev @types/node tsx
```

## 📈 Consumo de GitHub Actions

**Estimación mensual:**
- Lunes-Viernes: 6 ejecuciones/día × 5 días × 4 semanas = 120 ejecuciones
- Sábado-Domingo: 48 ejecuciones/día × 2 días × 4 semanas = 384 ejecuciones
- **Total: ~500 ejecuciones/mes** (~1500 minutos)

✅ Dentro del límite gratuito de GitHub (2000 minutos/mes)

## 📝 Notas

- Los commits automáticos incluyen `[skip ci]` para evitar builds infinitos
- Solo se hace commit si hay cambios reales en los datos
- El scraper usa timeout de 30 segundos con 1 retry automático
- Compatible con cualquier hosting (Vercel, Netlify, etc.)

## 🤝 Contribuir

Para modificar el scraper:
1. Edita `src/scripts/scraper.ts`
2. Prueba localmente: `npm run scrape:partidos`
3. Verifica el JSON generado en `src/data/partidos.json`
4. Commit y push los cambios

---

**Desarrollado para ADESA 80** 🏀
