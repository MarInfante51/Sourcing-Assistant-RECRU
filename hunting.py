import json
import re
import streamlit as st
from openai import OpenAI
from utils import normalize_linkedin_url


def _extract_json(text: str):
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S | re.I)
    if fenced:
        text = fenced.group(1).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("El modelo no devolvió un JSON válido.")
    return json.loads(text[start:end + 1])


def run_hunting(
    title,
    jd,
    location,
    seniority,
    min_years,
    must_have,
    nice_to_have,
    target_count,
    excluded_urls=None,
):
    excluded_urls = excluded_urls or set()

    api_key = st.secrets.get("OPENAI_API_KEY", "")
    if not api_key:
        raise ValueError("Falta OPENAI_API_KEY en los secrets.")

    model = st.secrets.get("OPENAI_MODEL", "gpt-5.2")
    client = OpenAI(api_key=api_key)
    excluded_text = "\n".join(sorted(excluded_urls)) if excluded_urls else "Ninguna"

    prompt = f"""
Sos un sourcer IT especializado en búsqueda de perfiles profesionales públicos.

OBJETIVO:
Encontrar al menos {target_count} candidatos NUEVOS para esta búsqueda.

PUESTO:
{title}

UBICACIÓN EXCLUYENTE:
{location}

SENIORITY:
{seniority}

AÑOS MÍNIMOS:
{min_years}

JD:
{jd}

REQUISITOS EXCLUYENTES:
{json.dumps(must_have, ensure_ascii=False)}

DESEABLES:
{json.dumps(nice_to_have, ensure_ascii=False)}

PERFILES YA CONOCIDOS / NO REPETIR:
{excluded_text}

REGLAS:
1. Buscá perfiles profesionales públicos, priorizando páginas públicas de LinkedIn.
2. La ubicación debe cumplir el filtro indicado.
3. No inventes experiencia que no sea visible públicamente.
4. No uses ni infieras edad, género, foto, estado civil, salud, religión,
   orientación sexual, etnia u otros datos personales sensibles.
5. No incluyas URLs que aparezcan en NO REPETIR.
6. No fuerces todos los deseables: priorizá los excluyentes reales.
7. Si algo importante no es demostrable públicamente, ponelo en validation.
8. Ejecutá múltiples búsquedas X-Ray y variaciones de títulos/sinónimos.
9. Devolvé únicamente URLs públicas reales y verificables.
10. No inventes URLs de LinkedIn.

Devolvé SOLO JSON válido:
{{
  "criteria_summary": "resumen corto de la estrategia usada",
  "source_summary": "resumen corto de las fuentes públicas consultadas",
  "candidates": [
    {{
      "name": "Nombre Apellido",
      "linkedin_url": "https://...linkedin.com/in/...",
      "location": "ubicación visible",
      "current_role": "cargo visible",
      "current_company": "empresa visible",
      "match_score": 0,
      "priority": "Alta|Media/Alta|Media",
      "evidence": "evidencia profesional visible contra la JD",
      "validation": "puntos que deberían verificarse en contacto",
      "source": "web pública"
    }}
  ]
}}

Intentá superar el objetivo porque luego se eliminarán repetidos.
"""

    response = client.responses.create(
        model=model,
        tools=[{
            "type": "web_search_preview",
            "search_context_size": "high",
            "user_location": {
                "type": "approximate",
                "country": "AR",
                "city": "Buenos Aires",
                "region": "Buenos Aires",
                "timezone": "America/Argentina/Buenos_Aires",
            },
        }],
        tool_choice="auto",
        input=prompt,
        include=["web_search_call.action.sources"],
    )

    data = _extract_json(response.output_text)
    clean = []
    seen = set()

    for c in data.get("candidates", []):
        url = normalize_linkedin_url(c.get("linkedin_url", ""))
        if not url or url in excluded_urls or url in seen:
            continue
        seen.add(url)
        c["linkedin_url"] = url
        clean.append(c)

    data["candidates"] = clean
    return data
