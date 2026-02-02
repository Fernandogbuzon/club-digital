# 🏀 ADESA 80 - Aplicación de Resultados FAB

Una aplicación moderna y minimalista para visualizar resultados y próximos partidos de ADESA 80 desde la Federación Andaluza de Baloncesto (FAB).

## ✨ Características

- ✅ **Scraper automático** de la web FAB con manejo de errores
- ✅ **Diseño minimalista** estilo Apple TV / ESPN
- ✅ **Dos secciones claras**: Últimos Resultados + Próximos Partidos
- ✅ **Responsive**: Optimizado para móvil, tablet y desktop
- ✅ **Indicador de victorias**: Borde verde y badge para partidos ganados
- ✅ **Marcadores tipo TV**: Cajas blancas con números grandes
- ✅ **Sin gradientes ni transparencias**: Colores sólidos elegantes
- ✅ **Hover effects**: Efectos sutiles al pasar el ratón

## 🎨 Diseño

### Paleta de Colores
- **Fondo**: Azul marino oscuro (`#0a0f1a`)
- **Tarjetas**: Gris oscuro (`#161e2d`)
- **Texto**: Blanco y gris claro
- **Acentos**: Verde esmeralda (`#10b981`)
- **Marcador**: Blanco sobre fondo blanco

### Tipografía
- **Títulos**: Montserrat Bold (moderno y fuerte)
- **Cuerpo**: Inter Regular (legible y limpio)

### Grid Responsivo
```
Mobile (1 col) → Tablet (2 cols) → Desktop (3 cols)
```

## 🚀 Quick Start

### Requisitos
- Node.js 18+
- npm o yarn

### Instalación

```bash
# Clonar o descargar el proyecto
cd club-digital

# Instalar dependencias
npm install

# Iniciar servidor de desarrollo
npm run dev
```

Abre `http://localhost:3000` en tu navegador.

## 📂 Estructura del Proyecto

```
club-digital/
├── src/
│   ├── lib/
│   │   └── scraper.js              # Web scraper FAB
│   └── pages/
│       └── index.astro              # Página principal
├── public/                          # Assets estáticos
├── package.json                     # Dependencias
├── astro.config.mjs                 # Config Astro
├── tsconfig.json                    # Config TypeScript
├── DESIGN_SPECS.md                  # Especificaciones de diseño
├── VISUAL_PREVIEW.md                # Vista previa visual
├── DATOS_EJEMPLO.md                 # Ejemplo de datos
├── INSTRUCCIONES.md                 # Guía de uso
└── ROADMAP_FUTURO.md                # Plan de mejoras
```

## 🔧 Tecnologías

- **Framework**: Astro 5.17.1
- **HTTP Client**: Axios 1.13.4
- **HTML Parser**: Cheerio 1.2.0
- **Styling**: Tailwind CSS
- **Fuentes**: Google Fonts (Montserrat + Inter)

## 📊 Secciones Principales

### 🏆 Últimos Resultados
- Muestra partidos ya jugados
- Fecha, equipos y marcador
- Indicador verde si ADESA 80 ganó
- Badge "VICTORIA" para partidos ganados

### 📅 Próximos Partidos
- Partidos programados
- Categoría, equipos, fecha y campo
- Organizado por grid responsivo
- Información clara y accesible

## 🛠️ Scraper FAB

El scraper está implementado en `src/lib/scraper.js` con:

### Características
- Extrae datos de la web oficial de FAB
- Manejo de errores con retry automático (3 intentos)
- Headers realistas de navegador moderno
- Soporte para HTTPS y certificados autofirmados
- Delays progresivos para evitar bloqueos

### Funciones Exportadas

```javascript
// Obtener próximos partidos
const upcomingGames = await getUpcomingGames();

// Obtener últimos resultados
const lastResults = await getLastResults();
```

## 📱 Respuesta en Diferentes Pantallas

### Mobile (< 768px)
- 1 columna de tarjetas
- Padding: 2rem
- Fuente más pequeña

### Tablet (768px - 1024px)
- 2 columnas de tarjetas
- Gap: 1.5rem

### Desktop (> 1024px)
- 3 columnas de tarjetas
- Max-width: 1152px
- Centrado automático

