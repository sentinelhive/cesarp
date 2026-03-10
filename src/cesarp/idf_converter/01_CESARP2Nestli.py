#!/usr/bin/env python3
"""
01_CESARP2Nestli.py

Converts CESAR-P IDF files to Nestli (DesignBuilder) format.
Auto-detects archetype era, zone count, and naming patterns.

Usage:
    python 01_CESARP2Nestli.py --cesarp file.idf --nestli template.idf
    python 01_CESARP2Nestli.py --batch ../IDFs/CESARP/ --nestli template.idf
"""

import os
import re
import glob
import copy
import csv
import argparse
from typing import Dict, List

from idf_parser import IDFFile, IDFObject, IDFField, make_object
from config import (
    CESARP_DIR, NESTLI_IDF, OUTPUT_DIR, TARGET_EP_VERSION,
    CATEGORY_LABELS, CONSTRUCTION_LABELS,
)


# -- Auto-detection of naming patterns --

class NameMapper:
    """Tracks all old->new name mappings. Exports them for the CSV report."""

    def __init__(self):
        self.map: Dict[str, str] = {}
        self.log: List[Dict] = []  # category, obj_type, old, new

    def add(self, old, new, category="", obj_type=""):
        self.map[old] = new
        if old != new:
            self.log.append({"category": category, "obj_type": obj_type,
                             "old": old, "new": new})

    def get(self, old):
        return self.map.get(old, old)

    def apply_to_object(self, obj: IDFObject):
        for fld in obj.fields:
            stripped = fld.value.strip()
            if stripped in self.map:
                fld.value = self.map[stripped]

    def write_csv(self, filepath):
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["Category", "Object Type", "CESARP Name", "Nestli Name"])
            for entry in self.log:
                w.writerow([entry["category"], entry["obj_type"],
                            entry["old"], entry["new"]])
        return len(self.log)


def auto_rename_material(uri_name):
    """
    Auto-detect material name from CESAR-P URI.
    Patterns:
      http://uesl_data/.../constructionLayers/{year}_{Cat}{N}_L{layer}
      http://uesl_data/.../floors/cesar_default_internal_ceiling_L1
    Falls back to last path segment cleaned up.
    """
    if "/" not in uri_name:
        return uri_name

    last = uri_name.rsplit("/", 1)[-1]

    # Pattern: {year}_{Cat}{N}_L{layer}  e.g. 1918_Gr2_L1
    m = re.match(r"(\d{4})_([A-Z][a-z])(\d+)_L(\d+)", last)
    if m:
        year, cat_code, type_num, layer_num = m.groups()
        cat_label = CATEGORY_LABELS.get(cat_code, cat_code)
        return f"{cat_label}_{year}_T{type_num}_Layer{layer_num}"

    # Pattern: cesar_default_*_L{N}
    m = re.match(r"cesar_default_(.+?)_L(\d+)", last)
    if m:
        desc = m.group(1).replace("_", " ").title()
        return f"{desc}_Layer{m.group(2)}"

    # Pattern: cesar_default_* (no layer suffix)
    if last.startswith("cesar_default_"):
        return last.replace("cesar_default_", "").replace("_", " ").title()

    return last.replace("_", " ")


def auto_rename_construction(uri_name):
    """
    Auto-detect construction name from CESAR-P URI.
    Patterns:
      http://uesl_data/.../grounds/Ground1918_concrete_medium
      http://uesl_data/.../walls/Wall1918_brick_dl_medium
      http://uesl_data/.../floors/cesar_default_internal_ceiling
    """
    if "/" not in uri_name:
        return uri_name

    # Get the category from path and last segment
    parts = uri_name.rsplit("/", 2)
    if len(parts) >= 2:
        category_seg = parts[-2] if len(parts) >= 2 else ""
        last = parts[-1]
    else:
        last = uri_name.rsplit("/", 1)[-1]
        category_seg = ""

    # Try to extract year and type
    # Pattern: {Type}{Year}_{description}  e.g. Ground1918_concrete_medium
    m = re.match(r"([A-Z][a-z]+)(\d{4})_(.+)", last)
    if m:
        element, year, desc = m.groups()
        desc_clean = desc.replace("_", " ").title()
        return f"{element} {year} {desc_clean}"

    # Pattern: cesar_default_*
    if last.startswith("cesar_default_"):
        desc = last.replace("cesar_default_", "").replace("_", " ").title()
        cat = CONSTRUCTION_LABELS.get(category_seg, "")
        return f"{cat} {desc}".strip() if cat else desc

    # Fallback
    return last.replace("_", " ").title()


