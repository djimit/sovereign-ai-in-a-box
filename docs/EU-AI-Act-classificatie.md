# EU AI Act — Risicoclassificatie Sovereign AI-in-a-Box

**Versie:** 0.1.0  
**Datum:** 2026-05-15  
**Referentie:** EU AI Act (Verordening (EU) 2024/1689)

## Classificatie: **Geen/Laag Risico**

De Sovereign AI-in-a-Box is een **infrastructuurproduct** — het is een platform waarop organisaties AI-modellen kunnen draaien. Het product zelf is **geen AI-systeem** in de zin van de AI Act.

### Redenatie

| Criterium | Analyse |
|-----------|---------|
| **Is het een AI-systeem?** | Nee — het is infrastructuur (inference engine + database + UI). |
| **Maakt het besluiten?** | Nee — de stack maakt geen autonome besluiten die natuurlijke personen raken. |
| **Valt het onder Annex III?** | Nee — de stack zelf is geen hoog-risico toepassing. |
| **GPAI verplichtingen?** | Nee — Ollama/Open WebUI vallen niet onder GPAI (geen model met systemisch risico). |

### Implicaties voor aanbieder (DjimIT B.V.)

Als **aanbieder** van AI-infrastructuur (geen AI-systeem):
- Geen conformiteitsbeoordeling nodig
- Geen CE-markering nodig
- Geen EU database registratie
- Wel: transparantie over capabilities en beperkingen (dit document)

### Implicaties voor gebruiksverantwoordelijke (klant)

De **klant** is verantwoordelijk voor de AI Act classificatie van wat zij **met** de stack doen:

- **Als de klant interne kennismanagement doet** (documenten doorzoeken, samenvatten) → **Laag risico**
- **Als de klant de stack gebruikt voor besluitvorming over natuurlijke personen** (subsidies, handhaving, HR) → **Mogelijk hoog risico** — klant moet zelf IAMA/FRIA uitvoeren
- **Als de klant een chatbot voor burgers bouwt** → **Beperkt risico** (transparantieverplichting: "u praat met AI")

## Aanbevolen klant-stappen vóór ingebruikname

1. **Doelbepaling**: wat gaat de organisatie met de stack doen?
2. **IAMA uitvoeren** als er impact op burgers is (Impact Assessment Mensenrechten en Algoritmes)
3. **FRIA uitvoeren** bij mogelijke grondrechtelijke impact (Fundamental Rights Impact Assessment)
4. **Transparantie**: medewerkers informeren over AI-gebruik
5. **AI-register**: indien van toepassing registreren in het nationale algoritmeregister

## DjimIT ondersteuning

DjimIT B.V. biedt als aanvullend dienstenpakket:
- AI Act compliance scan voor de specifieke use case
- IAMA begeleiding
- DPIA met AI-component (via `gdpr-dpia` plugin)

Contact: consulting@djimit.nl
