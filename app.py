import streamlit as st
import pandas as pd
import os
import io
from datetime import datetime
import folium
from folium.plugins import Fullscreen
from streamlit_folium import st_folium

# --- KONFIGURACJA ---
PLIK_BAZY = "flota_data.csv"
DATA_FILE = os.path.join(os.getcwd(), PLIK_BAZY)

AUTA = ["AYGO 28", "AYGO 29", "LUPO", "GOLF"]

STREFY_KOORDYNATY = {
    "Parking Biuro": [54.000567, 16.975717],
    "CIT": [54.000244, 16.974717],
    "Urząd": [53.999495, 16.974746],
    "Biblioteka": [54.000012, 16.974869],
    "Inne / Kliknij na mapie": [None, None],
}
STREFY_LISTA = list(STREFY_KOORDYNATY.keys())

KOLORY_AUT = {
    "AYGO 28": "red",
    "AYGO 29": "lightgreen",
    "LUPO": "blue",
    "GOLF": "purple",
}
KOLORY_CSS = {
    "red": "red",
    "lightgreen": "limegreen",
    "blue": "deepskyblue",
    "purple": "magenta",
}


# --- FUNKCJE DANYCH ---

def init_empty_df():
    cols = [
        "Numer", "Data", "Auto", "Kierowca", "Cel", "Trasa",
        "Licznik_poczatek", "Licznik_koniec", "Przejechane_km",
        "Strefa", "Opis_miejsca", "Lat", "Lon", "W_drodze",
    ]
    return pd.DataFrame(columns=cols)


def load_data():
    if not os.path.exists(DATA_FILE):
        df = init_empty_df()
        df.to_csv(DATA_FILE, index=False, encoding="utf-8-sig")
        return df

    df = None
    for enc in ("utf-8", "cp1250", "latin1"):
        try:
            df = pd.read_csv(DATA_FILE, encoding=enc)
            break
        except UnicodeDecodeError:
            df = None
    if df is None:
        try:
            os.rename(DATA_FILE, DATA_FILE + ".bak")
        except OSError:
            pass
        df = init_empty_df()
        df.to_csv(DATA_FILE, index=False, encoding="utf-8-sig")
        return df

    base_df = init_empty_df()
    for col in base_df.columns:
        if col not in df.columns:
            if col in [
                "Licznik_poczatek",
                "Licznik_koniec",
                "Przejechane_km",
                "Lat",
                "Lon",
                "Numer",
            ]:
                df[col] = 0
            elif col == "W_drodze":
                df[col] = False
            else:
                df[col] = ""

    if "W_drodze" in df.columns:
        df["W_drodze"] = df["W_drodze"].astype(str).str.lower().isin(
            ["true", "1", "yes", "t", "y"]
        )

    return df[base_df.columns]


def save_df(df: pd.DataFrame):
    df.to_csv(DATA_FILE, index=False, encoding="utf-8-sig")


def get_next_number(df):
    if df.empty:
        return 1
    try:
        return int(df["Numer"].max()) + 1
    except Exception:
        return 1


def get_last_odometer(df, auto):
    if df.empty:
        return 0
    sub = df[df["Auto"] == auto]
    if sub.empty:
        return 0
    try:
        return int(sub["Licznik_koniec"].max())
    except Exception:
        return 0


def get_car_status(df, auto):
    if df.empty:
        return "Wolne", None
    sub = df[df["Auto"] == auto].sort_values(by="Numer", ascending=False)
    if sub.empty:
        return "Wolne", None
    row = sub.iloc[0]
    is_busy = bool(row.get("W_drodze", False))
    return ("W trasie", row.get("Kierowca", "")) if is_busy else (
        "Wolne",
        row.get("Kierowca", ""),
    )


def get_open_trip_index(df, auto):
    """Index ostatniej otwartej trasy (W_drodze=True) lub None."""
    if df.empty:
        return None
    sub = df[(df["Auto"] == auto) & (df["W_drodze"] == True)].sort_values(
        by="Numer", ascending=False
    )
    if sub.empty:
        return None
    return sub.index[0]


# --- UI START ---

st.set_page_config(page_title="Flota", page_icon="🚗", layout="wide")
st.title("🚗 Ewidencja Floty")

df = load_data()

# --- SESJA ---

if "selected_auto" not in st.session_state:
    st.session_state["selected_auto"] = AUTA[0]
if "action_type" not in st.session_state:
    st.session_state["action_type"] = "oddaj"  # 'pobierz' / 'oddaj'


# --- PANEL GÓRNY: STAN FLOTY ---

