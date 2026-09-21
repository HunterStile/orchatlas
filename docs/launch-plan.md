# Nome e lancio pubblico

Data: 21 settembre 2026. Queste sono proposte editoriali, non previsioni di popolarità.

## Valutazione di OrchAtlas

Il nome funziona per il prodotto proposto: `Orch` richiama orchestration e `Atlas` un insieme di percorsi e scelte mantenuto nel tempo. Non lega il progetto a un vendor o a una coppia di modelli che potrebbe diventare superata.

Il limite è la comprensibilità immediata: non tutti capiscono `Orch` e la pronuncia può variare. Una tagline concreta, un esempio e una demo devono rendere chiaro il significato. Mantengo **OrchAtlas** come nome principale e **orchatlas** come slug.

Una ricerca web esatta per `OrchAtlas` non ha restituito risultati. La ricerca GitHub eseguita tramite API con `orchatlas in:name` ha restituito `total_count: 0`. Si tratta di verifiche preliminari, datate e limitate ai risultati visibili; non provano disponibilità di domini, handle, registri di pacchetti o marchi. [Query GitHub ripetibile](https://api.github.com/search/repositories?q=orchatlas%20in%3Aname).

## Posizionamento

Descrizione proposta per GitHub:

> Curated, versioned model teams for Codex and OpenCode. Choose your models, compare orchestration recipes, and track the evidence behind every recommendation.

Tagline proposta:

> Choose your models. Follow a tested playbook.

Il ruolo pubblico del maintainer è riconoscibile: provare combinazioni, spiegare i risultati e mantenere raccomandazioni affidabili. La selezione dei modelli è una funzione; il motivo per tornare sul progetto è una storia verificabile di aggiornamenti utili.

## Cosa preparare per la prima release

- README in inglese con promessa, esempio breve, requisiti, installazione realmente provata e limiti.
- Demo di 60–90 secondi su un task ripetibile per ciascuno dei due host: selezione ricetta, ruoli attivi, patch, verifiche e consumi.
- Una ricetta iniziale provata e almeno un confronto onesto; aggiungere categorie solo quando ci sono risultati.
- Matrice host/modello/provider/versione e stato delle verifiche.
- Guida agli aggiornamenti con pinning, differenze, rollback e deprecazioni.
- Contributi guidati per nuove ricette: contesto, versioni, task, comandi e risultati.
- Licenza del nuovo progetto e attribuzioni pertinenti a ogni parte riutilizzata.
- Release numerata, changelog, risultati CI e artefatti riproducibili.

Topics proposti per la release con entrambe le integrazioni verificate: `agent-orchestration`, `ai-agents`, `codex`, `opencode`, `developer-tools`, `model-routing`, `benchmarks`. Durante la fase di progettazione, il README chiarisce che il supporto è previsto e non ancora disponibile.

## Crescita basata sul progetto

Pubblicare aggiornamenti quando cambiano risultati o compatibilità, con una formula ripetibile: problema, combinazioni testate, esito, tradeoff e modifica alla raccomandazione. Una pagina storica delle ricette permette alla community di capire il percorso del progetto.

Favorire contributi riproducibili: report di incompatibilità con versioni, task pubblici e nuove ricette con evidenza. Evitare classifiche assolute, percentuali di risparmio estrapolate o numeri di stelle promessi. Documentazione accessibile e prove concrete sono una strategia ragionevole, non una garanzia di diffusione.

## Stato della pubblicazione

La cartella locale contiene analisi, proposta e un primo MVP funzionante di configurazione/installazione per entrambi gli host. Nessun repository remoto o pacchetto OrchAtlas è stato ancora pubblicato. Il nome dell'account GitHub di destinazione e i dettagli della release saranno risolti nel lavoro di pubblicazione.