def auto_detect_zones(cesarp):
    """
    Find all zones and build zone name mapping.
    CESAR-P pattern: ZoneFloor{N} to FLOOR{N}:ZONE0
    Also handles unknown zone names by keeping them.
    """
    zone_map = {}
    for obj in cesarp.get_objects("ZONE"):
        old = obj.name
        m = re.match(r"ZoneFloor(\d+)", old)
        if m:
            floor_num = m.group(1)
            zone_map[old] = f"FLOOR{floor_num}:ZONE0"
        else:
            zone_map[old] = old
    return zone_map


def rename_surface(name, zone_map):
    for old_z, new_z in zone_map.items():
        if name.startswith(old_z):
            return new_z + name[len(old_z):]
    return name


# -- Section extractors (generic) --

def extract_materials(cesarp, mapper):
    result = []
    for otype, pascal in [("MATERIAL", "Material"), ("MATERIAL:AIRGAP", "Material:AirGap")]:
        for obj in cesarp.get_objects(otype):
            new_obj = copy.deepcopy(obj)
            old_name = obj.name
            new_name = auto_rename_material(old_name)
            mapper.add(old_name, new_name, "Material", pascal)
            new_obj.name = new_name
            new_obj.obj_type = pascal
            result.append(new_obj)
    return result


def extract_glazing(cesarp, mapper):
    result = []
    for otype, pascal in [
        ("WINDOWMATERIAL:GLAZING", "WindowMaterial:Glazing"),
        ("WINDOWMATERIAL:GAS", "WindowMaterial:Gas"),
        ("WINDOWMATERIAL:SHADE", "WindowMaterial:Shade"),
    ]:
        for obj in cesarp.get_objects(otype):
            new_obj = copy.deepcopy(obj)
            old_name = obj.name
            new_name = auto_rename_material(old_name)
            mapper.add(old_name, new_name, "Window Material", pascal)
            new_obj.name = new_name
            new_obj.obj_type = pascal
            result.append(new_obj)
    return result


def extract_constructions(cesarp, mapper):
    result = []
    for obj in cesarp.get_objects("CONSTRUCTION"):
        new_obj = copy.deepcopy(obj)
        old_name = obj.name
        new_name = auto_rename_construction(old_name)
        mapper.add(old_name, new_name, "Construction", "Construction")
        new_obj.name = new_name
        new_obj.obj_type = "Construction"
        for i in range(1, len(new_obj.fields)):
            old_layer = new_obj.fields[i].value.strip()
            new_layer = mapper.get(old_layer)
            if old_layer != new_layer:
                new_obj.fields[i].value = new_layer
            else:
                # layer might not be mapped yet if order differs; try auto-rename
                auto = auto_rename_material(old_layer)
                if auto != old_layer:
                    mapper.add(old_layer, auto, "Construction Layer", "")
                    new_obj.fields[i].value = auto
        result.append(new_obj)
    return result


def extract_geometry(cesarp, mapper, zone_map):
    result = []
    for obj in cesarp.get_objects("ZONE"):
        new_obj = copy.deepcopy(obj)
        old_name = obj.name
        new_name = zone_map.get(old_name, old_name)
        mapper.add(old_name, new_name, "Zone", "Zone")
        new_obj.name = new_name
        new_obj.obj_type = "Zone"
        result.append(new_obj)

    for otype, pascal in [
        ("BUILDINGSURFACE:DETAILED", "BuildingSurface:Detailed"),
        ("FENESTRATIONSURFACE:DETAILED", "FenestrationSurface:Detailed"),
    ]:
        for obj in cesarp.get_objects(otype):
            new_obj = copy.deepcopy(obj)
            old_name = obj.name
            new_name = rename_surface(old_name, zone_map)
            mapper.add(old_name, new_name, "Surface", pascal)
            new_obj.name = new_name
            new_obj.obj_type = pascal
            mapper.apply_to_object(new_obj)
            result.append(new_obj)
    return result