st.subheader("🚦 Stan floty")
cols = st.columns(len(AUTA))
for i, auto in enumerate(AUTA):
    status, kier = get_car_status(df, auto)
    with cols[i]:
        st.write(f"**{auto}**")
        if status == "W trasie":
            st.error(f"🔴 W trasie ({kier})")
            if st.button("Oddaj", key=f"b_in_{i}"):
                st.session_state["selected_auto"] = auto
                st.session_state["action_type"] = "oddaj"
                st.rerun()
        else:
            st.success("🟢 Wolne")
            if st.button("Pobierz", key=f"b_out_{i}"):
                st.session_state["selected_auto"] = auto
                st.session_state["action_type"] = "pobierz"
                st.rerun()

st.divider()

# --- MAPA ---

st.info("Auta w trasie są ukryte na mapie.")
center = [54.000567, 16.975717]

vis = df[df["W_drodze"] == False]
if not vis.empty:
    for _, r in vis.iterrows():
        try:
            if float(r["Lat"]) != 0:
                center = [r["Lat"], r["Lon"]]
                break
        except Exception:
            pass

m = folium.Map(location=center, zoom_start=14)

Fullscreen(
    position="topright",
    title="Pełny ekran",
    title_cancel="Zamknij pełny ekran",
    force_separate_button=True,
).add_to(m)

legend_html = """
<div style="
    position: absolute; top: 10px; left: 10px; z-index:9999;
    background-color: rgba(255,255,255,0.95);
    padding: 10px 14px; border: 2px solid #000;
    font-size: 14px; font-family: Arial, sans-serif;
    color: #000; text-shadow: 0 0 3px #fff;">
<b>Legenda</b><br>
"""
for a in AUTA:
    c = KOLORY_CSS.get(KOLORY_AUT.get(a), "blue")
    legend_html += (
        f'<span style="color:{c}; font-size:18px;">■</span> '
        f'<span style="color:#000;">{a}</span><br>'
    )
legend_html += "</div>"
m.get_root().html.add_child(folium.Element(legend_html))

latest = df.sort_values("Numer", ascending=False).drop_duplicates("Auto")
for _, r in latest.iterrows():
    if r["W_drodze"]:
        continue
    try:
        lat, lon = float(r["Lat"]), float(r["Lon"])
        if lat != 0:
            color = KOLORY_AUT.get(r["Auto"], "blue")
            # znacznik z ikoną
            folium.Marker(
                [lat, lon],
                popup=f"<b>{r['Auto']}</b><br>{r['Opis_miejsca']}",
                tooltip=r["Auto"],
                icon=folium.Icon(color=color, icon="car", prefix="fa"),
            ).add_to(m)
            # etykieta z nazwą auta obok znacznika – większa czcionka
            folium.map.Marker(
                [lat, lon],
                icon=folium.DivIcon(
                    html=(
                        '<div style="font-size: 16px; font-weight:bold; '
                        'color:black; text-shadow: 1px 1px 2px white;">'
                        f'{r["Auto"]}</div>'
                    )
                ),
            ).add_to(m)
    except Exception:
        pass

out_map = st_folium(m, height=400, width="100%")

st.divider()

# --- FORMULARZ + HISTORIA / EKSPORT ---

c_form, c_hist = st.columns([1, 2])

