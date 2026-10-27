// =====================================================================
//  TIVUSAT - generatore di playlist IPTV con numerazione Tivusat + DTT
//
//  1. scarica in parallelo tutte le fonti (Free-TV, iptv-org, Maginet)
//  2. riconosce i canali confrontandoli con canali.txt (nome, alias, tvg-id)
//  3. per ogni canale sceglie il flusso migliore fra quelli disponibili
//  4. numera: Tivusat col numero Tivusat, gli altri col numero DTT
//  5. scrive la playlist ordinata
//
//  Uso:   tivusat [--verifica] [--diagnostica] [--output FILE]
//    --verifica     prova i flussi e, se il primo non risponde, passa al
//                   successivo (da usare da un collegamento italiano: dai
//                   server esteri molti canali risultano bloccati)
//    --diagnostica  elenca i canali Tivusat non trovati e i nomi italiani
//                   non riconosciuti, per aggiungere alias in canali.txt
// =====================================================================

use std::collections::{HashMap, HashSet};
use std::fmt::Write as _;
use std::io::Read;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Mutex;
use std::thread;
use std::time::{Duration, Instant};

const CANALI: &str = include_str!("canali.txt");
const FILE_USCITA: &str = "lista_tivusat.m3u";
const EPG_URL: &str = "https://epgshare01.online/epgshare01/epg_ripper_IT1.xml.gz";

