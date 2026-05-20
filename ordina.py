import urllib.request
import re

# =====================================================================
# MOTORE IBRIDO: MAGINET COME BASE + SCRAPER COME SOCCORSO
# =====================================================================
FONTE_PRINCIPALE = "https://raw.githubusercontent.com/maginetweb-arch/TVITALIA/refs/heads/main/iptvit.m3u"

FONTI_SOCCORSO = [
    "https://iptv-org.github.io/iptv/countries/it.m3u",
    "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlists/playlist_italy.m3u8"
]

FILE_OUTPUT = "lista_tivusat.m3u"

# LCN Completa Tivùsat
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
    "france 24": 69, "bbc news": 70, "al jazeera english": 71, "rai 4k": 210
}

def clean_channel_name(name):
    name = name.lower().strip()
    name = re.sub(r'\[.*?\]|\(.*\)', '', name) 
    for scoria in [" fhd", " hd", " sd", " 4k", " it:", ".it"]:
        name = name.replace(scoria, "")
    return name.strip()

def extract_channels(url, current_dict, is_primary):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            content = response.read().decode('utf-8').splitlines()
    except Exception as e:
        print(f"Errore caricamento fonte {url}: {e}")
        return

    current_extinf = ""
    for line in content:
        line = line.strip()
        if line.startswith("#EXTINF"):
            current_extinf = line
        elif line.startswith("http") and current_extinf:
            match = re.search(r',(.*?)$', current_extinf)
            original_channel_name = match.group(1) if match else ""
            clean_name = clean_channel_name(original_channel_name)
            
            if clean_name in LCN_TIVUSAT:
                final_lcn = LCN_TIVUSAT[clean_name]
                
                if 'tvg-chno="' in current_extinf:
                    current_extinf = re.sub(r'tvg-chno="\d+"', f'tvg-chno="{final_lcn}"', current_extinf)
                else:
                    current_extinf = current_extinf.replace('#EXTINF:-1 ', f'#EXTINF:-1 tvg-chno="{final_lcn}" ')
                
                is_hd = "hd" in original_channel_name.lower() or "fhd" in original_channel_name.lower()
                
                new_channel = {
                    'lcn': final_lcn,
                    'extinf': current_extinf,
                    'url': line,
                    'is_hd': is_hd
                }
                
                if is_primary:
                    # Logica Fonte Principale: sovrascrive solo se trova un HD migliore dentro se stessa
                    if final_lcn in current_dict:
                        if is_hd and not current_dict[final_lcn]['is_hd']:
                            current_dict[final_lcn] = new_channel
                    else:
                        current_dict[final_lcn] = new_channel
                else:
                    # Logica Soccorso: Entra SOLO se la sedia è vuota. Non tocca i link di Maginet.
                    if final_lcn not in current_dict:
                        current_dict[final_lcn] = new_channel
                
            current_extinf = ""

def process_playlist():
    channels_dict = {}
    
    print("FASE 1: Estrazione dalla base sicura (Maginet)...")
    extract_channels(FONTE_PRINCIPALE, channels_dict, is_primary=True)
    
    print("FASE 2: Avvio scraper per tappare i buchi...")
    for url in FONTI_SOCCORSO:
        extract_channels(url, channels_dict, is_primary=False)

    final_channels = list(channels_dict.values())
    final_channels.sort(key=lambda x: x['lcn'])

    print(f"Salvataggio di {len(final_channels)} canali in corso...")
    with open(FILE_OUTPUT, 'w', encoding='utf-8') as f:
        f.write('#EXTM3U url-tvg="https://epgshare01.online/epgshare01/epg_ripper_IT1.xml.gz"\n')
        for ch in final_channels:
            f.write(f"{ch['extinf']}\n{ch['url']}\n")
            
    print("Tabellone completato con architettura ibrida!")

if __name__ == "__main__":
    process_playlist()
    
