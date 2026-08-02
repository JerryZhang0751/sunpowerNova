To size a home solar battery, you mainly need to know **how much energy you want to store**, **how much backup time you want**, and **what loads you need to power**.

## 1. Decide your goal

There are two common reasons to add a battery:

### A. Backup power
You want the battery to keep essential loads running during outages.

### B. Self-consumption / bill savings
You want to store excess daytime solar energy and use it at night.

The sizing method is similar, but backup systems usually focus on **critical loads**, while bill-savings systems focus on **daily energy shifting**.

---

## 2. Find your daily energy use

Look at your electric bill for monthly usage in kWh.

Formula:

```text
Daily energy use = monthly kWh ÷ 30
```

Example:

```text
900 kWh/month ÷ 30 = 30 kWh/day
```

That means your home uses about **30 kWh per day**.

---

## 3. Choose what loads you want backed up

For backup, do not assume you need to power the whole house unless you specifically want that.

Common critical loads include:

- Refrigerator
- Wi-Fi/router
- Lights
- Outlets
- Medical devices
- Well pump
- Garage door
- Sump pump
- Furnace blower
- Small appliances

Large loads that require much bigger batteries include:

- Central air conditioning
- Electric heating
- Electric water heater
- EV charger
- Electric oven
- Pool pump

---

## 4. Estimate critical load energy use

Make a list of devices and how long they run.

Formula:

```text
Energy use = watts × hours ÷ 1,000
```

Example critical-load estimate:

| Load | Power | Hours/day | Energy |
|---|---:|---:|---:|
| Refrigerator | 150 W average | 24 | 3.6 kWh |
| Wi-Fi/router | 20 W | 24 | 0.5 kWh |
| Lights | 200 W | 5 | 1.0 kWh |
| TV/laptop/phone charging | 150 W | 6 | 0.9 kWh |
| Furnace blower | 500 W | 4 | 2.0 kWh |
| Misc outlets | 300 W | 3 | 0.9 kWh |

Total:

```text
3.6 + 0.5 + 1.0 + 0.9 + 2.0 + 0.9 = 8.9 kWh/day
```

So you would need roughly **9 kWh per day** for critical loads.

---

## 5. Decide how many days of backup you want

Multiply your daily energy need by the number of backup days.

```text
Battery energy needed = daily load × backup days
```

Example:

```text
9 kWh/day × 1 day = 9 kWh
9 kWh/day × 2 days = 18 kWh
```

---

## 6. Account for usable battery capacity

Batteries are not always used down to 0%. Also, there are inverter and system losses.

A good rule of thumb is to divide by **0.85 to 0.90**.

Formula:

```text
Required battery size = desired usable energy ÷ system efficiency
```

Example:

```text
9 kWh ÷ 0.90 = 10 kWh battery
```

So if you need **9 kWh usable**, you may want around a **10 kWh nominal battery**.

---

## 7. Check battery power rating, not just capacity

Battery size has two important specs:

### Energy capacity: kWh
How long the battery can run your loads.

### Power output: kW
How many appliances it can run at once.

Example:

- A 10 kWh battery with 5 kW output can run up to 5 kW of loads at one time.
- If your air conditioner needs 6–8 kW to start, one battery may not be enough.
- Motors, pumps, compressors, and AC units may need high surge power.

So you need enough:

```text
kWh = runtime
kW = simultaneous load capacity
```

---

## 8. Consider your solar array size

If the battery is paired with solar, the solar panels must be able to recharge the battery while also serving household loads.

Example:

- Battery: 10 kWh
- Solar array: 6 kW
- Average sun: 4 peak sun hours/day

Estimated daily solar production:

```text
6 kW × 4 hours = 24 kWh/day before losses
```

After losses, maybe **18–21 kWh/day**.

That could recharge a 10 kWh battery and run some home loads, depending on weather and usage.

---

## 9. Simple sizing rules of thumb

### For essential backup only
Usually:

```text
10–15 kWh
```

This may cover refrigerator, lights, internet, outlets, and some heating controls for about a day.

### For larger backup loads
Usually:

```text
20–30+ kWh
```

Needed if you want to run more circuits, well pumps, HVAC, or longer outages.

### For whole-home backup
Often:

```text
30–60+ kWh
```

Especially if you have central AC, electric heat, or high daily consumption.

---

## Example battery sizing

Suppose you want to back up essential loads:

- Critical loads: 8 kWh/day
- Backup time: 1.5 days
- Efficiency factor: 90%

Calculation:

```text
8 kWh/day × 1.5 days = 12 kWh usable
12 kWh ÷ 0.90 = 13.3 kWh nominal
```

A good target would be a **13–15 kWh battery system**.

If one battery module is 13.5 kWh, one unit may be enough. If you want two days or heavier loads, you may need two batteries.

---

## Quick formula

```text
Battery size in kWh =
Daily backed-up load × days of backup ÷ efficiency
```

Example:

```text
10 kWh/day × 2 days ÷ 0.90 = 22.2 kWh
```

So you would choose roughly **22–25 kWh** of battery capacity.

---

## Practical recommendation

For most homes:

- **Small backup system:** 10 kWh
- **Good essential-load backup:** 13–20 kWh
- **Larger backup with some HVAC:** 20–40 kWh
- **Whole-home backup:** 30+ kWh, sometimes much more

The best next step is to list your critical loads and calculate their daily kWh usage. Then size the battery based on desired backup duration and confirm the battery’s power rating can handle your largest simultaneous loads.