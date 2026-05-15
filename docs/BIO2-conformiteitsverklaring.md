# BIO2 Conformiteitsverklaring — Sovereign AI-in-a-Box v0.1

Voor organisatie: `[NAAM INVULLEN]`  
Datum beoordeling: `[DATUM INVULLEN]`  
Beoordeeld door: `[NAAM + ROL INVULLEN]`  
BIO2-versie: 2.0 (2024)  
Classificatie: `[BBN1/BBN2/BBN3]`

## Scope

Deze verklaring dekt de **Sovereign AI-in-a-Box** infrastructuur stack:
- Ollama (LLM inference)
- Qdrant (vector database)
- Open WebUI (gebruikersinterface)
- LiteLLM (proxy + budget control)
- Onderliggende Ubuntu 24.04 server

Niet in scope: organisatie-specifieke data, prompt logging, gebruikersdocumenten, integraties met externe systemen.

## BIO2 Hoofdstukken — Compliance Matrix

| BIO2 Hoofdstuk | Maatregel | Status | Toelichting |
|----------------|-----------|--------|-------------|
| **B.01 — Assetmanagement** | Inventarisatie hardware/software | ✅ | Ansible deployeert vaste, getagde Docker images. `docker ps` + playbook = actuele inventaris. |
| **B.02 — Classificatie** | BBN niveau bepaling | ✅ | BBN1/BBN2 default. BBN3 mogelijk met extra hardening (vraag aan). |
| **B.03 — Toegangsbeveiliging** | Authenticatie & autorisatie | ✅ | Open WebUI: email/wachtwoord + admin goedkeuring. UFW: alleen LAN IPs. SSH: sleutels + admin IPs. |
| **B.04 — Fysieke beveiliging** | Serverruimte | ⚠️ | Klant-verantwoordelijkheid. Stack draait on-premise. |
| **B.05 — Logging & monitoring** | Audit logs + health checks | ✅ | Docker JSON logs (rotatie: 10MB×3). node_exporter metrics. `health-check.sh` voor dagelijkse scan. |
| **B.06 — Capaciteitsmanagement** | Resource planning | ✅ | Docker resource limits per container. `df -h` + node_exporter voor disk monitoring. |
| **B.07 — Malware protectie** | Anti-malware | ✅ | Read-only LiteLLM config. Docker image digests (getagd). Geen internet-facing endpoints. |
| **B.08 — Backup & restore** | Data integriteit | ✅ | Dagelijkse Restic backup naar NAS/S3 (encrypted, deduplicated). Qdrant snapshots. 30 dagen retentie. |
| **B.09 — Netwerkbeveiliging** | Segmentatie + firewall | ✅ | UFW: deny all incoming behalve LAN + admin IPs. `network_mode: host` voor interne container communicatie. |
| **B.10 — Cryptografie** | Encryptie standaarden | ✅ | Restic: AES-256 encryptie. Docker registry: HTTPS. TLS voor externe API calls (Anthropic/OpenAI). |
| **B.11 — Leveranciers** | Vendor management | ✅ | Open source stack. Geen lock-in. Docker images van Docker Hub/GHCR (verifieerbaar). |
| **B.12 — Incident management** | Incident response | ⚠️ | `health-check.sh` voor detectie. Response procedure = klant-verantwoordelijkheid. |
| **B.13 — Business continuity** | Continuïteitsplan | ✅ | Fallback: cloud model → lokaal model. Restic restore <10 min. Docker auto-restart (`unless-stopped`). |
| **B.14 — Change management** | Wijzigingsbeheer | ✅ | Ansible playbook = version-controlled infrastructuur. `ansible-playbook --check` voor dry-runs. |
| **B.15 — Compliance** | BIO2-naleving | ✅ | Dit document + jaarlijkse herbeoordeling. |

## BIO2-aanvullingen BBN3 (Rechtspraak/Strafrechtketen)

Voor BBN3-classificatie gelden aanvullende eisen. Neem contact op voor de BBN3 hardening guide die toevoegt:
- SELinux/AppArmor mandatory access control
- File integrity monitoring (AIDE)
- SIEM koppeling (Splunk/Sentinel forwarder)
- Two-factor authenticatie op SSH
- Hardware security module (HSM) voor backup keys

## Verklaring

Deze infrastructuur voldoet aan BIO2 baseline niveau **`[BBN NIVEAU]`** onder de voorwaarde dat:
1. De klant fysieke beveiliging van de server verzorgt
2. De klant een incident response procedure heeft
3. Periodieke BIO2-reviews worden uitgevoerd (minimaal jaarlijks)

Ondertekening:  
`[NAAM]` — `[FUNCTIE]` — `[DATUM]`
