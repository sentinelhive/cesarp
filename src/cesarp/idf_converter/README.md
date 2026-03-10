# CESARP2Nestli

Converts CESAR-P EnergyPlus IDF files to Nestli format.

Works with any CESAR-P archetype era, any number of floors, and can process single files or entire folders.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
```

## Usage

### Single file
```bash
cd code/
python 01_CESARP2Nestli.py --cesarp ../IDFs/CESARP/B01_Mia_Dual_005_cesarp.idf --nestli ../IDFs/NESTLI/Foursquare_nestli.idf
```

### Batch (all .idf in a folder)
```bash
python 01_CESARP2Nestli.py --batch ../IDFs/CESARP/ --nestli ../IDFs/NESTLI/Foursquare_nestli.idf
```

### Custom output directory
```bash
python 01_CESARP2Nestli.py --cesarp file.idf --nestli template.idf --outdir ../results/run01/
```

## Output

For each input `{name}.idf`, the converter produces:
- `results/{name}_nestli.idf` — converted IDF
- `results/{name}_mapping.csv` — full list of what changed (old name -> new name)

## How it works

1. Auto-detects archetype era from URI patterns (1918, 1948, 1970, etc.)
2. Auto-detects zones (ZoneFloor0, ZoneFloor1, ...) and renames to FLOOR0:ZONE0, FLOOR1:ZONE0
3. Auto-renames materials from URI paths to descriptive names
4. Auto-renames constructions from URI paths
5. Updates cross-references throughout
6. Merges with the Nestli template for simulation infrastructure

