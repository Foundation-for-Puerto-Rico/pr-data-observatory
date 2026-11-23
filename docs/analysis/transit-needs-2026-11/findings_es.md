# Dónde hace más falta una ruta o una conexión nueva: hallazgos

Escrito por `transit_needs.py` con los horarios vigentes el 2026-11-10. Es una ayuda de planificación para que FPR la revise, no un pronóstico de demanda ni un estudio de ingeniería. El método y sus límites están en `README.md`; los públicos no tienen horario publicado, así que un barrio sin servicio con horario puede tener públicos.

## Resumen de la isla

- 3,284,650 residentes (bloques del Censo 2020); el 7.9% vive a 400 m o menos de una parada con guagua cada 30 minutos o mejor durante el día laborable, y el 21.5% a 400 m o menos de cualquier parada con horario vigente.
- Unos 167,247 hogares no tienen vehículo (ACS 2020-2024); unos 143,806 viven en la parte sin servicio de su barrio.
- Se ordenan 746 barrios con 500 residentes o más; 18 operadores tienen horario vigente el 2026-11-10.

## Los 25 barrios para mirar primero

| # | Barrio | Municipio | Prioridad | Necesidad | Hogares sin vehículo | sin servicio útil | Servicio útil | Horario municipal | Qué sugiere la brecha |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Mayagüez | Mayagüez | 98.1 | 79.7 | 2,919 (31.0%) | 2,919 | 0.0% | no publica | servicio nuevo (ninguna parada con guagua cada 30 minutos a 1.5 km o menos) |
| 2 | Machuelo Abajo | Ponce | 98.1 | 85.6 | 1,100 (22.2%) | 1,100 | 0.0% | vencido 2024-12-31 | servicio nuevo (ninguna parada con guagua cada 30 minutos a 1.5 km o menos) |
| 3 | Segundo | Ponce | 98.1 | 93.0 | 820 (34.5%) | 820 | 0.0% | vencido 2024-12-31 | servicio nuevo (ninguna parada con guagua cada 30 minutos a 1.5 km o menos) |
| 4 | Cayey | Cayey | 97.4 | 79.9 | 1,293 (22.0%) | 1,293 | 0.0% | no publica | servicio nuevo (ninguna parada con guagua cada 30 minutos a 1.5 km o menos) |
| 5 | Manatí | Manatí | 97.1 | 87.2 | 748 (37.2%) | 748 | 0.0% | vigente | más frecuencia en las paradas que ya tiene |
| 6 | Coamo | Coamo | 96.8 | 87.5 | 663 (24.6%) | 663 | 0.0% | vigente | más frecuencia en las paradas que ya tiene |
| 7 | San Antón | Ponce | 96.8 | 81.9 | 806 (20.8%) | 806 | 0.0% | vencido 2024-12-31 | servicio nuevo (ninguna parada con guagua cada 30 minutos a 1.5 km o menos) |
| 8 | Arecibo | Arecibo | 96.6 | 78.8 | 971 (30.3%) | 971 | 0.0% | sin sistema en la lista | servicio nuevo (ninguna parada con guagua cada 30 minutos a 1.5 km o menos) |
| 9 | Aguadilla | Aguadilla | 95.9 | 94.9 | 472 (35.7%) | 472 | 0.0% | sin sistema en la lista | servicio nuevo (ninguna parada con guagua cada 30 minutos a 1.5 km o menos) |
| 10 | Guayama | Guayama | 95.2 | 73.3 | 1,381 (22.0%) | 1,381 | 0.0% | sin sistema en la lista | servicio nuevo (ninguna parada con guagua cada 30 minutos a 1.5 km o menos) |
| 11 | Caguas | Caguas | 95.1 | 80.6 | 2,069 (23.7%) | 1,856 | 10.3% | vencido 2026-01-31 | extender o alimentar la ruta 30 (Autoridad de Transporte Integrado (ATI)): la parada más cercana con guagua cada 30 minutos, Ave. Gurabo antes PR-1 Tribunal Judicial, está a 615 m de donde vive la población sin servicio |
| 12 | Primero | Ponce | 94.0 | 86.9 | 414 (33.2%) | 414 | 0.0% | vencido 2024-12-31 | servicio nuevo (ninguna parada con guagua cada 30 minutos a 1.5 km o menos) |
| 13 | Sábalos | Mayagüez | 93.3 | 72.7 | 727 (18.2%) | 727 | 0.0% | no publica | servicio nuevo (ninguna parada con guagua cada 30 minutos a 1.5 km o menos) |
| 14 | Utuado | Utuado | 92.9 | 73.1 | 586 (25.4%) | 586 | 0.0% | vigente | más frecuencia en las paradas que ya tiene |
| 15 | Fajardo | Fajardo | 92.8 | 71.0 | 761 (16.4%) | 761 | 0.0% | vencido 2026-06-15 | servicio nuevo (ninguna parada con guagua cada 30 minutos a 1.5 km o menos) |
| 16 | Camaceyes | Aguadilla | 92.7 | 70.3 | 844 (19.3%) | 844 | 0.0% | sin sistema en la lista | servicio nuevo (ninguna parada con guagua cada 30 minutos a 1.5 km o menos) |
| 17 | Humacao | Humacao | 92.6 | 75.8 | 466 (27.6%) | 466 | 0.0% | vigente | más frecuencia en las paradas que ya tiene |
| 18 | Yauco | Yauco | 92.6 | 83.5 | 356 (33.6%) | 356 | 0.0% | no publica | servicio nuevo (ninguna parada con guagua cada 30 minutos a 1.5 km o menos) |
| 19 | Machuelo Arriba | Ponce | 91.7 | 70.4 | 613 (14.5%) | 613 | 0.0% | vencido 2024-12-31 | servicio nuevo (ninguna parada con guagua cada 30 minutos a 1.5 km o menos) |
| 20 | Comerío | Comerío | 91.4 | 80.1 | 331 (32.4%) | 331 | 0.0% | no publica | servicio nuevo (ninguna parada con guagua cada 30 minutos a 1.5 km o menos) |
| 21 | Juana Díaz | Juana Díaz | 91.4 | 87.6 | 302 (19.2%) | 302 | 0.0% | sin sistema en la lista | servicio nuevo (ninguna parada con guagua cada 30 minutos a 1.5 km o menos) |
| 22 | Quebrada Grande | Mayagüez | 91.3 | 81.8 | 315 (19.9%) | 315 | 0.0% | no publica | servicio nuevo (ninguna parada con guagua cada 30 minutos a 1.5 km o menos) |
| 23 | Aguas Buenas | Aguas Buenas | 91.2 | 94.2 | 282 (43.1%) | 282 | 0.0% | sin sistema en la lista | servicio nuevo (ninguna parada con guagua cada 30 minutos a 1.5 km o menos) |
| 24 | Playa | Ponce | 91.2 | 67.6 | 863 (16.8%) | 863 | 0.0% | vencido 2024-12-31 | servicio nuevo (ninguna parada con guagua cada 30 minutos a 1.5 km o menos) |
| 25 | Capitanejo | Juana Díaz | 91.1 | 78.9 | 345 (26.2%) | 345 | 0.0% | sin sistema en la lista | servicio nuevo (ninguna parada con guagua cada 30 minutos a 1.5 km o menos) |

