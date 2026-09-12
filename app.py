import streamlit as st
import pandas as pd
from database import (
    init_db, create_search, list_searches, get_search, update_search_status,
    delete_search, add_search_version, get_search_versions, get_candidates_for_search,
    add_batch, get_batches, add_candidate_to_batch, candidate_exists_global,
    update_search_core, get_global_candidates
)
from hunting import run_hunting
from excel_export import build_search_excel
from utils import normalize_linkedin_url
from styles import apply_voolkia_style

st.set_page_config(page_title="Sourcing Assistant RECRU", page_icon="🔎", layout="wide")
init_db()
apply_voolkia_style()

if "selected_search_id" not in st.session_state:
    st.session_state.selected_search_id = None

st.title("Sourcing Assistant RECRU")
st.caption("Sourcing asistido para Recruiting · Histórico por JD · Deduplicación global · Excel acumulativo")

menu = st.sidebar.radio("Navegación", ["Búsquedas", "Nueva búsqueda", "Base global"])


def split_lines(value: str):
    if not value:
        return []
    return [x.strip() for x in value.splitlines() if x.strip()]


if menu == "Nueva búsqueda":
    st.subheader("Nueva búsqueda")
    with st.form("new_search"):
        title = st.text_input("Nombre de la búsqueda", placeholder="Ej: Analista Funcional Ssr - Apps Mobile")
        location = st.text_input("Zona excluyente", value="Buenos Aires")
        seniority = st.text_input("Seniority", placeholder="Ej: Ssr")
        min_years = st.number_input("Años mínimos de experiencia", min_value=0, max_value=30, value=3)
        jd = st.text_area("JD completa", height=300)

        col1, col2 = st.columns(2)
        with col1:
            must_have = st.text_area(
                "Requisitos excluyentes",
                placeholder="Uno por línea\nAnalista Funcional\nApps mobile\nBuenos Aires",
                height=170,
            )
        with col2:
            nice_to_have = st.text_area(
                "Deseables",
                placeholder="Uno por línea\nAPIs\nTesting funcional\nOracle",
                height=170,
            )

        target = st.number_input("Cantidad objetivo de candidatos nuevos", min_value=5, max_value=100, value=20, step=5)
        submit = st.form_submit_button("Crear búsqueda", type="primary")

    if submit:
        if not title.strip() or not jd.strip():
            st.error("Completá al menos el nombre de la búsqueda y la JD.")
        else:
            search_id = create_search(title.strip(), location.strip(), seniority.strip(), int(min_years), int(target))
            add_search_version(
                search_id, jd, split_lines(must_have), split_lines(nice_to_have), "Versión inicial"
            )
            st.session_state.selected_search_id = search_id
            st.success("Búsqueda creada. Abrila desde Búsquedas para ejecutar el primer hunting.")

