# Sourcing Assistant RECRU

Aplicación Streamlit de sourcing asistido para Recruiting con:

- JD persistentes
- versiones de requisitos
- tandas históricas
- deduplicación global por URL normalizada de LinkedIn
- búsqueda web pública con OpenAI
- scoring de perfiles
- exportación Excel acumulativa por búsqueda
- identidad visual Voolkia

## Importante

La app trabaja con información profesional pública. No está diseñada para scrapear LinkedIn con sesión privada ni para inferir atributos personales sensibles.

## Flujo

1. Crear búsqueda.
2. Cargar JD, zona, seniority, excluyentes y deseables.
3. Ejecutar hunting.
4. La app busca perfiles públicos.
5. Normaliza URLs de LinkedIn.
6. Elimina repetidos contra la base global.
7. Guarda una tanda.
8. Si cambian requisitos, crea una nueva versión.
9. La siguiente tanda queda asociada a esa versión.
10. El Excel histórico diferencia la tanda actual de las anteriores.

## Deduplicación

La clave principal es la URL normalizada de LinkedIn.

Ejemplos equivalentes:

- `https://ar.linkedin.com/in/juan-perez/`
- `https://www.linkedin.com/in/juan-perez`
- `linkedin.com/in/juan-perez`

Se guarda como:

`https://www.linkedin.com/in/juan-perez`

La tabla `candidates` es global. Aunque una búsqueda sea eliminada, el candidato se conserva para evitar volver a presentarlo como nuevo.

## Ejecutar localmente

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

Instalar:

```bash
pip install -r requirements.txt
```

Copiar `.streamlit/secrets.toml.example` como `.streamlit/secrets.toml` y agregar la API key.

Ejecutar:

```bash
streamlit run app.py
```

## Deploy en Streamlit Community Cloud

1. Subir este proyecto a GitHub.
2. Entrar a Streamlit Community Cloud.
3. Crear una app nueva.
4. Seleccionar el repositorio.
5. Main file: `app.py`.
6. En Secrets agregar:

```toml
OPENAI_API_KEY = "..."
OPENAI_MODEL = "gpt-5.2"
```

## Persistencia

SQLite funciona bien para desarrollo local.

En algunos hosts gratuitos el filesystem puede reiniciarse. Para producción o uso compartido conviene migrar `data/hunting.db` a Supabase/PostgreSQL.
