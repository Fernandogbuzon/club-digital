# 🏀 ADESA 80 - Portal Web Oficial

Portal web oficial del Club de Baloncesto ADESA 80 de Cádiz, España.

## ✨ Características

- **Diseño Moderno**: Interfaz limpia y espaciosa inspirada en diseño Apple
- **Responsive**: Totalmente adaptado a dispositivos móviles, tablets y desktop
- **Tailwind CSS v4**: Utilizando la última versión con sintaxis actualizada
- **Astro Framework**: SSG ultrarrápido para máximo rendimiento
- **Colores del Club**: Paleta personalizada con el verde ADESA (#22c55e)

## 🗂️ Estructura del Sitio

### Páginas Principales

#### 🏠 **Inicio** (`/`)
- Hero section con lema del club
- **Bento Grid** moderna con:
  - Próximo partido destacado
  - Último resultado
  - Acceso directo a tienda
  - Campus de verano
  - Información del club
- Call to action para unirse al equipo

#### 🏀 **Partidos** (`/partidos`)
- Calendario completo de próximos partidos
- Histórico de resultados con indicadores de victoria/derrota
- **Filtros por categoría**: Junior, Senior, Baby, etc.
- Diseño "Instagram-Ready" para compartir en redes sociales
- Smart merge: conserva resultados históricos

#### 📰 **Noticias** (`/noticias`)
- Grid de tarjetas con últimas novedades
- Noticias destacadas en formato grande
- Filtros por categoría (Resultados, Club, Campus, Eventos)
- Newsletter para suscripción

#### 🎉 **Eventos** (`/eventos`)
- Torneos y actividades especiales
- Eventos destacados con información completa
- Próximos eventos y eventos realizados
- Formularios de inscripción

#### 🛍️ **Tienda** (`/tienda`)
- Catálogo visual de equipación oficial
- Productos organizados por categoría
- Filtros interactivos
- Información de envíos y devoluciones
- Diseño limpio con imágenes sobre fondo gris claro

#### 🏛️ **El Club** (`/club`)
- Historia del ADESA 80
- Valores y filosofía
- Palmarés con principales logros
- Formulario de contacto
- Información de ubicación

#### ⛹️ **Campus** (`/campus`)
- Escuelas de verano e invierno
- Programas por edades (Baby Basket, Infantil, Junior)
- Información de inscripciones y horarios
- Formulario de solicitud
- Beneficios de entrenar con ADESA 80

## 🎨 Diseño y Estilo

### Paleta de Colores
```css
--color-adesa-green: #22c55e  /* Verde principal */
--color-adesa-dark: #16a34a   /* Verde oscuro */
```

### Tipografía
- **Fuente**: Inter (Google Fonts)
- **Estilo**: System-Sans con mucho espacio entre elementos

### Componentes Clave
- **Tarjetas**: `rounded-3xl` para bordes redondeados suaves
- **Navbar**: Sticky con efecto `backdrop-blur`
- **Gradientes**: `bg-linear-to-br` para fondos dinámicos
- **Hover Effects**: Transiciones suaves en todos los elementos interactivos

## 🚀 Tecnologías

- **Astro 5.17**: Framework principal
- **Tailwind CSS 4.1**: Estilos con sintaxis v4
- **TypeScript**: Tipado estático
- **Cheerio & Puppeteer**: Web scraping para actualización automática de partidos

## 📦 Instalación y Uso

```bash
# Instalar dependencias
npm install

# Ejecutar en desarrollo
npm run dev

# Actualizar datos de partidos (scraping)
npm run scrape

# Build para producción
npm run build

# Preview de producción
npm run preview
```

## 📂 Estructura de Archivos

```
club-digital/
├── src/
│   ├── components/
│   │   └── MatchCard.astro
│   ├── data/
│   │   └── partidos.json
│   ├── layouts/
│   │   └── Layout.astro
│   ├── pages/
│   │   ├── index.astro          # Inicio con Bento Grid
│   │   ├── partidos.astro       # Calendario y resultados
│   │   ├── noticias.astro       # Noticias del club
│   │   ├── eventos.astro        # Torneos y eventos
│   │   ├── tienda.astro         # Merchandising
│   │   ├── club.astro           # Historia y valores
│   │   └── campus.astro         # Escuelas deportivas
│   └── styles/
│       └── tailwind.css         # Configuración Tailwind v4
├── public/
├── astro.config.mjs
├── tailwind.config.mjs
└── package.json
```

## 🎯 Características Destacadas

### Navegación Completa
- Navbar sticky con 7 secciones principales
- Menú móvil responsive
- Footer con 4 columnas y patrocinadores
- Enlaces a redes sociales

### Interactividad
- Filtros dinámicos por categoría (JavaScript vanilla)
- Formularios de contacto e inscripción
- Efectos hover en patrocinadores (gris → color)
- Transiciones suaves en todos los elementos

### Optimización
- SSG para carga ultrarrápida
- Imágenes optimizadas
- CSS purged en producción
- Prefetch de rutas

## 🏆 Patrocinadores

Sección dedicada en el footer con logos que pasan de escala de grises a color al hover.

## 📱 Responsive Design

- **Mobile First**: Diseñado primero para móviles
- **Breakpoints**: sm, md, lg, xl
- **Grid Adaptativo**: De 1 a 4 columnas según dispositivo

## 🔄 Actualización de Datos

El archivo `scraper.js` permite actualizar automáticamente los datos de partidos desde la federación:

```bash
npm run scrape
```

## 📄 Licencia

© 2026 ADESA 80. Todos los derechos reservados.

## 🤝 Contribuir

Para contribuir al proyecto, contacta con el equipo de ADESA 80:
- Email: info@adesa80.com
- Ubicación: Cádiz, España

---

Desarrollado con ❤️ y 🏀 para la familia ADESA 80