elif menu == "Búsquedas":
    searches = list_searches()
    st.subheader("Búsquedas guardadas")

    if not searches:
        st.info("Todavía no hay búsquedas guardadas.")
    else:
        df = pd.DataFrame(searches)
        visible = df[["id", "title", "status", "location", "candidate_count", "batch_count", "updated_at"]].copy()
        visible.columns = ["ID", "Búsqueda", "Estado", "Zona", "Candidatos", "Tandas", "Actualizada"]
        st.dataframe(visible, use_container_width=True, hide_index=True)

        options = {f'{x["id"]} · {x["title"]}': x["id"] for x in searches}
        chosen = st.selectbox("Abrir búsqueda", list(options.keys()))
        if chosen:
            st.session_state.selected_search_id = options[chosen]

        search_id = st.session_state.selected_search_id
        if search_id:
            s = get_search(search_id)
            versions = get_search_versions(search_id)
            batches = get_batches(search_id)
            candidates = get_candidates_for_search(search_id)

            st.divider()
            st.header(s["title"])
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Estado", s["status"])
            c2.metric("Candidatos únicos", len(candidates))
            c3.metric("Tandas", len(batches))
            c4.metric("Objetivo por tanda", s["target_count"])

            with st.expander("JD y requisitos actuales", expanded=True):
                current = versions[0]
                st.text_area("JD actual", current["jd"], height=240, disabled=True)
                a, b, c = st.columns(3)
                a.write("**Zona excluyente**")
                a.write(s["location"] or "—")
                b.write("**Excluyentes**")
                b.write("\n".join([f"- {x}" for x in current["must_have"]]) or "—")
                c.write("**Deseables**")
                c.write("\n".join([f"- {x}" for x in current["nice_to_have"]]) or "—")

            tab1, tab2, tab3, tab4 = st.tabs(["Buscar candidatos", "Histórico", "Cambiar requisitos", "Administrar"])

            with tab1:
                st.write("El hunting busca perfiles públicos, descarta URLs ya existentes en la base global y guarda solamente candidatos nuevos.")
                if not st.secrets.get("OPENAI_API_KEY", ""):
                    st.warning("Falta configurar OPENAI_API_KEY en `.streamlit/secrets.toml` o en Streamlit Cloud.")

                if st.button("Buscar candidatos nuevos", type="primary", use_container_width=True):
                    try:
                        with st.spinner("Buscando y evaluando perfiles públicos..."):
                            current = get_search_versions(search_id)[0]
                            existing_urls = {
                                normalize_linkedin_url(x["linkedin_url"])
                                for x in get_candidates_for_search(search_id)
                                if x.get("linkedin_url")
                            }

                            result = run_hunting(
                                title=s["title"], jd=current["jd"], location=s["location"],
                                seniority=s["seniority"], min_years=s["min_years"],
                                must_have=current["must_have"], nice_to_have=current["nice_to_have"],
                                target_count=s["target_count"], excluded_urls=existing_urls,
                            )

                            batch_id = add_batch(
                                search_id, current["id"], result["criteria_summary"], result.get("source_summary", "")
                            )

                            new_count = 0
                            duplicates = 0
                            for cand in result["candidates"]:
                                url = normalize_linkedin_url(cand.get("linkedin_url", ""))
                                if not url:
                                    continue
                                if candidate_exists_global(url):
                                    duplicates += 1
                                    continue

                                add_candidate_to_batch(
                                    search_id=search_id,
                                    batch_id=batch_id,
                                    name=cand.get("name", ""),
                                    linkedin_url=url,
                                    location=cand.get("location", ""),
                                    current_role=cand.get("current_role", ""),
                                    current_company=cand.get("current_company", ""),
                                    match_score=int(cand.get("match_score", 0)),
                                    priority=cand.get("priority", "Media"),
                                    evidence=cand.get("evidence", ""),
                                    validation=cand.get("validation", ""),
                                    source=cand.get("source", "web"),
                                )
                                new_count += 1

                        st.success(f"Tanda guardada: {new_count} candidatos nuevos.")
                        if duplicates:
                            st.info(f"{duplicates} perfiles fueron descartados por estar ya en la base global.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"No se pudo completar el hunting: {e}")

            with tab2:
                if not candidates:
                    st.info("Todavía no hay candidatos en esta búsqueda.")
                else:
                    cdf = pd.DataFrame(candidates)
                    cols = [
                        "name", "location", "match_score", "priority", "current_role", "current_company",
                        "batch_number", "evidence", "validation", "linkedin_url"
                    ]
                    st.dataframe(cdf[cols], use_container_width=True, hide_index=True)

                    excel_bytes = build_search_excel(search_id)
                    filename = f'{s["title"].replace(" ", "_")}_Historico.xlsx'
                    st.download_button(
                        "Descargar Excel histórico",
                        data=excel_bytes,
                        file_name=filename,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary",
                    )

                if batches:
                    st.markdown("#### Tandas")
                    bdf = pd.DataFrame(batches)
                    st.dataframe(
                        bdf[["batch_number", "created_at", "criteria_summary", "candidate_count"]],
                        use_container_width=True,
                        hide_index=True,
                    )

            with tab3:
                current = get_search_versions(search_id)[0]
                with st.form("change_requirements"):
                    new_location = st.text_input("Zona", value=s["location"] or "")
                    new_seniority = st.text_input("Seniority", value=s["seniority"] or "")
                    new_years = st.number_input("Años mínimos", min_value=0, max_value=30, value=int(s["min_years"] or 0))
                    new_jd = st.text_area("JD", value=current["jd"], height=260)
                    new_must = st.text_area("Excluyentes", value="\n".join(current["must_have"]), height=150)
                    new_nice = st.text_area("Deseables", value="\n".join(current["nice_to_have"]), height=150)
                    note = st.text_input("Qué cambió", placeholder="Ej: Se elimina experiencia financiera como excluyente")
                    save_version = st.form_submit_button("Guardar nueva versión", type="primary")

                if save_version:
                    update_search_core(search_id, new_location.strip(), new_seniority.strip(), int(new_years))
                    add_search_version(
                        search_id, new_jd, split_lines(new_must), split_lines(new_nice),
                        note.strip() or "Cambio de requisitos"
                    )
                    st.success("Nueva versión guardada. La próxima tanda usará estos criterios.")
                    st.rerun()

                st.markdown("#### Historial de versiones")
                vdf = pd.DataFrame(get_search_versions(search_id))
                st.dataframe(vdf[["version_number", "created_at", "change_note"]], use_container_width=True, hide_index=True)

            with tab4:
                status = st.selectbox("Estado", ["Activa", "Pausada", "Cerrada"], index=["Activa", "Pausada", "Cerrada"].index(s["status"]))
                if st.button("Actualizar estado"):
                    update_search_status(search_id, status)
                    st.success("Estado actualizado.")
                    st.rerun()

                st.warning("Eliminar borra esta búsqueda y su histórico. La base global de candidatos se conserva para evitar repeticiones futuras.")
                confirm = st.checkbox("Confirmo que quiero eliminar esta búsqueda")
                if st.button("Eliminar búsqueda", disabled=not confirm):
                    delete_search(search_id)
                    st.session_state.selected_search_id = None
                    st.success("Búsqueda eliminada.")
                    st.rerun()

elif menu == "Base global":
    st.subheader("Base global de candidatos")
    st.caption("Esta base es la barrera principal contra candidatos repetidos.")
    data = get_global_candidates()
    if not data:
        st.info("Todavía no hay candidatos guardados.")
    else:
        st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
