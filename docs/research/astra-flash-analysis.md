# Analisi di Astra Flash Orchestrator

Data: 21 settembre 2026. Repository: [ethanplusai/astra-flash-orchestrator](https://github.com/ethanplusai/astra-flash-orchestrator).

Snapshot analizzato: `bcc7f9eaee051126c0ce821a55194d0b20425b22`, commit del 20 settembre 2026. `VERSION` contiene `1.2.0`, ma il changelog include anche modifiche sotto `Unreleased`: questa analisi riguarda il commit, non garantisce il contenuto di un archivio pubblicato. Il checkout ha 39 file tracciati.

## Che cosa è realmente

È un pacchetto di personalizzazione di Codex: una skill, istruzioni per il worker, un installer e strumenti di verifica. Il ciclo agentico e gli strumenti restano quelli del client Codex. Un router esterno permette di utilizzare un provider diverso per il worker. Il pacchetto non implementa un proprio motore di inferenza, server applicativo o scheduler deterministico. [Skill](https://github.com/ethanplusai/astra-flash-orchestrator/blob/bcc7f9eaee051126c0ce821a55194d0b20425b22/skill/astra-flash-orchestrator/SKILL.md).

Il flusso previsto è:

```mermaid
flowchart LR
    U[Richiesta o piano] --> A[Astra: obiettivi e contratti]
    A --> B[Subagente nativo Codex]
    B --> R[Codex Router]
    R --> F[DeepSeek V4.1 Flash: sviluppo e verifiche]
    F --> V[Astra: esame della patch e accettazione]
    V --> C[Integrazione e checkpoint]
    V -->|Correzioni mirate| F
```

Il lavoro banale rimane nel thread principale. Per il lavoro sostanziale Astra prepara un incarico completo e lascia al worker esplorazione, sviluppo, test e correzioni. Un solo writer è il default; due richiedono attività indipendenti e workspace separati verificati. La revisione finale riguarda sia conformità alla specifica sia qualità del codice. [Esecuzione](https://github.com/ethanplusai/astra-flash-orchestrator/blob/bcc7f9eaee051126c0ce821a55194d0b20425b22/skill/astra-flash-orchestrator/references/execution.md), [revisione](https://github.com/ethanplusai/astra-flash-orchestrator/blob/bcc7f9eaee051126c0ce821a55194d0b20425b22/skill/astra-flash-orchestrator/references/review.md).

## Tecnologie e integrazioni

| Componente | Presenza e funzione |
| --- | --- |
| Codex | Host necessario, con subagenti nativi e agenti personalizzati TOML. |
| GPT-6 Astra | Modello principale richiesto dal workflow documentato. |
| DeepSeek V4.1 Flash | Unico modello worker previsto. |
| Codex Router | Dipendenza esterna già installata e configurata; non inclusa nell'installer. |
| Python 3.11+ | Installer, diagnostica, validazione del piano, packaging e test; libreria standard. |
| Markdown | Skill, policy, contratti di lavoro e report. |
| TOML / JSON / YAML | Configurazione agente generata, binding del routing e piani, metadati della skill. |
| OpenCode | Non è l'host di questa repo; `opencode Go` è un provider opzionale raggiunto dal router. |
| OpenClaw | Nessuna integrazione o dipendenza presente nei file di questo snapshot. |
| Superpowers / GSD | Piani accettati come input; riferimenti metodologici, non dipendenze obbligatorie. |
| LangChain / LangGraph / CrewAI / AutoGen | Nessuna di queste librerie è importata o inclusa nel pacchetto analizzato. |
| MCP | Nessun server MCP proprio; eventuali tool provengono dall'host. |

Fonti: [installer](https://github.com/ethanplusai/astra-flash-orchestrator/blob/bcc7f9eaee051126c0ce821a55194d0b20425b22/install.py), [provenienza](https://github.com/ethanplusai/astra-flash-orchestrator/blob/bcc7f9eaee051126c0ce821a55194d0b20425b22/SOURCES.md), [configurazione locale](https://github.com/ethanplusai/astra-flash-orchestrator/blob/bcc7f9eaee051126c0ce821a55194d0b20425b22/skill/astra-flash-orchestrator/scripts/local_config.py). Per le dipendenze del router, distinte da quelle di questa skill, vedere [ricerca sull'ecosistema](ecosystem.md).

## Scelta del provider, non scelta libera del modello

`SUPPORTED_ROUTES` elenca sei route dello stesso modello:

- `deepseek/deepseek-v4.1-flash`
- `openrouter/deepseek-v4.1-flash`
- `opencode-go/deepseek-v4.1-flash`
- `commandcode/deepseek-v4.1-flash`
- `nousresearch/deepseek-v4.1-flash`
- `ollama-cloud/deepseek-v4.1-flash`

La CLI accetta `--worker-route`, ma rifiuta valori fuori da questa lista. Cambiare provider non consente di scegliere liberamente Claude, Gemini, un altro GPT o un altro DeepSeek. Anche la policy, i ruoli del piano e le istruzioni sono legati ad Astra/Flash. Per generalizzare occorre cambiare il modello dei dati e le istruzioni, non solo aggiungere un menu. [Routing e controlli](https://github.com/ethanplusai/astra-flash-orchestrator/blob/bcc7f9eaee051126c0ce821a55194d0b20425b22/skill/astra-flash-orchestrator/scripts/local_config.py), [validatore](https://github.com/ethanplusai/astra-flash-orchestrator/blob/bcc7f9eaee051126c0ce821a55194d0b20425b22/skill/astra-flash-orchestrator/scripts/validate_plan.py).

## File da capire prima di replicare

| File | Responsabilità |
| --- | --- |
| `skill/astra-flash-orchestrator/SKILL.md` | Procedura operativa dell'orchestratore. |
| `references/planning.md`, `execution.md`, `review.md`, `routing.md` | Regole dettagliate di pianificazione, delega, revisione e routing. |
| `WORKER-INSTRUCTIONS.md` | Contratto del worker e formato del risultato. |
| `POLICY.md` | Blocco di istruzioni globali inseribile nell'ambiente Codex. |
| `install.py` | Preflight, generazione del ruolo, copia della skill, backup, sostituzione e undo. |
| `scripts/local_config.py` nella skill | Lettura TOML, selezione della route, controllo catalogo e URL locale. |
| `scripts/doctor.py` nella skill | Report statico ed eventuale GET locale a `/models`. |
| `scripts/validate_plan.py` nella skill | Controlli su struttura, dipendenze, percorsi e conflitti dei task. Non esegue il piano. |
| `templates/` | Specifica, brief, piano, report e checkpoint. |
| `examples/invoice-filter/` | Esempio di pianificazione, non applicazione eseguibile. |
| `scripts/release.py`, `MANIFEST.sha256` | Inventario con hash e archivio ZIP filtrato. |
| `tests/` | Test sintetici offline di installer, configurazione, piano e packaging. |

L'inventario deriva dal checkout del commit indicato. [Albero sorgente](https://github.com/ethanplusai/astra-flash-orchestrator/tree/bcc7f9eaee051126c0ce821a55194d0b20425b22).

## Installazione e confini

L'installer copia la skill in `~/.agents/skills/astra-flash-orchestrator/`, genera `$CODEX_HOME/agents/astra_flash_builder.toml` e `routing.json`, e può aggiungere la policy a `AGENTS.md` o all'override già attivo. Il ruolo blocca il modello worker e disabilita la creazione di ulteriori subagenti. Non installa il router né configura le credenziali. [Installer](https://github.com/ethanplusai/astra-flash-orchestrator/blob/bcc7f9eaee051126c0ce821a55194d0b20425b22/install.py).

La scrittura è atomica per singolo file; un errore durante l'applicazione avvia un rollback dei file già completati. Questo non equivale a una transazione garantita contro qualsiasi crash del processo o del sistema. L'undo verifica hash per non sovrascrivere modifiche successive.

Il doctor verifica catalogo e configurazione locale. La presenza di `multi_agent_version: "v2"` è un requisito, non prova che una richiesta reale sia arrivata al provider dichiarato. La verifica runtime richiede metadati della richiesta dell'host/router. Inoltre il controllo statico non risolve tutte le precedenze di progetto, UI, CLI e policy gestite. [Diagnostica](https://github.com/ethanplusai/astra-flash-orchestrator/blob/bcc7f9eaee051126c0ce821a55194d0b20425b22/skill/astra-flash-orchestrator/scripts/doctor.py), [validazione dichiarata dall'autore](https://github.com/ethanplusai/astra-flash-orchestrator/blob/bcc7f9eaee051126c0ce821a55194d0b20425b22/docs/VALIDATION.md).

La documentazione ufficiale conferma che gli agenti Codex personalizzati possono impostare modello e reasoning in file TOML. Questa possibilità dell'host non certifica automaticamente le route di terze parti. [Documentazione ufficiale OpenAI](https://learn.chatgpt.com/docs/agent-configuration/subagents).

## Verifica locale svolta

Ambiente: Windows, Python 3.12.4. Comando eseguito sul checkout senza modificarlo:

```text
python -B -m unittest discover -s tests -v
Ran 63 tests
FAILED (errors=3)
```

60 test superati; 3 errori nella creazione dei link simbolici delle fixture, tutti con `WinError 1314`:

- `test_worker_route_resolution_refuses_symlinked_binding`
- `test_symlink_destination_is_refused`
- `test_symlinked_distribution_file_is_rejected`

L'errore precede le asserzioni sulla protezione dai symlink: non prova un difetto di quelle protezioni, ma neppure le verifica su questa macchina. La suite completa non è quindi verde in questo ambiente. Non sono stati modificati privilegi Windows o test upstream per aggirare l'esito.

I test usano directory temporanee e una fixture HTTP locale. Non è stata applicata l'installazione alla configurazione personale e non sono state eseguite richieste di inferenza attraverso il router analizzato. Nessuna compatibilità runtime di OrchAtlas è stata ancora testata. Fonte di questi risultati: esecuzione locale del 21 settembre 2026, non una dichiarazione upstream.

## Risparmi: che cosa dimostrano i numeri pubblicati

L'autore riporta una riduzione del 98,9% dell'input Astra per mille righe e del 97,0–97,7% del costo computazionale equivalente per mille righe. La metodologia descrive un singolo field build, fasi con attività diverse, costi Astra stimati e alcuni task non ancora accettati al cutoff. Non è una comparazione controllata dello stesso insieme di task. [Metodologia originale](https://github.com/ethanplusai/astra-flash-orchestrator/blob/bcc7f9eaee051126c0ce821a55194d0b20425b22/docs/BENCHMARK.md).

La mia valutazione: il principio economico è plausibile, ma quei numeri non sono una previsione per OrchAtlas. Le righe prodotte non misurano da sole correttezza o utilità. Per una raccomandazione pubblica servono task identici, verifiche di accettazione, ripetizioni, tempi, tentativi, consumi e limiti del campione.

## Cosa conviene riprendere e cosa cambiare

Da riprendere: incarichi completi, separazione fra implementazione e accettazione, contesto limitato al necessario, report verificabili, installazione reversibile, modello/provider espliciti e assenza di sostituzioni silenziose.

Da cambiare: coppia di modelli fissa, nomi dei ruoli legati al vendor, lista di route nel codice, assenza di ricette versionate e confrontabili, assenza di un processo pubblico per mantenere le raccomandazioni, copertura multipiattaforma non ancora dimostrata.

Una copia con nomi diversi aggiungerebbe poco. La proposta OrchAtlas è una libreria curata di combinazioni, con un formato comune e integrazioni concrete. Vedere [blueprint](../blueprint.md).

## Licenza e provenienza

Il repository contiene una licenza MIT, copyright 2026 Ethan Rogers. Il testo consente uso e modifica e richiede che avviso di copyright e permesso accompagnino copie o parti sostanziali. Se riutilizziamo codice o testi sostanziali, manteniamo gli avvisi pertinenti e documentiamo l'origine. [Licenza al commit analizzato](https://github.com/ethanplusai/astra-flash-orchestrator/blob/bcc7f9eaee051126c0ce821a55194d0b20425b22/LICENSE).

Questa cartella contiene ricerca e proposte originali, non una copia dell'implementazione. Le dipendenze future vanno valutate in base alla loro specifica licenza.
