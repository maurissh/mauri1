#!/usr/bin/env python3
# =====================================================================
#  TIVUSAT BUILDER  -  Maginet come base + sostituzione automatica
#  Logica: per ogni canale provo prima Maginet; se lo stream e' morto
#  passo alla fonte di soccorso successiva che risponde davvero.
#  Serve la libreria requests:  pip install requests
# =====================================================================

import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

# ----------------------------- CONFIG --------------------------------
BASE_SOURCE = "https://raw.githubusercontent.com/maginetweb-arch/TVITALIA/refs/heads/main/iptvit.m3u"

FALLBACK_SOURCES = [
    "https://iptv-org.github.io/iptv/countries/it.m3u",
    "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlists/playlist_italy.m3u8",
]

OUTPUT_FILE = "lista_tivusat.m3u"
EPG_URL = "https://epgshare01.online/epgshare01/epg_ripper_IT1.xml.gz"

HEADERS = {"User-Agent": "Mozilla/5.0"}
CHECK_TIMEOUT = 8        # secondi per considerare uno stream "morto"
MAX_WORKERS = 24         # quanti stream testo in parallelo
KEEP_DEAD_AS_FALLBACK = True   # se NESSUNA fonte risponde, tengo comunque Maginet come ripiego

QUALITY_TAGS = ("fhd", "uhd", "hd", "sd", "4k", "h265", "h264")

# LCN completa Tivusat
LCN_TIVUSAT = {
    "rai 1": 1, "rai1": 1, "rai 2": 2, "rai2": 2, "rai 3": 3, "rai3": 3,
    "rete 4": 4, "rete4": 4, "canale 5": 5, "canale5": 5, "italia 1": 6, "italia1": 6,
    "la7": 7, "tv8": 8, "tv 8": 8, "nove": 9,
    "rai 4": 10, "rai4": 10, "iris": 11, "la5": 12, "rai 5": 13, "rai5": 13,
    "rai movie": 14, "rai premium": 15, "italia 2": 16, "mediaset italia 2": 16,
    "mediaset extra": 17, "extra": 17, "tv2000": 18, "tv 2000": 18, "cielo": 19,
    "20 mediaset": 20, "canale 20": 20, "20": 20,
    "rai sport": 21, "raisport": 21, "rai sport +": 21, "focus": 22, "rai storia": 23,
    "rai news 24": 24, "rainews24": 24, "tgcom24": 25, "mediaset tgcom24": 25,
    "rai scuola": 26, "twentyseven": 27, "27": 27, "dmax": 28, "la7d": 29, "la7 cinema": 29,
    "we do movies": 30, "real time": 31, "qvc": 32, "food network": 33, "cine34": 34, "cine 34": 34,
    "radio italia tv": 35, "rtl 102.5": 36, "rtl 102.5 tv": 36, "discovery": 37, "warner tv": 37,
    "giallo": 38, "top crime": 39, "topcrime": 39, "boing": 40, "cartoonito": 41,
    "rai gulp": 42, "rai yoyo": 43, "frisbee": 44, "k2": 46, "super!": 47, "super": 47,
    "arte": 48, "mezzo": 49, "rds social tv": 50, "sky tg24": 50, "equ tv": 51,
    "aci sport": 52, "sportitalia": 54, "marcopolo": 55, "hgtv": 56, "motor trend": 57,
    "euronews italian": 58, "discovery turbo": 59, "turbo": 59,
    "radio kiss kiss tv": 64, "radio zeta tv": 65, "radio freccia tv": 66,
    "france 24": 69, "bbc news": 70, "al jazeera english": 71, "rai 4k": 210,
}

# mappa inversa LCN -> nome (solo per messaggi piu' leggibili)
LCN_NAME = {}
for _name, _n in LCN_TIVUSAT.items():
    LCN_NAME.setdefault(_n, _name)


# --------------------------- UTILITY ---------------------------------
def clean_channel_name(name):
    """Normalizza il nome per matcharlo col dizionario LCN."""
    name = name.lower().strip()
    name = re.sub(r"\[.*?\]", "", name)      # [ ... ]
    name = re.sub(r"\(.*?\)", "", name)      # ( ... )  -> non-greedy, niente over-match
    for tag in QUALITY_TAGS:                 # togli tag qualita' come parole intere
        name = re.sub(rf"\b{tag}\b", "", name)
    name = name.replace(".it", "").replace("it:", "")
    name = re.sub(r"\s+", " ", name)
    return name.strip()


def apply_chno(extinf, lcn):
    """Imposta/sovrascrive tvg-chno con il numero Tivusat."""
    if 'tvg-chno="' in extinf:
        return re.sub(r'tvg-chno="\d+"', f'tvg-chno="{lcn}"', extinf)
    return re.sub(r"(#EXTINF:-?\d+)", rf'\1 tvg-chno="{lcn}"', extinf, count=1)


