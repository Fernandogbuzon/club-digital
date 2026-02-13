# 🏀 Guía Paso a Paso: GitHub Actions para Scraping Automático

## ¿Qué es GitHub Actions?

GitHub Actions es un sistema de automatización **gratuito** integrado en GitHub.
Puedes programar scripts que se ejecutan en servidores de GitHub (no en tu PC).

- **Gratis**: 2.000 minutos/mes para repositorios privados
- **Sin tu PC encendido**: se ejecuta en la nube
- **Automático**: se dispara por horario o por eventos

---

## Paso 1: Crear cuenta en GitHub (si no la tienes)

1. Ve a [github.com](https://github.com) y regístrate
2. Confirma tu email

---

## Paso 2: Crear repositorio

1. En GitHub, haz clic en **"+" → "New repository"**
2. Nombre: `club-digital` (o el que prefieras)
3. Marca **Private** (para que tu código no sea público)
4. **NO** marques "Add README" (ya tienes uno local)
5. Clic en **"Create repository"**

---

## Paso 3: Conectar tu proyecto local con GitHub

Abre la terminal en VS Code (`` Ctrl+` ``) y ejecuta estos comandos **uno por uno**:

```powershell
# 1. Inicializar git (si no lo has hecho ya)
git init

# 2. Conectar con tu repositorio de GitHub
#    CAMBIA "tu-usuario" por tu nombre de usuario de GitHub
git remote add origin https://github.com/tu-usuario/club-digital.git

# 3. Verificar que se conectó
git remote -v
```

> Si ya tenías git inicializado y remote configurado, salta al paso 4.

---

## Paso 4: Configurar permisos del repositorio

**IMPORTANTE** — sin esto, los workflows no pueden hacer commits automáticos.

1. Ve a tu repositorio en GitHub (en el navegador)
2. **Settings** (pestaña de arriba, la del engranaje)
3. En el menú lateral izquierdo: **Actions → General**
4. Baja hasta **"Workflow permissions"**
5. Selecciona: **✅ Read and write permissions**
6. Marca también: **✅ Allow GitHub Actions to create and approve pull requests**
7. Clic en **Save**

---

## Paso 5: Subir tu código por primera vez

```powershell
# 1. Añadir todos los archivos al staging
git add -A

# 2. Crear el primer commit
git commit -m "Proyecto inicial con scrapers y workflows"

# 3. Cambiar la rama a "main" (por si estás en "master")
git branch -M main

# 4. Subir a GitHub
git push -u origin main
```

> Te pedirá credenciales de GitHub la primera vez.
> Si usas Windows, se abrirá una ventana del navegador para autenticarte.

---

## Paso 6: Verificar que los workflows se activaron

1. Ve a tu repositorio en GitHub
2. Haz clic en la pestaña **"Actions"** (arriba, junto a "Code", "Issues", etc.)
3. Deberías ver 3 workflows listados en la barra lateral izquierda:
   - **1. Calendario - Actualizar fechas y horarios**
   - **2. Disparador - Detectar partidos terminados**
   - **3. Resultados - Scraping rapido**

Si ves estos 3, **¡ya está todo configurado!**

---

## Paso 7: Ejecutar manualmente la primera vez

El workflow 1 (Calendario) se ejecuta automáticamente cada día a las 7:00.
Pero puedes lanzarlo ahora para probar:

1. En **Actions**, haz clic en **"1. Calendario..."** (menú izquierdo)
2. Verás un botón **"Run workflow"** a la derecha
3. Haz clic → **"Run workflow"** (rama `main`)
4. Espera ~15 minutos a que termine
5. El circulito se pondrá 🟢 verde si fue bien

> Esto scrapeará todas las competiciones y generará los archivos iniciales.
> Aparecerá un commit automático como "Calendario actualizado - 13/02/2026 12:00"

---

## Paso 8: Verificar que funciona automáticamente

Una vez ejecutado el workflow 1:

1. Ve a la pestaña **"Code"** de tu repositorio
2. Comprueba que aparecen archivos nuevos en `src/data/`
3. Comprueba que existe `partidos_hoy.json` y `comp_url_map.json`

A partir de ahora:
- **Workflow 1** se ejecuta solo cada día a las 7:00 España
- **Workflow 2** comprueba cada 10 min si hay partidos terminados (hora de partido)
- **Workflow 3** solo se ejecuta cuando el 2 detecta partidos pendientes

---

## Funcionamiento automático (resumen)

```
┌─────────────────┐
│ Workflow 1       │  Diario 7:00 España
│ Calendario       │  Scrapea TODAS las competiciones
│                  │  → src/data/, partidos_hoy.json, comp_url_map.json
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Workflow 2       │  Cada 10 min (horario de partidos)
│ Disparador       │  ¿Hay partidos terminados sin resultado?
│ (ultra ligero)   │  Solo lee JSONs, NO abre navegador
└────────┬────────┘
         │ SI hay pendientes
         ▼
┌─────────────────┐
│ Workflow 3       │  Solo cuando el #2 lo activa
│ Resultados       │  Abre Playwright, scrapea SOLO los grupos
│                  │  necesarios. Max 3 intentos por partido.
└─────────────────┘
```

**Coste estimado: ~200 min/mes** (de los 2.000 gratuitos)

---

## Comandos útiles del día a día

### Ver el estado desde tu PC

```powershell
# Traer los últimos cambios de GitHub
git pull

# Ver los últimos commits automáticos
git log --oneline -10
```

### Actualizar tu código local y subir cambios

```powershell
# Después de hacer cambios en tu código:
git add -A
git commit -m "Descripción de los cambios"
git push
```

### Relanzar un workflow manualmente

1. GitHub → Actions → selecciona el workflow → **Run workflow**

---

## Solución de problemas comunes

### ❌ "Permission denied" al hacer push
- Asegúrate de estar autenticado: `git config --global credential.helper manager`
- O usa SSH: [guía de GitHub](https://docs.github.com/es/authentication/connecting-to-github-with-ssh)

### ❌ Workflow falla con "Permission to create/push"
- Paso 4: verificar que **"Read and write permissions"** está activado

### ❌ El disparador no activa el workflow 3
- Verifica que la rama se llama `main` (no `master`)
- Comprueba en Actions → Workflow 2 que se ejecuta correctamente

### ❌ Scraper falla con "Cloudflare challenge"
- Esto es normal a veces. El workflow reintentará en la próxima ejecución
- Si falla consistentemente, puede que Cloudflare haya cambiado algo

### ❌ El workflow tarda mucho
- El workflow 1 (scraper completo) puede tardar 10-20 min, es normal
- El workflow 3 (resultados) debería tardar 2-5 min

---

## Reutilizar para otro equipo

Para usar este sistema con un equipo diferente:

1. **Crea un nuevo repositorio** en GitHub
2. **Copia el proyecto** (o haz fork)
3. **Edita `team_config.json`**:
   ```json
   {
     "team_name": "CB PORTUENSE",
     "team_slug": "cbportuense",
     "province": "cadiz",
     "province_base_url": "https://www.andaluzabaloncesto.org/cadiz",
     "competitions": [
       "https://www.andaluzabaloncesto.org/cadiz/delegacion-competicion-2445/comp-copa-andalucia-a",
       "https://www.andaluzabaloncesto.org/cadiz/delegacion-competicion-2446/comp-copa-andalucia-b"
     ],
     "match_duration_hours": 2.5,
     "max_retry_attempts": 3
   }
   ```
4. **Ejecuta el scraper completo una vez** para generar los datos iniciales
5. **Personaliza los logos** en `public/logos/` y el `logoMap` en `PartidosCarousel.astro`
6. **Push a GitHub** y los workflows se activan solos

> NOTA: `team_slug` debe coincidir con el nombre del fichero JSON que genera el scraper.
> El scraper crea archivos como `cb-portuense.json`, así que el slug sería `cb-portuense`.
> Puedes verificarlo ejecutando el scraper y mirando qué archivos crea en `src/data/`.
