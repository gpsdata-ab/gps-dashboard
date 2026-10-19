# ⚽ CE Europa - Sistema de Análisis GPS v2.5.0

Aplicación de Streamlit para visualización y análisis de datos GPS del CE Europa, con carga centralizada desde Google Drive y vistas específicas para equipo y jugador.

## ✨ Características

- 🔐 **Sistema de autenticación** con contraseñas
- 📁 **Integración con Google Drive** (carga automática de datos)
- 📊 **Análisis por equipo** centrado en contexto de partido
- 👤 **Análisis individual** con evolución temporal y comparativas
- 📈 **Referencias normalizadas** a 94 minutos
- 📄 **Exportación a PDF** de informes individuales
- 🎨 **Interfaz moderna** con sidebar auto-ocultable

---

## 📁 Estructura del Proyecto
```
Europa_APP/
├── app.py                          # Aplicación principal con autenticación
├── config.py                       # Configuración centralizada
├── requirements.txt                # Dependencias Python
│
├── pages/                          # Páginas Streamlit
│   ├── 1_📋_Prescripción_de_la_carga.py # Prescripción de la carga
│   └── 2_📊_Análisis_de_partidos.py     # Análisis de partidos
│
├── utils/                          # Módulos de utilidades
│   ├── __init__.py                # Exports principales
│   ├── auth.py                    # Sistema de autenticación
│   ├── sidebar.py                 # Sidebar con auto-ocultación
│   ├── data_loader.py             # Carga principal de datos
│   ├── drive_loader.py            # Integración con Google Drive
│   ├── data_processor.py          # Procesamiento de datos
│   ├── calculations.py            # Cálculos y normalizaciones
│   ├── filtros.py                 # Sistema de filtros reutilizable
│   ├── plantilla.py               # Gestión de plantilla de jugadores
│   ├── minutaje_labels.py         # Etiquetas y reglas de minutos
│   ├── visualizations.py          # Gráficos y fotos
│   └── pdf_*.py                   # Generadores de PDF
│
├── .streamlit/
│   ├── config.toml                # Configuración de Streamlit
│   └── secrets.toml.example       # Ejemplo de secrets (NO subir secrets.toml)
│
├── fotos_jugadores/               # Fotos de jugadores (opcional)
├── informes_pdf/                  # PDFs generados (no subir)
└── README.md                      # Este archivo
```

---

## 🚀 Instalación Local

### **1. Clonar el repositorio**
```bash
git clone https://github.com/TU_USUARIO/europa-gps-analytics.git
cd europa-gps-analytics
```

### **2. Crear entorno virtual**
```bash
# Crear entorno virtual
python3 -m venv venv

# Activar entorno virtual
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows
```

### **3. Instalar dependencias**
```bash
pip install -r requirements.txt
```

### **4. Configurar secrets**
```bash
# Copiar ejemplo
cp .streamlit/secrets.toml.example .streamlit/secrets.toml

# Editar con tus credenciales
nano .streamlit/secrets.toml  # o cualquier editor
```

Ver sección **🔐 Configuración de Secrets** más abajo.

### **5. Ejecutar la aplicación**
```bash
streamlit run app.py
```

La app se abrirá en: `http://localhost:8501`

---

## ☁️ Despliegue en Streamlit Cloud

### **Paso 1: Preparar GitHub**
```bash
# Verificar que secrets.toml NO se suba
git status  # NO debe aparecer secrets.toml

# Commit y push
git add .
git commit -m "Deploy CE Europa GPS v2.5.0"
git push origin main
```

### **Paso 2: Crear App en Streamlit Cloud**