## 🎯 Vista Previa

```
┌────────────────────────────────────────────────────────┐
│  ADESA 80                                               │
│  Federación Andaluza de Baloncesto • Cádiz             │
├────────────────────────────────────────────────────────┤
│  Últimos Resultados                                     │
│                                                         │
│  ┌─────────────────┐ ┌─────────────────┐ ┌────────┐   │
│  │ 15 Febrero 2026 │ │ 12 Febrero 2026 │ │ 10 Feb │   │
│  │                 │ │                 │ │        │   │
│  │ CB Cádiz        │ │ ADESA 80 Senior │ │ ADESA  │   │
│  │  ┌──────┐┌──┐   │ │  ┌──────┐┌──┐   │ │ ┌────┐ │   │
│  │  │ 85   ││78│   │ │  │ 92   ││86│   │ │ │ 78 │ │   │
│  │  └──────┘└──┘   │ │  └──────┘└──┘   │ │ └────┘ │   │
│  │ ADESA 80 B      │ │ CB Jerez        │ │ CB     │   │
│  │ ▮ VICTORIA      │ │ ▮ VICTORIA      │ │ Huelva │   │
│  └─────────────────┘ └─────────────────┘ └────────┘   │
│                                                         │
│  Próximos Partidos                                      │
│                                                         │
│  ┌─────────────────┐ ┌─────────────────┐ ┌────────┐   │
│  │ SENIOR          │ │ CADETE B        │ │ JUVENIL│   │
│  │ ADESA 80        │ │ ADESA 80 B      │ │ ADESA  │   │
│  │       VS        │ │        VS       │ │   VS   │   │
│  │ CB Málaga       │ │ CB Córdoba      │ │ CB Jaén│   │
│  │ 📌 20 Feb 2026  │ │ 📌 21 Feb 2026  │ │📌 22   │   │
│  │ 📍 Pab. Cádiz   │ │ 📍 Pab. Sur     │ │📍 Pab. │   │
│  └─────────────────┘ └─────────────────┘ └────────┘   │
│                                                         │
├────────────────────────────────────────────────────────┤
│  © 2026 ADESA 80 • Federación Andaluza de Baloncesto   │
└────────────────────────────────────────────────────────┘
```

## 🐛 Troubleshooting

### Error 403 del scraper
El scraper incluye manejo automático. Si persiste:
1. Verifica tu conexión a internet
2. Revisa los logs en la consola
3. La web FAB puede requerir JavaScript (Playwright como alternativa)

### Tarjetas se ven desordenadas
1. Limpia caché del navegador (Ctrl+Shift+Del)
2. Recarga la página (F5)
3. Reinicia el servidor (`npm run dev`)

### Datos no se cargan
1. Abre las DevTools (F12)
2. Revisa la consola para errores
3. Verifica que la URL de FAB esté activa

## 📈 Mejoras Futuras

Ver [ROADMAP_FUTURO.md](./ROADMAP_FUTURO.md) para:
- Filtros por categoría
- Estadísticas de victorias
- Modal de detalles
- PWA instalable
- Notificaciones push
- Compartir en redes

## 📚 Documentación Adicional

- [DESIGN_SPECS.md](./DESIGN_SPECS.md) - Especificaciones de diseño
- [VISUAL_PREVIEW.md](./VISUAL_PREVIEW.md) - Vista previa visual
- [DATOS_EJEMPLO.md](./DATOS_EJEMPLO.md) - Estructura de datos
- [INSTRUCCIONES.md](./INSTRUCCIONES.md) - Guía de ejecución

## 🤝 Contribuir

Las contribuciones son bienvenidas. Por favor:
1. Fork el proyecto
2. Crea una rama para tu feature
3. Commit tus cambios
4. Push a la rama
5. Abre un Pull Request

## 📄 Licencia

Este proyecto está bajo licencia MIT. Consulta el archivo LICENSE para más detalles.

## 📧 Contacto

Para preguntas o sugerencias sobre ADESA 80:
- 📱 Web: https://www.andaluzabaloncesto.org
- 🏀 Club: ADESA 80 (Cádiz)

---

**Última actualización**: Febrero 2026
**Versión**: 1.0.0
**Estado**: ✅ Producción
