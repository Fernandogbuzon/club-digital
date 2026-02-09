# 🚀 Inicio Rápido - Scraper Automático

## ✅ Ya está todo listo!

El scraper automático de partidos está completamente implementado y funcionando.

---

## 🎯 Para Activarlo en GitHub

### 1. Hacer commit y push

```bash
git add .
git commit -m "✨ Implementar scraper automático de partidos"
git push origin feat
```

### 2. Verificar en GitHub
1. Ve a tu repositorio en GitHub
2. Pestaña **"Actions"**
3. Deberías ver el workflow **"🤖 Actualizar Partidos"**
4. Haz clic en **"Run workflow"** para probarlo manualmente

---

## 🧪 Probar Localmente

```bash
# Ejecutar el scraper una vez
npm run scrape:partidos

# Ver los datos generados
cat src/data/partidos.json

# O en PowerShell
Get-Content src/data/partidos.json | ConvertFrom-Json
```

---

## 📱 Integrar en Tu Sitio

### Opción 1: Usar el ejemplo completo
Copia el contenido de `src/pages/partidos-ejemplo.astro` a tu página `partidos.astro`

### Opción 2: Importar en tu código actual

```astro
---
import partidosData from '../data/partidos.json';

const { partidos, ultima_actualizacion } = partidosData;
const proximos = partidos.filter(p => p.estado === 'proximo');
---

<!-- Tu código HTML aquí -->
```

---

## ⏰ Actualización Automática

Una vez que hagas push a GitHub, el scraper se ejecutará automáticamente:

- **Lunes-Viernes**: Cada 4 horas (6 veces al día)
- **Sábado-Domingo**: Cada 30 minutos (48 veces al día)

---

## 📊 Verificar Primera Ejecución

### Local ✅
```
✅ 19 partidos encontrados
⏱️  Completado en 9.93s
```

### GitHub Actions
1. Ve a **Actions** → **"🤖 Actualizar Partidos"**
2. Haz clic en **"Run workflow"**
3. Espera 1-2 minutos
4. Verifica que aparezca un commit nuevo con los partidos actualizados

---

## 📚 Documentación Completa

- **Implementación**: `IMPLEMENTACION_COMPLETA.md`
- **Manual de uso**: `SCRAPER_README.md`
- **Código fuente**: `src/scripts/scraper.ts`

---

## 🎉 ¡Eso es todo!

El sistema está listo para usar. Los datos de partidos se actualizarán automáticamente y estarán disponibles en `src/data/partidos.json` para usarlos en cualquier página de tu sitio Astro.

**¿Alguna duda?** Revisa la documentación completa en los archivos mencionados arriba.
