import urllib.request
import re

# =====================================================================
# MOTORE MULTI-SORGENTE: Caccia ai "Link di Cache" (Proxy Restream)
# =====================================================================
FONTI = [
    "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlists/playlist_italy.m3u8",
    "https://iptv-org.github.io/iptv/countries/it.m3u",
    "https://raw.githubusercontent.com/maginetweb-arch/TVITALIA/refs/heads/main/iptvit.m3u"
]

FILE_OUTPUT = "lista_tivusat.m3u"

# LCN Ufficiale Tivùsat 2026 (Abbreviata per comodità, puoi usare quella lunga)
LCN_TIVUSAT = {
    "rai 1": 1, "rai 2": 2, "rai 3": 3, "rete 4": 4, "canale 5": 5, "italia 1": 6, 
    "la7": 7, "tv8": 8, "nove": 9, "20 mediaset": 20, "canale 20": 20, "20": 20,
    "rai 4": 10, "iris": 11, "la5": 12, "rai 5": 13, "rai movie": 14, "rai premium": 15,
    "italia 2": 16, "mediaset extra": 17, "extra": 17, "tv2000": 18, "cielo": 19,
    "rai sport": 21, "focus": 22, "rai storia": 23, "rai news 24": 24, "tgcom24": 25,
    "twentyseven": 27, "27": 27, "dmax": 28, "la7d": 29, "real time": 31,
    "cine34": 34, "rtl 102.5": 36, "warner tv": 37, "warnertv": 37, "discovery": 37,
    "giallo": 38, "top crime": 39, "boing": 40, "cartoonito": 41, "motor trend": 57
}

def clean_channel_name(name):
    name = name.lower().strip()
    name = re.sub(r'\[.*?\]|\(.*\)', '', name) 
    scorie = [" fhd", " hd", " sd", " 4k", " it:", ".it"]
    for scoria in scorie:
        name = name.replace(scoria, "")
    return name.strip()

def process_playlist():
    print("Avvio ricerca multi-sorgente dei link di cache...")
    channels_dict = {}
    
    for url in FONTI:
        print(f"Scandagliando la fonte: {url}")
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                content = response.read().decode('utf-8').splitlines()
        except Exception as e:
            print(f"Fonte saltata (non risponde): {e}")
            continue

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
                    
                    # Logica Aggressiva: Sovrascrive i link se trova una cache HD
                    if final_lcn in channels_dict:
                        if is_hd and not channels_dict[final_lcn]['is_hd']:
                            channels_dict[final_lcn] = new_channel
                    else:
                        channels_dict[final_lcn] = new_channel
                    
                current_extinf = ""

    final_channels = list(channels_dict.values())
    final_channels.sort(key=lambda x: x['lcn'])

    print(f"Trovati {len(final_channels)} canali. Salvataggio in corso...")
    with open(FILE_OUTPUT, 'w', encoding='utf-8') as f:
        f.write('#EXTM3U url-tvg="https://epgshare01.online/epgshare01/epg_ripper_IT1.xml.gz"\n')
        for ch in final_channels:
            f.write(f"{ch['extinf']}\n{ch['url']}\n")
            
    print("Finito! Link di cache e proxy integrati con successo.")

if __name__ == "__main__":
    process_playlist()
    
