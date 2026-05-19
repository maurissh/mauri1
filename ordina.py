import urllib.request
import re

# Configurazione
URL_LISTA = "https://raw.githubusercontent.com/maginetweb-arch/TVITALIA/refs/heads/main/iptvit.m3u"
FILE_OUTPUT = "lista_tivusat.m3u"

# Mappatura rigorosa LCN Tivùsat (Satellitare)
LCN_TIVUSAT = {
    # Generaliste
    "rai 1": 1, "rai1": 1, "rai 1 hd": 1,
    "rai 2": 2, "rai2": 2, "rai 2 hd": 2,
    "rai 3": 3, "rai3": 3, "rai 3 hd": 3,
    "rete 4": 4, "rete4": 4, "rete 4 hd": 4,
    "canale 5": 5, "canale5": 5, "canale 5 hd": 5,
    "italia 1": 6, "italia1": 6, "italia 1 hd": 6,
    "la7": 7, "la 7": 7, "la7 hd": 7,
    "tv8": 8, "tv 8": 8, "tv8 hd": 8,
    "nove": 9, "nove hd": 9,
    
    # Intrattenimento, Film e Serie
    "rai 4": 10, "rai4": 10, "rai 4 hd": 10,
    "iris": 11, "iris hd": 11,
    "la5": 12, "la 5": 12, "la5 hd": 12,
    "rai 5": 13, "rai5": 13, "rai 5 hd": 13,
    "rai movie": 14, "rai movie hd": 14,
    "rai premium": 15, "rai premium hd": 15,
    "italia 2": 16, "italia2": 16, "italia 2 hd": 16, "mediaset italia 2": 16,
    "mediaset extra": 17, "mediaset extra hd": 17, "extra": 17,
    "tv2000": 18, "tv 2000": 18, "tv2000 hd": 18,
    "cielo": 19, "cielo hd": 19,
    "20 mediaset": 20, "canale 20": 20, "20 hd": 20, "20": 20,
    
    # Sport, Documentari e Cultura
    "rai sport": 21, "rai sport hd": 21, "raisport": 21, "rai sport + hd": 21,
    "focus": 22, "focus hd": 22,
    "rai storia": 23, "rai storia hd": 23,
    
    # News e Didattica
    "rai news 24": 24, "rainews24": 24, "rai news 24 hd": 24, "rainews": 24,
    "tgcom24": 25, "mediaset tgcom24": 25, "tgcom 24": 25, "tgcom24 hd": 25,
    "rai scuola": 26, "rai scuola hd": 26,
    
    # Factual e Lifestyle
    "twentyseven": 27, "27": 27, "27 twentyseven": 27, "twenty seven": 27, "twentyseven hd": 27,
    "dmax": 28, "dmax hd": 28,
    "la7d": 29, "la7d hd": 29,
    "real time": 31, "real time hd": 31,
    "qvc": 32, "qvc hd": 32,
    "food network": 33, "food network hd": 33,
    "cine34": 34, "cine 34": 34, "cine34 hd": 34,
    
    # Musica e Crime
    "radio italia tv": 35, "radio italia tv hd": 35,
    "rtl 102.5": 36, "rtl 102.5 tv": 36, "rtl 102.5 hd": 36,
    "warner tv": 37, "warner tv italy": 37, "warner tv hd": 37,
    "giallo": 38, "giallo hd": 38,
    "top crime": 39, "top crime hd": 39, "topcrime": 39,
    
    # Bambini e Ragazzi (Ordine rigoroso SAT)
    "boing": 40, "boing hd": 40,
    "cartoonito": 41, "cartoonito hd": 41,
    "rai gulp": 42, "rai gulp hd": 42, "raigulp": 42,
    "rai yoyo": 43, "rai yoyo hd": 43, "raiyoyo": 43,
    "frisbee": 44,
    "k2": 46,
    "super!": 47, "super": 47,
    
    # Arte, Motori e Altro
    "arte": 48, "arte hd": 48,
    "sky tg24": 50, "sky tg 24": 50,
    "hgtv": 56, "hgtv hd": 56, "hgtv - home & garden tv": 56,
    "motor trend": 57, "motor trend hd": 57, "motortrend": 57,
    "sportitalia": 58, "sportitalia hd": 58
}

def clean_channel_name(name):
    """Pulisce il nome del canale rimuovendo scorie per un riconoscimento perfetto."""
    name = name.lower().strip()
    name = re.sub(r'\[.*?\]|\(.*\)', '', name) 
    scorie = [" fhd", " hd", " sd", " 4k", " it:", ".it"]
    for scoria in scorie:
        name = name.replace(scoria, "")
    return name.strip()

def process_playlist():
    print("Prelevamento lista maginetweb in corso...")
    req = urllib.request.Request(URL_LISTA, headers={'User-Agent': 'Mozilla/5.0'})
    
    try:
        with urllib.request.urlopen(req) as response:
            content = response.read().decode('utf-8').splitlines()
    except Exception as e:
        print(f"Errore fatale in fase di download: {e}")
        return

    channels = []
    current_extinf = ""
    channel_index = 0
    
    for line in content:
        line = line.strip()
        if line.startswith("#EXTINF"):
            current_extinf = line
        elif line.startswith("http") and current_extinf:
            channel_index += 1
            
            # Estrae il nome puro del canale
            match = re.search(r',(.*?)$', current_extinf)
            channel_name = match.group(1) if match else ""
            clean_name = clean_channel_name(channel_name)
            
            # Estrae il numero canale originale dalla lista (se esiste)
            orig_chno_match = re.search(r'tvg-chno="(\d+)"', current_extinf)
            orig_chno = int(orig_chno_match.group(1)) if orig_chno_match else None
            
            # Assegna LCN: Tivùsat ha priorità. Se non è in Tivùsat, mantiene l'originale.
            if clean_name in LCN_TIVUSAT:
                final_lcn = LCN_TIVUSAT[clean_name]
            else:
                # Se non aveva un numero originale, gliene diamo uno progressivo alto per non fare danni
                final_lcn = orig_chno if orig_chno is not None else (10000 + channel_index)
            
            # Applica il nuovo numero (o ripristina quello corretto)
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

    # Ordina i canali in base al parametro finale assegnato
    channels.sort(key=lambda x: x['lcn'])

    # Scrive il file finale
    print("Salvataggio lista ordinata in corso...")
    with open(FILE_OUTPUT, 'w', encoding='utf-8') as f:
        f.write('#EXTM3U url-tvg="https://epgshare01.online/epgshare01/epg_ripper_IT1.xml.gz"\n')
        for ch in channels:
            f.write(f"{ch['extinf']}\n{ch['url']}\n")
            
    print("Operazione completata con rispetto della numerazione originale per i canali extra.")

if __name__ == "__main__":
    process_playlist()
    
