"""
idf_parser.py
Parses and writes EnergyPlus IDF files.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from collections import OrderedDict


@dataclass
class IDFField:
    value: str
    comment: str = ""
    is_last: bool = False


@dataclass
class IDFObject:
    obj_type: str
    fields: List[IDFField] = field(default_factory=list)
    header_comments: List[str] = field(default_factory=list)

    @property
    def type_upper(self) -> str:
        return self.obj_type.upper().replace(" ", "")

    @property
    def name(self) -> str:
        return self.fields[0].value.strip() if self.fields else ""

    @name.setter
    def name(self, val: str):
        if self.fields:
            self.fields[0].value = val

    def get_field(self, index: int) -> Optional[str]:
        if 0 <= index < len(self.fields):
            return self.fields[index].value.strip()
        return None

    def set_field(self, index: int, value: str):
        if 0 <= index < len(self.fields):
            self.fields[index].value = value


class IDFFile:

    def __init__(self):
        self.objects: List[IDFObject] = []
        self.header_comments: List[str] = []
        self.version: str = ""

    @classmethod
    def parse(cls, filepath: str) -> "IDFFile":
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return cls.parse_string(content)

    @classmethod
    def parse_string(cls, content: str) -> "IDFFile":
        idf = cls()
        content = content.replace("\r\n", "\n").replace("\r", "\n")

        pending_comments = []
        current_obj_type = None
        current_fields = []
        current_header = []

        for line in content.split("\n"):
            stripped = line.strip()

            if stripped.startswith("!"):
                pending_comments.append(stripped)
                continue
            if not stripped:
                if current_obj_type is None:
                    pending_comments.append("")
                continue

            if current_obj_type is None:
                if "," not in stripped and ";" not in stripped:
                    pending_comments.append(stripped)
                    continue

                sep_pos = len(stripped)
                for ch in [",", ";"]:
                    p = stripped.find(ch)
                    if p >= 0:
                        sep_pos = min(sep_pos, p)

                obj_type = stripped[:sep_pos].strip()
                remainder = stripped[sep_pos:]

                if not obj_type or obj_type.startswith("!"):
                    pending_comments.append(stripped)
                    continue

                current_obj_type = obj_type
                current_header = list(pending_comments)
                pending_comments = []
                current_fields = []

                if remainder.startswith(","):
                    remainder = remainder[1:]
                    if remainder.strip():
                        _parse_field_part(remainder, current_fields)

                if ";" in stripped[sep_pos:]:
                    obj = IDFObject(obj_type=current_obj_type,
                                    fields=current_fields,
                                    header_comments=current_header)
                    if current_fields:
                        current_fields[-1].is_last = True
                    idf.objects.append(obj)
                    current_obj_type = None
                    current_fields = []
                    current_header = []
                continue

            _parse_field_part(stripped, current_fields)

            if ";" in stripped:
                obj = IDFObject(obj_type=current_obj_type,
                                fields=current_fields,
                                header_comments=current_header)
                if current_fields:
                    current_fields[-1].is_last = True
                idf.objects.append(obj)
                current_obj_type = None
                current_fields = []
                current_header = []

        if idf.objects:
            idf.header_comments = idf.objects[0].header_comments
        for obj in idf.objects:
            if obj.type_upper == "VERSION":
                idf.version = obj.name
                break

        return idf

    def get_objects(self, obj_type: str) -> List[IDFObject]:
        key = obj_type.upper().replace(" ", "")
        return [o for o in self.objects if o.type_upper == key]

    def get_first(self, obj_type: str) -> Optional[IDFObject]:
        objs = self.get_objects(obj_type)
        return objs[0] if objs else None

    def get_types(self) -> Dict[str, int]:
        counts = OrderedDict()
        for o in self.objects:
            counts[o.type_upper] = counts.get(o.type_upper, 0) + 1
        return counts

    def remove_objects(self, obj_type: str):
        key = obj_type.upper().replace(" ", "")
        self.objects = [o for o in self.objects if o.type_upper != key]

    def replace_objects(self, obj_type: str, new_objects: List[IDFObject]):
        key = obj_type.upper().replace(" ", "")
        new_list = []
        inserted = False
        for o in self.objects:
            if o.type_upper == key:
                if not inserted:
                    new_list.extend(new_objects)
                    inserted = True
            else:
                new_list.append(o)
        if not inserted:
            new_list.extend(new_objects)
        self.objects = new_list

    def write(self, filepath: str, style: str = "nestli"):
        with open(filepath, "w", encoding="utf-8", newline="\n") as f:
            f.write(self.to_string(style))

    def to_string(self, style: str = "nestli") -> str:
        lines = []
        for obj in self.objects:
            for c in obj.header_comments:
                lines.append(c if c else "")
            if not obj.fields:
                if not obj.obj_type:
                    continue
                lines.append(f"{obj.obj_type};")
                lines.append("")
                continue

            type_str = obj.obj_type
            if style == "nestli":
                type_str = _to_pascal_case(obj.obj_type)
            elif style == "cesarp":
                type_str = obj.obj_type.upper()

            lines.append(f"{type_str},")
            for i, fld in enumerate(obj.fields):
                sep = ";" if i == len(obj.fields) - 1 else ","
                if fld.comment:
                    lines.append(f"    {fld.value}{sep}    !- {fld.comment}")
                else:
                    lines.append(f"    {fld.value}{sep}")
            lines.append("")
        return "\n".join(lines) + "\n"


PASCAL_MAP = {
    "VERSION": "Version", "SIMULATIONCONTROL": "SimulationControl",
    "BUILDING": "Building", "SHADOWCALCULATION": "ShadowCalculation",
    "TIMESTEP": "Timestep", "CONVERGENCELIMITS": "ConvergenceLimits",
    "RUNPERIOD": "RunPeriod",
    "RUNPERIODCONTROL:DAYLIGHTSAVINGTIME": "RunPeriodControl:DaylightSavingTime",
    "SITE:LOCATION": "Site:Location",
    "SITE:GROUNDTEMPERATURE:BUILDINGSURFACE": "Site:GroundTemperature:BuildingSurface",
    "SITE:GROUNDTEMPERATURE:FCFACTORMETHOD": "Site:GroundTemperature:FCfactorMethod",
    "SITE:GROUNDTEMPERATURE:SHALLOW": "Site:GroundTemperature:Shallow",
    "SITE:GROUNDTEMPERATURE:DEEP": "Site:GroundTemperature:Deep",
    "SITE:GROUNDREFLECTANCE": "Site:GroundReflectance",
    "SITE:WATERMAINSTEMPERATURE": "Site:WaterMainsTemperature",
    "SCHEDULETYPELIMITS": "ScheduleTypeLimits",
    "SCHEDULE:COMPACT": "Schedule:Compact", "SCHEDULE:CONSTANT": "Schedule:Constant",
    "SCHEDULE:FILE": "Schedule:File", "SCHEDULE:DAY:HOURLY": "Schedule:Day:Hourly",
    "SCHEDULE:WEEK:DAILY": "Schedule:Week:Daily",
    "MATERIAL": "Material", "MATERIAL:NOMASS": "Material:NoMass",
    "MATERIAL:AIRGAP": "Material:AirGap",
    "MATERIAL:INFRAREDTRANSPARENT": "Material:InfraredTransparent",
    "WINDOWMATERIAL:GLAZING": "WindowMaterial:Glazing",
    "WINDOWMATERIAL:GAS": "WindowMaterial:Gas",
    "WINDOWMATERIAL:SHADE": "WindowMaterial:Shade",
    "CONSTRUCTION": "Construction", "GLOBALGEOMETRYRULES": "GlobalGeometryRules",
    "ZONE": "Zone",
    "ZONEAIRHEATBALANCEALGORITHM": "ZoneAirHeatBalanceAlgorithm",
    "ZONECAPACITANCEMULTIPLIER:RESEARCHSPECIAL": "ZoneCapacitanceMultiplier:ResearchSpecial",
    "ZONEAIRCONTAMINANTBALANCE": "ZoneAirContaminantBalance",
    "BUILDINGSURFACE:DETAILED": "BuildingSurface:Detailed",
    "FENESTRATIONSURFACE:DETAILED": "FenestrationSurface:Detailed",
    "WINDOWSHADINGCONTROL": "WindowShadingControl",
    "WINDOWPROPERTY:FRAMEANDDIVIDER": "WindowProperty:FrameAndDivider",
    "PEOPLE": "People", "LIGHTS": "Lights",
    "ELECTRICEQUIPMENT": "ElectricEquipment", "HOTWATEREQUIPMENT": "HotWaterEquipment",
    "WATERUSE:EQUIPMENT": "WaterUse:Equipment",
    "WATERUSE:CONNECTIONS": "WaterUse:Connections",
    "ZONEINFILTRATION:DESIGNFLOWRATE": "ZoneInfiltration:DesignFlowRate",
    "ZONECONTROL:THERMOSTAT": "ZoneControl:Thermostat",
    "THERMOSTATSETPOINT:DUALSETPOINT": "ThermostatSetpoint:DualSetpoint",
    "HVACTEMPLATE:THERMOSTAT": "HVACTemplate:Thermostat",
    "HVACTEMPLATE:ZONE:IDEALLOADSAIRSYSTEM": "HVACTemplate:Zone:IdealLoadsAirSystem",
    "DESIGNSPECIFICATION:OUTDOORAIR": "DesignSpecification:OutdoorAir",
    "DESIGNSPECIFICATION:ZONEAIRDISTRIBUTION": "DesignSpecification:ZoneAirDistribution",
    "SIZING:ZONE": "Sizing:Zone", "SIZING:SYSTEM": "Sizing:System",
    "SIZING:PLANT": "Sizing:Plant", "SIZING:PARAMETERS": "Sizing:Parameters",
    "SIZINGPERIOD:DESIGNDAY": "SizingPeriod:DesignDay",
    "AIRLOOPHVAC": "AirLoopHVAC",
    "AIRLOOPHVAC:SUPPLYPATH": "AirLoopHVAC:SupplyPath",
    "AIRLOOPHVAC:RETURNPATH": "AirLoopHVAC:ReturnPath",
    "AIRLOOPHVAC:ZONESPLITTER": "AirLoopHVAC:ZoneSplitter",
    "AIRLOOPHVAC:ZONEMIXER": "AirLoopHVAC:ZoneMixer",
    "AIRLOOPHVAC:OUTDOORAIRSYSTEM": "AirLoopHVAC:OutdoorAirSystem",
    "AIRLOOPHVAC:CONTROLLERLIST": "AirLoopHVAC:ControllerList",
    "AIRLOOPHVAC:OUTDOORAIRSYSTEM:EQUIPMENTLIST": "AirLoopHVAC:OutdoorAirSystem:EquipmentList",
    "AIRLOOPHVAC:UNITARYHEATPUMP:AIRTOAIR": "AirLoopHVAC:UnitaryHeatPump:AirToAir",
    "AIRTERMINAL:SINGLEDUCT:CONSTANTVOLUME:NOREHEAT": "AirTerminal:SingleDuct:ConstantVolume:NoReheat",
    "ZONEHVAC:EQUIPMENTCONNECTIONS": "ZoneHVAC:EquipmentConnections",
    "ZONEHVAC:EQUIPMENTLIST": "ZoneHVAC:EquipmentList",
    "ZONEHVAC:AIRDISTRIBUTIONUNIT": "ZoneHVAC:AirDistributionUnit",
    "COIL:COOLING:DX:SINGLESPEED": "Coil:Cooling:DX:SingleSpeed",
    "COIL:HEATING:DX:SINGLESPEED": "Coil:Heating:DX:SingleSpeed",
    "COIL:HEATING:ELECTRIC": "Coil:Heating:Electric",
    "FAN:ONOFF": "Fan:OnOff", "FAN:ZONEEXHAUST": "Fan:ZoneExhaust",
    "CONTROLLER:OUTDOORAIR": "Controller:OutdoorAir",
    "OUTDOORAIR:MIXER": "OutdoorAir:Mixer",
    "OUTDOORAIR:NODELIST": "OutdoorAir:NodeList",
    "SETPOINTMANAGER:SCHEDULED": "SetpointManager:Scheduled",
    "AVAILABILITYMANAGER:HYBRIDVENTILATION": "AvailabilityManager:HybridVentilation",
    "AVAILABILITYMANAGER:SCHEDULED": "AvailabilityManager:Scheduled",
    "AVAILABILITYMANAGERASSIGNMENTLIST": "AvailabilityManagerAssignmentList",
    "BRANCH": "Branch", "BRANCHLIST": "BranchList",
    "CONNECTOR:SPLITTER": "Connector:Splitter",
    "CONNECTOR:MIXER": "Connector:Mixer", "CONNECTORLIST": "ConnectorList",
    "PIPE:ADIABATIC": "Pipe:Adiabatic", "NODELIST": "NodeList",
    "PLANTLOOP": "PlantLoop", "WATERHEATER:MIXED": "WaterHeater:Mixed",
    "WATERHEATER:SIZING": "WaterHeater:Sizing",
    "DAYLIGHTING:CONTROLS": "Daylighting:Controls",
    "DAYLIGHTING:REFERENCEPOINT": "Daylighting:ReferencePoint",
    "CURVE:BIQUADRATIC": "Curve:Biquadratic", "CURVE:CUBIC": "Curve:Cubic",
    "CURVE:QUADRATIC": "Curve:Quadratic", "CURVE:QUARTIC": "Curve:Quartic",
    "CURVE:LINEAR": "Curve:Linear", "CURVE:EXPONENT": "Curve:Exponent",
    "EXTERNALINTERFACE": "ExternalInterface",
    "EXTERNALINTERFACE:FUNCTIONALMOCKUPUNITEXPORT:TO:SCHEDULE": "ExternalInterface:FunctionalMockupUnitExport:To:Schedule",
    "EXTERNALINTERFACE:FUNCTIONALMOCKUPUNITEXPORT:FROM:VARIABLE": "ExternalInterface:FunctionalMockupUnitExport:From:Variable",
    "FUNCTIONALMOCKUPUNITEXPORT": "FunctionalMockupUnitExport",
    "AIRFLOWNETWORK:SIMULATIONCONTROL": "AirflowNetwork:SimulationControl",
    "AIRFLOWNETWORK:MULTIZONE:ZONE": "AirflowNetwork:MultiZone:Zone",
    "AIRFLOWNETWORK:MULTIZONE:SURFACE": "AirflowNetwork:MultiZone:Surface",
    "AIRFLOWNETWORK:MULTIZONE:SURFACE:CRACK": "AirflowNetwork:MultiZone:Surface:Crack",
    "AIRFLOWNETWORK:MULTIZONE:EXTERNALNODE": "AirflowNetwork:MultiZone:ExternalNode",
    "AIRFLOWNETWORK:MULTIZONE:REFERENCECRACKCONDITIONS": "AirflowNetwork:MultiZone:ReferenceCrackConditions",
    "AIRFLOWNETWORK:MULTIZONE:WINDPRESSURECOEFFICIENTARRAY": "AirflowNetwork:MultiZone:WindPressureCoefficientArray",
    "AIRFLOWNETWORK:MULTIZONE:WINDPRESSURECOEFFICIENTVALUES": "AirflowNetwork:MultiZone:WindPressureCoefficientValues",
    "AIRFLOWNETWORK:MULTIZONE:COMPONENT:DETAILEDOPENING": "AirflowNetwork:MultiZone:Component:DetailedOpening",
    "AIRFLOWNETWORK:MULTIZONE:COMPONENT:ZONEEXHAUSTFAN": "AirflowNetwork:MultiZone:Component:ZoneExhaustFan",
    "HEATBALANCEALGORITHM": "HeatBalanceAlgorithm",
    "SURFACECONVECTIONALGORITHM:INSIDE": "SurfaceConvectionAlgorithm:Inside",
    "SURFACECONVECTIONALGORITHM:OUTSIDE": "SurfaceConvectionAlgorithm:Outside",
    "OUTPUT:VARIABLE": "Output:Variable", "OUTPUT:METER": "Output:Meter",
    "OUTPUT:VARIABLEDICTIONARY": "Output:VariableDictionary",
    "OUTPUT:TABLE:SUMMARYREPORTS": "Output:Table:SummaryReports",
    "OUTPUT:SURFACES:DRAWING": "Output:Surfaces:Drawing",
    "OUTPUT:SURFACES:LIST": "Output:Surfaces:List",
    "OUTPUT:CONSTRUCTIONS": "Output:Constructions",
    "OUTPUT:DAYLIGHTFACTORS": "Output:DaylightFactors",
    "OUTPUT:ENERGYMANAGEMENTSYSTEM": "Output:EnergyManagementSystem",
    "OUTPUT:DIAGNOSTICS": "Output:Diagnostics",
    "OUTPUT:ENVIRONMENTALIMPACTFACTORS": "Output:EnvironmentalImpactFactors",
    "OUTPUTCONTROL:TABLE:STYLE": "OutputControl:Table:Style",
    "OUTPUTCONTROL:ILLUMINANCEMAP:STYLE": "OutputControl:IlluminanceMap:Style",
    "OUTPUTCONTROL:REPORTINGTOLERANCES": "OutputControl:ReportingTolerances",
    "ENVIRONMENTALIMPACTFACTORS": "EnvironmentalImpactFactors",
    "CURRENCYTYPE": "CurrencyType",
}


def _to_pascal_case(obj_type: str) -> str:
    key = obj_type.upper().replace(" ", "")
    if key in PASCAL_MAP:
        return PASCAL_MAP[key]
    return ":".join(p.strip().title() for p in obj_type.split(":"))


def _parse_field_part(text: str, fields: List[IDFField]):
    remaining = text
    while remaining:
        remaining = remaining.strip()
        if not remaining or remaining.startswith("!"):
            break
        comma_pos = remaining.find(",")
        semi_pos = remaining.find(";")

        if comma_pos < 0 and semi_pos < 0:
            if "!" in remaining:
                parts = remaining.split("!", 1)
                val = parts[0].strip()
                comment = parts[1].strip().lstrip("-").strip()
                if val:
                    fields.append(IDFField(value=val, comment=comment))
            elif remaining.strip():
                fields.append(IDFField(value=remaining.strip()))
            break

        if comma_pos >= 0 and (semi_pos < 0 or comma_pos < semi_pos):
            sep_pos, is_last = comma_pos, False
        else:
            sep_pos, is_last = semi_pos, True

        before = remaining[:sep_pos].strip()
        after = remaining[sep_pos + 1:].strip()
        comment = ""
        if "!" in after:
            cp = after.find("!")
            comment = after[cp + 1:].strip().lstrip("-").strip()
            after = after[:cp].strip()
        val = before
        if "!" in val:
            val = val.split("!", 1)[0].strip()

        fields.append(IDFField(value=val, comment=comment, is_last=is_last))
        if is_last:
            break
        remaining = after


def make_field(value, comment="", is_last=False):
    return IDFField(value=str(value), comment=comment, is_last=is_last)


def make_object(obj_type, fields, header_comments=None):
    flds = []
    for i, (val, cmt) in enumerate(fields):
        flds.append(IDFField(value=str(val), comment=cmt,
                             is_last=(i == len(fields) - 1)))
    return IDFObject(obj_type=obj_type, fields=flds,
                     header_comments=header_comments or [])
