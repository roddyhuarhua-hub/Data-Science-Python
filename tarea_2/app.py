"""Dashboard de la Tarea 2: explorar documentos (OCR) y entrevistas (ASR) ya procesados.

Solo lee los CSV de datos/ y los ejemplos publicables de datos/ejemplos/: no carga ningún modelo.
    streamlit run app.py
"""
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

BASE = Path(__file__).resolve().parent
D = BASE / "datos"
st.set_page_config(page_title="Voces y documentos peruanos", page_icon="🎙️", layout="wide")


@st.cache_data
def cargar():
    docs = pd.read_csv(D / "documentos.csv").fillna({"texto_ocr": "", "texto_referencia": ""})
    aud = pd.read_csv(D / "transcripciones.csv").fillna({"texto_asr": "", "texto_referencia": ""})
    ext = pd.read_csv(D / "extraccion_llm.csv") if (D / "extraccion_llm.csv").exists() else pd.DataFrame(columns=["id", "campos_json"])
    met = pd.read_csv(D / "metricas.csv") if (D / "metricas.csv").exists() else pd.DataFrame()
    fue = pd.read_csv(D / "fuentes.csv")
    audit = pd.read_csv(D / "auditoria_resumen.csv") if (D / "auditoria_resumen.csv").exists() else None
    return docs, aud, ext, met, fue, audit


def cer_wer(ref, hip, palabras):
    import jiwer, re, unicodedata
    def n(t):
        t = re.sub(r"\[HABLANTE_\d+\]", " ", str(t)).lower()
        t = re.sub(r"[^\w\s']", " ", unicodedata.normalize("NFC", t))
        return re.sub(r"\s+", " ", t).strip()
    return (jiwer.wer if palabras else jiwer.cer)(n(ref), n(hip) or "∅")


docs, aud, ext, met, fue, audit = cargar()
campos = dict(zip(ext.id, ext.campos_json))

st.title("¿Podemos convertir documentos escaneados y entrevistas peruanas en un archivo de texto buscable?")
st.caption("Tarea 2 · Data Science con Python · RoddyHuarhua (@roddyhuarhua-hub)")
st.markdown(
    "**Método.** 25 documentos de Wikimedia Commons (impresos, fotos y manuscritos) leídos con **PaddleOCR**; "
    f"{len(aud)} clips en español peruano (OpenSLR 73 y entrevistas de Commons) transcritos con **faster-whisper + VAD**, "
    "con diarización en los audios de varias voces. Todo se seudonimizó y se revisó antes de publicarlo. "
    "Un LLM local extrajo campos en JSON y se auditó a mano. Los modelos corrieron en los notebooks; esta app solo lee los resultados."
)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Documentos procesados", len(docs))
c2.metric("Minutos de audio transcritos", f"{aud.duracion_seg.sum() / 60:.1f}")
if len(met):
    d, a = met[met.modalidad == "documentos"].sort_values("CER"), met[met.modalidad == "audio"].sort_values("WER")
    c3.metric(f"CER · {d.modelo.iloc[0]}", f"{d.CER.iloc[0]:.2f}", f"{d.CER.iloc[0] - d.CER.iloc[-1]:+.2f} vs {d.modelo.iloc[-1]}", delta_color="inverse")
    c4.metric(f"WER · {a.modelo.iloc[0]}", f"{a.WER.iloc[0]:.2f}", f"{a.WER.iloc[0] - a.WER.iloc[-1]:+.2f} vs {a.modelo.iloc[-1]}", delta_color="inverse")
c5.metric("Acuerdo LLM vs auditoría", f"{audit.acuerdo[0] / audit.total[0]:.0%} ({audit.acuerdo[0]}/{audit.total[0]})" if audit is not None else "pendiente")

tab_res, tab_doc, tab_aud, tab_fue = st.tabs(["📊 Resultados", "📄 Documentos", "🎧 Audios", "📚 Fuentes y licencias"])

