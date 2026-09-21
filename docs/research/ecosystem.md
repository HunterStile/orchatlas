# Ecosistema e backend candidati per OrchAtlas

Data della verifica: **2026-09-21**. Ricerca documentale su fonti primarie; nessuna installazione, credenziale, chiamata di inferenza o benchmark. Le capacità riportate sono dichiarazioni e contratti upstream, non risultati di una prova locale di OrchAtlas.

**Decisione dell'utente: Codex e OpenCode sono entrambi nel perimetro della v0.1.** Il confronto seguente spiega le differenze di integrazione; non rimette in discussione questa scelta e non rinvia OpenCode a una versione successiva.

## Componenti diversi, responsabilità diverse

| Componente | Ruolo documentato | Implicazione per OrchAtlas |
| --- | --- | --- |
| Codex Router | Adattatore locale di inferenza e protocolli per usare provider esterni nel client Codex. Codex conserva loop agentico, strumenti, permessi, skill, file e conversazioni. | Può fornire trasporto e catalogo all'adattatore Codex della v0.1. Non esegue da solo le ricette di lavoro. [README](https://github.com/duolahypercho/codex-router/tree/9c0db45676238d032757370ec4010b66b6759dd8#how-routing-works) |
| OpenCode | Host per coding agent. Permette agenti primari e subagent, con modello e permessi configurati per agente. | È uno dei due host previsti dalla v0.1, con un adattatore dedicato. [Agents](https://opencode.ai/docs/agents/) |
| OpenCode Go | Servizio di accesso ai modelli in abbonamento, con API key ed endpoint pubblici. | È una scelta di provider; usarlo attraverso Router non significa eseguire il client OpenCode. [Go](https://opencode.ai/docs/go/) |
| OpenClaw | Gateway self-hosted per assistenti collegati a canali di messaggistica; gestisce sessioni, agenti e connessioni. | Ha senso per un assistente raggiungibile da chat e automazioni. Non è una dipendenza necessaria della replica di una skill di coding. [Documentazione](https://docs.openclaw.ai/) |

OpenCode usa AI SDK e Models.dev per il supporto ai provider e accetta identificativi `provider/model`. Il suo catalogo non costituisce un benchmark comparativo. [Models](https://opencode.ai/docs/models/)

OpenCode Go espone protocolli diversi a seconda del modello: Responses, Chat Completions e Messages. Per esempio la pagina ufficiale assegna `deepseek-v4.1-flash` al percorso Chat Completions sotto `https://opencode.ai/zen/go/v1`. La coppia provider/modello, e non soltanto il nome commerciale del modello, deve quindi far parte di una ricetta. [Endpoint Go](https://opencode.ai/docs/go/#endpoints)

OpenClaw descrive agenti con workspace, configurazione e cronologia separati, instradati dai binding dei canali; documenta anche un preset con coordinatore e specialisti. Queste funzioni vanno distinte sia dal trasporto HTTP sia dalla ricetta operativa che OrchAtlas vuole curare. [Multi-agent routing](https://docs.openclaw.ai/concepts/multi-agent)

## Codex Router: revisione, dipendenze e licenza

La lettura del codice è fissata al commit **`9c0db45676238d032757370ec4010b66b6759dd8`**, datato 2026-09-20. L'API GitHub `releases/latest`, interrogata il 2026-09-21, indica **v0.6.0**, pubblicata il 2026-09-15. Il commit di `main` esaminato è successivo alla release: non va descritto come identico al tag. [Commit](https://github.com/duolahypercho/codex-router/commit/9c0db45676238d032757370ec4010b66b6759dd8), [release](https://github.com/duolahypercho/codex-router/releases/tag/v0.6.0)

| Ambito | Dipendenze dichiarate nella revisione esaminata |
| --- | --- |
| Package principale | `codex-model-router` 0.6.0, privato, ESM; Node `>=22.19.0`; `proper-lockfile` 4.1.2 e `undici` 8.10.2; sviluppo: `playwright` 1.63.0. [package.json](https://github.com/duolahypercho/codex-router/blob/9c0db45676238d032757370ec4010b66b6759dd8/package.json) |
| Gateway Python | Dipendenze dirette `litellm[proxy]==1.96.0` e `fastapi==0.139.2`; lock delle dipendenze transitive con hash. [python.in](https://github.com/duolahypercho/codex-router/blob/9c0db45676238d032757370ec4010b66b6759dd8/requirements/python.in), [python.txt](https://github.com/duolahypercho/codex-router/blob/9c0db45676238d032757370ec4010b66b6759dd8/requirements/python.txt) |
| Control Center separato | React/React DOM 19.2.8, lucide-react 1.31.0; strumenti di sviluppo/build fra cui Electron 43.4.0, Vite 8.2.1 e TypeScript 7.0.2. Queste dipendenze appartengono all'app grafica, non tutte al package principale. [Manifest dell'app](https://github.com/duolahypercho/codex-router/blob/9c0db45676238d032757370ec4010b66b6759dd8/apps/control-center/package.json) |

Il README richiede anche `uv` oppure Python 3.10+ con `venv`, Git e un client Codex; l'installazione Windows controlla requisiti PowerShell specifici. Non risulta pubblicato da questo progetto un CLI installabile con `npm install codex-router`. [Requisiti e installazione](https://github.com/duolahypercho/codex-router/tree/9c0db45676238d032757370ec4010b66b6759dd8#guided-installer)

La licenza del router è MIT, copyright 2026 dei contributori, con obbligo di conservare avviso di copyright e licenza nelle copie o porzioni sostanziali. `NOTICE.md` registra attribuzioni distinte a opencodex, devin-2api e Primer Octicons. Collegare una dipendenza e copiarne codice sono scelte diverse: eventuali incorporazioni richiederanno gli avvisi pertinenti. [LICENSE](https://github.com/duolahypercho/codex-router/blob/9c0db45676238d032757370ec4010b66b6759dd8/LICENSE), [NOTICE](https://github.com/duolahypercho/codex-router/blob/9c0db45676238d032757370ec4010b66b6759dd8/NOTICE.md)

## Catalogo esistente e compatibilità dei subagent

Il router offre già catalogo unificato nativo/esterno, visibilità e ordinamento dei modelli, selezione dei provider e un registro con mapping, limiti, modalità e profili delle richieste. La gestione locale del picker è persistente. Sono funzioni già presenti, quindi il solo selettore di modelli non differenzierebbe OrchAtlas. [Architettura e catalogo](https://github.com/duolahypercho/codex-router/blob/9c0db45676238d032757370ec4010b66b6759dd8/docs/HOW-IT-WORKS.md), [stato del picker](https://github.com/duolahypercho/codex-router/blob/9c0db45676238d032757370ec4010b66b6759dd8/src/model-picker-state.mjs)

**Distinzione essenziale: un modello selezionabile non è automaticamente una delega verificata.** I test del registro per DeepSeek V4.1 Flash controllano che le route diretta, OpenCode Go, OpenRouter, Nous, Command Code e Ollama Cloud non dichiarino `multiAgentVersion: "v2"` come capacità iniziale. Questo dimostra l'assenza di quella certificazione nel registro esaminato, non un'incompatibilità assoluta. [Test V4.1 Flash](https://github.com/duolahypercho/codex-router/blob/9c0db45676238d032757370ec4010b66b6759dd8/test/deepseek-v4-1-flash.test.mjs)

Nel codice corrente esistono tre percorsi per ottenere una dichiarazione v2 effettiva:

1. Una capacità v2 già presente nel registro upstream.
2. La scelta locale dell'operatore: `selected` più abilitazione della route, oppure `all`, promuove le route non nascoste e non disabilitate, aggiungendo `subagentSelectedByOperator: true`.
3. Una verifica locale completa, registrata con stato `verified`, slug esatto, epoca valida e tutti e cinque i controlli superati.

Il comportamento della scelta locale è nel corpo di `applyMultiAgentSettings`, ed è coperto dal test di modalità `selected`; la verifica completa passa invece da `verifiedForRoute` e `applySubagentProofs`. [Implementazione della scelta](https://github.com/duolahypercho/codex-router/blob/9c0db45676238d032757370ec4010b66b6759dd8/src/multi-agent-state.mjs#L193-L239), [test](https://github.com/duolahypercho/codex-router/blob/9c0db45676238d032757370ec4010b66b6759dd8/test/multi-agent-state.test.mjs#L115-L137), [verifica locale](https://github.com/duolahypercho/codex-router/blob/9c0db45676238d032757370ec4010b66b6759dd8/src/subagent-proofs.mjs#L158-L211)

L'upstream distingue a sua volta `selected_not_certified`, `certified_in_registry` e `verified_locally`. I cinque controlli includono streaming, tool call, relay del payload cifrato, restituzione di un marker e follow-up nello stesso thread. Selezionare una route esprime una preferenza; non dimostra che la delega riuscirà. [Spiegazione della provenienza](https://github.com/duolahypercho/codex-router/blob/9c0db45676238d032757370ec4010b66b6759dd8/src/subagent-explain.mjs#L158-L179), [procedura di certificazione](https://github.com/duolahypercho/codex-router/blob/9c0db45676238d032757370ec4010b66b6759dd8/docs/SUBAGENT-CERTIFICATION.md)

Esiste un'incoerenza documentale: alcune frasi del README, di HOW-IT-WORKS e alcuni commenti iniziali affermano che la scelta locale non possa promuovere route non certificate; il corpo della funzione e i test sopra documentano invece la promozione esplicita. La ricostruzione qui privilegia codice eseguibile, test e documento specifico di certificazione. Non è stata verificata una sessione reale.

## Contratto documentato per l'adattatore OpenCode

Gli agenti si dichiarano nel blocco `agent` di `opencode.json` oppure in Markdown con frontmatter. Il nome del file determina il nome dell'agente. `mode` distingue `primary`, `subagent` e `all`; `model` accetta `provider/model-id`. Senza override, il primario usa il modello globale e il subagent eredita dal primario. `permission.task` limita le deleghe effettuate tramite Task, ma l'invocazione manuale con `@` resta distinta. `steps` limita le iterazioni agentiche, non certifica un budget monetario. [Configurazione agenti](https://opencode.ai/docs/agents/)

I percorsi seguenti sono destinazioni supportate dall'host. **Proposta di export OrchAtlas:** generarne una copia in una directory di output da ispezionare, prima di un'eventuale applicazione al progetto; usare nomi `orchatlas-*` e una sola definizione per agente.

| Destinazione nel progetto | Contenuto da generare | Contratto ufficiale |
| --- | --- | --- |
| `opencode.json` | Frammento JSON con schema, impostazioni OrchAtlas e, se richiesto, `default_agent`. Le definizioni dei ruoli possono vivere qui oppure nei file Markdown della riga seguente. | [Config](https://opencode.ai/docs/config/) |
| `.opencode/agents/orchatlas-<ruolo>.md` | Frontmatter con descrizione, modalità, modello e permessi; corpo con istruzioni del ruolo. | [Agent Markdown](https://opencode.ai/docs/agents/#markdown) |
| `.opencode/skills/orchatlas/SKILL.md` | Procedura riutilizzabile della ricetta, con `name: orchatlas` e descrizione. | [Agent Skills](https://opencode.ai/docs/skills/) |

Le alternative globali ufficiali sono `~/.config/opencode/agents/`, `~/.config/opencode/skills/` e `~/.config/opencode/opencode.json`; per il primo export proponiamo l'ambito progetto. Le directory canoniche sono plurali. I file JSON/JSONC vengono uniti: le chiavi in conflitto seguono le precedenze, mentre le altre restano. `OPENCODE_CONFIG` si carica prima del file del progetto; non crea quindi un ambiente isolato. `default_agent` deve indicare un primario. `subagent_depth` ha default 1 e controlla la profondità della delega, non il numero di agenti simultanei. [Posizioni, precedenze e opzioni](https://opencode.ai/docs/config/)

I permessi usano `allow`, `ask` e `deny`, con regole per pattern e ultima corrispondenza vincente. `permission` sostituisce il vecchio `tools` booleano. Gran parte dei permessi è permissiva per default: un ruolo di sola analisi deve avere restrizioni esplicite per modifica, shell e altre capacità abilitate. **Proposta OrchAtlas:** tradurre ogni ruolo in una policy dichiarata e presentare le differenze quando si unisce la configurazione esistente; non rappresentare un semplice prompt come isolamento di sistema. [Permissions](https://opencode.ai/docs/permissions/)

Le skill si caricano su richiesta tramite lo strumento `skill`. Sono riconosciuti anche i percorsi `.agents/skills/<name>/SKILL.md` e quelli compatibili con Claude. Nome e descrizione sono obbligatori; il nome deve corrispondere alla cartella, usare minuscole/numeri/trattini e avere 1–64 caratteri; la descrizione 1–1024. **Proposta OrchAtlas:** scegliere un solo percorso di installazione per evitare duplicazioni e mettere il comportamento indispensabile nel contratto dell'agente primario, senza presumere che una skill disponibile sia sempre caricata. [Discovery e frontmatter](https://opencode.ai/docs/skills/)

OpenCode espone un server HTTP/OpenAPI tramite `opencode serve`. Lo SDK `@opencode-ai/sdk` offre sia `createOpencode`, che avvia server e client, sia `createOpencodeClient` per un server già esistente; documenta API di configurazione, agenti e sessioni. **Limite di questa fase:** l'adattatore pianificato esporta e valida file; lo SDK è un'opzione per una futura esecuzione controllata. Non occorre avviare il server o inviare prompt per produrre l'export. [Server](https://opencode.ai/docs/server/), [SDK](https://opencode.ai/docs/sdk/)

## Decisione v0.1 e architettura proposta

**Decisione vincolante: due adattatori, Codex e OpenCode, dalla prima versione.** Non è una dichiarazione che siano già implementati o verificati dal vivo. L'analisi comparativa indica soltanto dove differiscono i contratti: Codex mantiene continuità con Astra; OpenCode espone configurazione multi-provider e modelli per ruolo nel proprio host.

**Proposta progettuale:** un cuore OrchAtlas indipendente dal runtime conserva ricette versionate, ruoli, scelta `provider/model`, criteri di escalation, limiti e prove per combinazione. Il maintainer aggiorna le ricette; l'utente può fissarne la versione e sostituire i modelli. Lo stesso manifest passa a due compilatori, `adapters/codex` e `adapters/opencode`, che producono artefatti e diagnostica specifici per l'host. Ogni adattatore deve segnalare opzioni non traducibili invece di dichiarare equivalenza fra host.

L'adattatore **Codex** può usare **Codex Router opzionalmente** per provider esterni. Il router rimane una dipendenza da verificare e aggiornare. L'adattatore **OpenCode** genera configurazione, agenti e skill nei formati ufficiali sopra descritti. Una route selezionata, un file valido e una sessione funzionante sono tre evidenze distinte: nessun export conferisce da solo un badge di compatibilità live.

OpenClaw può essere un adattatore successivo se emerge l'obiettivo di operare da Telegram, WhatsApp o altri canali. È già un possibile client del router: la presenza di tale integrazione nel router non dimostra che il progetto Astra la utilizzi. [Target OpenClaw del router](https://github.com/duolahypercho/codex-router/tree/9c0db45676238d032757370ec4010b66b6759dd8#make-models-appear-in-openclaw)

Il valore aggiunto proposto è la **curatela riproducibile delle squadre di modelli**: per quali compiti una ricetta è adatta, perché sono scelti quei ruoli, quale combinazione è stata provata, quando, con quali limiti e con quali risultati. Stati separati come `documented`, `operator-selected` e `tested` eviterebbero di confondere discovery, preferenza e prova. Per sostenere una promessa di superiorità serviranno task pubblici ripetibili, metodo di valutazione e misure reali; questa analisi non le produce.

## Incertezze da risolvere prima di dichiarare supporto

- Non sono state provate delega, tool call, follow-up, costi o latenza delle combinazioni candidate.
- Il risultato va vincolato alla coppia provider/modello, al client e alla versione dell'adattatore; nomi simili non provano equivalenza delle route.
- La modalità di autenticazione e il relay possono modificare il risultato: la documentazione del router segnala verifiche ancora incomplete per alcuni percorsi con account ChatGPT o API key. Non dedurne né supporto universale né impossibilità universale. [Stato delle verifiche](https://github.com/duolahypercho/codex-router/blob/9c0db45676238d032757370ec4010b66b6759dd8/docs/SUBAGENT-CERTIFICATION.md#what-has-already-been-verified-and-what-has-not)
- OpenCode è stato valutato sulla documentazione pubblica corrente, senza fissare né provare una release locale. L'adattatore previsto dalla v0.1 deve specificare versioni e controlli prima del badge di compatibilità.

Punto di partenza della ricerca: `SOURCES.md` del checkout di `ethanplusai/astra-flash-orchestrator`; riferimenti esterni verificati direttamente presso i rispettivi progetti.

La v0.1 prevista ha quindi **un catalogo di ricette condiviso e due adattatori di pari livello: Codex e OpenCode**. Implementazione e prove dei rispettivi artefatti restano attività separate dalla presente ricerca.
