# Test results

**Prompts:** 5 · **Failed:** 0 · **Avg score:** 0.88

| # | Prompt | Result | Score |
|---|--------|--------|-------|
| 1 | Gaśnica proszkowa sześć kilo, klatka schodowa parter, ciśnienie w normie, zielone pole, następny przegląd za rok, sprawna. | ✅ OK | 1.00 |
| 2 | Hydrant wewnętrzny numer trzy, drugie piętro, wąż przetarty trzeba wymienić, ciśnienie tylko dwa i pół bara za mało, do naprawy. | ⚠️ OK | 0.97 |
| 3 | Gaśnica CO2 pięć kilogramów, kuchnia na zapleczu, brak plomby, waga poniżej normy, do wymiany, przegląd dzisiaj dziesiątego lipca. | ⚠️ OK | 0.88 |
| 4 | Hydrant zewnętrzny przy wjeździe, ciśnienie siedem bar wszystko w porządku, sprawny, następny przegląd lipiec dwa tysiące dwadzieścia siedem. | ⚠️ OK | 0.88 |
| 5 | Znaczy tam gaśnica jest, korytarz pierwsze piętro, no data przeglądu minęła w zeszłym miesiącu, reszta wygląda ok. | ⚠️ OK | 0.66 |

## [1] Gaśnica proszkowa sześć kilo, klatka schodowa parter, ciśnienie w normie, zielone pole, następny przegląd za rok, sprawna.

Entry score: **1.00**

| Field | Verdict | Score | Gold | Model output | Note |
|-------|---------|-------|------|--------------|------|
| device_type | ✓ exact | 1.00 | gaśnica proszkowa | gaśnica proszkowa |  |
| location | ✓ semantic | 1.00 | klatka schodowa, parter | klatka schodowa parter | semantically identical, formatting differs |
| pressure_bar | ✓ exact | 1.00 | — | — |  |
| capacity | ✓ exact | 1.00 | 6 kg | 6 kg |  |
| defects | ✓ exact | 1.00 | [] | [] |  |
| status | ✓ exact | 1.00 | sprawna | sprawna |  |
| inspection_date | ✓ exact | 1.00 | — | — |  |
| next_inspection | ✓ exact | 1.00 | za rok | za rok |  |

## [2] Hydrant wewnętrzny numer trzy, drugie piętro, wąż przetarty trzeba wymienić, ciśnienie tylko dwa i pół bara za mało, do naprawy.

Entry score: **0.97**

| Field | Verdict | Score | Gold | Model output | Note |
|-------|---------|-------|------|--------------|------|
| device_type | ✗ format | 0.75 | hydrant wewnętrzny nr 3 | hydrant wewnętrzny numer trzy | same numeric value, type/format differs |
| location | ✓ exact | 1.00 | drugie piętro | drugie piętro |  |
| pressure_bar | ✓ exact | 1.00 | 2.5 | 2.5 |  |
| capacity | ✓ exact | 1.00 | — | — |  |
| defects | ✓ exact | 1.00 | ["wąż przetarty"] | ["wąż przetarty"] |  |
| status | ✓ exact | 1.00 | do_naprawy | do_naprawy |  |
| inspection_date | ✓ exact | 1.00 | — | — |  |
| next_inspection | ✓ exact | 1.00 | — | — |  |

## [3] Gaśnica CO2 pięć kilogramów, kuchnia na zapleczu, brak plomby, waga poniżej normy, do wymiany, przegląd dzisiaj dziesiątego lipca.

Entry score: **0.88**

| Field | Verdict | Score | Gold | Model output | Note |
|-------|---------|-------|------|--------------|------|
| device_type | ✓ exact | 1.00 | gaśnica CO2 | gaśnica CO2 |  |
| location | ✗ wrong | 0.00 | kuchnia, zaplecze | kuchnia na zapleczu | value does not match gold |
| pressure_bar | ✓ exact | 1.00 | — | — |  |
| capacity | ✓ exact | 1.00 | 5 kg | 5 kg |  |
| defects | ✓ exact | 1.00 | ["brak plomby", "waga poniżej normy"] | ["brak plomby", "waga poniżej normy"] |  |
| status | ✓ exact | 1.00 | do_wymiany | do_wymiany |  |
| inspection_date | ✓ exact | 1.00 | 10 lipca | 10 lipca |  |
| next_inspection | ✓ exact | 1.00 | — | — |  |

## [4] Hydrant zewnętrzny przy wjeździe, ciśnienie siedem bar wszystko w porządku, sprawny, następny przegląd lipiec dwa tysiące dwadzieścia siedem.

Entry score: **0.88**

| Field | Verdict | Score | Gold | Model output | Note |
|-------|---------|-------|------|--------------|------|
| device_type | ✓ exact | 1.00 | hydrant zewnętrzny | hydrant zewnętrzny |  |
| location | ✗ wrong | 0.00 | wjazd | przy wjeździe | value does not match gold |
| pressure_bar | ✓ exact | 1.00 | 7 | 7 |  |
| capacity | ✓ exact | 1.00 | — | — |  |
| defects | ✓ exact | 1.00 | [] | [] |  |
| status | ✓ exact | 1.00 | sprawny | sprawny |  |
| inspection_date | ✓ exact | 1.00 | — | — |  |
| next_inspection | ✓ exact | 1.00 | lipiec 2027 | lipiec 2027 |  |

## [5] Znaczy tam gaśnica jest, korytarz pierwsze piętro, no data przeglądu minęła w zeszłym miesiącu, reszta wygląda ok.

Entry score: **0.66**

| Field | Verdict | Score | Gold | Model output | Note |
|-------|---------|-------|------|--------------|------|
| device_type | ✓ exact | 1.00 | gaśnica | gaśnica |  |
| location | ✓ exact | 1.00 | korytarz, pierwsze piętro | korytarz, pierwsze piętro |  |
| pressure_bar | ✓ exact | 1.00 | — | — |  |
| capacity | ✓ exact | 1.00 | — | — |  |
| defects | ✗ partial | 0.25 | ["data przeglądu minęła"] | [] | 'data przeglądu minęła': missing |
| status | ✗ hallucination | 0.00 | — | sprawna | gold is null, model invented a value |
| inspection_date | ✗ hallucination | 0.00 | — | zeszły miesiąc | gold is null, model invented a value |
| next_inspection | ✓ exact | 1.00 | — | — |  |
