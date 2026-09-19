from PIL import Image
from pathlib import Path
import tempfile


def reducir_paleta_de_colores(input_file: str, colors: int) -> str:
    input_file = Path(input_file)

    # TEMP de Windows
    temp_dir = Path(tempfile.gettempdir())

    # Archivo de salida
    output_file = temp_dir / f"{input_file.stem}_{colors}_colors.png"

    # Abrir y convertir a RGBA
    img = Image.open(input_file).convert("RGB")

    # Reducir paleta
    img_colors = img.quantize(
        colors=colors,
        method=Image.Quantize.MEDIANCUT
    )

    # Guardar PNG indexado
    img_colors.save(
        output_file,
        format="PNG",
        optimize=False
    )

    return str(output_file)