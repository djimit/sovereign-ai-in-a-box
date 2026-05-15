# Architectuurbeschrijving — Sovereign AI-in-a-Box

**Datum:** 2026-05-15  
**Versie:** 0.1.0  
**RA:** NORA vijflaagsmodel  
**Doel:** Overheidsorganisaties voorzien van soevereine AI-infrastructuur

---

## 1. NORA Vijflaagsmodel — Inpassing

| NORA Laag | Invulling AI-in-a-Box |
|-----------|----------------------|
| **Politiek-Bestuurlijk** | Strategie: soevereine AI. Voldoet aan NL cloudbeleid (BZK/CIO-Rijk), BIO2, EU AI Act. |
| **Organisatie** | Gebruikers: beleidsmedewerkers, kenniswerkers, analisten. Processen: documentanalyse, kennismanagement, conceptgeneratie. |
| **Informatievoorziening** | Data: organisatie-eigen documenten → embeddings → Qdrant. Lokaal, geen cloud. |
| **Applicaties** | Open WebUI (interface) + LiteLLM (routering) + Qdrant (vector search) + Restic (backup). |
| **Technische Infrastructuur** | Ubuntu 24.04 server. Docker containers. NVIDIA GPU (optioneel). LAN-connected. |

---

## 2. Componentendiagram

```
┌──────────────────────────────────────────────────────┐
│                    LAN (intern)                       │
│                                                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │ Gebruiker │  │ Beheerder │  │ Externe Monitor   │   │
│  │ :3000    │  │ SSH :22  │  │ Prometheus :9090  │   │
│  └────┬─────┘  └────┬─────┘  └────────┬─────────┘   │
│       │             │                 │              │
│  ─────┼─────────────┼─────────────────┼────────────  │
│       │      UFW Firewall             │              │
│  ─────┼─────────────┼─────────────────┼────────────  │
│       │             │                 │              │
│       ▼             ▼                 ▼              │
│  ┌────────────────────────────────────────────────┐  │
│  │              Docker Host (Ubuntu 24.04)         │  │
│  │                                                 │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │  │
│  │  │ Ollama   │  │ Qdrant   │  │ Open WebUI   │  │  │
│  │  │ :11434   │  │ :6333    │  │ :3000        │  │  │
│  │  │ GPU/NPU  │  │ vector   │  │ auth + chat  │  │  │
│  │  └────┬─────┘  └────┬─────┘  └──────┬───────┘  │  │
│  │       │             │               │          │  │
│  │       └─────────────┼───────────────┘          │  │
│  │                     │                          │  │
│  │               ┌─────▼──────┐                   │  │
│  │               │ LiteLLM    │                   │  │
│  │               │ :4000      │                   │  │
│  │               │ router +   │                   │  │
│  │               │ budget cap │                   │  │
│  │               └────────────┘                   │  │
│  │                                                 │  │
│  │  ┌──────────────┐  ┌───────────────────────┐   │  │
│  │  │ node_exporter│  │ Restic (04:00 cron)   │   │  │
│  │  │ :9100       │  │ → NAS / S3            │   │  │
│  │  └──────────────┘  └───────────────────────┘   │  │
│  └────────────────────────────────────────────────┘  │
│                                                       │
│  ┌──────────────────────┐                            │
│  │ NAS / S3 Backup      │                            │
│  │ (optioneel, extern)  │                            │
│  └──────────────────────┘                            │
└──────────────────────────────────────────────────────┘
```

---

## 3. Datastromen

| Stroom | Pad | Protocol | Encryptie |
|--------|-----|----------|-----------|
| Gebruiker → WebUI | LAN HTTPS | HTTPS | TLS (optioneel, via reverse proxy) |
| WebUI → Ollama | localhost | HTTP | N.v.t. (localhost) |
| WebUI → LiteLLM | localhost | HTTP | N.v.t. (localhost) |
| LiteLLM → Ollama | localhost | HTTP | N.v.t. (localhost) |
| LiteLLM → Cloud LLM | Internet | HTTPS | TLS |
| Qdrant → Ollama (embeddings) | localhost | HTTP | N.v.t. (localhost) |
| Backup → NAS | LAN | Restic (SSH/HTTPS) | AES-256 |
| Prometheus → node_exporter | LAN | HTTP | N.v.t. (LAN-only) |

**Belangrijk:** Embeddings worden lokaal gegenereerd. Er worden GEEN ruwe documenten naar externe APIs gestuurd (tenzij een gebruiker expliciet een cloud model selecteert).

---

## 4. Beveiligingsarchitectuur

| Laag | Maatregel |
|------|-----------|
| **Netwerk** | UFW: deny all incoming, alleen LAN + admin IPs. Geen internet-facing poorten. |
| **Applicatie** | Open WebUI: email/wachtwoord auth, admin-goedgekeurde accounts. |
| **Container** | Docker: memory limits per container. Read-only config volumes. Json-file logging met rotatie. |
| **Data** | On-premise. Embeddings lokaal. Restic AES-256 encrypted backups. |
| **Infra** | Ansible: idempotente deployment. Docker: tagged images. Ubuntu: security auto-updates. |

---

## 5. Schaalbaarheid

| Aspect | v0.1 (enkele server) | v0.2+ (cluster) |
|--------|---------------------|-------------------|
| **Ollama** | 1 instance, GPU | Ollama cluster met load balancer |
| **Qdrant** | 1 node, single disk | Qdrant cluster met replicatie |
| **WebUI** | 1 instance | Meerdere instances achter load balancer |
| **Backup** | Restic naar NAS | Restic met off-site replicate |

---

## 6. Open Standaarden

| Standaard | Toepassing |
|-----------|------------|
| Docker Compose v2 | Container orchestratie |
| OpenAPI (Ollama compatible) | LLM inference API |
| gRPC | Qdrant query protocol |
| Prometheus exposition format | Metrics |
| Restic REST/SFTP | Backup storage |

---

## 7. Architectuurprincipes (NORA-derived)

1. **Data soevereiniteit**: data verlaat de organisatie niet zonder expliciete actie
2. **Open source by default**: alle kerncomponenten zijn open source
3. **Geen vendor lock-in**: elke component is vervangbaar (Ollama ↔ vLLM, Qdrant ↔ pgvector)
4. **Infrastructure as Code**: Ansible playbook is de single source of truth
5. **Secure by design**: UFW + auth + encryptie vanaf dag 1
6. **Compliance by default**: BIO2 + EU AI Act baseline ingebouwd
