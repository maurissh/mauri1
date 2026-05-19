import urllib.request
import re

# Usa la lista originale che preferisci
URL_LISTA = "https://raw.githubusercontent.com/maginetweb-arch/TVITALIA/refs/heads/main/iptvit.m3u"
FILE_OUTPUT = "lista_tivusat.m3u"

# LCN Ufficiale Tivùsat - Certificata e Aggiornata al 2026
LCN_TIVUSAT = {
    "rai 1": 1, "rai1": 1,
    "rai 2": 2, "rai2": 2,
    "rai 3": 3, "rai3": 3,
    "rete 4": 4, "rete4": 4,
    "canale 5": 5, "canale5": 5,
    "italia 1": 6, "italia1": 6,
    "la7": 7,
    "tv8": 8, "tv 8": 8,
    "nove": 9,
    "rai 4": 10, "rai4": 10,
    "iris": 11,
    "la5": 12,
    "rai 5": 13, "rai5": 13,
    "rai movie": 14,
    "rai premium": 15,
    "italia 2": 16, "mediaset italia 2": 16,
    "mediaset extra": 17, "extra": 17,
    "tv2000": 18, "tv 2000": 18,
    "cielo": 19,
    "20 mediaset": 20, "canale 20": 20, "20": 20,
    "rai sport": 21, "raisport": 21, "rai sport +": 21,
    "focus": 22,
    "rai storia": 23,
    "rai news 24": 24, "rainews24": 24, "rainews": 24,
    "tgcom24": 25, "mediaset tgcom24": 25, "tgcom 24": 25,
    "rai scuola": 26,
    "twentyseven": 27, "27": 27, "27 twentyseven": 27, "twenty seven": 27,
    "dmax": 28,
    "la7d": 29, "la7 cinema": 29,
    "we do movies": 30,
    "real time": 31,
    "qvc": 32,
    "food network": 33,
    "cine34": 34, "cine 34": 34,
    "radio italia tv": 35, "radio italia": 35,
    "rtl 102.5": 36, "rtl 102.5 tv": 36,
    "discovery": 37, "warner tv": 37, "warnertv": 37, "warner": 37,
    "giallo": 38,
    "top crime": 39, "topcrime": 39,
    "boing": 40,
    "cartoonito": 41,
    "rai gulp": 42, "raigulp": 42,
    "rai yoyo": 43, "raiyoyo": 43,
    "frisbee": 44,
    "k2": 46,
    "super!": 47, "super": 47,
    "arte": 48,
    "mezzo": 49,
    "rds social tv": 50, "rds": 50, "sky tg24": 50, "sky tg 24": 50,
    "equ tv": 51, "equtv": 51,
    "aci sport": 52, "aci sport tv": 52,
    "sportitalia": 54, "sportitalia solo calcio": 54,
    "hgtv": 56, "hgtv - home & garden tv": 56,
    "motor trend": 57, "motortrend": 57, "turbo": 57, "discovery turbo": 57
}

def clean_channel_name(name):
    """Pulisce la stringa rimuovendo i tag inutili (HD, FHD, parentesi, ecc.) per il match perfetto."""
    name = name.lower().strip()
    name = re.sub(r'\[.*?\]|\(.*\)', '', name) 
    scorie = [" fhd", " hd", " sd", " 4k", " it:", ".it"]
    for scoria in scorie:
        name = name.replace(scoria, "")
    return name.strip()

def process_playlist():
    print("Scaricamento della lista in corso...")
    req = urllib.request.Request(URL_LISTA, headers={'User-Agent': 'Mozilla/5.0'})
    
    try:
        with urllib.request.urlopen(req) as response:
            content = response.read().decode('utf-8').splitlines()
    except Exception as e:
        print(f"Errore fatale in download: {e}")
        return

    channels = []
    current_extinf = ""
    
    for line in content:
        line = line.strip()
        if line.startswith("#EXTINF"):
            current_extinf = line
        elif line.startswith("http") and current_extinf:
            match = re.search(r',(.*?)$', current_extinf)
            channel_name = match.group(1) if match else ""
            clean_name = clean_channel_name(channel_name)
            
            # FILTRO SPIETATO AGGIORNATO 2026: Accetta solo i canali presenti in LCN_TIVUSAT
            if clean_name in LCN_TIVUSAT:
                final_lcn = LCN_TIVUSAT[clean_name]
                
                # Sostituisce o inietta l'attributo LCN corretto
                if 'tvg-chno="' in current_extinf:
                    current_extinf = re.sub(r'tvg-chno="\d+"', f'tvg-chno="{final_lcn}"', current_extinf)
                else:
                    current_extinf = current_extinf.replace('#EXTINF:-1 ', f'#EXTINF:-1 tvg-chno="{final_lcn}" ')
                    
                channels.append({
                    'lcn': final_lcn,
                    'extinf': current_extinf,
                    'url': line
                })
                
            current_extinf = ""

    # Mette in ordine sequenziale rigoroso da 1 a 57
    channels.sort(key=lambda x: x['lcn'])

    print("Salvataggio lista ordinata in corso...")
    with open(FILE_OUTPUT, 'w', encoding='utf-8') as f:
        # Intestazione file con link alla Guida EPG (Programmazione Elettronica)
        f.write('#EXTM3U url-tvg="https://epgshare01.online/epgshare01/epg_ripper_IT1.xml.gz"\n')
        for ch in channels:
            f.write(f"{ch['extinf']}\n{ch['url']}\n")
            
    print("Elaborazione completata. Tabellone Tivùsat 2026 applicato con successo.")

if __name__ == "__main__":
    process_playlist()
    
