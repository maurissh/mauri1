#!/usr/bin/env python3
# =====================================================================
#  ORDINA FREE-TV (IPTV) SECONDO TIVUSAT
#  Scarica la playlist Free-TV/IPTV, tiene solo i canali italiani
#  (tvg-country="IT"), assegna a ogni canale il numero LCN Tivusat,
#  riordina e salva il file. Solo Free-TV/IPTV, nessun'altra fonte.
#  Serve la libreria requests:  pip install requests
# =====================================================================

import re
import requests

# ----------------------------- CONFIG --------------------------------
FREETV = "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8"
COUNTRY_FILTER = 'tvg-country="IT"'  # tiene solo i canali italiani
OUTPUT_FILE = "lista_tivusat.m3u"
EPG_URL = "https://epgshare01.online/epgshare01/epg_ripper_IT1.xml.gz"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# i canali NON in elenco LCN finiscono in fondo? -> True per tenerli, False per scartarli
TIENI_CANALI_SCONOSCIUTI = False

# tag qualita' da ignorare nei nomi (NON includere "4k": serve a Rai 4K)
QUALITY_TAGS = ("fhd", "uhd", "hd", "sd", "h265", "h264", "hevc")

# Numerazione LCN Tivusat aggiornata al 01/04/2026 (chiavi normalizzate)
LCN_TIVUSAT = {
    "rai1": 1, "rai2": 2, "rai3": 3, "rete4": 4, "canale5": 5, "italia1": 6,
    "la7": 7, "tv8": 8, "nove": 9, "rai4": 10, "iris": 11, "la5": 12, "rai5": 13,
    "raimovie": 14, "raipremium": 15, "italia2": 16, "mediasetitalia2": 16,
    "mediasetextra": 17, "extra": 17, "tv2000": 18, "cielo": 19,
    "20": 20, "20mediaset": 20, "canale20": 20, "venti": 20,
    "raisport": 21, "raisportpiu": 21, "focus": 22, "raistoria": 23,
    "rainews24": 24, "rainews": 24, "tgcom24": 25, "mediasettgcom24": 25,
    "raiscuola": 26, "twentyseven": 27, "27": 27, "27twentyseven": 27,
    "dmax": 28, "dmaxitaly": 28, "la7cinema": 29, "la7d": 29,
    "wedotvmovies": 30, "wedomovies": 30, "wedotv": 30,
    "realtime": 31, "realtimeitaly": 31,
    "foodnetwork": 33, "foodnetworkitaly": 33, "cine34": 34,
    "radioitaliatv": 35, "rtl1025": 36, "rtl1025tv": 36,
    "discovery": 37, "discoveryitaly": 37, "discoverychannel": 37, "discoverytv": 37,
    "giallo": 38, "topcrime": 39, "boing": 40, "cartoonito": 41,
    "raigulp": 42, "raiyoyo": 43, "frisbee": 44, "k2": 46, "super": 47,
    "arte": 48, "mezzo": 49, "mezzotv": 49, "rdssocialtv": 50, "rdssocial": 50,
    "equtv": 51, "acisport": 52, "acisporttv": 52, "solocalcio": 54,
    "marcopolo": 55, "hgtv": 56, "hgtvitaly": 56, "hgtvhomegarden": 56, "homegarden": 56,
    "euronewsitalian": 58, "euronewsitaliano": 58,
    "discoveryturbo": 59, "discoveryturboitaly": 59, "wedobigstories": 60,
    "rtl1025caliente": 62, "radioitalialive": 63, "radiokisskisstv": 64,
    "radiozeta": 65, "radiozetatv": 65, "radiofreccia": 66, "radiofrecciatv": 66,
    "radiomontecarlotv": 67, "radiomontecarlo": 67, "rmc": 67,
    "virginradiotv": 68, "virginradio": 68, "france24": 69,
    "bbcnews": 70, "bbcnewseurope": 70, "aljazeeraenglish": 71, "rai4k": 210,
}
LCN_TIVUSAT = {re.sub(r"[^a-z0-9]", "", k.lower()): v for k, v in LCN_TIVUSAT.items()}


def normalize(name):
    """'La 7 HD' -> 'la7' : minuscolo, senza tag qualita', spazi, punteggiatura."""
    name = name.lower().strip()
    name = re.sub(r"\[.*?\]", " ", name)
    name = re.sub(r"\(.*?\)", " ", name)
    name = name.replace("it:", " ").replace(".it", " ")
    for tag in QUALITY_TAGS:
        name = re.sub(rf"\b{tag}\b", " ", name)
    return re.sub(r"[^a-z0-9]", "", name)