def extract_shading(cesarp, mapper):
    result = []
    for obj in cesarp.get_objects("WINDOWSHADINGCONTROL"):
        new_obj = copy.deepcopy(obj)
        new_obj.obj_type = "WindowShadingControl"
        mapper.apply_to_object(new_obj)
        result.append(new_obj)
    for obj in cesarp.get_objects("WINDOWPROPERTY:FRAMEANDDIVIDER"):
        new_obj = copy.deepcopy(obj)
        new_obj.obj_type = "WindowProperty:FrameAndDivider"
        result.append(new_obj)
    return result


def extract_gains(cesarp, mapper, zone_map):
    result = []
    for otype, pascal in [
        ("PEOPLE", "People"), ("LIGHTS", "Lights"),
        ("ELECTRICEQUIPMENT", "ElectricEquipment"),
        ("HOTWATEREQUIPMENT", "HotWaterEquipment"),
        ("ZONEINFILTRATION:DESIGNFLOWRATE", "ZoneInfiltration:DesignFlowRate"),
    ]:
        for obj in cesarp.get_objects(otype):
            new_obj = copy.deepcopy(obj)
            new_obj.obj_type = pascal
            mapper.apply_to_object(new_obj)
            for old_z, new_z in zone_map.items():
                if old_z in new_obj.name:
                    old_gain = new_obj.name
                    new_obj.name = new_obj.name.replace(old_z, new_z)
                    mapper.add(old_gain, new_obj.name, "Internal Gains", pascal)
            result.append(new_obj)
    return result


def extract_ground_temps(cesarp):
    result = []
    types = {
        "SITE:GROUNDTEMPERATURE:BUILDINGSURFACE": "Site:GroundTemperature:BuildingSurface",
        "SITE:GROUNDTEMPERATURE:FCFACTORMETHOD": "Site:GroundTemperature:FCfactorMethod",
        "SITE:GROUNDTEMPERATURE:SHALLOW": "Site:GroundTemperature:Shallow",
        "SITE:GROUNDTEMPERATURE:DEEP": "Site:GroundTemperature:Deep",
    }
    for otype, pascal in types.items():
        for obj in cesarp.get_objects(otype):
            new_obj = copy.deepcopy(obj)
            new_obj.obj_type = pascal
            result.append(new_obj)
    return result


def extract_outdoor_air(cesarp, mapper):
    result = []
    for obj in cesarp.get_objects("DESIGNSPECIFICATION:OUTDOORAIR"):
        new_obj = copy.deepcopy(obj)
        new_obj.obj_type = "DesignSpecification:OutdoorAir"
        mapper.apply_to_object(new_obj)
        result.append(new_obj)
    return result


def extract_schedules(cesarp):
    result = []
    for obj in cesarp.get_objects("SCHEDULE:FILE"):
        new_obj = copy.deepcopy(obj)
        new_obj.obj_type = "Schedule:File"
        result.append(new_obj)
    for obj in cesarp.get_objects("SCHEDULE:CONSTANT"):
        new_obj = copy.deepcopy(obj)
        new_obj.obj_type = "Schedule:Constant"
        result.append(new_obj)
    return result


def extract_hvac(cesarp, mapper, zone_map):
    result = []
    for otype, pascal in [
        ("HVACTEMPLATE:THERMOSTAT", "HVACTemplate:Thermostat"),
        ("HVACTEMPLATE:ZONE:IDEALLOADSAIRSYSTEM", "HVACTemplate:Zone:IdealLoadsAirSystem"),
    ]:
        for obj in cesarp.get_objects(otype):
            new_obj = copy.deepcopy(obj)
            new_obj.obj_type = pascal
            mapper.apply_to_object(new_obj)
            for old_z, new_z in zone_map.items():
                if old_z in new_obj.name:
                    new_obj.name = new_obj.name.replace(old_z, new_z)
            result.append(new_obj)
    return result


