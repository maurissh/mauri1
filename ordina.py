#!/usr/bin/env python3
# =====================================================================
#  TIVUSAT BUILDER  -  Maginet come base + sostituzione automatica
#  - Maginet = fonte prioritaria; se uno stream e' morto si passa
#    alla prima fonte di soccorso che risponde davvero.
#  - Nomi normalizzati: "La 7", "LA7 HD", "la7" combaciano tutti.
#  - Numerazione LCN aggiornata al 01/04/2026.
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

# Mettere a False quando si gira da GitHub Actions / server estero:
# il geo-blocking farebbe risultare "morti" gli stream italiani validi.
# Con False non si testa nulla -> vince sempre Maginet, i soccorsi
# riempiono solo i buchi (comportamento sicuro fuori dall'Italia).
TEST_STREAMS = False

CHECK_TIMEOUT = 8        # secondi per considerare uno stream "morto"
MAX_WORKERS = 24         # quanti stream testo in parallelo
KEEP_DEAD_AS_FALLBACK = True   # se NESSUNA fonte risponde tengo comunque il ripiego

# tag di qualita' da ignorare nei nomi (NON includere "4k": serve a Rai 4K)
QUALITY_TAGS = ("fhd", "uhd", "hd", "sd", "h265", "h264", "hevc")

# ---------------------------------------------------------------------
#  LCN TIVUSAT  -  chiavi gia' NORMALIZZATE (minuscolo, senza spazi
#  ne' punteggiatura). Aggiornata al 01/04/2026.
# ---------------------------------------------------------------------
LCN_TIVUSAT = {
    "rai1": 1,
    "rai2": 2,
    "rai3": 3,
    "rete4": 4,
    "canale5": 5,
    "italia1": 6,
    "la7": 7,
    "tv8": 8,
    "nove": 9,
    "rai4": 10,
    "iris": 11,
    "la5": 12,
    "rai5": 13,
    "raimovie": 14,
    "raipremium": 15,
    "italia2": 16, "mediasetitalia2": 16,
    "mediasetextra": 17, "extra": 17,
    "tv2000": 18,
    "cielo": 19,
    "20": 20, "20mediaset": 20, "canale20": 20, "venti": 20,
    "raisport": 21, "raisportpiu": 21,
    "focus": 22,
    "raistoria": 23,
    "rainews24": 24, "rainews": 24,
    "tgcom24": 25, "mediasettgcom24": 25,
    "raiscuola": 26,
    "twentyseven": 27, "27": 27, "27twentyseven": 27,
    "dmax": 28, "dmaxitaly": 28,
    "la7cinema": 29, "la7d": 29,
    "wedotvmovies": 30, "wedomovies": 30, "wedotv": 30,
    "realtime": 31, "realtimeitaly": 31,
    # 32 (QVC) ELIMINATO il 01/04/2026 - LCN non piu' esistente
    "foodnetwork": 33, "foodnetworkitaly": 33,
    "cine34": 34,
    "radioitaliatv": 35,
    "rtl1025": 36, "rtl1025tv": 36,
    "discovery": 37, "discoveryitaly": 37, "discoverychannel": 37,
    "giallo": 38,
    "topcrime": 39,
    "boing": 40,
    "cartoonito": 41,
    "raigulp": 42,
    "raiyoyo": 43,
    "frisbee": 44,
    "k2": 46,
    "super": 47,
    "arte": 48,
    "mezzo": 49, "mezzotv": 49,
    "rdssocialtv": 50, "rdssocial": 50,
    "equtv": 51,
    "acisport": 52, "acisporttv": 52,
    "solocalcio": 54,           # ex Sportitalia: il 54 ora e' Solo Calcio
    "marcopolo": 55,
    "hgtv": 56, "hgtvitaly": 56,
    "euronewsitalian": 58, "euronewsitaliano": 58,
    "discoveryturbo": 59, "discoveryturboitaly": 59,
    "wedobigstories": 60,
    "rtl1025caliente": 62,
    "radioitalialive": 63,
    "radiokisskisstv": 64,
    "radiozeta": 65, "radiozetatv": 65,
    "radiofreccia": 66, "radiofrecciatv": 66,
    "radiomontecarlotv": 67,
    "virginradiotv": 68,
    "france24": 69,
    "bbcnews": 70, "bbcnewseurope": 70,
    "aljazeeraenglish": 71,
    # 4K (solo con tessera Tivusat 4K)
    "rai4k": 210,
}

