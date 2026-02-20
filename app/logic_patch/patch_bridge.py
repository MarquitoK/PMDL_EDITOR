class PatchBridge:
    """Sincronizar datos entre PMDL Editor y Character Editor"""
    
    def __init__(self):
        self.patch_context = {
            'is_from_patch': False,
            'patch_path': None,
            'patch_analyzer': None,
            'is_secondary': False,
            'has_unsaved_changes': False
        }
    
    def set_patch_context(self, patch_path, patch_analyzer, is_secondary=False):
        """Establece el contexto del parche."""
        self.patch_context['is_from_patch'] = True
        self.patch_context['patch_path'] = patch_path
        self.patch_context['patch_analyzer'] = patch_analyzer
        self.patch_context['is_secondary'] = is_secondary
        self.patch_context['has_unsaved_changes'] = False
    
    def clear_patch_context(self):
        """Limpia el contexto del parche."""
        self.patch_context['is_from_patch'] = False
        self.patch_context['patch_path'] = None
        self.patch_context['patch_analyzer'] = None
        self.patch_context['is_secondary'] = False
        self.patch_context['has_unsaved_changes'] = False
    
    def extract_pmdl_from_patch(self, patch_analyzer):
        """Extrae el PMDL del parche"""
        if not patch_analyzer or not patch_analyzer.pmdl_info:
            return None
        
        return patch_analyzer.get_pmdl_data()
    
    def update_pmdl_in_patch(self, pmdl_data):
        """Actualiza el PMDL en el parche con los datos modificados"""
        if not self.patch_context['is_from_patch']:
            return False
        
        analyzer = self.patch_context['patch_analyzer']
        if not analyzer:
            return False
        
        success = analyzer.set_pmdl_data(pmdl_data)
        if success:
            self.patch_context['has_unsaved_changes'] = True
        
        return success
    
    def is_from_patch(self):
        """Verifica si el PMDL actual viene de un parche."""
        return self.patch_context['is_from_patch']
    
    def is_secondary_patch(self):
        """Verifica si es un parche secundario."""
        return self.patch_context['is_secondary']
    
    def get_patch_analyzer(self):
        """Obtiene el analizador de parche actual."""
        return self.patch_context['patch_analyzer']
    
    def get_patch_path(self):
        """Obtiene la ruta del parche actual."""
        return self.patch_context['patch_path']
    
    def has_unsaved_changes(self):
        """Verifica si hay cambios sin guardar."""
        return self.patch_context['has_unsaved_changes']
    
    def mark_saved(self):
        """Marca el parche como guardado."""
        self.patch_context['has_unsaved_changes'] = False
    
    def has_patch_context(self):
        """Verifica si hay un contexto de parche activo."""
        return self.patch_context['is_from_patch']
    
    def extract_texture_temp(self):
        """Extrae la textura del parche a un archivo temporal y retorna su ruta."""
        if not self.patch_context['is_from_patch']:
            return None
        
        analyzer = self.patch_context['patch_analyzer']
        if not analyzer:
            return None
        
        # Intentar extraer la textura del analyzer
        try:
            import tempfile
            import os
            
            # Obtener datos de textura del analyzer
            texture_data = analyzer.get_texture_data()
            if not texture_data:
                return None
            
            # Crear archivo temporal
            with tempfile.NamedTemporaryFile(mode='wb', suffix='.png', delete=False) as tmp:
                tmp.write(texture_data)
                return tmp.name
        except Exception as e:
            print(f"Error extrayendo textura: {e}")
            return None