def extract_outputs(cesarp):
    result = []
    for otype, pascal in [
        ("OUTPUT:VARIABLEDICTIONARY", "Output:VariableDictionary"),
        ("OUTPUT:TABLE:SUMMARYREPORTS", "Output:Table:SummaryReports"),
        ("OUTPUTCONTROL:TABLE:STYLE", "OutputControl:Table:Style"),
        ("OUTPUT:VARIABLE", "Output:Variable"),
        ("OUTPUT:METER", "Output:Meter"),
    ]:
        for obj in cesarp.get_objects(otype):
            new_obj = copy.deepcopy(obj)
            new_obj.obj_type = pascal
            result.append(new_obj)
    return result


def section_comment(title):
    return IDFObject(obj_type="", fields=[],
                     header_comments=["", f"! --- {title} ---", ""])


# -- Assembly --

def convert_single(cesarp_path, nestli_path, output_idf, output_csv):
    """Convert one CESAR-P IDF to Nestli format."""

    basename = os.path.basename(cesarp_path)
    print(f"  Converting: {basename}")

    cesarp = IDFFile.parse(cesarp_path)
    nestli = IDFFile.parse(nestli_path)
    mapper = NameMapper()

    # Auto-detect zones
    zone_map = auto_detect_zones(cesarp)
    n_zones = len(zone_map)
    n_floors = len(set(re.findall(r"ZoneFloor(\d+)", " ".join(zone_map.keys()))))
    print(f"    Detected: {n_zones} zone(s), {n_floors} floor(s)")

    # Detect archetype era from material URIs
    years = set()
    for obj in cesarp.get_objects("MATERIAL"):
        m = re.search(r"/(\d{4})_", obj.name)
        if m:
            years.add(m.group(1))
    era = ", ".join(sorted(years)) if years else "unknown"
    print(f"    Archetype era: {era}")

    # Extract sections
    materials = extract_materials(cesarp, mapper)
    glazing = extract_glazing(cesarp, mapper)
    constructions = extract_constructions(cesarp, mapper)
    geometry = extract_geometry(cesarp, mapper, zone_map)
    shading = extract_shading(cesarp, mapper)
    gains = extract_gains(cesarp, mapper, zone_map)
    ground_temps = extract_ground_temps(cesarp)
    outdoor_air = extract_outdoor_air(cesarp, mapper)
    schedules = extract_schedules(cesarp)
    hvac = extract_hvac(cesarp, mapper, zone_map)
    outputs = extract_outputs(cesarp)

    # Assemble
    out = IDFFile()

    out.objects.append(section_comment("SIMULATION CONTROL (from Nestli template)"))
    out.objects.append(make_object("Version", [(TARGET_EP_VERSION, "Version Identifier")]))

    for otype in ["SIMULATIONCONTROL", "BUILDING", "SHADOWCALCULATION",
                   "HEATBALANCEALGORITHM",
                   "SURFACECONVECTIONALGORITHM:INSIDE",
                   "SURFACECONVECTIONALGORITHM:OUTSIDE",
                   "ZONECAPACITANCEMULTIPLIER:RESEARCHSPECIAL",
                   "ZONEAIRCONTAMINANTBALANCE",
                   "TIMESTEP", "CONVERGENCELIMITS"]:
        for obj in nestli.get_objects(otype):
            out.objects.append(copy.deepcopy(obj))

    out.objects.append(section_comment("RUN PERIOD (from Nestli template)"))
    for otype in ["RUNPERIOD", "RUNPERIODCONTROL:DAYLIGHTSAVINGTIME"]:
        for obj in nestli.get_objects(otype):
            out.objects.append(copy.deepcopy(obj))

    out.objects.append(section_comment("SITE & GROUND TEMPERATURES"))
    for obj in nestli.get_objects("SITE:LOCATION"):
        out.objects.append(copy.deepcopy(obj))
    out.objects.extend(ground_temps)
    for otype in ["SITE:GROUNDREFLECTANCE", "SITE:WATERMAINSTEMPERATURE"]:
        for obj in nestli.get_objects(otype):
            out.objects.append(copy.deepcopy(obj))

    out.objects.append(section_comment("SCHEDULE TYPE LIMITS"))
    for obj in cesarp.get_objects("SCHEDULETYPELIMITS"):
        new_obj = copy.deepcopy(obj)
        new_obj.obj_type = "ScheduleTypeLimits"
        out.objects.append(new_obj)

    out.objects.append(section_comment("SCHEDULES (from CESAR-P)"))
    out.objects.extend(schedules)

    out.objects.append(section_comment("MATERIALS (from CESAR-P)"))
    out.objects.extend(materials)

    out.objects.append(section_comment("WINDOW MATERIALS (from CESAR-P)"))
    out.objects.extend(glazing)

    out.objects.append(section_comment("CONSTRUCTIONS (from CESAR-P)"))
    out.objects.extend(constructions)

    out.objects.append(section_comment("GEOMETRY (from CESAR-P)"))
    out.objects.extend(geometry)

    out.objects.append(section_comment("WINDOW SHADING & FRAME (from CESAR-P)"))
    out.objects.extend(shading)

    out.objects.append(section_comment("INTERNAL GAINS (from CESAR-P)"))
    out.objects.extend(gains)

    out.objects.append(section_comment("OUTDOOR AIR (from CESAR-P)"))
    out.objects.extend(outdoor_air)

    out.objects.append(section_comment("HVAC (from CESAR-P, placeholder)"))
    out.objects.extend(hvac)

    out.objects.append(section_comment("SIZING (from Nestli template)"))
    for otype in ["SIZING:PARAMETERS", "SIZINGPERIOD:DESIGNDAY"]:
        for obj in nestli.get_objects(otype):
            out.objects.append(copy.deepcopy(obj))

    out.objects.append(section_comment("OUTPUT VARIABLES & METERS"))
    out.objects.extend(outputs)

    # Global cross-reference pass
    rename_count = 0
    for obj in out.objects:
        for fld in obj.fields:
            old_val = fld.value.strip()
            new_val = mapper.get(old_val)
            if new_val != old_val:
                fld.value = new_val
                rename_count += 1

    # Write IDF
    os.makedirs(os.path.dirname(output_idf), exist_ok=True)
    out.write(output_idf, style="nestli")

    # Write CSV
    n_csv = mapper.write_csv(output_csv)

    final = IDFFile.parse(output_idf)
    print(f"    Output: {len(final.objects)} objects, {len(final.get_types())} types")
    print(f"    Mapped: {len(mapper.map)} names, {rename_count} cross-refs")
    print(f"    CSV:    {n_csv} rows -> {os.path.basename(output_csv)}")
    print()


