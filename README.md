# Aegis Telematics & Transport (ATT) - Immutable Enterprise Infrastructure

## Project Overview
An enterprise-grade, Zero Trust infrastructure environment simulating a 48-state logistics telemetry backend. This project utilizes an immutable operating system paradigm to completely eliminate configuration drift and enforce strict regulatory compliance (NIST SP 800-53 Rev 5, PCI DSS v4.0).

## Architecture & Technology Stack
* **Operating System:** Fedora CoreOS (Strictly Immutable, Read-Only Root)
* **Provisioning:** Declarative Ignition/Butane Bootstrapping
* **Orchestration:** Native systemd Podman Quadlets
* **Edge Perimeter:** Cloudflare Zero Trust Tunnels (`cloudflared`) & Traefik Ingress
* **Application Tier:** High-performance Rust/Axum asynchronous engine
* **Data Tier:** Isolated PostgreSQL Vault
* **Observability & SIEM:** Wazuh, Prometheus, Grafana, Loki, and Homarr
