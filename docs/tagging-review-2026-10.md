# Tagging review: 594 dictionary entries to domains (2026-10-05)

Phase 3, item 1. Every dictionary entry now has a primary `domain` and a `domains` list (primary first, then secondary domains). The old ten 'areas' were mapped by the rules below. Rows marked **review** are judgment calls: tell me which to change and I will edit the rule, not the entries one by one.

## Rules

1. The primary domain is what the thing measures **about** (placing a school flood flag: primary Education, secondary Hazards). Where an entry counts tourism places inside a flood or protected area, the subject is the tourism places, so the primary is Visitor economy and the secondary is Hazards or Land.
2. Methods and documentation entries are `system.docs`; the twin's own tools are `system.tools`; boundaries and land area are `system.geography`. Documentation entries that count something (snapshot counts, build facts) carry the counted subject as a secondary domain so they show up under it.
3. Methods written for one field (Housing methods, Jobs and money, how tourism places are built, Route planner) take that field as primary and `system.docs` or `system.tools` as secondary.

## Entries per domain

| Domain | Primary | Tagged with this exact id (primary or secondary) |
|---|---:|---:|
| `housing` (Housing) | 63 | 81 |
| `education` (Education) | 3 | 3 |
| `infrastructure` (Infrastructure) | 2 | 2 |
| `infrastructure.mobility` (Mobility and transit) | 104 | 124 |
| `economy` (Economy) | 63 | 80 |
| `economy.visitor-economy` (Visitor economy) | 96 | 108 |
| `economy.public-money` (Public money and recovery) | 11 | 11 |
| `environment` (Environment) | 0 | 0 |
| `environment.hazards` (Hazards) | 20 | 32 |
| `environment.land` (Land and protected areas) | 46 | 56 |
| `health` (Health) | 0 | 0 |
| `population` (Population and households) | 12 | 23 |
| `system` (Twin system) | 0 | 0 |
| `system.geography` (Reference geography) | 20 | 27 |
| `system.docs` (Methods and documentation) | 65 | 75 |
| `system.tools` (Twin tools) | 89 | 101 |

## Mapping of the old areas and groups