Servicio útil: residentes a 400 m o menos (en línea recta) de una parada con guagua cada 30 minutos o mejor, de 7:00 a 19:00 en día laborable. Poca confiabilidad: el margen de error del porcentaje sin vehículo es mayor que el porcentaje. Horario municipal: el sistema propio del municipio en `operators.json`. **14 de estos 25 barrios están en un municipio cuyo sistema no publica horario o lo tiene vencido**: ahí la brecha puede estar en los datos y no en el servicio, y el primer paso es confirmar con el municipio qué servicio opera (y conseguir su horario).

## Donde los horarios están vigentes: las brechas que los datos sí muestran

La misma lista, solo con los barrios de municipios cuyo sistema propio tiene horario vigente, o que no tienen sistema propio en la lista y tienen paradas de la ATI (el horario de la ATI está vigente). Aquí una brecha es una brecha en el servicio publicado.

| # | Barrio | Municipio | Prioridad | Hogares sin vehículo sin servicio útil | Servicio útil | Alguna parada vigente | Qué sugiere la brecha |
|---|---|---|---|---|---|---|---|
| 5 | Manatí | Manatí | 97.1 | 748 | 0.0% | 89.6% | más frecuencia en las paradas que ya tiene |
| 6 | Coamo | Coamo | 96.8 | 663 | 0.0% | 78.3% | más frecuencia en las paradas que ya tiene |
| 14 | Utuado | Utuado | 92.9 | 586 | 0.0% | 92.9% | más frecuencia en las paradas que ya tiene |
| 17 | Humacao | Humacao | 92.6 | 466 | 0.0% | 66.4% | más frecuencia en las paradas que ya tiene |
| 40 | Quebrada Negrito | Trujillo Alto | 87.6 | 273 | 0.0% | 0.0% | servicio nuevo (ninguna parada con guagua cada 30 minutos a 1.5 km o menos) |
| 48 | Río | Guaynabo | 85.1 | 219 | 0.0% | 26.1% | más frecuencia en las paradas que ya tiene |
| 54 | Medianía Baja | Loíza | 84.8 | 432 | 0.5% | 0.5% | servicio nuevo (ninguna parada con guagua cada 30 minutos a 1.5 km o menos) |
| 56 | Medianía Alta | Loíza | 84.7 | 452 | 0.0% | 0.0% | servicio nuevo (ninguna parada con guagua cada 30 minutos a 1.5 km o menos) |
| 57 | Monacillo | San Juan | 84.7 | 652 | 0.0% | 87.4% | más frecuencia en las paradas que ya tiene |
| 58 | Isabel II | Vieques | 84.5 | 198 | 0.0% | 78.6% | más frecuencia en las paradas que ya tiene |
| 61 | Cabo Caribe | Vega Baja | 84.2 | 316 | 0.0% | 71.7% | más frecuencia en las paradas que ya tiene |
| 62 | Pájaros | Bayamón | 84.0 | 1,519 | 0.0% | 8.5% | servicio nuevo (ninguna parada con guagua cada 30 minutos a 1.5 km o menos) |
| 65 | Maricao | Vega Alta | 83.8 | 300 | 0.0% | 22.1% | más frecuencia en las paradas que ya tiene |
| 67 | Guaraguao | Guaynabo | 83.6 | 213 | 0.0% | 90.0% | más frecuencia en las paradas que ya tiene |
| 71 | Bajura Adentro | Manatí | 83.3 | 197 | 0.0% | 0.0% | servicio nuevo (ninguna parada con guagua cada 30 minutos a 1.5 km o menos) |

