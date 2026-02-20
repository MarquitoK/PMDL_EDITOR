from .canvas_base import UVCanvasBase
from .canvas_drawing import UVCanvasDrawing
from .canvas_events import UVCanvasEvents
from .canvas_selection import UVCanvasSelection
from .canvas_gmode import UVCanvasGMode
from .canvas_smode import UVCanvasSMode


class UVCanvas(
    UVCanvasBase,
    UVCanvasDrawing,
    UVCanvasEvents,
    UVCanvasSelection,
    UVCanvasGMode,
    UVCanvasSMode
):
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._setup_bindings()


__all__ = ['UVCanvas']