with tab_res:
    st.subheader("Buscar en todos los textos")
    q = st.text_input("Palabra o frase", placeholder="ej.: Lima, independencia, mercado…")
    col_a, col_b = st.columns(2)
    tipos = col_a.multiselect("Tipo de documento", sorted(docs.tipo.unique()), default=sorted(docs.tipo.unique()))
    modelos = col_b.multiselect("Modelo", sorted(set(docs.modelo_ocr) | set(aud.modelo_asr)),
                                default=sorted(set(docs.modelo_ocr) | set(aud.modelo_asr)))
    dur = st.slider("Duración del audio (s)", 0, int(aud.duracion_seg.max()) + 1, (0, int(aud.duracion_seg.max()) + 1))
    df_d = docs[docs.tipo.isin(tipos) & docs.modelo_ocr.isin(modelos)]
    df_a = aud[aud.modelo_asr.isin(modelos) & aud.duracion_seg.between(*dur)]
    if q:
        df_d = df_d[df_d.texto_ocr.str.contains(q, case=False, regex=False)]
        df_a = df_a[df_a.texto_asr.str.contains(q, case=False, regex=False)]
    tabla = pd.concat([
        df_d.assign(modalidad="documento", texto=df_d.texto_ocr, modelo=df_d.modelo_ocr)[["id", "modalidad", "tipo", "modelo", "texto"]],
        df_a.assign(modalidad="audio", tipo="audio", texto=df_a.texto_asr, modelo=df_a.modelo_asr)[["id", "modalidad", "tipo", "modelo", "texto"]],
    ])
    st.write(f"**{len(tabla)}** registros ({len(df_d)} documentos, {len(df_a)} audios)")
    g1, g2 = st.columns(2)
    if len(df_d):
        g1.plotly_chart(px.histogram(df_d.assign(caracteres=df_d.texto_ocr.str.len()), x="caracteres", color="tipo",
                                     title="Caracteres reconocidos por documento"), use_container_width=True)
    if len(df_a):
        g2.plotly_chart(px.bar(df_a.sort_values("duracion_seg"), x="id", y="duracion_seg", color="n_hablantes",
                               title="Duración de cada clip (s) y hablantes detectados"), use_container_width=True)
    if len(met):
        m = met.melt(id_vars=["modelo", "modalidad"], value_vars=[c for c in ["CER", "WER"] if c in met], var_name="métrica", value_name="error").dropna()
        st.plotly_chart(px.bar(m, x="modelo", y="error", color="modalidad", facet_col="métrica",
                               title="Error de cada modelo sobre las mismas 10 muestras (menor es mejor)"), use_container_width=True)
        st.dataframe(met, use_container_width=True, hide_index=True)
    st.dataframe(tabla, use_container_width=True, hide_index=True)
    st.download_button("Descargar CSV (textos revisados y seudonimizados)", tabla.to_csv(index=False).encode("utf-8"),
                       "resultados_filtrados.csv", "text/csv")

with tab_doc:
    i = st.selectbox("Documento", docs.id, format_func=lambda x: f"{x} · {docs.set_index('id').tipo[x]}")
    r = docs.set_index("id").loc[i]
    izq, der = st.columns([2, 3])
    img = D / "ejemplos" / "img" / f"{i}.jpg"
    if img.exists():
        izq.image(str(img), caption=r.fuente)
    else:
        izq.info("Imagen no publicada; se muestra solo el texto.")
    der.markdown(f"**Tipo:** {r.tipo} · **Modelo:** {r.modelo_ocr}")
    der.text_area("Texto OCR", r.texto_ocr, height=220)
    if r.texto_referencia:
        der.text_area("Referencia manual", r.texto_referencia, height=150)
        der.metric("CER de este documento", f"{cer_wer(r.texto_referencia, r.texto_ocr, False):.2f}")
    if i in campos:
        der.markdown("**Campos extraídos por el LLM**")
        der.json(json.loads(campos[i]))

with tab_aud:
    j = st.selectbox("Clip", aud.id, format_func=lambda x: f"{x} · {aud.set_index('id').duracion_seg[x]:.0f} s")
    r = aud.set_index("id").loc[j]
    st.markdown(f"**Duración:** {r.duracion_seg:.0f} s · **Hablantes detectados:** {r.n_hablantes} · **Modelo:** {r.modelo_asr}")
    ogg = D / "ejemplos" / "audio" / f"{j}.ogg"
    if ogg.exists():
        st.audio(str(ogg))
        st.caption("Primeros 45 s del clip (licencia CC BY-SA 4.0, ver pestaña Fuentes).")
    else:
        st.info("Este clip no se publica en la app; se muestra su transcripción.")
    texto = r.texto_asr.replace("[HABLANTE_", "\n\n**[HABLANTE_").replace("] ", "]** ")
    st.markdown(texto)
    alt = D / "asr_alternativo.csv"
    if r.texto_referencia:
        cols = st.columns(2)
        cols[0].text_area("Referencia humana", r.texto_referencia, height=150)
        cols[1].metric("WER de faster-whisper small", f"{cer_wer(r.texto_referencia, r.texto_asr, True):.2f}")
        if alt.exists():
            a2 = pd.read_csv(alt).set_index("id")
            if j in a2.index:
                cols[1].text_area(f"Transcripción de {a2.modelo[j]}", a2.texto[j], height=150)
                cols[1].metric(f"WER de {a2.modelo[j]}", f"{cer_wer(r.texto_referencia, a2.texto[j], True):.2f}")
    if j in campos:
        st.markdown("**Campos extraídos por el LLM**")
        st.json(json.loads(campos[j]))

with tab_fue:
    st.dataframe(fue, use_container_width=True, hide_index=True)
    st.markdown("OpenSLR 73: Guevara-Rukoz et al. (2020), *Crowdsourcing Latin American Spanish for Low-Resource Text-to-Speech*, LREC. "
                "Entrevistas e imágenes: Wikimedia Commons, con el autor y la licencia de cada archivo.")
