# Sovereign AI-in-a-Box

Turnkey, BIO2-compliant, on-premise AI-infrastructuur voor Nederlandse overheidsorganisaties.

## Wat is het?

Een complete AI-stack die in één commando op een Ubuntu 24.04 server wordt geïnstalleerd:

- **Ollama** — lokale LLM inference (geen data naar cloud)
- **Qdrant** — vector database voor organisatie-eigen kennisbank
- **Open WebUI** — gebruiksvriendelijke chatinterface
- **LiteLLM** — proxy met harde budget caps (€X/dag)
- **Prometheus node_exporter** — monitoring
- **UFW firewall** — BIO2-conform (alleen LAN-toegang)
- **Restic backups** — encrypted, dagelijks naar NAS/S3

## Waarom?

Nederlandse overheden willen AI gebruiken maar zitten met:

- **AVG/GDPR**: geen persoonsgegevens naar Amerikaanse clouds
- **BIO2**: verplichte beveiligingsmaatregelen
- **EU AI Act**: compliance met AI-verordening
- **CLOUD Act**: Amerikaanse extraterritoriale toegang
- **Aanbestedingsplicht**: onder €50K drempel blijven

Deze stack lost dat op: **on-premise, open source, compliant, <€25K**.

## Quickstart

```bash
# 1. Installeer Ansible (eenmalig, op je eigen laptop)
brew install ansible  # macOS
# of: apt install ansible  # Linux

# 2. Kopieer en pas configuratie aan
cp inventory.example.yml inventory.yml
nano inventory.yml  # pas IP, modellen, backup target aan

# 3. Deploy
ansible-playbook -i inventory.yml sovereign-ai-in-a-box.yml

# 4. Open in browser
open http://<server-ip>:3000
```

Na ~15 minuten heb je een werkende AI-omgeving.

## Vereisten

- Ubuntu 24.04 server (fysiek of VM)
- Minimaal: 16GB RAM, 4 cores, 100GB disk
- GPU aanbevolen voor productie (NVIDIA RTX 3060+ of A-series)
- Server op intern LAN, geen internet-facing nodig
- Ansible op je beheer-laptop

## Wat krijg je?

| Component | Technologie | Licentie |
|-----------|-------------|----------|
| LLM Inference | Ollama + lokale modellen | MIT |
| Vector Database | Qdrant | Apache 2.0 |
| UI | Open WebUI | MIT |
| API Gateway | LiteLLM | MIT |
| Monitoring | Prometheus node_exporter | Apache 2.0 |
| Provisioning | Ansible playbook | MIT |
| Documentatie | BIO2 + EU AI Act + DPIA | DjimIT B.V. |

## Compliance

Dit product includeert:

- ✅ **BIO2 conformiteitsverklaring** ([docs/BIO2-conformiteitsverklaring.md](docs/BIO2-conformiteitsverklaring.md))
- ✅ **EU AI Act classificatie** ([docs/EU-AI-Act-classificatie.md](docs/EU-AI-Act-classificatie.md))
- ✅ **DPIA sjabloon** ([docs/DPIA-sjabloon.md](docs/DPIA-sjabloon.md))
- ✅ **NORA architectuurbeschrijving** ([docs/architectuur.md](docs/architectuur.md))

## Consulting & ondersteuning

DjimIT B.V. biedt:

- **Installatiebegeleiding**: remote of on-site (€1.500/dag)
- **Custom hardening**: BBN3, ZBO-specifiek, strafrechtketen
- **Training**: AI-geletterdheid voor overheidsmedewerkers
- **Use-case ontwikkeling**: custom RAG pipelines, agent workflows
- **Doorontwikkeling**: opmaat naar multi-node, federated learning

Contact: consulting@djimit.nl | djimit.nl

## Licentie

MIT — de stack is open source. DjimIT B.V. verdient aan consulting, niet aan softwarelicenties.
