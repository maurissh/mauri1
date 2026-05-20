import urllib.request
import re

URL_LISTA = "https://iptv-org.github.io/iptv/countries/it.m3u"
FILE_OUTPUT = "lista_tivusat.m3u"

# LCN Ufficiale Tivùsat 2026
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
    "rai movie": 14, "raimovie": 14,
    "rai premium": 15, "raipremium": 15,
    "italia 2": 16, "mediaset italia 2": 16,
    "mediaset extra": 17, "extra": 17,
    "tv2000": 18, "tv 2000": 18,
    "cielo": 19,
    "20 mediaset": 20, "canale 20": 20, "20": 20,
    "rai sport": 21, "raisport": 21, "rai sport +": 21,
    "focus": 22,
    "rai storia": 23, "raistoria": 23,
    "rai news 24": 24, "rainews24": 24, "rainews": 24,
    "tgcom24": 25, "mediaset tgcom24": 25, "tgcom 24": 25,
    "rai scuola": 26, "raiscuola": 26,
    "twentyseven": 27, "27": 27, "27 twentyseven": 27,
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
    "marcopolo": 55, "marcopolo travel tv": 55,
    "hgtv": 56, "hgtv - home & garden tv": 56,
    "motor trend": 57, "motortrend": 57,
    "euronews italian": 58, "euronews it": 58, "euronews ita": 58, "euronews": 58,
    "discovery turbo": 59, "turbo": 59, 
    "we do big stories": 60,
    "juwelo tv": 61, "juwelo": 61,
    "rtl 102.5 caliente": 62, "caliente": 62,
    "radio italia live": 63,
    "radio kiss kiss tv": 64, "kiss kiss tv": 64, "radio kiss kiss": 64,
    "radio zeta tv": 65, "radio zeta": 65,
    "radio freccia tv": 66, "radiofreccia": 66, "radio freccia": 66,
    "radio monte carlo tv": 67, "radio monte carlo": 67, "rmc tv": 67,
    "virgin radio tv": 68, "virgin radio": 68,
    "france 24": 69, "france 24 english": 69,
    "bbc news": 70, "bbc news europe": 70, "bbc": 70,
    "al jazeera english": 71, "al jazeera": 71,
    "trt world": 72,
    "cnbc europe": 81, "cnbc": 81,
    "bloomberg": 82, "bloomberg european tv": 82,
    "daystar": 83,
    "dw": 85, "deutsche welle": 85,
    "cgtn": 87,
    "cgtn documentary": 88,
    "rai 4k": 210,
    "museum 4k": 220, "museum tv": 220,
    "myzen 4k": 222, "myzen tv": 222,
    "travelxp 4k": 225, "travelxp": 225,
    "hot bird 4k": 230, "hotbird 4k": 230,
    "rai 3 tgr valle d'aosta": 301, "tgr valle d'aosta": 301,
    "rai 3 tgr piemonte": 302, "tgr piemonte": 302, "rai 3 piemonte": 302,
    "rai 3 tgr liguria": 303, "tgr liguria": 303, "rai 3 liguria": 303,
    "rai 3 tgr lombardia": 304, "tgr lombardia": 304, "rai 3 lombardia": 304,
    "rai 3 tgr veneto": 305, "tgr veneto": 305, "rai 3 veneto": 305,
    "rai 3 tgr alto adige": 306, "tgr alto adige": 306, "rai 3 alto adige": 306,
    "rai 3 tgr trentino": 307, "tgr trentino": 307, "rai 3 trentino": 307,
    "rai sudtirol": 308, "rai 3 sudtirol": 308,
    "rai 3 tgr friuli": 309, "tgr friuli": 309, "rai 3 friuli": 309, "rai 3 tgr fvg": 309,
    "rai 3 tgr fvg bis": 310, "tgr fvg bis": 310,
    "rai 3 tgr emilia romagna": 311, "tgr emilia romagna": 311, "rai 3 emilia romagna": 311,
    "rai 3 tgr toscana": 312, "tgr toscana": 312, "rai 3 toscana": 312,
    "rai 3 tgr marche": 313, "tgr marche": 313, "rai 3 marche": 313,
    "rai 3 tgr umbria": 314, "tgr umbria": 314, "rai 3 umbria": 314,
    "rai 3 tgr lazio": 315, "tgr lazio": 315, "rai 3 lazio": 315,
    "rai 3 tgr abruzzo": 316, "tgr abruzzo": 316, "rai 3 abruzzo": 316,
    "rai 3 tgr molise": 317, "tgr molise": 317, "rai 3 molise": 317,
    "rai 3 tgr campania": 318, "tgr campania": 318, "rai 3 campania": 318,
    "rai 3 tgr puglia": 319, "tgr puglia": 319, "rai 3 puglia": 319,
    "rai 3 tgr basilicata": 320, "tgr basilicata": 320, "rai 3 basilicata": 320,
    "rai 3 tgr calabria": 321, "tgr calabria": 321, "rai 3 calabria": 321,
    "rai 3 tgr sardegna": 322, "tgr sardegna": 322, "rai 3 sardegna": 322,
    "rai 3 tgr sicilia": 323, "tgr sicilia": 323, "rai 3 sicilia": 323
}

def clean_channel_name(name):
    name = name.lower().strip()
    name = re.sub(r'\[.*?\]|\(.*\)', '', name) 
    scorie = [" fhd", " hd", " sd", " 4k", " it:", ".it"]
    for scoria in scorie:
        name = name.replace(scoria, "")
    return name.strip()

def process_playlist():
    print("Scaricamento della lista mondiale iptv-org in corso...")
    req = urllib.request.Request(URL_LISTA, headers={'User-Agent': 'Mozilla/5.0'})
    
    try:
        with urllib.request.urlopen(req) as response:
            content = response.read().decode('utf-8').splitlines()
    except Exception as e:
        print(f"Errore in download: {e}")
        return

    # Usiamo un dizionario per sovrascrivere i doppioni sullo stesso LCN
    channels_dict = {}
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
                
                # Capisce se il canale attuale è in Alta Definizione guardando il nome originale
                is_hd = "hd" in original_channel_name.lower() or "fhd" in original_channel_name.lower() or "4k" in original_channel_name.lower()
                
                new_channel = {
                    'lcn': final_lcn,
                    'extinf': current_extinf,
                    'url': line,
                    'is_hd': is_hd
                }
                
                # LOGICA ANTI-DOPPIONI
                if final_lcn in channels_dict:
                    # Il posto è già occupato. Lo rimpiazza SOLO se il nuovo è HD e il vecchio era SD.
                    if is_hd and not channels_dict[final_lcn]['is_hd']:
                        channels_dict[final_lcn] = new_channel
                else:
                    # Il posto è libero, si accomoda.
                    channels_dict[final_lcn] = new_channel
                
            current_extinf = ""

    # Estrae i canali unici dal dizionario e li ordina
    final_channels = list(channels_dict.values())
    final_channels.sort(key=lambda x: x['lcn'])

    print("Salvataggio lista ordinata e senza doppioni in corso...")
    with open(FILE_OUTPUT, 'w', encoding='utf-8') as f:
        f.write('#EXTM3U url-tvg="https://epgshare01.online/epgshare01/epg_ripper_IT1.xml.gz"\n')
        for ch in final_channels:
            f.write(f"{ch['extinf']}\n{ch['url']}\n")
            
    print("Operazione completata. Cloni SD eliminati, lista Full HD generata.")

if __name__ == "__main__":
    process_playlist()
    