1. Ve a [share.streamlit.io](https://share.streamlit.io)
2. Click en **"New app"**
3. Conecta tu repositorio de GitHub
4. Configuración:
   - **Repository:** `tu-usuario/europa-gps-analytics`
   - **Branch:** `main`
   - **Main file path:** `app.py`

### **Paso 3: Configurar Secrets**

1. En Streamlit Cloud, ve a **Settings → Secrets**
2. Copia el contenido completo de tu archivo local `.streamlit/secrets.toml`
3. Pégalo en el editor de secrets
4. Click en **Save**

### **Paso 4: Deploy**

1. Click en **Deploy!**
2. Espera 2-3 minutos
3. ¡Listo! Tu app estará disponible en `https://tu-app.streamlit.app`

---

## 🔐 Configuración de Secrets

### **Estructura de `secrets.toml`**
```toml
# Autenticación de usuarios
[passwords]
admin = "tu_contraseña_segura"
# Añade más usuarios aquí

# Google Drive Service Account
[google_service_account]
type = "service_account"
project_id = "tu-project-id"
private_key_id = "tu-private-key-id"
private_key = "-----BEGIN PRIVATE KEY-----\nTU_CLAVE_PRIVADA\n-----END PRIVATE KEY-----\n"
client_email = "tu-service-account@proyecto.iam.gserviceaccount.com"
client_id = "123456789"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/tu-service-account%40proyecto.iam.gserviceaccount.com"
```

### **Obtener credenciales de Google Drive**

1. **Crear proyecto en Google Cloud Console:**
   - Ve a [console.cloud.google.com](https://console.cloud.google.com)
   - Crea un nuevo proyecto
   - Nombre: "CE Europa GPS"

2. **Habilitar Google Drive API:**
   - En el proyecto, ve a "APIs & Services" → "Library"
   - Busca "Google Drive API"
   - Click en "Enable"

3. **Crear Service Account:**
   - Ve a "IAM & Admin" → "Service Accounts"
   - Click en "Create Service Account"
   - Nombre: "europa-fc-gps-reader"
   - Rol: "Viewer" (o sin rol)
   - Click en "Create and Continue" → "Done"

4. **Generar clave JSON:**
   - Click en el service account creado
   - Tab "Keys" → "Add Key" → "Create new key"
   - Tipo: JSON
   - Se descarga automáticamente

5. **Configurar permisos en Google Drive:**
   - Abre Google Drive
   - Ve a la carpeta con los archivos GPS
   - Click derecho → "Share"
   - Pega el email del service account (termina en `@...iam.gserviceaccount.com`)
   - Permiso: "Viewer"
   - Click en "Share"

6. **Copiar credenciales a secrets.toml:**
   - Abre el archivo JSON descargado
   - Copia cada campo a `secrets.toml` bajo `[google_service_account]`
   - **IMPORTANTE:** La `private_key` debe mantener los `\n`

---

## 📊 Uso de la Aplicación

### **1. Iniciar Sesión**
- Abre la aplicación
- Ingresa usuario y contraseña
- Click en "Iniciar Sesión"

### **2. Cargar Datos desde Google Drive**
- La app intenta cargar automáticamente al iniciar sesión
- Si necesitas refrescar, usa el botón de recarga manual en la pantalla principal

### **3. Configurar Filtros**
- **Rango de fechas:** Desde/hasta en el sidebar
- **Modo de análisis:** Partido específico, últimos N partidos, o rango personalizado

### **4. Navegar por las Páginas**

#### **📊 Equipo**
- Vista colectiva orientada a partido
- Filtro de partido específico, últimos N partidos o rango de fechas
- Comparativas por equipo, posiciones o jugadores
- Estadísticos como media, máximo, P70, P95 y sumatorio según contexto

#### **👤 Individual**
- Evolución individual con líneas acumuladas
- Comparativa entre jugadores
- Exportación a PDF de informes personalizados
- Foto del jugador cuando está disponible

---

## 🛠️ Tecnologías

- **Python 3.12**
- **Streamlit** - Framework web
- **Pandas** - Manipulación de datos
- **Plotly** - Visualizaciones interactivas
- **Google Drive API** - Integración con Drive
- **ReportLab** - Generación de PDFs
- **Pillow** - Procesamiento de imágenes

---

## 📝 Notas Técnicas

### **Normalización a 94 minutos**
- Solo para calcular referencias
- Filtro: jugadores con >60 minutos
- Fórmula: `valor_94min = valor_original × (94 / tiempo_jugado)`

### **Métricas Acumulativas (se normalizan)**
- `total_distance`, `hsr`, `distance_vrange6`
- `sprints`, `num_acc_expl`, `num_dec_expl`, `hmld`

### **Métricas Relativas (NO se normalizan)**
- `minute_distance` - Ya es por minuto
- `max_speed` - Es un valor máximo
- `hsr_rel`, `hmld_relative` - Ya son relativos

### **Estructura de datos GPS**
Los CSV deben contener:
- `player`: Nombre del jugador
- `date`: Fecha del partido
- `time`: Tiempo jugado (MM:SS o decimal)
- `task`: Tipo de sesión (debe incluir "Total")
- Métricas físicas (ver `config.py`)

---

## 🔧 Configuración Avanzada

### **Añadir nuevas métricas**

Edita `config.py`:
```python
METRICAS_DICT = {
    'Mi Nueva Métrica': 'columna_en_csv',
    # ...
}

METRICAS_ACUMULATIVAS = [
    'columna_en_csv',  # Si es acumulativa
    # ...
]
```

### **Cambiar minutos mínimos para referencias**

En `config.py`:
```python
MINUTOS_MINIMOS = 60  # Cambiar aquí
```

### **Personalizar colores**

En `config.py`:
```python
COLORES = {
    'primario': '#1f77b4',
    'secundario': '#ff7f0e',
    # ...
}
```

---

## 🛡️ Seguridad

- ✅ Autenticación por contraseña
- ✅ Secrets NO incluidos en el repositorio
- ✅ Service Account con permisos mínimos
- ✅ Archivos sensibles en `.gitignore`

**NUNCA subas a GitHub:**
- `.streamlit/secrets.toml`
- `service_account.json`
- Archivos CSV con datos personales

---

## 🐛 Troubleshooting

### **Error: "No se encontraron datos"**
- Verifica que la carpeta de Google Drive tenga CSV
- Confirma que compartiste la carpeta con el service account
- Revisa que los CSV tengan las columnas base necesarias (`player`, `date`, `time`, `task`, etc.)

### **Error: "Authentication failed"**
- Verifica las credenciales en `secrets.toml`
- Asegúrate de que la `private_key` tenga los `\n` correctos
- Confirma que Google Drive API está habilitada

### **Error: "Module not found"**
```bash
pip install -r requirements.txt --force-reinstall
```

### **Sidebar no se oculta automáticamente**
- Verifica `initial_sidebar_state="collapsed"` en cada página
- Revisa que `render_sidebar()` se llame sin parámetros

---

## 📈 Roadmap

- [ ] Mejorar la documentación funcional y técnica
- [ ] Añadir más automatismos de validación de datos
- [ ] Incorporar nuevas vistas comparativas si el flujo del staff lo requiere

---

## 👥 Créditos

**Desarrollado por:**
- **Montxinho** - Community Manager UDDEA & Analista MCODE Sport Analytics

**Para:**
- **CE Europa** - Análisis GPS y rendimiento físico

---

## 📄 Licencia

Privado - CE Europa  
Todos los derechos reservados © 2025

---

## 📧 Contacto

Para soporte técnico o consultas:
- UDDEA: [contacto]
- MCODE Sport Analytics: [contacto]

---

**CE Europa GPS Analytics v2.5.0** ⚽📊  
*Última actualización: Julio 2026*