# normalizzazione delle chiavi (sicurezza: se ne aggiungi una con spazi)
LCN_TIVUSAT = {re.sub(r"[^a-z0-9]", "", k.lower()): v for k, v in LCN_TIVUSAT.items()}


# --------------------------- UTILITY ---------------------------------
def normalize(name):
    """Riduce un nome canale a forma canonica: minuscolo, senza tag
    qualita', senza spazi ne' punteggiatura. 'La 7 HD' -> 'la7'."""
    name = name.lower().strip()
    name = re.sub(r"\[.*?\]", " ", name)        # [ ... ]
    name = re.sub(r"\(.*?\)", " ", name)        # ( ... )
    name = name.replace("it:", " ").replace(".it", " ")
    for tag in QUALITY_TAGS:                     # via i tag qualita' come parole intere
        name = re.sub(rf"\b{tag}\b", " ", name)
    name = re.sub(r"[^a-z0-9]", "", name)        # via spazi e punteggiatura
    return name


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
            key = normalize(raw)
            if key in LCN_TIVUSAT:
                lcn = LCN_TIVUSAT[key]
                is_hd = any(t in raw.lower() for t in ("hd", "fhd", "uhd", "4k"))
                out.append({
                    "lcn": lcn,
                    "name": raw,
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
        if url.lower().endswith(".m3u8") or "mpegurl" in ctype:
            return b"#EXTM3U" in chunk or b"#EXT" in chunk
        return len(chunk) > 0
    except Exception:
        return False


def test_urls(urls):
    """Testa tutti gli URL in parallelo -> dict {url: True/False}."""
    urls = list(urls)
    if not TEST_STREAMS:
        return {u: True for u in urls}   # nessun test: tutto considerato vivo
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
    candidates = {}
    for prio, src in enumerate([BASE_SOURCE] + FALLBACK_SOURCES):
        tag = "BASE (Maginet)" if prio == 0 else f"soccorso #{prio}"
        print(f"  {tag}: {src}")
        for ch in parse_source(src):
            ch["priority"] = prio
            candidates.setdefault(ch["lcn"], []).append(ch)

    # ordino: prima priorita' fonte, poi HD prima di SD
    for lcn in candidates:
        candidates[lcn].sort(key=lambda c: (c["priority"], 0 if c["is_hd"] else 1))

    # FASE 2 - testo gli stream unici (saltato se TEST_STREAMS = False)
    all_urls = {c["url"] for lst in candidates.values() for c in lst}
    if TEST_STREAMS:
        print(f"\nFASE 2: verifico {len(all_urls)} stream unici (timeout {CHECK_TIMEOUT}s)...")
    else:
        print(f"\nFASE 2: test disattivato (TEST_STREAMS=False) - {len(all_urls)} stream")
    alive = test_urls(all_urls)

    # FASE 3 - per ogni canale prendo il primo candidato VIVO
    print("\nFASE 3: scelgo la fonte migliore per ogni canale...")
    chosen = {}
    for lcn, lst in sorted(candidates.items()):
        live = next((c for c in lst if alive.get(c["url"])), None)
        if live:
            chosen[lcn] = live
            if live["priority"] != 0 and TEST_STREAMS:
                print(f"  [~] LCN {lcn:>3} {live['name']:<22} Maginet KO -> soccorso #{live['priority']}")
        elif KEEP_DEAD_AS_FALLBACK:
            chosen[lcn] = lst[0]
            print(f"  [!] LCN {lcn:>3} {lst[0]['name']:<22} nessuna fonte attiva, tengo il ripiego")

    # FASE 4 - scrittura file ordinato per LCN
    final = sorted(chosen.values(), key=lambda c: c["lcn"])
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(f'#EXTM3U url-tvg="{EPG_URL}"\n')
        for c in final:
            f.write(c["extinf"] + "\n" + c["url"] + "\n")

    n_live = sum(1 for c in final if alive.get(c["url"]))
    print(f"\nFatto: {len(final)} canali scritti in '{OUTPUT_FILE}'", end="")
    if TEST_STREAMS:
        print(f" ({n_live} verificati attivi, {len(final) - n_live} ripieghi).")
    else:
        print(".")


if __name__ == "__main__":
    main()
