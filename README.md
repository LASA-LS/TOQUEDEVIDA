# Dinámica Rosa – Deploy en Render con GitHub

Este repo está listo para subirlo a **GitHub** y desplegar en **Render** con disco persistente.

## Archivos clave
- `wsgi.py` → entrada para Gunicorn/Render.
- `requirements.txt` → dependencias mínimas.
- `render.yaml` → define el servicio web, disco en `/data` y enlaces simbólicos para `./uploads` y `./data`.
- `.gitignore` → mantiene vacíos `uploads/` y `data/` en el repo (pero los crea).
- `uploads/.gitkeep` y `data/.gitkeep` → para versionar las carpetas sin sus contenidos.

## Subir a GitHub (desde esta carpeta)
```bash
git init
git add .
git commit -m "Init dinamica rosa"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/dinamica-rosa.git
git push -u origin main
```

## Desplegar en Render
1. En Render → **New** → **Web Service** → conecta tu repo.
2. Render detecta `render.yaml` automáticamente.
3. En **Environment** agrega variables:
   - `SECRET_KEY` → cadena segura (ej: `costena-sec-XXXX`)
   - `ADMIN_PIN` → tu PIN (ej: `serviciomedico`)
4. Deploy. Render creará un **Disk** (2 GB) en `/data` y ejecutará:
   ```bash
   mkdir -p /data/uploads /data/data
   ln -sf /data/uploads ./uploads
   ln -sf /data/data ./data
   gunicorn wsgi:application --bind 0.0.0.0:$PORT --workers 3
   ```

## Dominio propio
En **Settings → Custom Domains** añade tu dominio (CNAME). Para cambiar el enlace después, cambias los DNS o renombras el servicio.

## Exportar CSV (en producción)
```
https://TU-SERVICIO.onrender.com/export.csv?pin=serviciomedico
```
(_Cambia el PIN en **Environment** si lo modificas_)

## Desarrollo local (opcional)
```bash
python app.py
# o con Gunicorn:
gunicorn wsgi:application --bind 127.0.0.1:5000
```
> Las carpetas `uploads/` y `data/` existen vacías para pruebas locales.
