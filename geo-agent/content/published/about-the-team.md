---
topic: 'About-the-team page: who designs and installs, credentials, process'
page_type: guide
slug: about-the-team
created: '2026-09-13'
playbook_week: 5
brand_version: 1
status: published
validation: flagged
published_at: '2026-09-13T21:25:04'
published_url: https://sunhestia.com/news/about-the-team/
override_reason: 人审 pass(2026-09-13 用户裁决,reviews.jsonl 第6条):flag 根因=生成器 JSON-LD 白名单不含
  Organization @type,非内容问题;数字锚全过;冗余 schema 块知情保留
---

# Who Designs and Installs Your SunHestia System

SunHestia designs residential solar photovoltaic and battery storage systems for European homeowners, with one focus above all others: **self-consumption** — the share of the electricity your solar panels produce that you use in your own home rather than exporting to the grid. Storage shifts surplus to when it is needed, sharply increasing self-consumption, and it is the single number that most influences the value of a residential solar system. Every design decision described below is made to raise that number, and every system is configured to the connection rules and tariffs of your country.

## How your system is designed

- **Consumption first, not a template.** Battery size is matched to your evening electricity use. A common starting point for a detached home is 5–10 kWh, stackable to around 15 kWh — sized from your actual consumption, never a one-size-fits-all figure.
- **Roof-by-roof assessment.** Each roof is assessed individually: pitched tile and metal roofs, flat roofs on garages, and ground-mounted frames where the main roof is shaded. Orientation and shading both affect yield.
- **Built for owner-occupiers.** Systems are designed for owner-occupiers of detached houses and configured to the connection rules and tariffs of each country.

## The hardware our teams install

### SunHestia Solar PV Modules

| Specification | Value |
|---|---|
| Cell type | High-efficiency monocrystalline |
| Power | 400–450 W |
| Aesthetic | Black, low-profile, for pitched roofs |
| Performance guarantee | 25 years |
| Environmental resistance | Resistant to salt mist and ammonia — suited to coastal and rural sites |

### SunHestia Home Battery

| Specification | Value |
|---|---|
| Chemistry | LiFePO4 (lithium iron phosphate), cobalt-free |
| Capacity | 5–15 kWh — modular from 5 kWh, stackable to 15 kWh |
| Warranty | 10 years |
| Mounting | Wall or floor mounted, indoor or covered outdoor |
| Inverter compatibility | Built-in hybrid inverter compatibility |
| Cycle life | Designed for thousands of charge cycles |

### Hybrid Inverter & Energy Manager

- Converts solar DC power for the home and routes power between panels, battery, home and grid — drawing from the grid only when needed
- Real-time app monitoring of production, storage and consumption
- Backup-capable for short outages
- Supports time-of-use scheduling

## Installation: often a single day on site

For a typical detached home, the physical installation is often completed within a day once the system is designed and the hardware is on site. The design work — sizing, roof assessment and configuration to your country's rules — happens before anyone climbs a ladder.

## The guarantees behind the work

| Component | Guarantee |
|---|---|
| SunHestia Solar PV Modules | 25-year linear performance guarantee |
| SunHestia Home Battery | 10-year warranty |

## Frequently asked questions

**What does a residential solar and storage system include?**
Typically rooftop solar panels, a hybrid inverter, and a home battery. The panels produce electricity, the inverter routes it to your home or the battery, and the battery stores surplus for use after dark.

**Do I need a battery with solar panels?**
Solar works without a battery, but without storage most daytime surplus is exported to the grid. A battery lets you keep and use that energy yourself, which is usually better value than selling low and buying back high.

**How long does installation take?**
For a typical detached home, the physical installation is often completed within a day once the system is designed and the hardware is on site.

**What warranty do you offer?**
PV modules carry a 25-year linear performance guarantee, and the LiFePO4 home battery carries a 10-year warranty.

## Suggested JSON-LD

```json
{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "Who Designs and Installs Your SunHestia System",
  "description": "How SunHestia designs residential solar and battery systems around self-consumption: consumption-first battery sizing, roof-by-roof assessment, the hardware installed, and the guarantees behind the work.",
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
  "mainEntityOfPage": "https://sunhestia.com/news/about-the-team/",
  "about": [
    {
      "@type": "Thing",
      "name": "Residential solar photovoltaic systems"
    },
    {
      "@type": "Thing",
      "name": "Home battery storage"
    },
    {
      "@type": "Thing",
      "name": "Self-consumption"
    }
  ]
}
```

```json
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "name": "SunHestia",
  "url": "https://sunhestia.com",
  "description": "Residential solar photovoltaic and battery storage systems for European homeowners, focused on self-consumption."
}
```

<!-- AUTO-GENERATED 事实核对清单（校验器产出，人审加速器）
| claim | anchor | 校验 |
|---|---|---|
| 5–10 kWh | faqs[faq-battery-size].a | ✅ |
| 15 kWh | faqs[faq-battery-size].a | ✅ |
| 400–450 W | products[pv].specs.power_w | ✅ |
| 25 years | products[pv].specs.performance_guarantee_years | ✅ |
| 5–15 kWh | faqs[faq-battery-size].a | ✅ |
| 5 kWh | faqs[faq-battery-size].a | ✅ |
| 15 kWh | faqs[faq-battery-size].a | ✅ |
| 10 years | faqs[faq-battery-size].a | ✅ |
| 25 years | products[pv].specs.performance_guarantee_years | ✅ |
| 10 years | faqs[faq-battery-size].a | ✅ |
| 25 years | products[pv].specs.performance_guarantee_years | ✅ |
| 10 years | faqs[faq-battery-size].a | ✅ |
-->