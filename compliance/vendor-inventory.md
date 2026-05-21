---
title: Vendor & Subprocessor Inventory
tsc: CC9.1, CC9.2
owner: Kevin Armstrong
review-cadence: quarterly
last-reviewed: 2026-05-21
---

# Vendor & Subprocessor Inventory — website-auditor.io

## Active Vendors

| Vendor | Service | Data Access | SOC 2 / ISO | Data Residency | DPA |
|--------|---------|-------------|-------------|----------------|-----|
| GitHub | Source control, CI/CD | Source code | SOC 2 Type II | US | Yes |
| Google Cloud | Cloud Run hosting | Application runtime, logs | SOC 2 Type II, ISO 27001 | US (us-central1) | Yes |
| Cloudflare | CDN, DDoS protection | Request logs | SOC 2 Type II, ISO 27001 | Global edge | Yes |
| Supabase | Audit data storage | Website audit results | SOC 2 Type II | US (AWS us-east-1) | Yes |
| Stripe | Subscription billing | Customer email, payment metadata | SOC 2 Type II, PCI DSS L1 | US | Yes |
| Google PSI / Places | Performance + business detection | Public URLs only | Covered by Google Cloud DPA | US | Yes |
| Perplexity | AI-powered queries | User search queries (gated) | SOC 2 in progress | US | Yes |
| Trello (Atlassian) | Bug tracking | Bug report text, screenshots | SOC 2 Type II, ISO 27001 | US | Yes |
| Mailgun | Transactional email alerts | Email addresses (admin only) | SOC 2 Type II | US | Yes |

## Assessment Criteria

Each vendor evaluated on: data access level, SOC 2/ISO certification, data residency, contractual protections (DPA/BAA), and breach notification SLA.

## Review Process

Reviewed quarterly. New vendors require security assessment before onboarding. Certification loss or breach triggers immediate review.

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-05-21 | Initial vendor inventory | Kevin Armstrong |
