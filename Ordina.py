import urllib.request
import re

# Configurazione
URL_LISTA = "https://raw.githubusercontent.com/maginetweb-arch/TVITALIA/refs/heads/main/iptvit.m3u"
FILE_OUTPUT = "lista_tivusat.m3u"

# Mappatura essenziale LCN Tivùsat (nome canale in minuscolo: numero)
LCN_TIVUSAT = {
    "rai 1": 1, "rai1": 1, "rai 1 hd": 1,
    "rai 2": 2, "rai2": 2, "rai 2 hd": 2,
    "rai 3": 3, "rai3": 3, "rai 3 hd": 3,
    "rete 4": 4, "rete4": 4, "rete 4 hd": 4,
    "canale 5": 5, "canale5": 5, "canale 5 hd": 5,
    "italia 1": 6, "italia1": 6, "italia 1 hd": 6,
    "la7": 7, "la 7": 7, "la7 hd": 7,
    "tv8": 8, "tv 8": 8, "tv8 hd": 8,
    "nove": 9, "nove hd": 9,
    "20 mediaset": 20, "canale 20": 20, "20 hd": 20,
    "rai 4": 21, "rai4": 21,
    "iris": 22,
    "rai 5": 23, "rai5": 23,
    "rai movie": 24,
    "rai premium": 25,
    "cielo": 26,
    "twentyseven": 27, "27": 27, "27 twentyseven": 27,
    "tv2000": 28,
    "la7d": 29,
    "la5": 30,
    "real time": 31,
    "qvc": 32,
    "food network": 33,
    "cine34": 34,
    "focus": 35,
    "rtl 102.5": 36, "rtl 102.5 tv": 36,
    "warner tv": 37,
    "giallo": 38,
    "top crime": 39,
    "boing": 40,
    "k2": 41,
    "rai gulp": 42,
    "rai yoyo": 43,
    "frisbee": 44,
    "cartoonito": 45,
    "super!": 46,
    "rai news 24": 48, "rainews24": 48,
    "tgcom24": 49, "mediaset tgcom24": 49,
    "sky tg24": 50,
    "dmax": 52,
    "rai storia": 53,
    "rai scuola": 54,
    "mediaset extra": 55,
    "hgtv": 56,
    "motor trend": 57,
    "sportitalia": 58
}

def clean_channel_name(name):
    """Pulisce il nome del canale per facilitare il matching."""
    name = name.lower().strip()
    name = re.sub(r'\[.*?\]|\(.*\)', '', name) # Rimuove tag come [FHD] o (ITA)
    name = name.replace(" fhd", "").replace(" it:", "").strip()
    return name

def process_playlist():
    print("Scaricamento della lista originale in corso...")
    req = urllib.request.Request(URL_LISTA, headers={'User-Agent': 'Mozilla/5.0'})
    
    try:
        with urllib.request.urlopen(req) as response:
            content = response.read().decode('utf-8').splitlines()
    except Exception as e:
        print(f"Errore durante il download: {e}")
        return

    channels = []
    current_extinf = ""
    
    for line in content:
        line = line.strip()
        if line.startswith("#EXTINF"):
            current_extinf = line
        elif line.startswith("http") and current_extinf:
            # Estrai il nome del canale (tutto ciò che c'è dopo l'ultima virgola)
            match = re.search(r',(.*?)$', current_extinf)
            channel_name = match.group(1) if match else ""
            clean_name = clean_channel_name(channel_name)
            
            # Assegna LCN
            lcn = LCN_TIVUSAT.get(clean_name, 9999) # 9999 per i canali sconosciuti
            
            # Inietta tvg-chno se non esiste o sostituiscilo
            if 'tvg-chno="' in current_extinf:
                current_extinf = re.sub(r'tvg-chno="\d+"', f'tvg-chno="{lcn}"', current_extinf)
            else:
                current_extinf = current_extinf.replace('#EXTINF:-1 ', f'#EXTINF:-1 tvg-chno="{lcn}" ')
                
            channels.append({
                'lcn': lcn,
                'extinf': current_extinf,
                'url': line,
                'original_name': channel_name
            })
            current_extinf = ""

    # Ordina i canali in base al numero LCN
    channels.sort(key=lambda x: x['lcn'])

    # Scrittura del nuovo file
    print("Generazione della lista ordinata...")
    with open(FILE_OUTPUT, 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        for ch in channels:
            f.write(f"{ch['extinf']}\n{ch['url']}\n")
            
    print(f"Completato. La lista riordinata è stata salvata come '{FILE_OUTPUT}'.")

if __name__ == "__main__":
    process_playlist()
  