## Conexiones entre operadores para mirar primero

| # | Dónde | Rutas que se acercan | Distancia mínima | Residentes a 800 m |
|---|---|---|---|---|
| 1 | 18.40743, -66.02996 | ATI 40 (32 viajes); San Juan 4 (7 viajes) | 392 m | 10,081 |
| 2 | 18.40743, -66.0688 | ATI 8 (32 viajes); San Juan 7 (8 viajes) | 584 m | 9,132 |
| 3 | 18.39752, -66.00084 | ATI 43 (43 viajes); San Juan 4 (7 viajes) | 480 m | 7,810 |
| 4 | 18.39837, -66.04354 | ATI 41 (78 viajes); San Juan 6A (10 viajes) | 686 m | 7,767 |
| 5 | 18.44029, -66.06778 | ATI 10 (106 viajes); San Juan 1 (6 viajes) | 723 m | 7,594 |
| 6 | 18.41063, -66.05537 | ATI 26 (45 viajes); San Juan 7 (8 viajes); ATI 40 (32 viajes); ATI 41 (78 viajes); ATI 17 (30 viajes); San Juan 3 (8 viajes) | 524 m | 7,224 |
| 7 | 18.45532, -66.07266 | ATI 53 (27 viajes); San Juan 2 (6 viajes) | 533 m | 7,176 |
| 8 | 18.42969, -66.05858 | ATI 4 (60 viajes); San Juan 2 (6 viajes) | 635 m | 7,149 |
| 9 | 18.40782, -66.05237 | ATI 40 (32 viajes); San Juan 3 (8 viajes) | 702 m | 6,948 |
| 10 | 18.37845, -66.12699 | Guaynabo TORR (22 viajes); Bayamon BR-3 (12 viajes) | 305 m | 6,915 |
| 11 | 18.40133, -66.05188 | ATI 1 (81 viajes); San Juan 6A (10 viajes); ATI 26 (45 viajes); ATI 4 (60 viajes); ATI 8 (32 viajes) | 528 m | 6,777 |
| 12 | 18.37022, -66.08669 | ATI 27 (41 viajes); San Juan 6 (7 viajes) | 667 m | 5,425 |
| 13 | 18.44177, -66.11772 | ATI 37 (48 viajes); Guaynabo AME (22 viajes); ATI CSJ (32 viajes) | 324 m | 4,544 |
| 14 | 18.36509, -66.13524 | Guaynabo CANTAG (22 viajes); Bayamon BR-3 (12 viajes) | 619 m | 4,150 |
| 15 | 18.39347, -66.10567 | ATI 8 (32 viajes); Guaynabo TORR (22 viajes) | 713 m | 4,148 |

26 pares de rutas vigentes de operadores distintos pasan a 250-800 m una de otra sin paradas a 250 m o menos, en 19 lugares (los pares cuyos puntos más cercanos están a 400 m o menos cuentan como un lugar): un enlace corto, una parada nueva o un trasbordo coordinado podría unirlas. Los viajes son de día laborable, en ambas direcciones. Todos los pares están en `connections.csv`.

