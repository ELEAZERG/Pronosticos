import requests
import streamlit as st
import engine as e

st.set_page_config(page_title="Pronósticos", page_icon="⚽", layout="centered")
BASE = "https://v3.football.api-sports.io"
HEAD = {"x-apisports-key": st.secrets.get("API_FOOTBALL_KEY", "")}
SEASON = st.secrets.get("SEASON", 2026)

# IDs de API-Football (verifica en tu panel si alguna liga no aparece)
LIGAS = {
    "Liga MX": 262, "Liga MX Femenil": 673, "MLS": 253, "La Liga": 140,
    "Premier League": 39, "Serie A (Italia)": 135, "Brasileirão Serie A": 71,
    "Primeira Liga (Portugal)": 94, "Premiership (Escocia)": 179,
    "Liga Profesional (Argentina)": 128, "Bundesliga": 78, "Saudi Pro League": 307,
    "Champions League": 2, "Pro League (Bélgica)": 144, "Liga DIMAYOR (Colombia)": 239,
}


def api(path, **params):
    r = requests.get(f"{BASE}/{path}", headers=HEAD, params=params, timeout=20)
    r.raise_for_status()
    j = r.json()
    if j.get("errors"):
        raise RuntimeError(str(j["errors"]))
    return j["response"]


@st.cache_data(ttl=86400)
def equipos(liga):
    return {t["team"]["name"]: t["team"]["id"] for t in api("teams", league=liga, season=SEASON)}


@st.cache_data(ttl=86400)
def prom_liga(liga):
    gf = pj = 0
    try:
        for grupo in api("standings", league=liga, season=SEASON)[0]["league"]["standings"]:
            for t in grupo:
                gf += t["all"]["goals"]["for"]; pj += t["all"]["played"]
    except Exception:
        return 0
    return gf / pj if pj else 0


@st.cache_data(ttl=3600)
def ultimos(team, liga, n, con_stats):
    fx = api("fixtures", team=team, league=liga, season=SEASON)
    fx = [f for f in fx if f["fixture"]["status"]["short"] in ("FT", "AET", "PEN")]
    fx = sorted(fx, key=lambda f: f["fixture"]["timestamp"])[-n:]
    out = {"gf": [], "gc": [], "goles": [], "corners": [], "tarjetas": []}
    for f in fx:
        local = f["teams"]["home"]["id"] == team
        h, a = f["goals"]["home"], f["goals"]["away"]
        if h is None:
            continue
        out["gf"].append(h if local else a); out["gc"].append(a if local else h)
        out["goles"].append(h + a)
        if con_stats:
            c = t = 0
            for eq in api("fixtures/statistics", fixture=f["fixture"]["id"]):
                for s in eq["statistics"]:
                    if s["type"] == "Corner Kicks": c += s["value"] or 0
                    if s["type"] in ("Yellow Cards", "Red Cards"): t += s["value"] or 0
            out["corners"].append(c); out["tarjetas"].append(t)
    return out


st.title("⚽ Pronósticos")
tab_f, tab_o = st.tabs(["Fútbol", "NBA · NFL · MLB"])

with tab_f:
    liga_n = st.selectbox("Liga", list(LIGAS))
    try:
        eqs = equipos(LIGAS[liga_n])
    except Exception as ex:
        st.error(f"No pude cargar equipos: {ex}"); st.stop()
    c1, c2 = st.columns(2)
    A = c1.selectbox("Local", sorted(eqs), index=None, placeholder="Escribe para buscar…")
    B = c2.selectbox("Visitante", sorted(eqs), index=None, placeholder="Escribe para buscar…")
    n = st.slider("Partidos a analizar", 5, 20, 10)
    stats_on = st.toggle("Incluir corners y tarjetas (gasta más consultas)", True)

    if st.button("Analizar", type="primary", disabled=not (A and B and A != B)):
        with st.spinner("Descargando partidos…"):
            da = ultimos(eqs[A], LIGAS[liga_n], n, stats_on)
            db = ultimos(eqs[B], LIGAS[liga_n], n, stats_on)
            la = prom_liga(LIGAS[liga_n])
        gA = e.expected_goals(e.wmean(da["gf"]), e.wmean(db["gc"]), la)
        gB = e.expected_goals(e.wmean(db["gf"]), e.wmean(da["gc"]), la)
        st.metric("Goles esperados", f"{gA + gB:.2f}", f"{A} {gA:.2f} · {B} {gB:.2f}")

        mercados = [("Goles", "goles", gA + gB, [0.5, 1.5, 2.5, 3.5], "poisson")]
        if stats_on:
            mercados += [
                ("Corners", "corners", (e.wmean(da["corners"]) + e.wmean(db["corners"])) / 2,
                 [7.5, 8.5, 9.5, 10.5, 11.5], "nbinom"),
                ("Tarjetas", "tarjetas", (e.wmean(da["tarjetas"]) + e.wmean(db["tarjetas"])) / 2,
                 [2.5, 3.5, 4.5, 5.5], "nbinom")]
        for nombre, k, lam, lines, kind in mercados:
            st.subheader(nombre)
            st.caption(f"{A}: {e.stats(da[k])}  \n{B}: {e.stats(db[k])}")
            st.dataframe(e.analyze_market(da[k], db[k], lam, lines, kind),
                         hide_index=True, use_container_width=True)
        st.info("✅ = prob. final ≥ 85%, cumplida ≥ 80% en los últimos partidos de AMBOS "
                "equipos y muestra ≥ 10. Si no hay ✅, no hay línea segura.")

    st.divider()
    st.subheader("Valor frente a la cuota")
    p = st.number_input("Probabilidad final (%)", 1.0, 99.0, 85.0)
    q = st.number_input("Cuota decimal", 1.01, 50.0, 1.30)
    v = e.value(p / 100, q) * 100
    st.write(f"Ventaja: **{v:+.1f} puntos** → " + ("hay valor" if v > 3 else "sin valor claro"))

with tab_o:
    st.write("Próxima fase: NBA (`nba_api`), NFL (nflverse) y MLB (API oficial), "
             "con distribución normal para puntos y Poisson para carreras.")
