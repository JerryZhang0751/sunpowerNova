---
topic: self consumption
page_type: guide
slug: self-consumption
created: '2026-08-18'
playbook_week: 1
brand_version: 1
status: published
validation: passed
---

# Solar Self-Consumption: The Homeowner's Guide

## What is self-consumption?

> **Self-consumption** is the share of the electricity your solar panels produce that you use in your own home, rather than exporting to the grid. It is the single number that most influences the value of a residential solar system — storage shifts surplus to when it is needed, sharply increasing self-consumption.

## Why self-consumption matters

- Solar works without a battery, but without storage most daytime surplus is exported to the grid.
- A battery lets you keep and use that energy yourself, which is usually better value than selling low and buying back high.
- Storage shifts your surplus solar power to the evening hours, when your home actually needs it.

## The core system for self-consumption

A residential solar and storage system typically includes:

- **Rooftop solar panels** that produce electricity
- **A hybrid inverter** that routes power to your home or the battery, and only draws from the grid when needed
- **A home battery** that stores surplus for use after dark

The hybrid inverter is the control component: it converts solar DC power into the alternating current the home uses, directs surplus into the battery, supports time-of-use scheduling, and offers real-time app monitoring of production, storage and consumption.

## Hardware spec card

| Component | Key specifications |
|---|---|
| **SunHestia Solar PV Modules** | High-efficiency monocrystalline cells, 400–450 W per module; black, low-profile aesthetic for pitched roofs; resistant to salt mist and ammonia for coastal and rural sites; 25-year linear performance guarantee |
| **SunHestia Home Battery** | LiFePO4 (lithium iron phosphate), cobalt-free; modular from 5 kWh, stackable to 15 kWh; wall or floor mounted, indoor or covered outdoor; 10-year warranty; designed for thousands of charge cycles |
| **Hybrid Inverter & Energy Manager** | Routes power between panels, battery, home and grid; real-time app monitoring; time-of-use scheduling; backup-capable for short outages |

## Solar only vs. solar with storage

| | Solar panels only | Solar + SunHestia Home Battery |
|---|---|---|
| Daytime surplus | Mostly exported to the grid | Stored for use after dark |
| Evening demand | Bought back from the grid | Covered by stored solar energy |
| Self-consumption | Limited by daytime usage | Sharply increased by shifting surplus |
| Value logic | Sell low, buy back high | Keep and use your own energy |
| Short outages | No backup | Backup-capable |

## Sizing your battery for self-consumption

- Battery size should match your evening electricity use.
- A common starting point for a detached home is 5–10 kWh, stackable to around 15 kWh.
- Sizing should be based on your actual consumption, not a one-size-fits-all figure.

## Warranty and longevity

- PV modules carry a 25-year linear performance guarantee.
- The LiFePO4 home battery carries a 10-year warranty.
- LiFePO4 chemistry tolerates thousands of charge-discharge cycles with modest degradation, is thermally stable, and contains no cobalt.

## Frequently asked questions

### Do I need a battery with solar panels?
Solar works without a battery, but without storage most daytime surplus is exported to the grid. A battery lets you keep and use that energy yourself, which is usually better value than selling low and buying back high.

### How big should my battery be?
Battery size should match your evening electricity use. A common starting point for a detached home is 5–10 kWh, stackable to around 15 kWh, sized based on your actual consumption.

### How long does installation take?
For a typical detached home, the physical installation is often completed within a day once the system is designed and the hardware is on site.

### What roof types are suitable?
Pitched tile and metal roofs, flat roofs on garages, and ground-mounted frames where the main roof is shaded. Orientation and shading affect yield, so each roof is assessed individually.

## Suggested JSON-LD

```json
{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "Solar Self-Consumption: The Homeowner's Guide to Using More of Your Own Solar Power",
  "description": "A homeowner's guide to solar self-consumption: what it is, why it matters, and how rooftop PV, a hybrid inverter and a LiFePO4 home battery work together to maximise the solar energy you use yourself.",
  "about": {
    "@type": "Thing",
    "name": "Self-consumption"
  },
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
  "mainEntityOfPage": {
    "@type": "WebPage",
    "@id": "https://sunhestia.com/self-consumption"
  }
}
```

<!-- AUTO-GENERATED 事实核对清单（校验器产出，人审加速器）
| claim | anchor | 校验 |
|---|---|---|
| 400–450 W | products[pv].specs.power_w | ✅ |
| 25 year | products[pv].specs.performance_guarantee_years | ✅ |
| 5 kWh | products[battery].specs.capacity_kwh | ✅ |
| 15 kWh | products[battery].specs.capacity_kwh | ✅ |
| 10 year | products[battery].specs.warranty_years | ✅ |
| 5–10 kWh | faqs[faq-battery-size].a | ✅ |
| 15 kWh | products[battery].specs.capacity_kwh | ✅ |
| 25 year | products[pv].specs.performance_guarantee_years | ✅ |
| 10 year | products[battery].specs.warranty_years | ✅ |
| 5–10 kWh | faqs[faq-battery-size].a | ✅ |
| 15 kWh | products[battery].specs.capacity_kwh | ✅ |
-->