| Old area | Old group | Entries | Primary | Secondary | |
|---|---|---:|---|---|---|
| Economy and work | Change since 2008-2012 | 1 | `economy` | - |  |
| Economy and work | Change since 2008-2012 | 1 | `education` | `population` | **review** |
| Economy and work | Education | 2 | `education` | `population` | **review** |
| Economy and work | Income and poverty | 8 | `economy` | - |  |
| Economy and work | Income and poverty | 2 | `economy` | `population` | **review** |
| Economy and work | Industries | 19 | `economy` | - |  |
| Economy and work | Industries | 5 | `economy` | `economy.visitor-economy` |  |
| Economy and work | Jobs and employers | 8 | `economy` | - |  |
| Economy and work | Labor force | 8 | `economy` | - |  |
| Economy and work | Vehicles and internet | 2 | `infrastructure` | `housing` | **review** |
| Economy and work | Vehicles and internet | 1 | `infrastructure.mobility` | `housing` | **review** |
| Economy and work | Workers and commuting | 5 | `economy` | `infrastructure.mobility` | **review** |
| Economy and work | Workers and commuting | 4 | `economy` | - |  |
| Hazards and environment | Flood exposure by municipality | 3 | `economy.visitor-economy` | `environment.hazards` | **review** |
| Hazards and environment | Flood exposure of tourism places | 3 | `economy.visitor-economy` | `environment.hazards` | **review** |
| Hazards and environment | Flood hazard zones (FEMA) | 6 | `environment.hazards` | - |  |
| Hazards and environment | Hurricanes and tropical storms | 12 | `environment.hazards` | - |  |
| Hazards and environment | Protected areas (PAD-US) | 8 | `environment.land` | - |  |
| Hazards and environment | Protected-area exposure by municipality | 1 | `economy.visitor-economy` | `environment.land` | **review** |
| Hazards and environment | Protected-area exposure of tourism places | 2 | `economy.visitor-economy` | `environment.land` | **review** |
| Hazards and environment | Sea level rise | 2 | `environment.hazards` | - |  |
| Housing | Affordability | 4 | `housing` | - |  |
| Housing | Change since 2008-2012 | 2 | `housing` | - |  |
| Housing | Cost burden | 6 | `housing` | - |  |
| Housing | Homes counted in the census | 2 | `housing` | - |  |
| Housing | Housing stock | 24 | `housing` | - |  |
| Housing | Owners and renters | 2 | `housing` | - |  |
| Housing | Prices and costs | 6 | `housing` | - |  |
| Housing | State of Housing study (2023) | 14 | `housing` | - |  |
| Housing | Survey window | 1 | `housing` | - |  |
| Land and boundaries | Barrios | 5 | `system.geography` | - |  |
| Land and boundaries | Barrios: tourism-place counts | 5 | `economy.visitor-economy` | `system.geography` | **review** |
| Land and boundaries | Boundary methods | 4 | `system.geography` | - |  |
| Land and boundaries | Land area | 1 | `system.geography` | - |  |
| Land and boundaries | Land use plan: area | 5 | `environment.land` | - |  |
| Land and boundaries | Land use plan: classes and methods | 2 | `environment.land` | - |  |
| Land and boundaries | Land use plan: place listings | 5 | `economy.visitor-economy` | `environment.land` | **review** |
| Land and boundaries | Land-use plan: classes | 17 | `environment.land` | - |  |
| Land and boundaries | Land-use plan: groups | 6 | `environment.land` | - |  |
| Land and boundaries | Land-use plan: map layer and fields | 6 | `environment.land` | - |  |
| Land and boundaries | Land-use plan: methods | 1 | `environment.land` | - |  |
| Land and boundaries | Municipalities and regions | 2 | `system.geography` | - |  |
| Land and boundaries | Municipality boundaries | 8 | `system.geography` | - |  |
| Land and boundaries | Zoning (Calificación) | 1 | `environment.land` | - |  |
| Map layers and tools | 2D map: Economy tab | 17 | `system.tools` | `economy` |  |
| Map layers and tools | 2D map: Layers tab | 18 | `system.tools` | - |  |
| Map layers and tools | 2D map: Municipality and Rankings tabs | 3 | `system.tools` | - |  |
| Map layers and tools | 2D map: Transit tab | 7 | `system.tools` | `infrastructure.mobility` |  |
| Map layers and tools | 2D map: page and controls | 3 | `system.tools` | - |  |
| Map layers and tools | 3D + Time view | 14 | `system.tools` | - |  |
| Map layers and tools | Ask the twin (chat) | 4 | `system.tools` | - |  |
| Map layers and tools | Data dictionary page | 2 | `system.tools` | - |  |
| Map layers and tools | Data inventory and wish list | 6 | `system.docs` | - | moved from tools to documentation |
| Map layers and tools | Housing page | 10 | `system.tools` | `housing` |  |
| Map layers and tools | Place names and search | 5 | `system.tools` | - |  |
| Map layers and tools | Search, links and downloads | 6 | `system.tools` | - |  |
| Measures and methods | Build information | 6 | `system.docs` | - |  |
| Measures and methods | Build information | 2 | `system.docs` | `infrastructure.mobility` |  |
| Measures and methods | Build information | 1 | `system.docs` | `system.geography` |  |
| Measures and methods | Build information | 1 | `system.docs` | `housing` |  |
| Measures and methods | Build information | 1 | `system.docs` | `environment.land` |  |
| Measures and methods | Build information | 1 | `system.docs` | `infrastructure.mobility`, `environment.hazards` |  |
| Measures and methods | Classes and colors | 5 | `system.docs` | - |  |
| Measures and methods | Dollars and prices | 1 | `system.docs` | - |  |
| Measures and methods | Housing methods | 2 | `housing` | `system.docs` | **review** |
| Measures and methods | How places and points are built | 4 | `economy.visitor-economy` | `system.docs` | **review** |
| Measures and methods | Jobs and money | 3 | `economy` | `system.docs` | **review** |
| Measures and methods | Ranking and comparing | 3 | `system.docs` | - |  |
| Measures and methods | Relationships between datasets | 3 | `system.docs` | - |  |
| Measures and methods | Rescaling a value | 11 | `system.docs` | - |  |
| Measures and methods | Route planner | 12 | `infrastructure.mobility` | `system.tools` | **review** |
| Measures and methods | Snapshot counts | 7 | `system.docs` | `economy.visitor-economy` |  |
| Measures and methods | Snapshot counts | 1 | `system.docs` | `environment.hazards` |  |
| Measures and methods | Snapshot counts | 1 | `system.docs` | `system.geography` |  |
| Measures and methods | Snapshot counts | 1 | `system.docs` | `environment.land` |  |
| Measures and methods | Snapshot counts | 1 | `system.docs` | `population` |  |
| Measures and methods | Survey tables | 3 | `system.docs` | - |  |
| Measures and methods | Time and vintages | 6 | `system.docs` | - |  |
| Measures and methods | Uncertainty | 1 | `system.docs` | - |  |
| Measures and methods | Using the twin | 3 | `system.docs` | - |  |
| Measures and methods | Which places a percentage counts | 1 | `economy.visitor-economy` | `system.docs` | **review** |
| Mobility and transit | Airports, taxis and charging | 9 | `infrastructure.mobility` | - |  |
| Mobility and transit | Municipal transit systems | 2 | `infrastructure.mobility` | - |  |
| Mobility and transit | Operators and timetable feeds | 8 | `infrastructure.mobility` | - |  |
| Mobility and transit | Real-time data | 1 | `infrastructure.mobility` | - |  |
| Mobility and transit | Ride-hailing | 1 | `infrastructure.mobility` | - |  |
| Mobility and transit | Road network | 5 | `infrastructure.mobility` | - |  |
| Mobility and transit | Routes | 18 | `infrastructure.mobility` | - |  |
| Mobility and transit | Service coverage and planning | 12 | `infrastructure.mobility` | - |  |
| Mobility and transit | Stops, stations and terminals | 20 | `infrastructure.mobility` | - |  |
| Mobility and transit | Timetable replay | 5 | `infrastructure.mobility` | - |  |
| Mobility and transit | Transit access of residents | 5 | `infrastructure.mobility` | `population` |  |
| Mobility and transit | Transit access of tourism places | 5 | `economy.visitor-economy` | `infrastructure.mobility` | **review** |
| Mobility and transit | Transit methods and categories | 5 | `infrastructure.mobility` | - |  |
| Population and households | Change since 2008-2012 | 1 | `population` | - |  |
| Population and households | Households | 2 | `population` | `housing` |  |
| Population and households | People counted in the census | 3 | `population` | - |  |
| Population and households | Population | 6 | `population` | - |  |
| Public money and recovery | Disaster recovery | 2 | `economy.public-money` | `housing`, `environment.hazards` | **review** |
| Public money and recovery | Disaster recovery | 2 | `economy.public-money` | `environment.hazards` | **review** |
| Public money and recovery | Federal awards by place of performance | 7 | `economy.public-money` | - |  |
| Tourism supply | Tourism places counted | 6 | `economy.visitor-economy` | - |  |
| Tourism supply | Tourism places relative to people and land | 2 | `economy.visitor-economy` | - |  |
| Tourism supply | Tourism places: categories | 4 | `economy.visitor-economy` | - |  |
| Tourism supply | Tourism places: classification | 3 | `economy.visitor-economy` | - |  |
| Tourism supply | Tourism places: how the data are made | 8 | `economy.visitor-economy` | - |  |
| Tourism supply | Tourism places: identity and location | 7 | `economy.visitor-economy` | - |  |
| Tourism supply | Tourism places: quality and source | 4 | `economy.visitor-economy` | - |  |
| Tourism supply | Tourism places: types | 27 | `economy.visitor-economy` | - |  |
| Tourism supply | Tourism supply layers on the Economy tab | 6 | `economy.visitor-economy` | - |  |
