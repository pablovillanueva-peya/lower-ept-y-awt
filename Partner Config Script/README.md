# Automatización Diaria de Preptime para Vendors (Seamless Bulk Updates)

Este proyecto automatiza la ingesta diaria de vendors (desde carpeta compartida de Drive o BigQuery), aplica la jerarquía de reglas de negocio para estimar el tiempo de preparación (**Preptime**) y realiza la carga masiva en el portal **Seamless Dashboard** de PedidosYa mediante navegación automatizada (**Playwright**).

---

## 📘 Documentación Completa de Traspaso

> 👉 **Consulta el [DOCUMENTO_DE_TRASPASO.md](DOCUMENTO_DE_TRASPASO.md) para ver la guía completa paso a paso, arquitectura, mantenimiento de reglas en Excel, modos de ejecución y configuración en Windows Task Scheduler.**

---

## ⚡ Inicio Rápido

### 1. Ejecución con 1 Clic
Haz doble clic en `run.bat` en la raíz del proyecto. El script se encargará automáticamente de:
- Crear el entorno virtual si no existe.
- Instalar dependencias (`requirements.txt`) y Chromium.
- Ejecutar el proceso diario leyendo el archivo de hoy en `data_vendors_drive`.

### 2. Modos de Ejecución en Consola (PowerShell)
```powershell
cd C:\Users\cristian.alvarez\Desktop\Proyectos\PartnerConfigs

# Modo Seguro / Simulación (sin abrir navegador)
.\venv\Scripts\python main.py --dry-run

# Ejecución Completa con Carga en Seamless
.\venv\Scripts\python main.py
```

---

## 📂 Archivos y Carpetas Principales

| Carpeta / Archivo | Propósito |
| :--- | :--- |
| [`DOCUMENTO_DE_TRASPASO.md`](DOCUMENTO_DE_TRASPASO.md) | **Manual de traspaso y operación para otros equipos**. |
| [`config/rules_preptime.csv`](config/rules_preptime.csv) | Tabla editable de reglas (Franquicias, Cuisines, Verticales, Keywords). |
| [`data_vendors_drive/`](data_vendors_drive/) | Carpeta donde se depositan los archivos diarios de vendors. |
| [`data/output/`](data/output/) | CSVs generados para Seamless y Reportes de Auditoría. |
| [`data/logs/`](data/logs/) | Logs diarios y capturas de pantalla de confirmación. |
| [`.env`](.env) | Variables de entorno, URLs y credenciales. |
| [`run.bat`](run.bat) | Lanzador automático para Windows / Programador de Tareas. |