// Alcune CDN (Warner Bros. Discovery in particolare) rifiutano i lettori che
// non si presentano come un browser. Se la fonte non indica uno User-Agent
// proprio, si aggiunge questo. Mettere false per non aggiungerlo.
const AGGIUNGI_USER_AGENT: bool = true;
const BROWSER_UA: &str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 \
                          (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36";

// Canale DTT il cui numero e' gia' usato da Tivusat: va a 1000 + numero DTT.
const OFFSET_CONFLITTI: u32 = 1000;
// Sicurezza: se si trovano meno canali Tivusat di cosi', la vecchia playlist
// non viene sovrascritta (fonti irraggiungibili o cambiate di formato).
const MINIMO_CANALI_TIVUSAT: usize = 20;

const SECONDI_DOWNLOAD: u64 = 25;
const SECONDI_VERIFICA: u64 = 8;
const THREAD_VERIFICA: usize = 32;

// ------------------------------- FONTI --------------------------------
// L'ordine e' la priorita': a parita' di qualita' vince la fonte piu' in alto.
enum Paese {
    Attributo,           // il paese e' scritto in ogni canale (tvg-country)
    Fisso(&'static str), // tutta la lista appartiene a un paese
}

struct Fonte {
    nome: &'static str,
    url: &'static str,
    paese: Paese,
}

const FONTI: &[Fonte] = &[
    Fonte { nome: "Free-TV", url: "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8", paese: Paese::Attributo },
    Fonte { nome: "iptv-org IT", url: "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/it.m3u", paese: Paese::Fisso("it") },
    Fonte { nome: "Maginet", url: "https://raw.githubusercontent.com/maginetweb-arch/TVITALIA/refs/heads/main/iptvit.m3u", paese: Paese::Fisso("it") },
    Fonte { nome: "iptv-org SM", url: "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/sm.m3u", paese: Paese::Fisso("sm") },
    Fonte { nome: "iptv-org CH", url: "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/ch.m3u", paese: Paese::Fisso("ch") },
    Fonte { nome: "iptv-org VA", url: "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/va.m3u", paese: Paese::Fisso("va") },
    // liste estere: servono solo ai canali internazionali di Tivusat (T*)
    Fonte { nome: "iptv-org FR", url: "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/fr.m3u", paese: Paese::Fisso("fr") },
    Fonte { nome: "iptv-org DE", url: "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/de.m3u", paese: Paese::Fisso("de") },
    Fonte { nome: "iptv-org UK", url: "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/uk.m3u", paese: Paese::Fisso("uk") },
    Fonte { nome: "iptv-org US", url: "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/us.m3u", paese: Paese::Fisso("us") },
    Fonte { nome: "iptv-org QA", url: "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/qa.m3u", paese: Paese::Fisso("qa") },
    Fonte { nome: "iptv-org TR", url: "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/tr.m3u", paese: Paese::Fisso("tr") },
    Fonte { nome: "iptv-org JP", url: "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/jp.m3u", paese: Paese::Fisso("jp") },
    Fonte { nome: "iptv-org CN", url: "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/cn.m3u", paese: Paese::Fisso("cn") },
    Fonte { nome: "iptv-org KR", url: "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/kr.m3u", paese: Paese::Fisso("kr") },
    Fonte { nome: "iptv-org IN", url: "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/in.m3u", paese: Paese::Fisso("in") },
    Fonte { nome: "iptv-org NL", url: "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/nl.m3u", paese: Paese::Fisso("nl") },
];

// ------------------------------ CANALI --------------------------------
#[derive(Clone, Copy, PartialEq)]
enum Piano {
    Tivusat,
    Dtt,
    Extra,
}

struct Canale {
    piano: Piano,
    lcn: Vec<u32>,
    nome: String,
    epg: Option<String>,
    internazionale: bool,
}

fn carica_canali() -> (Vec<Canale>, HashMap<String, usize>) {
    let mut canali = Vec::new();
    let mut chiavi: HashMap<String, usize> = HashMap::new();
    let mut errori = Vec::new();

    for (riga_n, riga) in CANALI.lines().enumerate() {
        let riga = riga.trim();
        if riga.is_empty() || riga.starts_with('#') {
            continue;
        }
        let campi: Vec<&str> = riga.split('|').map(str::trim).collect();
        if campi.len() < 3 {
            errori.push(format!("riga {}: servono almeno 3 campi", riga_n + 1));
            continue;
        }
        let (piano, internazionale) = match campi[0] {
            "T" => (Piano::Tivusat, false),
            "T*" => (Piano::Tivusat, true),
            "D" => (Piano::Dtt, false),
            "D*" => (Piano::Dtt, true),
            "X" => (Piano::Extra, false),
            "X*" => (Piano::Extra, true),
            altro => {
                errori.push(format!("riga {}: piano '{}' sconosciuto", riga_n + 1, altro));
                continue;
            }
        };
        let lcn: Vec<u32> = campi[1].split(',').filter_map(|n| n.trim().parse().ok()).collect();
        if lcn.is_empty() {
            errori.push(format!("riga {}: numero LCN mancante", riga_n + 1));
            continue;
        }
        let nome = campi[2].to_string();
        let epg = campi.get(3).filter(|s| !s.is_empty()).map(|s| s.to_string());
        let idx = canali.len();

        let mut nomi = vec![nome.clone()];
        if let Some(alias) = campi.get(4) {
            nomi.extend(alias.split(',').map(str::trim).filter(|a| !a.is_empty()).map(String::from));
        }
        for n in nomi {
            let k = normalizza(&n);
            if k.is_empty() {
                continue;
            }
            match chiavi.get(&k) {
                Some(&altro) if altro != idx => errori.push(format!(
                    "riga {}: il nome '{}' e' gia' usato da '{}'",
                    riga_n + 1,
                    n,
                    canali.get(altro).map(|c: &Canale| c.nome.as_str()).unwrap_or("?")
                )),
                _ => {
                    chiavi.insert(k, idx);
                }
            }
        }
        canali.push(Canale { piano, lcn, nome, epg, internazionale });
    }

    if !errori.is_empty() {
        eprintln!("Errori in canali.txt:");
        for e in errori {
            eprintln!("  {e}");
        }
        std::process::exit(2);
    }
    (canali, chiavi)
}

// --------------------------- NORMALIZZAZIONE ---------------------------
const TAG_QUALITA: &[&str] = &["hd", "fhd", "uhd", "sd", "h264", "h265", "hevc"];

fn piega_accenti(c: char) -> char {
    match c {
        'à' | 'á' | 'â' | 'ä' | 'ã' => 'a',
        'è' | 'é' | 'ê' | 'ë' => 'e',
        'ì' | 'í' | 'î' | 'ï' => 'i',
        'ò' | 'ó' | 'ô' | 'ö' | 'õ' => 'o',
        'ù' | 'ú' | 'û' | 'ü' => 'u',
        'ç' => 'c',
        'ñ' => 'n',
        _ => c,
    }
}

/// "Rai 1 HD (720p) [Geo-blocked]" -> "rai1"
fn normalizza(nome: &str) -> String {
    let mut s = nome.to_lowercase();
    for prefisso in ["it:", "it |", "it|"] {
        if let Some(resto) = s.strip_prefix(prefisso) {
            s = resto.to_string();
        }
    }
    // toglie il contenuto di [] e ()
    let mut pulito = String::with_capacity(s.len());
    let mut profondita = 0u32;
    for c in s.chars() {
        match c {
            '[' | '(' => profondita += 1,
            ']' | ')' => profondita = profondita.saturating_sub(1),
            _ if profondita == 0 => pulito.push(piega_accenti(c)),
            _ => {}
        }
    }
    pulito
        .split(|c: char| !c.is_ascii_alphanumeric())
        .filter(|p| !p.is_empty() && !TAG_QUALITA.contains(p))
        .collect()
}

/// "Rai1.it@SD" -> "rai1"   "freetv:rai1" -> "rai1"
fn normalizza_tvg_id(id: &str) -> String {
    let id = id.split('@').next().unwrap_or("");
    let id = id.rsplit(':').next().unwrap_or("");
    let id = match id.rsplit_once('.') {
        Some((base, paese)) if (2..=3).contains(&paese.len()) && paese.chars().all(|c| c.is_ascii_alphabetic()) => base,
        _ => id,
    };
    normalizza(id)
}

/// Varianti tolleranti: "Gold TV" trova "Gold", "Cielo" trova "Cielo TV" ecc.
fn varianti(k: &str) -> Vec<String> {
    let mut v = Vec::new();
    for suffisso in ["tv", "italia", "italy", "channel", "network"] {
        if let Some(base) = k.strip_suffix(suffisso) {
            if base.len() >= 2 {
                v.push(base.to_string());
            }
        }
    }
    v.push(format!("{k}tv"));
    v
}

// ------------------------------ PARSING --------------------------------
struct Voce {
    fonte: usize,
    ordine: usize,
    nome: String,
    tvg_id: String,
    logo: String,
    url: String,
    opzioni: Vec<String>,
    user_agent: Option<String>,
    referrer: Option<String>,
    italiana: bool,
}

fn attributo(extinf: &str, chiave: &str) -> Option<String> {
    let cerca = format!("{chiave}=\"");
    let inizio = extinf.find(&cerca)? + cerca.len();
    let fine = extinf[inizio..].find('"')? + inizio;
    Some(extinf[inizio..fine].to_string())
}

/// nome del canale: il testo dopo la prima virgola fuori dalle virgolette
fn nome_canale(extinf: &str) -> String {
    let mut tra_virgolette = false;
    for (i, c) in extinf.char_indices() {
        match c {
            '"' => tra_virgolette = !tra_virgolette,
            ',' if !tra_virgolette => return extinf[i + 1..].trim().to_string(),
            _ => {}
        }
    }
    String::new()
}

fn analizza(testo: &str, fonte: usize) -> Vec<Voce> {
    let mut voci = Vec::new();
    let mut extinf: Option<&str> = None;
    let mut opzioni: Vec<String> = Vec::new();

    for riga in testo.lines() {
        let riga = riga.trim();
        if riga.is_empty() {
            continue;
        }
        if riga.starts_with("#EXTINF") {
            extinf = Some(riga);
            opzioni.clear();
        } else if riga.starts_with("#EXTVLCOPT") || riga.starts_with("#KODIPROP") || riga.starts_with("#EXTHTTP") {
            if extinf.is_some() {
                opzioni.push(riga.to_string());
            }
        } else if riga.starts_with('#') {
            continue;
        } else if let Some(ext) = extinf.take() {
            let tvg_id = attributo(ext, "tvg-id").unwrap_or_default();
            let italiana = match FONTI[fonte].paese {
                Paese::Fisso(p) => p == "it",
                Paese::Attributo => {
                    attributo(ext, "tvg-country").is_some_and(|p| p.to_uppercase().split(';').any(|x| x.trim() == "IT"))
                }
            } || tvg_id.to_lowercase().split('@').next().unwrap_or("").ends_with(".it");

            let opz_valore = |prefisso: &str| {
                opzioni.iter().find_map(|o| o.strip_prefix(prefisso).map(|v| v.trim().to_string()))
            };
            let user_agent = opz_valore("#EXTVLCOPT:http-user-agent=")
                .or_else(|| attributo(ext, "http-user-agent"))
                .filter(|s| !s.is_empty());
            let referrer = opz_valore("#EXTVLCOPT:http-referrer=")
                .or_else(|| attributo(ext, "http-referrer"))
                .filter(|s| !s.is_empty());

            voci.push(Voce {
                fonte,
                ordine: voci.len(),
                nome: nome_canale(ext),
                tvg_id,
                logo: attributo(ext, "tvg-logo").unwrap_or_default(),
                url: riga.to_string(),
                opzioni: std::mem::take(&mut opzioni),
                user_agent,
                referrer,
                italiana,
            });
        }
    }
    voci
}

/// Piu' basso = migliore. Penalizza YouTube, flussi non 24h, SD, geoblocco estero.
fn penalita(v: &Voce) -> u32 {
    let n = &v.nome;
    let mut p = 0;
    if n.contains('Ⓨ') || v.url.contains("youtube.com") || v.url.contains("youtu.be") {
        p += 50;
    }
    if n.contains("[Not 24/7]") {
        p += 20;
    }
    if !v.italiana && n.contains("[Geo-blocked]") {
        p += 10;
    }
    if n.contains('Ⓢ') || ["(576p)", "(480p)", "(360p)", "(240p)"].iter().any(|r| n.contains(r)) {
        p += 5;
    }
    // server indicato con l'indirizzo IP nudo: di solito ritrasmissioni di terzi
    let host = v.url.split("://").nth(1).unwrap_or("").split(['/', ':']).next().unwrap_or("").to_lowercase();
    if !host.is_empty() && host.chars().all(|c| c.is_ascii_digit() || c == '.') {
        p += 8;
    }
    // a parita' di condizioni si preferisce il server dell'emittente
    if !server_ufficiale(&host) {
        p += 4;
    }
    p
}

// Server delle emittenti (suffisso del nome). Un flusso su questi server
// viene preferito alle ritrasmissioni di terzi dello stesso canale, che
// possono andare a scatti o sparire. Rai e Mediaset funzionano solo da un
// collegamento italiano.
const SERVER_UFFICIALI: &[&str] = &[
    ".rai.it", ".cdn.mediaset.net", "skycdn-it.akamaized.net", ".enhanced.live",
];

fn server_ufficiale(host: &str) -> bool {
    SERVER_UFFICIALI.iter().any(|s| host == s.trim_start_matches('.') || host.ends_with(s))
        // CDN Akamai della Rai: rai1-live, tgrbolzano-live, stream6-rai-it...
        || (host.ends_with(".akamaized.net")
            && (host.starts_with("rai") || host.starts_with("tgr") || host.contains("-rai-it")))
}

// ------------------------------- RETE ----------------------------------
fn agente(secondi: u64) -> ureq::Agent {
    ureq::AgentBuilder::new()
        .timeout(Duration::from_secs(secondi))
        .redirects(5)
        .try_proxy_from_env(true)
        .user_agent(BROWSER_UA)
        .build()
}

fn scarica_fonti() -> Vec<Result<(String, Duration), String>> {
    let agent = agente(SECONDI_DOWNLOAD);
    thread::scope(|s| {
        let lavori: Vec<_> = FONTI
            .iter()
            .map(|f| {
                let agent = agent.clone();
                s.spawn(move || {
                    let t = Instant::now();
                    agent
                        .get(f.url)
                        .call()
                        .map_err(|e| e.to_string())
                        .and_then(|r| r.into_string().map_err(|e| e.to_string()))
                        .map(|testo| (testo, t.elapsed()))
                })
            })
            .collect();
        lavori.into_iter().map(|l| l.join().unwrap_or_else(|_| Err("errore interno".into()))).collect()
    })
}

fn risponde(agent: &ureq::Agent, v: &Voce) -> bool {
    let mut req = agent.get(&v.url).set("User-Agent", v.user_agent.as_deref().unwrap_or(BROWSER_UA));
    if let Some(r) = &v.referrer {
        req = req.set("Referer", r);
    }
    match req.call() {
        Ok(resp) => {
            let mut buf = [0u8; 256];
            resp.into_reader().take(256).read(&mut buf).map(|n| n > 0).unwrap_or(false)
        }
        Err(_) => false,
    }
}

// ------------------------------- MAIN ----------------------------------
fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let verifica = args.iter().any(|a| a == "--verifica");
    let diagnostica = args.iter().any(|a| a == "--diagnostica");
    let uscita = args
        .iter()
        .position(|a| a == "--output")
        .and_then(|i| args.get(i + 1))
        .cloned()
        .unwrap_or_else(|| FILE_USCITA.to_string());

    let inizio = Instant::now();
    let (canali, chiavi) = carica_canali();

    // 1. download parallelo
    let mut voci: Vec<Voce> = Vec::new();
    let mut scaricate = 0;
    println!("Fonti:");
    for (i, esito) in scarica_fonti().into_iter().enumerate() {
        match esito {
            Ok((testo, tempo)) => {
                let v = analizza(&testo, i);
                println!("  {:<12} {:>5} canali  {:>5} ms", FONTI[i].nome, v.len(), tempo.as_millis());
                voci.extend(v);
                scaricate += 1;
            }
            Err(e) => println!("  {:<12} NON RAGGIUNGIBILE: {e}", FONTI[i].nome),
        }
    }
    if scaricate == 0 {
        eprintln!("Nessuna fonte raggiungibile: playlist non aggiornata.");
        std::process::exit(1);
    }

    // 2. riconoscimento: nome esatto, poi tvg-id, poi nome tollerante
    let mut candidati: Vec<Vec<usize>> = vec![Vec::new(); canali.len()];
    let mut non_riconosciuti: Vec<&str> = Vec::new();
    for (vi, v) in voci.iter().enumerate() {
        let k = normalizza(&v.nome);
        let trovato = chiavi
            .get(&k)
            .or_else(|| chiavi.get(&normalizza_tvg_id(&v.tvg_id)).filter(|_| !v.tvg_id.is_empty()))
            .or_else(|| varianti(&k).iter().find_map(|x| chiavi.get(x)))
            .copied()
            // le voci estere valgono solo per i canali internazionali
            .filter(|&ci| v.italiana || canali[ci].internazionale);
        match trovato {
            Some(ci) => candidati[ci].push(vi),
            None if v.italiana => non_riconosciuti.push(&v.nome),
            None => {}
        }
    }
    for lista in &mut candidati {
        lista.sort_by_key(|&vi| (penalita(&voci[vi]), voci[vi].fonte, voci[vi].ordine));
        lista.dedup_by(|a, b| voci[*a].url == voci[*b].url);
    }

    // 3. scelta del flusso (con --verifica: il primo che risponde)
    let mut scelta: Vec<Option<usize>> = candidati.iter().map(|l| l.first().copied()).collect();
    let mut non_verificati = 0;
    if verifica {
        let agent = agente(SECONDI_VERIFICA);
        let prossimo = AtomicUsize::new(0);
        let risultati = Mutex::new(vec![None; canali.len()]);
        thread::scope(|s| {
            for _ in 0..THREAD_VERIFICA {
                s.spawn(|| loop {
                    let ci = prossimo.fetch_add(1, Ordering::Relaxed);
                    if ci >= canali.len() {
                        break;
                    }
                    let buono = candidati[ci].iter().copied().find(|&vi| risponde(&agent, &voci[vi]));
                    risultati.lock().unwrap()[ci] = buono;
                });
            }
        });
        for (ci, buono) in risultati.into_inner().unwrap().into_iter().enumerate() {
            match buono {
                Some(vi) => scelta[ci] = Some(vi),
                // nessun flusso risponde: si tiene il migliore (puo' essere un
                // blocco geografico del collegamento da cui si verifica)
                None if scelta[ci].is_some() => non_verificati += 1,
                None => {}
            }
        }
    }

    // 4. numerazione
    let riservati: HashSet<u32> = canali.iter().filter(|c| c.piano == Piano::Tivusat).map(|c| c.lcn[0]).collect();
    let mut righe: Vec<(u32, usize, usize)> = Vec::new(); // (numero, canale, voce)
    let mut spostati = Vec::new();
    for (ci, c) in canali.iter().enumerate() {
        let Some(vi) = scelta[ci] else { continue };
        let numero = match c.piano {
            Piano::Tivusat | Piano::Extra => c.lcn[0],
            Piano::Dtt => match c.lcn.iter().copied().find(|n| !riservati.contains(n)) {
                Some(n) => n,
                None => {
                    let n = OFFSET_CONFLITTI + c.lcn[0];
                    spostati.push(format!("{} {} -> {}", c.lcn[0], c.nome, n));
                    n
                }
            },
        };
        righe.push((numero, ci, vi));
    }
    righe.sort_by_key(|r| r.0);

    let tivusat_trovati = righe.iter().filter(|r| canali[r.1].piano == Piano::Tivusat).count();
    let extra_trovati = righe.iter().filter(|r| canali[r.1].piano == Piano::Extra).count();
    let dtt_trovati = righe.len() - tivusat_trovati - extra_trovati;
    let tivusat_totali = canali.iter().filter(|c| c.piano == Piano::Tivusat).count();
    if tivusat_trovati < MINIMO_CANALI_TIVUSAT {
        eprintln!("Solo {tivusat_trovati} canali Tivusat trovati: playlist non aggiornata per sicurezza.");
        std::process::exit(1);
    }

    // 5. scrittura
    let mut m3u = format!("#EXTM3U url-tvg=\"{EPG_URL}\" x-tvg-url=\"{EPG_URL}\"\n");
    for &(numero, ci, vi) in &righe {
        let c = &canali[ci];
        let v = &voci[vi];
        let tvg_id = c.epg.clone().unwrap_or_else(|| v.tvg_id.split('@').next().unwrap_or("").to_string());
        let gruppo = match (c.piano, numero) {
            (Piano::Dtt, _) => "Digitale terrestre",
            (Piano::Extra, _) => "Svizzera italiana",
            (_, 300..=399) => "Tivùsat - Rai regionali",
            (_, 400..) => "Tivùsat - locali e altri",
            _ => "Tivùsat",
        };
        let _ = writeln!(
            m3u,
            "#EXTINF:-1 tvg-id=\"{tvg_id}\" tvg-chno=\"{numero}\" tvg-name=\"{}\" tvg-logo=\"{}\" group-title=\"{gruppo}\",{}",
            c.nome, v.logo, c.nome
        );
        let mut ha_ua = false;
        for o in &v.opzioni {
            ha_ua |= o.starts_with("#EXTVLCOPT:http-user-agent=");
            m3u.push_str(o);
            m3u.push('\n');
        }
        if !ha_ua {
            match &v.user_agent {
                Some(ua) => {
                    let _ = writeln!(m3u, "#EXTVLCOPT:http-user-agent={ua}");
                }
                None if AGGIUNGI_USER_AGENT => {
                    let _ = writeln!(m3u, "#EXTVLCOPT:http-user-agent={BROWSER_UA}");
                }
                None => {}
            }
        }
        if let (Some(r), false) = (&v.referrer, v.opzioni.iter().any(|o| o.starts_with("#EXTVLCOPT:http-referrer="))) {
            let _ = writeln!(m3u, "#EXTVLCOPT:http-referrer={r}");
        }
        m3u.push_str(&v.url);
        m3u.push('\n');
    }
    if let Err(e) = std::fs::write(&uscita, m3u) {
        eprintln!("Impossibile scrivere {uscita}: {e}");
        std::process::exit(1);
    }

    // 6. riepilogo
    println!(
        "\nScritto '{uscita}': {tivusat_trovati}/{tivusat_totali} canali Tivusat + {dtt_trovati} DTT + {extra_trovati} svizzeri in {} ms",
        inizio.elapsed().as_millis()
    );
    let mut per_fonte = vec![0usize; FONTI.len()];
    for &(_, _, vi) in &righe {
        per_fonte[voci[vi].fonte] += 1;
    }
    let uso: Vec<String> = FONTI
        .iter()
        .zip(&per_fonte)
        .filter(|(_, n)| **n > 0)
        .map(|(f, n)| format!("{} {}", f.nome, n))
        .collect();
    println!("Flussi scelti per fonte: {}", uso.join(", "));
    if verifica {
        println!("Verifica: {non_verificati} canali senza alcun flusso che risponda (tenuti comunque).");
    }
    if !spostati.is_empty() {
        println!("DTT con numero gia' occupato da Tivusat: {}", spostati.join("; "));
    }

    if diagnostica {
        println!("\nCanali Tivusat senza flusso in nessuna fonte:");
        for (ci, c) in canali.iter().enumerate() {
            if c.piano == Piano::Tivusat && scelta[ci].is_none() {
                println!("  {:>4}  {}", c.lcn[0], c.nome);
            }
        }
        let mut visti = HashSet::new();
        non_riconosciuti.retain(|n| visti.insert(normalizza(n)));
        non_riconosciuti.sort_by_key(|n| n.to_lowercase());
        println!("\nNomi italiani non riconosciuti ({}), con la chiave da usare come alias:", non_riconosciuti.len());
        for n in non_riconosciuti {
            println!("  {n}  ->  {}", normalizza(n));
        }
    }
}

// ------------------------------- TEST ----------------------------------
#[cfg(test)]
mod test {
    use super::*;

    #[test]
    fn normalizzazione() {
        assert_eq!(normalizza("La 7 HD"), "la7");
        assert_eq!(normalizza("Rai 4K"), "rai4k");
        assert_eq!(normalizza("Sky TG24 Ⓖ"), "skytg24");
        assert_eq!(normalizza("France 24 English (720p) [Geo-blocked]"), "france24english");
        assert_eq!(normalizza("Radio Libertà"), "radioliberta");
        assert_eq!(normalizza("IT: Rai 1"), "rai1");
        assert_eq!(normalizza("IT Channel"), "itchannel");
        assert_eq!(normalizza_tvg_id("Rai1.it@SD"), "rai1");
        assert_eq!(normalizza_tvg_id("TV2000.va"), "tv2000");
    }

    #[test]
    fn nome_con_virgole_negli_attributi() {
        let e = r#"#EXTINF:-1 tvg-logo="a,b.png" group-title="x",Rai 1"#;
        assert_eq!(nome_canale(e), "Rai 1");
        let m = r#"#EXTINF:-1 tvg-id="Rai1.it"tvg-chno="1"group-title="Rai":http-user-agent="HbbTV/1.6.1",Rai 1"#;
        assert_eq!(nome_canale(m), "Rai 1");
        assert_eq!(attributo(m, "http-user-agent").as_deref(), Some("HbbTV/1.6.1"));
    }

    #[test]
    fn elenco_canali_valido() {
        let (canali, _) = carica_canali();
        assert!(canali.len() > 150);
    }
}
