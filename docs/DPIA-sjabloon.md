# DPIA Sjabloon — AI-in-a-Box Gebruik

**Organisatie:** `[NAAM]`  
**Verwerkingsverantwoordelijke:** `[NAAM + FUNCTIE]`  
**FG (Functionaris Gegevensbescherming):** `[NAAM]`  
**Datum:** `[DATUM]`  
**Versie:** 1.0

> Dit sjabloon dekt de DPIA voor het **gebruik** van de AI-in-a-Box infrastructuur.
> Vul de gemarkeerde secties in voor jouw specifieke use case.

---

## Stap 1: Beschrijving van de verwerking

### 1.1 Doel van de AI-toepassing
`[BESCHRIJF: wat gaat de organisatie doen met de AI-stack? Bijv. "interne documenten doorzoeken met RAG", "beleidsstukken samenvatten", "conceptbrieven genereren"]`

### 1.2 Technische opzet
- **Inference:** Ollama draait lokaal op dedicated server — geen data naar externe cloud
- **Embeddings:** nomic-embed-text via lokale Ollama
- **Vector DB:** Qdrant op lokale server
- **Interface:** Open WebUI (lokaal netwerk)
- **Budget control:** LiteLLM proxy met €X/dag cap

### 1.3 Gegevensverwerkingen
| Type data | Bron | Opslaglocatie | Bewaartermijn |
|-----------|------|---------------|---------------|
| Documenten (RAG) | `[NETWERKSHARE, HANDMATIGE UPLOAD, ETC.]` | Qdrant vector DB + lokale chunk storage | `[X MAANDEN/JAREN]` |
| Gebruikersaccounts | Handmatig door admin | Open WebUI database | Tot verwijdering account |
| Chat geschiedenis | Gebruikersinteractie | Open WebUI database | `[X DAGEN/MAANDEN]` |
| `[VOEG VERWERKINGEN TOE]` | | | |

---

## Stap 2: Noodzaak & proportionaliteit

### 2.1 Is de verwerking noodzakelijk?
`[BESCHRIJF: waarom is AI nodig voor dit doel? Zijn er minder ingrijpende alternatieven?]`

### 2.2 Is de verwerking proportioneel?
- ✅ Data blijft on-premise — geen cloud-verwerking
- ✅ Geen Amerikaanse cloud providers (geen FISA 702/CLOUD Act risico)
- ✅ Embedding model draait lokaal — ruwe tekst verlaat server niet
- ⚠️ `[BENOEM EVENTUELE UITZONDERINGEN]`

---

## Stap 3: Risico's voor betrokkenen

### 3.1 Risicomatrix

| Risico | Kans | Impact | Mitigatie |
|--------|------|--------|-----------|
| Ongeautoriseerde toegang tot documenten | Laag | Hoog | UFW: alleen LAN. WebUI auth. Geen internet endpoint. |
| Data lekt via embedding API | Zeer laag | Hoog | Lokaal model (nomic-embed-text). Geen externe API call. |
| Model hallucinaties in antwoorden | Middel | Middel | Retrieval-augmented generation (RAG) verankert aan brondocumenten. Gebruikerswaarschuwing. |
| `[VOEG ORGANISATIE-SPECIFIEKE RISICO'S TOE]` | | | |

### 3.2 Bijzondere persoonsgegevens
`[CHECK: bevatten de documenten bijzondere persoonsgegevens (Art. 9 AVG), strafrechtelijke gegevens (Art. 10 AVG), of BSN-nummers? Zo ja: extra DPIA diepgang nodig.]`

---

## Stap 4: Maatregelen

### 4.1 Technische maatregelen
- [x] UFW firewall: alleen LAN-toegang
- [x] Open WebUI: email/wachtwoord authenticatie
- [x] Docker container isolatie
- [x] Log rotatie (10MB×3) — geen onbeperkte geschiedenis
- [ ] `[VOEG TOE: encryptie van rustende data?]`
- [ ] `[VOEG TOE: netwerksegmentatie?]`

### 4.2 Organisatorische maatregelen
- [ ] Gebruikers instructie: "AI is hulpmiddel, geen beslisser"
- [ ] Periodieke audit van chat logs
- [ ] Procedure voor verwijderen van verouderde documenten uit Qdrant
- [ ] `[VOEG TOE: autorisatieprocedure voor nieuwe gebruikers?]`

---

## Stap 5: Conclusie & ondertekening

### Residueel risico na mitigatie:
`[LAAG / MIDDEL / HOOG]`

### Advies FG:
`[POSITIEF / POSITIEF ONDER VOORWAARDEN / NEGATIEF]`

### Ondertekening

| Rol | Naam | Datum | Handtekening |
|-----|------|-------|--------------|
| Verwerkingsverantwoordelijke | | | |
| Functionaris Gegevensbescherming | | | |
| CISO | | | |

---

## Stap 6: Periodieke herbeoordeling

- [ ] Eerste herbeoordeling: `[DATUM + 6 MAANDEN]`
- [ ] Jaarlijkse herbeoordeling: `[DATUM + 1 JAAR]`
- [ ] Herbeoordeling bij significante wijziging in gebruik of techniek