def parse_source(url):
    """Scarica una playlist e restituisce i candidati che combaciano con la LCN."""
    out = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        lines = r.text.splitlines()
    except Exception as e:
        print(f"  [!] impossibile caricare {url}: {e}")
        return out

    extinf = ""
    for line in lines:
        line = line.strip()
        if line.startswith("#EXTINF"):
            extinf = line
        elif "://" in line and not line.startswith("#") and extinf:
            m = re.search(r",(.*)$", extinf)
            raw = m.group(1).strip() if m else ""
            clean = clean_channel_name(raw)
            if clean in LCN_TIVUSAT:
                lcn = LCN_TIVUSAT[clean]
                is_hd = any(t in raw.lower() for t in ("hd", "fhd", "uhd", "4k"))
                out.append({
                    "lcn": lcn,
                    "extinf": apply_chno(extinf, lcn),
                    "url": line,
                    "is_hd": is_hd,
                })
            extinf = ""
    return out


def is_stream_alive(url):
    """Health-check leggero: lo stream risponde 200 e manda dei byte?"""
    try:
        r = requests.get(url, headers=HEADERS, timeout=CHECK_TIMEOUT,
                         stream=True, allow_redirects=True)
        if r.status_code != 200:
            r.close()
            return False
        ctype = r.headers.get("Content-Type", "").lower()
        chunk = next(r.iter_content(chunk_size=2048), b"")
        r.close()
        # se e' un manifest HLS deve contenere l'header M3U
        if url.lower().endswith(".m3u8") or "mpegurl" in ctype:
            return b"#EXTM3U" in chunk or b"#EXT" in chunk
        return len(chunk) > 0
    except Exception:
        return False


def test_urls(urls):
    """Testa tutti gli URL in parallelo -> dict {url: True/False}."""
    urls = list(urls)
    results = {}
    done = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = {ex.submit(is_stream_alive, u): u for u in urls}
        for fut in as_completed(futs):
            u = futs[fut]
            try:
                results[u] = fut.result()
            except Exception:
                results[u] = False
            done += 1
            print(f"    testati {done}/{len(urls)}", end="\r")
    print()
    return results


# ----------------------------- MAIN ----------------------------------
def main():
    # FASE 1 - raccolta candidati (Maginet = priorita' 0, poi i soccorsi)
    print("FASE 1: raccolgo i candidati...")
    candidates = {}   # lcn -> lista di candidati
    for prio, src in enumerate([BASE_SOURCE] + FALLBACK_SOURCES):
        tag = "BASE (Maginet)" if prio == 0 else f"soccorso #{prio}"
        print(f"  {tag}: {src}")
        for ch in parse_source(src):
            ch["priority"] = prio
            candidates.setdefault(ch["lcn"], []).append(ch)

    # ordino i candidati: prima priorita' fonte, poi HD prima di SD
    for lcn in candidates:
        candidates[lcn].sort(key=lambda c: (c["priority"], 0 if c["is_hd"] else 1))

    # FASE 2 - testo TUTTI gli stream unici una volta sola
    all_urls = {c["url"] for lst in candidates.values() for c in lst}
    print(f"\nFASE 2: verifico {len(all_urls)} stream unici (timeout {CHECK_TIMEOUT}s)...")
    alive = test_urls(all_urls)

    # FASE 3 - per ogni canale prendo il primo candidato VIVO
    print("\nFASE 3: scelgo la fonte migliore per ogni canale...")
    chosen = {}
    for lcn, lst in candidates.items():
        live = next((c for c in lst if alive.get(c["url"])), None)
        if live:
            chosen[lcn] = live
            if live["priority"] != 0:
                print(f"  [~] LCN {lcn:>3} {LCN_NAME.get(lcn,''):<18} Maginet KO -> uso soccorso #{live['priority']}")
        elif KEEP_DEAD_AS_FALLBACK:
            chosen[lcn] = lst[0]
            print(f"  [!] LCN {lcn:>3} {LCN_NAME.get(lcn,''):<18} nessuna fonte attiva, tengo il ripiego")

    # FASE 4 - scrittura file ordinato per LCN
    final = sorted(chosen.values(), key=lambda c: c["lcn"])
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(f'#EXTM3U url-tvg="{EPG_URL}"\n')
        for c in final:
            f.write(c["extinf"] + "\n" + c["url"] + "\n")

    n_live = sum(1 for c in final if alive.get(c["url"]))
    print(f"\nFatto: {len(final)} canali scritti in '{OUTPUT_FILE}' "
          f"({n_live} verificati attivi, {len(final) - n_live} ripieghi).")


if __name__ == "__main__":
    main()
