# PMDL Editor

PMDL Editor es una herramienta de escritorio desarrollada en Python para visualizar, editar y gestionar archivos **PMDL**, usados en el modding de modelos para juegos de PSP.

La aplicación está pensada para trabajar de forma **segura**, manipulando los datos en memoria y escribiendo cambios únicamente cuando el usuario decide guardar, evitando corrupciones de offsets y residuos binarios.

---

## Características principales

- Importar y visualizar archivos PMDL
- Edición visual de partes:
  - Capa (ID)
  - Nombre
  - Tamaño (hexadecimal)
  - Opacidad
  - Función (flags)
- Exportar partes individuales (`.tttpart`)
- Importar partes externas
- Eliminar partes con corrección automática de offsets
- Limpieza automática de residuos al final del archivo
- Soporte para **PMDL secundario**:
  - Visualización de partes
  - Transferencia directa de partes al PMDL principal
- Interfaz gráfica hecha con **CustomTkinter**
- Edición completamente en memoria hasta presionar Guardar

---

## Interfaz

La aplicación cuenta con dos paneles:

### Panel principal
- Edición completa del PMDL
- Guardar y Guardar Como
- Importar / eliminar / exportar partes
- Control total de offsets, longitudes y flags

### Panel secundario
- Importación de un PMDL auxiliar
- Visualización de partes (solo lectura)
- Botón **Agregar** para transferir partes al PMDL principal

---

## Requisitos

- Python **3.10 o superior**
- Sistema operativo: Windows (probado)
- Dependencias:
  - customtkinter

---

## Instalación

1. Clonar el repositorio:

git clone https://github.com/tu-usuario/PMDL-Editor.git

2. Entrar al directorio:

cd PMDL-Editor

3. Instalar dependencias:

pip install -r requirements.txt

---

## Uso

Ejecutar la aplicación con:

python "PMDL_EDITOR.py"

---

## Notas técnicas importantes

- Los índices de partes usan bloques fijos de 0x20

- Al importar o eliminar partes:

	- Se corrigen automáticamente todos los offsets afectados

	- Se actualiza el byte de cantidad de partes

	- Se eliminan residuos al final del archivo si existen

- El PMDL no se modifica hasta que el usuario selecciona **Guardar

---

## Público objetivo

- Modders de juegos PSP

- Programadores interesados en formatos binarios

- Herramientas internas de edición de modelos

---

## Autor

Creado por Los ijue30s

Proyecto con fines de modding y aprendizaje.