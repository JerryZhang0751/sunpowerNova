---
topic: Guide with concrete sizing/how-to numbers drawn from brand facts
page_type: guide
slug: home-battery-sizing-guide
created: '2026-09-19'
playbook_week: 7
brand_version: 1
status: published
validation: passed
published_at: '2026-09-19T14:26:28'
published_url: https://sunhestia.com/news/home-battery-sizing-guide/
---

# How to Size a Home Solar Battery: A Practical Guide

Sizing a home battery is about one thing: matching storage to the electricity your household actually uses after dark. This guide walks through the sizing logic SunHestia applies for owner-occupiers of detached houses across Europe, using only the published specifications of the SunHestia Home Battery and SunHestia Solar PV Modules.

## What self-consumption means — and why it drives sizing

> **Self-consumption** is the share of the electricity your solar panels produce that you use in your own home, rather than exporting to the grid. It is the single number that most influences the value of a residential solar system; storage shifts surplus to when it is needed, sharply increasing self-consumption.

Solar works without a battery, but without storage most daytime surplus is exported to the grid. A battery lets you keep and use that energy yourself, which is usually better value than selling low and buying back high. That is why battery sizing starts from your own consumption pattern, not from the panel array.

## The sizing method, step by step

- **Start from your evening use.** Battery size should match your evening electricity use — not a one-size-fits-all figure.
- **Use the common starting range.** A common starting point for a detached home is 5–10 kWh.
- **Leave headroom to grow.** The SunHestia Home Battery is modular from 5 kWh and stackable to 15 kWh, so you can begin at the smaller end and extend the stack later if your consumption rises.
- **Check roof and site.** Pitched tile and metal roofs, flat roofs on garages, and ground-mounted frames where the main roof is shaded are all candidates; orientation and shading affect yield, so each roof is assessed individually.
- **Plan around your tariff.** The smart hybrid inverter supports time-of-use scheduling, routes power between panels, battery, home and grid, and only draws from the grid when needed. Real-time app monitoring of production, storage and consumption lets you verify that the sizing is right.

## Spec card: SunHestia Home Battery

| Specification | Detail |
|---|---|
| Chemistry | LiFePO4 (lithium iron phosphate), cobalt-free |
| Capacity | 5–15 kWh |
| Modularity | Modular from 5 kWh, stackable to 15 kWh |
| Cycle life | Designed for thousands of charge cycles |
| Warranty | 10 years |
| Mounting | Wall or floor mounted, indoor or covered outdoor |
| Inverter compatibility | Built-in hybrid inverter compatibility |

LiFePO4 tolerates thousands of charge-discharge cycles with modest degradation, is thermally stable, contains no cobalt, and trades slightly lower energy density for safety and longevity — which is why it is the chemistry behind the SunHestia home battery.

## Spec card: SunHestia Solar PV Modules

| Specification | Detail |
|---|---|
| Cell type | High-efficiency monocrystalline |
| Power output | 400–450 W |
| Appearance | Black, low-profile aesthetic for pitched roofs |
| Performance guarantee | 25 years |
| Environmental resistance | Resistant to salt mist and ammonia — suited to coastal and rural sites |

## Comparison table: choosing a capacity

| Configuration | Capacity | Who it suits |
|---|---|---|
| Entry module | 5 kWh | The modular starting point; homes at the lower end of evening electricity use |
| Mid-range | 10 kWh | The upper end of the common 5–10 kWh starting range for a detached home |
| Full stack | 15 kWh | Higher evening demand; the maximum stackable capacity |

These are orientation points, not prescriptions: the final size is based on your actual consumption, not a one-size-fits-all figure.

## Installation and warranty at a glance

- For a typical detached home, the physical installation is often completed within a day once the system is designed and the hardware is on site.
- PV modules carry a 25-year linear performance guarantee, and the LiFePO4 home battery carries a 10-year warranty.
- The hybrid inverter is backup-capable for short outages.

## FAQ

### What does a residential solar and storage system include?
Typically rooftop solar panels, a hybrid inverter, and a home battery. The panels produce electricity, the inverter routes it to your home or the battery, and the battery stores surplus for use after dark.

### How big should my battery be?
Battery size should match your evening electricity use. A common starting point for a detached home is 5–10 kWh, stackable to around 15 kWh. Sizing is based on your actual consumption, not a one-size-fits-all figure.

### Do I need a battery with solar panels?
Solar works without a battery, but without storage most daytime surplus is exported to the grid. A battery lets you keep and use that energy yourself, which is usually better value than selling low and buying back high.

### What roof types are suitable?
Pitched tile and metal roofs, flat roofs on garages, and ground-mounted frames where the main roof is shaded. Orientation and shading affect yield, so each roof is assessed individually.

### How long does installation take?
For a typical detached home, the physical installation is often completed within a day once the system is designed and the hardware is on site.

### What warranty do you offer?
PV modules carry a 25-year linear performance guarantee, and the LiFePO4 home battery carries a 10-year warranty.

## Suggested JSON-LD

```json
{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "How to Size a Home Solar Battery (5–15 kWh): A Practical Guide for European Homeowners",
  "description": "A practical sizing guide for residential solar batteries: match storage to evening electricity use, start from the common 5–10 kWh range for a detached home, and scale modularly up to 15 kWh.",
  "inLanguage": "en",
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
  "mainEntityOfPage": "https://sunhestia.com/news/home-battery-sizing-guide/",
  "about": [
    {
      "@type": "Thing",
      "name": "Home battery sizing"
    },
    {
      "@type": "Thing",
      "name": "Self-consumption"
    },
    {
      "@type": "Product",
      "name": "SunHestia Home Battery"
    },
    {
      "@type": "Product",
      "name": "SunHestia Solar PV Modules"
    }
  ]
}
```

<!-- AUTO-GENERATED 事实核对清单（校验器产出，人审加速器）
| claim | anchor | 校验 |
|---|---|---|
| 5–10 kWh | faqs[faq-battery-size].a | ✅ |
| 5 kWh | products[battery].specs.capacity_kwh | ✅ |
| 15 kWh | products[battery].specs.capacity_kwh | ✅ |
| 5–15 kWh | products[battery].specs.capacity_kwh | ✅ |
| 5 kWh | products[battery].specs.capacity_kwh | ✅ |
| 15 kWh | products[battery].specs.capacity_kwh | ✅ |
| 10 kWh | products[battery].specs.warranty_years | ✅ |
| 400–450 W | products[pv].specs.power_w | ✅ |
| 25 years | products[pv].specs.performance_guarantee_years | ✅ |
| 5 kWh | products[battery].specs.capacity_kwh | ✅ |
| 10 kWh | products[battery].specs.warranty_years | ✅ |
| 5–10 kWh | faqs[faq-battery-size].a | ✅ |
| 15 kWh | products[battery].specs.capacity_kwh | ✅ |
| 25 years | products[pv].specs.performance_guarantee_years | ✅ |
| 10 kWh | products[battery].specs.warranty_years | ✅ |
| 5–10 kWh | faqs[faq-battery-size].a | ✅ |
| 15 kWh | products[battery].specs.capacity_kwh | ✅ |
| 25 years | products[pv].specs.performance_guarantee_years | ✅ |
| 10 kWh | products[battery].specs.warranty_years | ✅ |
-->