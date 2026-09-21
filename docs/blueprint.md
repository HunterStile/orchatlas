# OrchAtlas: proposta di prodotto e implementazione

Aggiornamento v0.2.0: OrchAtlas coordina Codex e OpenCode nello stesso run autonomo, con un terminale interattivo. La proposta originale qui sotto è storica; l'architettura corrente e i suoi limiti sono descritti in [RUNTIME](RUNTIME.md).

Data: 21 settembre 2026. Questo documento conserva la proposta di prodotto; il primo MVP ora implementa CLI, ricette e generazione/installazione per entrambi gli host. Per lo stato effettivo e i limiti vedere [MVP](MVP.md) e [validazione](VALIDATION.md). Baseline: [analisi della repo originale](research/astra-flash-analysis.md) e [ricerca sull'ecosistema](research/ecosystem.md).

## La promessa del prodotto

OrchAtlas aiuta a scegliere una combinazione di modelli e un metodo di lavoro adatti al task in **Codex e OpenCode**. Il maintainer aggiorna le raccomandazioni pubbliche; gli utenti possono scegliere i modelli o adottare una ricetta verificata e fissarne la versione. Il supporto a entrambi gli host nella prima versione è una decisione esplicita dell'utente del 21 settembre 2026.

Tagline proposta: **Choose your models. Follow a tested playbook.** Da usare come promessa di prodotto; fino ai primi test reali il README deve mantenere visibile lo stato di sviluppo.

Il valore distintivo è la curatela supportata da prove: per quale attività funziona una combinazione, con quali costi osservati, tempi, qualità e versioni degli strumenti. Un elenco di modelli o un selettore da solo è una differenziazione debole rispetto ai router già esistenti.

## Quattro scelte diverse

| Concetto | Significato |
| --- | --- |
| Host | Strumento che esegue agenti e tool: Codex oppure OpenCode, entrambi nel perimetro iniziale. |
| Modello | Identità del modello incaricato di un ruolo. |
| Provider/route | Servizio e percorso effettivo che erogano il modello. |
| Workflow | Regole di assegnazione, revisione, retry e integrazione. |

Due provider dello stesso modello possono avere prezzi, limiti e comportamento operativo diversi. Una ricetta registra entrambi. La disponibilità presso un provider non implica supporto ai subagenti nel client scelto.

## Perimetro iniziale deciso

Costruire due adapter nella prima versione: Codex con subagenti nativi e OpenCode con i suoi agenti primari/subagenti. Condividere schema delle ricette, catalogo, resolver e formato delle prove; tradurre separatamente configurazione, capacità e permessi. Per Codex, Codex Router è un'integrazione opzionale per le route esterne che superano la verifica. OpenCode usa i provider supportati dal proprio host.

Ogni installazione sceglie il proprio host. Il supporto a entrambi non significa avviare Codex e OpenCode insieme per lo stesso task, né promettere una delega fra i due processi. L'orchestrazione fra host distinti sarebbe una funzionalità ulteriore con coordinamento, stato e isolamento da progettare.

Un profilo che usa soltanto modelli nativi disponibili all'utente non dovrebbe richiedere il router. Un profilo con provider esterni deve verificarne i prerequisiti. Non installare il router come conseguenza nascosta della scelta di una ricetta.

OpenClaw non è necessario per questo primo obiettivo di sviluppo software. Un'eventuale integrazione avrebbe senso quando esiste un caso d'uso specifico che la richiede.

## Ruoli

- `planner`: obiettivi, contratti, rischi e piano.
- `builder`: implementazione e verifiche dell'incarico.
- `reviewer`: verifica della patch rispetto a specifica e qualità.

Sono responsabilità logiche, non tre processi obbligatori. Il coordinatore può fare anche la revisione; i task minimi possono restare su un agente. Un revisore distinto va giustificato dai risultati o dal rischio.

Il selettore deve consentire modello/provider/effort per ruolo soltanto fra combinazioni compatibili. Il cambio del modello principale si applica attraverso i meccanismi supportati dall'host, normalmente nella configurazione o all'avvio di una nuova sessione; scrivere un nome in un file non cambia magicamente il modello della chat in corso.

## Architettura proposta

```text
Catalogo modelli e compatibilità       Ricette versionate e prove
                  \                   /
                   Resolver e validazione
                             |
                    Configurazione risolta
                             |
              Generatore di configurazioni host
                             |
            Preview -> installazione -> verifica
                             |
               Adapter Codex / Adapter OpenCode
                             |
             Evidenze della run e accettazione
```

| Modulo | Responsabilità | Esclude |
| --- | --- | --- |
| Catalogo | Identità, route, capacità, fonte e data di verifica | Ranking universali senza task o evidenza |
| Ricette | Assegnazioni, workflow, criteri e versioni | Credenziali e configurazioni personali |
| Resolver | Incrocia scelta utente, disponibilità e capacità; produce scelta esplicita o errore | Fallback silenziosi |
| Adapter Codex | Genera ruoli/configurazione supportati e controlla prerequisiti | Un secondo loop agentico duplicato |
| Adapter OpenCode | Genera agenti e configurazione nativi, traducendo modello e permessi | Assumere che TOML, effort e permessi Codex abbiano equivalenti identici |
| Installer | Preview, applicazione, backup, aggiornamento e undo | Attivazione automatica di inferenza a pagamento |
| Evidenze | Risultati, route osservata, consumi e versione del task | Deduzioni dell'identità del modello dalla sua risposta testuale |

Per una prima CLI di generazione/configurazione Python 3.11+ è sufficiente e allinea le utility all'upstream. JSON può contenere catalogo e ricette; l'output è TOML per gli agenti Codex e configurazione/Markdown nativi per OpenCode. Un'app che controlli direttamente il server OpenCode potrebbe valutare il suo SDK TypeScript, ma non è necessario per distribuire ricette ai due host. Nessun framework multiagente aggiuntivo è richiesto per replicare questo workflow.

La traduzione deve essere esplicita: effort e varianti del modello dipendono dall'host/provider; un'opzione non traducibile produce una spiegazione o un errore, non viene ignorata. Anche autorizzazioni dei tool e della delega devono essere controllate per ciascun host. Una ricetta può risultare verificata su uno e ancora sperimentale sull'altro.

La prima versione può governare il flusso con skill e configurazioni. Questo non offre limiti di spesa o scheduling deterministici. Un budget scritto nelle istruzioni è una regola operativa: un limite monetario rigido richiede controllo runtime o del provider. Documentare la distinzione.

## Dati da versionare

Una scheda modello/route dovrebbe contenere identificatore esatto, provider, capacità richieste dall'host, livelli di effort documentati, fonte, data di controllo, stato di disponibilità e limiti noti.

Una ricetta dovrebbe contenere:

- ID stabile e versione immutabile.
- Classe di task, priorità e campo di applicazione.
- Ruoli con modello, provider ed effort espliciti.
- Host, adapter e versioni provate; eventuale versione router.
- Regole per writer simultanei, revisione e correzioni.
- Fallback dichiarati; nessun cambio provider implicito.
- Evidenza collegata, data, maintainer e motivazione della raccomandazione.

Separare gli stati `draft`, `static-checked`, `runtime-verified`, `benchmarked`, `deprecated`. Un modello nel catalogo non diventa automaticamente raccomandato.

La configurazione risolta locale deve fissare versione ricetta, revisione catalogo, modelli richiesti, route e adapter. Registrare l'identità osservata durante la run; se un provider espone solo un alias mutabile, dichiarare che la riproducibilità dell'identità sottostante è limitata.

## Aggiornamenti curati dal maintainer

1. Registri una nuova combinazione come candidata, con le fonti aggiornate.
2. Esegui validazione statica e una prova reale sulla combinazione host/route.
3. La confronti su task ripetibili con la raccomandazione esistente e una baseline ad agente singolo.
4. Pubblichi risultati, difetti e motivazione; promuovi solo i casi supportati dai dati.
5. Crei una nuova versione della ricetta e una release del catalogo.
6. Gli utenti visualizzano la differenza e scelgono se aggiornare; una versione fissata continua a identificare la stessa ricetta.

Le modifiche possono essere manuali, mentre CI e validatori automatizzano i controlli. Separare la versione del catalogo da quella della CLI permette di aggiornare raccomandazioni senza distribuire ogni volta il programma.

Non promettere una sola combinazione migliore per tutto. Prevedere categorie come economica, rapida, qualità e task specifici, senza riempirle di vincitori prima delle misure.

## Benchmark utile

Usare gli stessi task, commit iniziali, test di accettazione e limiti per ogni configurazione. Comprendere fix di bug, feature, refactoring e almeno un progetto concreto dimostrabile. Ripetere le run, riportando numero di campioni e variabilità.

Metriche principali: task accettati, regressioni, tempo totale, tentativi/correzioni, token distinti per ruolo, cache e costi osservati. Separare fatturazione API reale, stima API equivalente e consumo di abbonamento. Conservare soltanto evidenze pubblicabili prive di contenuti riservati.

Confrontare almeno: un modello singolo, una coppia planner/builder e la ricetta candidata. Tenere conto del costo di coordinamento e delle run fallite. Le righe di codice possono essere un dato accessorio, non il criterio di vittoria.

## Roadmap con criteri di uscita

| Fase | Risultato | Criterio per passare oltre |
| --- | --- | --- |
| 0 — Ricerca | Analisi upstream, confini e posizionamento | Fatti distinti da proposte; fonti fissate a commit |
| 1 — Formato | Catalogo, ricette, resolver e fixture sintetiche | Errori chiari per route inesistente, effort incompatibile o ricetta ambigua |
| 2 — Entrambi gli adapter | Codex e OpenCode: generazione agenti, preview, installazione e undo | Fixture per entrambi e prove isolate Windows/Linux/macOS; nessun danno a config o file successivi |
| 3 — Run reali sui due host | Modelli selezionati eseguono task utili in Codex e OpenCode | Metadati confermano route; verifiche di accettazione completate separatamente |
| 4 — Prima release | Demo per entrambi, ricette supportate e misure pubbliche | Almeno un percorso realmente verificato per ciascun host; limiti di portabilità documentati |
| 5 — Catalogo mantenuto | Nuove combinazioni, aggiornamenti e deprecazioni | Evidenze collegate alle precise versioni di ogni host e adapter |

Stato attuale: primo MVP locale delle fasi 1–2. Test offline e controlli di caricamento host sono distinti da run reali e benchmark, che restano da svolgere. La matrice CI multipiattaforma è predisposta; la sua presenza non è prova che sia stata eseguita.