with c_form:
    act = st.session_state["action_type"]
    aut = st.session_state["selected_auto"]

    status_auta, kto_jedzie = get_car_status(df, aut)
    open_idx = get_open_trip_index(df, aut)

    if act == "pobierz":
        st.subheader(f"🚀 WYJAZD: {aut}")
        st.caption("Wyjazd: podajesz kierowcę i licznik startowy. Resztę wpiszesz przy powrocie.")
    else:
        st.subheader(f"🏁 POWRÓT: {aut}")
        st.caption("Powrót: uzupełniasz cel, trasę, licznik końcowy i miejsce parkowania.")

    c_lat, c_lon = 0.0, 0.0
    if out_map and out_map.get("last_clicked"):
        c_lat = out_map["last_clicked"]["lat"]
        c_lon = out_map["last_clicked"]["lng"]
        if act == "oddaj":
            st.caption(f"📍 Kliknięto: {c_lat:.5f}, {c_lon:.5f}")

    with st.form("f1"):
        d_wyj = st.date_input("Data", value=datetime.now())
        last_km = get_last_odometer(df, aut)

        kier = st.text_input("Kierowca", value=kto_jedzie or "")

        if act == "pobierz":
            st.caption("Licznik na starcie trasy")
            km_start = st.number_input(
                "Licznik start",
                value=int(last_km),
                min_value=int(last_km),
                step=1,
            )
            km_end = km_start
            cel = ""
            trasa = ""
            strefa = "W trasie"
            opis = "Wyjazd"
            s_lat, s_lon = 0.0, 0.0

        else:
            if open_idx is None:
                st.warning("To auto nie ma otwartej trasy. Najpierw użyj 'Pobierz'.")
            st.caption("Cel i trasa")
            c1, c2 = st.columns(2)
            cel = c1.text_input("Cel")
            t1, t2, t3 = st.columns(3)
            trasa = " -> ".join(
                filter(
                    None,
                    [
                        t1.text_input("Punkt 1"),
                        t2.text_input("Punkt 2"),
                        t3.text_input("Punkt 3"),
                    ],
                )
            )

            st.caption("Liczniki")
            km_start = last_km
            km_end = st.number_input(
                "Licznik końcowy",
                value=int(last_km),
                min_value=int(last_km),
                step=1,
            )

            st.write("---")
            st.write("Lokalizacja parkowania:")
            strefa = st.selectbox("Miejsce parkowania", STREFY_LISTA)
            s_lat, s_lon = STREFY_KOORDYNATY[strefa]
            if strefa == "Inne / Kliknij na mapie":
                cc1, cc2 = st.columns(2)
                s_lat = cc1.number_input("Lat", value=c_lat, format="%.5f")
                s_lon = cc2.number_input("Lon", value=c_lon, format="%.5f")
            opis = st.text_input("Opis miejsca", value="")

        if st.form_submit_button("Zapisz", type="primary"):
            if act == "pobierz":
                new_num = get_next_number(df)
                entry = {
                    "Numer": new_num,
                    "Data": d_wyj.strftime("%Y-%m-%d"),
                    "Auto": aut,
                    "Kierowca": kier,
                    "Cel": "",
                    "Trasa": "",
                    "Licznik_poczatek": int(km_start),
                    "Licznik_koniec": int(km_start),
                    "Przejechane_km": 0,
                    "Strefa": "W trasie",
                    "Opis_miejsca": "Wyjazd",
                    "Lat": 0.0,
                    "Lon": 0.0,
                    "W_drodze": True,
                }
                df2 = pd.concat([df, pd.DataFrame([entry])], ignore_index=True)
                save_df(df2)
                st.success("Wyjazd zapisany. Auto oznaczone jako 'W trasie'.")
                st.session_state["action_type"] = "oddaj"
                st.session_state["selected_auto"] = aut
                st.rerun()
            else:
                if open_idx is None:
                    st.error("Brak otwartej trasy dla tego auta.")
                else:
                    if km_end < last_km:
                        st.error("Licznik końcowy nie może być mniejszy niż ostatni zapisany.")
                    elif strefa == "Inne / Kliknij na mapie" and s_lat == 0:
                        st.error("Kliknij na mapie lub wpisz współrzędne.")
                    else:
                        df2 = df.copy()
                        start_val = int(df2.loc[open_idx, "Licznik_poczatek"])
                        przejechane = int(km_end - start_val)
                        df2.loc[open_idx, "Data"] = d_wyj.strftime("%Y-%m-%d")
                        df2.loc[open_idx, "Kierowca"] = kier
                        df2.loc[open_idx, "Cel"] = cel
                        df2.loc[open_idx, "Trasa"] = trasa
                        df2.loc[open_idx, "Licznik_koniec"] = int(km_end)
                        df2.loc[open_idx, "Przejechane_km"] = przejechane
                        df2.loc[open_idx, "Strefa"] = strefa
                        df2.loc[open_idx, "Opis_miejsca"] = opis
                        df2.loc[open_idx, "Lat"] = float(s_lat) if s_lat else 0.0
                        df2.loc[open_idx, "Lon"] = float(s_lon) if s_lon else 0.0
                        df2.loc[open_idx, "W_drodze"] = False
                        save_df(df2)
                        st.success("Powrót zapisany. Trasa domknięta.")
                        st.session_state["action_type"] = "oddaj"
                        st.rerun()

with c_hist:
    st.subheader("📋 Historia")
    if not df.empty:
        df_view = df.sort_values("Numer", ascending=False)
        st.dataframe(
            df_view[
                [
                    "Numer",
                    "Data",
                    "Auto",
                    "Kierowca",
                    "Cel",
                    "Trasa",
                    "Licznik_poczatek",
                    "Licznik_koniec",
                    "Przejechane_km",
                    "W_drodze",
                ]
            ],
            use_container_width=True,
        )

        st.write("---")
        st.subheader("📥 Eksport do Excela")
        auto_export = st.selectbox("Wybierz auto do eksportu", ["Wszystkie"] + AUTA)

        if auto_export == "Wszystkie":
            df_export = df_view.copy()
        else:
            df_export = df_view[df_view["Auto"] == auto_export].copy()

        if st.button("Przygotuj plik Excel"):
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine="xlsxwriter") as w:
                df_export.to_excel(w, index=False, sheet_name="Ewidencja")
            buf.seek(0)
            fname = "Ewidencja_Flota"
            if auto_export != "Wszystkie":
                fname += f"_{auto_export.replace(' ', '_')}"
            fname += f"_{datetime.now().strftime('%Y%m%d')}.xlsx"
            st.download_button(
                "Pobierz plik",
                buf,
                file_name=fname,
                mime="application/vnd.ms-excel",
            )
    else:
        st.info("Brak zapisanych przejazdów.")
