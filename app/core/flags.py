"""
Mapas de flags especiales para las partes del modelo PMDL.
"""

FLAG_MAP_VALUE_TO_LABEL = {
    0x00: "Ninguna",
    0x01: "Equip. 1",
    0x02: "Equip. 2",
    0x06: "Cara",
    0x07: "Ocultable",
}

FLAG_MAP_LABEL_TO_VALUE = {v: k for k, v in FLAG_MAP_VALUE_TO_LABEL.items()}

FLAG_OPTIONS_LABELS = list(FLAG_MAP_LABEL_TO_VALUE.keys())