# ---------------------------------------------------------------------
#  tvg-id EPG (epgshare01 IT1) per LCN. Solo ID verificati: meglio
#  nessun EPG che un EPG sbagliato. ATTENZIONE: TV2000 e' .va (Vaticano).
# ---------------------------------------------------------------------
EPG_TVGID = {
    1: "Rai1.it", 2: "Rai2.it", 3: "Rai3.it", 4: "Rete4.it", 5: "Canale5.it",
    6: "Italia1.it", 7: "La7.it", 8: "TV8.it", 9: "Nove.it", 10: "Rai4.it",
    11: "Iris.it", 12: "La5.it", 13: "Rai5.it", 14: "RaiMovie.it", 15: "RaiPremium.it",
    16: "Italia2.it", 17: "MediasetExtra.it", 18: "TV2000.va", 19: "CieloTV.it",
    20: "20.it", 21: "RaiSport.it", 22: "Focus.it", 23: "RaiStoria.it",
    24: "RaiNews24.it", 25: "TGCom24.it", 26: "RaiScuola.it", 27: "27Twentyseven.it",
    28: "DMAXItaly.it", 29: "La7Cinema.it", 31: "RealTimeItaly.it",
    33: "FoodNetworkItaly.it", 34: "Cine34.it", 35: "RadioItaliaTV.it",
    36: "RTL1025TV.it", 37: "DiscoveryChannel.it", 38: "Giallo.it", 39: "TopCrime.it",
    40: "BoingItaly.it", 41: "CartoonitoItaly.it", 42: "RaiGulp.it", 43: "RaiYoyo.it",
    44: "Frisbee.it", 46: "K2.it", 47: "Super.it", 50: "RDSSocialTV.it",
    54: "SportitaliaSolocalcio.it", 56: "HGTVItaly.it", 64: "KissKissTV.it",
    65: "RadioZetaTV.it", 66: "RadioFrecciaTV.it", 67: "RadioMonteCarloTV.it",
    68: "VirginRadioTV.it", 210: "Rai4K.it",
}


def apply_chno(extinf, lcn):
    if 'tvg-chno="' in extinf:
        return re.sub(r'tvg-chno="\d+"', f'tvg-chno="{lcn}"', extinf)
    return re.sub(r"(#EXTINF:-?\d+)", rf'\1 tvg-chno="{lcn}"', extinf, count=1)


def apply_tvgid(extinf, lcn):
    """Imposta tvg-id dall'EPG. Se non ho un ID verificato per questo LCN,
    lascio quello eventualmente gia' presente in Free-TV."""
    tvgid = EPG_TVGID.get(lcn)
    if not tvgid:
        return extinf
    if 'tvg-id="' in extinf:
        return re.sub(r'tvg-id="[^"]*"', f'tvg-id="{tvgid}"', extinf)
    return re.sub(r"(#EXTINF:-?\d+)", rf'\1 tvg-id="{tvgid}"', extinf, count=1)


def main():
    print(f"Scarico Free-TV/IPTV...")
    r = requests.get(FREETV, headers=HEADERS, timeout=15)
    r.raise_for_status()
    lines = r.text.splitlines()

    noti = {}        # lcn -> miglior candidato (preferisce HD)
    sconosciuti = []  # canali non in elenco LCN

    extinf = ""
    for line in lines:
        line = line.strip()
        if line.startswith("#EXTINF"):
            extinf = line
        elif "://" in line and not line.startswith("#") and extinf:
            if COUNTRY_FILTER not in extinf:
                extinf = ""
                continue
            m = re.search(r",(.*)$", extinf)
            raw = m.group(1).strip() if m else ""
            key = normalize(raw)
            # Free-TV segna con "Ⓢ" i canali non-HD nel nome; se il simbolo
            # e' assente il canale si presume HD (filosofia "quality over
            # quantity" della fonte: un solo URL per canale, di norma in HD).
            is_hd = "Ⓢ" not in raw

            if key in LCN_TIVUSAT:
                lcn = LCN_TIVUSAT[key]
                ext = apply_chno(extinf, lcn)
                ext = apply_tvgid(ext, lcn)
                cand = {"lcn": lcn, "extinf": ext,
                        "url": line, "is_hd": is_hd, "name": raw}
                # se gia' presente, tengo solo se questa e' HD e l'altra no
                if lcn not in noti or (is_hd and not noti[lcn]["is_hd"]):
                    noti[lcn] = cand
            elif TIENI_CANALI_SCONOSCIUTI:
                sconosciuti.append({"extinf": extinf, "url": line, "name": raw})
            extinf = ""

    ordinati = sorted(noti.values(), key=lambda c: c["lcn"])

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(f'#EXTM3U url-tvg="{EPG_URL}"\n')
        for c in ordinati:
            f.write(c["extinf"] + "\n" + c["url"] + "\n")
        for c in sconosciuti:   # eventuali extra in fondo, senza numero
            f.write(c["extinf"] + "\n" + c["url"] + "\n")

    print(f"Fatto: {len(ordinati)} canali numerati", end="")
    if sconosciuti:
        print(f" + {len(sconosciuti)} senza LCN in fondo", end="")
    print(f" -> '{OUTPUT_FILE}'.")


if __name__ == "__main__":
    main()