def main():
    parser = argparse.ArgumentParser(description="CESAR-P to Nestli IDF converter")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--cesarp", help="Single CESAR-P IDF file")
    group.add_argument("--batch", help="Folder of CESAR-P IDF files")
    parser.add_argument("--nestli", default=NESTLI_IDF, help="Nestli template IDF")
    parser.add_argument("--outdir", default=OUTPUT_DIR, help="Output directory")
    args = parser.parse_args()

    if args.cesarp:
        # Single file mode
        stem = os.path.splitext(os.path.basename(args.cesarp))[0]
        out_idf = os.path.join(args.outdir, f"{stem}_nestli.idf")
        out_csv = os.path.join(args.outdir, f"{stem}_mapping.csv")
        convert_single(args.cesarp, args.nestli, out_idf, out_csv)

    elif args.batch:
        # Batch mode
        idf_files = sorted(glob.glob(os.path.join(args.batch, "*.idf")))
        if not idf_files:
            print(f"No .idf files found in {args.batch}")
            return
        print(f"Batch mode: {len(idf_files)} file(s) in {args.batch}")
        print()
        for idf_path in idf_files:
            stem = os.path.splitext(os.path.basename(idf_path))[0]
            out_idf = os.path.join(args.outdir, f"{stem}_nestli.idf")
            out_csv = os.path.join(args.outdir, f"{stem}_mapping.csv")
            try:
                convert_single(idf_path, args.nestli, out_idf, out_csv)
            except Exception as e:
                print(f"    ERROR: {e}")
                print()


if __name__ == "__main__":
    main()
