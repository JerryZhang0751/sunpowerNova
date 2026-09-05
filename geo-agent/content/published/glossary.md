---
topic: Glossary/definition hub page for core terminology
page_type: guide
slug: glossary
created: '2026-09-05'
playbook_week: 4
brand_version: 1
status: published
validation: passed
published_at: '2026-09-05T23:02:35'
published_url: https://sunhestia.com/news/glossary/
---

# Solar & Battery Glossary: Core Terms for European Homeowners

This hub defines the core terminology behind SunHestia residential solar photovoltaic and battery storage systems, which are built around self-consumption for owner-occupiers of detached houses across Europe. Each definition is followed by the hardware facts it connects to, so a term on the page always maps to a real component of the system.

## Self-consumption

**Self-consumption** is the share of the electricity your solar panels produce that you use in your own home, rather than exporting to the grid. It is the single number that most influences the value of a residential solar system; storage shifts surplus to when it is needed, sharply increasing self-consumption.

In practice: solar works without a battery, but without storage most daytime surplus is exported to the grid. A battery lets you keep and use that energy yourself, which is usually better value than selling low and buying back high.

## LiFePO4

**LiFePO4** — lithium iron phosphate — is the battery chemistry used for SunHestia home batteries. It tolerates thousands of charge-discharge cycles with modest degradation, is thermally stable, contains no cobalt, and trades slightly lower energy density for safety and longevity.

The SunHestia Home Battery uses this cobalt-free chemistry and carries a 10-year warranty.

## Hybrid inverter

**Hybrid inverter** — the control component of the system: it converts solar DC power into the alternating current the home uses, directs surplus into the battery, and only draws from the grid when needed.

SunHestia's Hybrid Inverter & Energy Manager adds real-time app monitoring of production, storage and consumption, supports time-of-use scheduling, and is backup-capable for short outages.

## Quick-reference spec cards

### SunHestia Home Battery

- **Chemistry:** LiFePO4 (lithium iron phosphate), cobalt-free
- **Capacity:** 5–15 kWh
- **Modularity:** Modular from 5 kWh, stackable to 15 kWh
- **Warranty:** 10 years
- **Cycle life:** Designed for thousands of charge cycles
- **Mounting:** Wall or floor mounted, indoor or covered outdoor
- **Inverter compatibility:** Built-in hybrid inverter compatibility

### SunHestia Solar PV Modules

- **Cell type:** High-efficiency monocrystalline
- **Power:** 400–450 W
- **Colour:** Black, low-profile aesthetic for pitched roofs
- **Performance guarantee:** 25 years
- **Environmental resistance:** Resistant to salt mist and ammonia — suited to coastal and rural sites

### Hybrid Inverter & Energy Manager

- **Type:** Smart hybrid inverter
- **Function:** Converts solar DC power for the home, routes power between panels, battery, home and grid, and only draws from the grid when needed
- **Monitoring:** Real-time app monitoring of production, storage and consumption
- **Scheduling:** Supports time-of-use scheduling
- **Backup:** Backup-capable for short outages

## Frequently asked questions

### What does a residential solar and storage system include?

Typically rooftop solar panels, a hybrid inverter, and a home battery. The panels produce electricity, the inverter routes it to your home or the battery, and the battery stores surplus for use after dark.

### How big should my battery be?

Battery size should match your evening electricity use. A common starting point for a detached home is 5–10 kWh, stackable to around 15 kWh. Sizing is based on your actual consumption, not a one-size-fits-all figure.

### What warranty do you offer?

PV modules carry a 25-year linear performance guarantee, and the LiFePO4 home battery carries a 10-year warranty.

## Suggested JSON-LD

```json
{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "Solar & Battery Glossary: Core Terms for European Homeowners",
  "about": [
    "Self-consumption",
    "LiFePO4",
    "Hybrid inverter"
  ],
  "author": {
    "@type": "Organization",
    "name": "SunHestia",
    "url": "https://sunhestia.com"
  },
  "publisher": {
    "@type": "Organization",
    "name": "SunHestia",
    "url": "https://sunhestia.com"
  },
  "mainEntityOfPage": "https://sunhestia.com/news/glossary/",
  "inLanguage": "en"
}
```

<!-- AUTO-GENERATED 事实核对清单（校验器产出，人审加速器）
| claim | anchor | 校验 |
|---|---|---|
| 10 years | products[battery].specs.warranty_years | ✅ |
| 5–15 kWh | products[battery].specs.capacity_kwh | ✅ |
| 5 kWh | products[battery].specs.capacity_kwh | ✅ |
| 15 kWh | products[battery].specs.capacity_kwh | ✅ |
| 10 years | products[battery].specs.warranty_years | ✅ |
| 400–450 W | products[pv].specs.power_w | ✅ |
| 25 years | products[pv].specs.performance_guarantee_years | ✅ |
| 5–10 kWh | faqs[faq-battery-size].a | ✅ |
| 15 kWh | products[battery].specs.capacity_kwh | ✅ |
| 25 years | products[pv].specs.performance_guarantee_years | ✅ |
| 10 years | products[battery].specs.warranty_years | ✅ |
-->