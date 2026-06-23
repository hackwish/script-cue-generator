# Script Cue Creator

Este script en Python permite generar de forma interactiva un archivo `.cue` faltante para un archivo de audio sin dividir (como un disco completo en un solo archivo FLAC, MP3, WAV, etc.), buscando los metadatos y la lista de pistas en la base de datos de **MusicBrainz**.

Una vez generado el archivo `.cue`, puedes usar herramientas estándar en la terminal para dividir el archivo de audio original en sus pistas independientes con sus nombres correspondientes.

## Requisitos Previos

Asegúrate de tener instalados los siguientes paquetes en tu sistema Linux:

```bash
# Para audio en formato FLAC:
sudo apt install cuetools shntool flac

# Para audio en formato MP3 (permite dividir sin perder calidad):
sudo apt install mp3splt
```

## Instalación y Configuración

El script requiere de un entorno virtual de Python con las dependencias `musicbrainzngs` y `mutagen`.

Para inicializar el entorno e instalar las dependencias:

```bash
# Crear entorno virtual
python3 -m venv .venv

# Instalar dependencias
.venv/bin/pip install -r requirements.txt
```

## Uso del Script

Puedes ejecutar el script directamente usando el ejecutable o a través del entorno virtual de Python:

```bash
./create_cue.py [opciones]
# o
.venv/bin/python create_cue.py [opciones]
```

### Opciones Disponibles

- `-f`, `--file` (opcional): Ruta del archivo de audio original (FLAC, MP3, WAV, M4A). Si se omite, el script escaneará el directorio actual. Si encuentra un único archivo de audio, lo usará; si encuentra varios, te dará a elegir.
- `-a`, `--artist` (opcional): Nombre del artista para la búsqueda. Si se omite, intentará leerlo de los metadatos del archivo.
- `-l`, `--album` (opcional): Nombre del álbum para la búsqueda. Si se omite, intentará leerlo de los metadatos del archivo.
- `-i`, `--mbid` (opcional): ID de lanzamiento (UUID) de MusicBrainz. Permite saltarse la búsqueda general y obtener directamente los datos exactos del álbum.
- `-o`, `--output` (opcional): Ruta para el archivo `.cue` resultante (por defecto tiene el mismo nombre que el archivo de audio con extensión `.cue`).

### Flujo de Funcionamiento

1. **Lectura de Audio**: El script escanea el archivo de audio seleccionado y extrae cualquier etiqueta existente (Artista, Álbum, ID de MusicBrainz) para pre-rellenar la búsqueda.
2. **Búsqueda**: Si falta información o deseas afinar los resultados, puedes buscar interactivamente en la base de datos de MusicBrainz.
3. **Selección**: Si existen múltiples coincidencias, el script te presentará una lista de opciones que incluye el título del álbum, año de lanzamiento, cantidad de pistas, cantidad de discos (medios) y descripción para que selecciones el correcto.
4. **Múltiples Discos**: Si el lanzamiento seleccionado consta de varios CD/discos, te preguntará a cuál de ellos corresponde el archivo de audio actual.
5. **Cálculo de Tiempos**: Obtiene las duraciones exactas de cada pista y calcula la marca de tiempo acumulativa (`INDEX 01`) para cada una.
6. **Validación**: Compara la duración total calculada con la duración real del archivo de audio. Si hay desalineación te advertirá.
7. **Escritura**: Escribe el archivo `.cue` con soporte UTF-8.

---

## Cómo Dividir las Pistas (Split)

Una vez que el archivo `.cue` haya sido generado correctamente, puedes ejecutar los siguientes comandos para dividir el audio:

### Para archivos FLAC

Usa `shnsplit` para dividir las pistas:

```bash
cuebreakpoints "album.cue" | shnsplit -f "album.cue" -t "%n-%t" -o flac "album.flac"
```

*Nota: Reemplaza `album.cue` y `album.flac` con los nombres reales de tus archivos.*

#### Copiar las etiquetas de metadatos (Tags)
`shnsplit` dividirá el archivo de audio pero las pistas individuales creadas carecerán de metadatos/tags (artista, título, etc.). Para copiar los tags desde el archivo `.cue` a las nuevas pistas FLAC, ejecuta:

```bash
cuetag "album.cue" [0-9]*.flac
```

### Para archivos MP3

Para archivos MP3 es mucho mejor usar `mp3splt` ya que realiza el corte de forma nativa sin decodificar ni re-codificar (evitando pérdida de calidad por compresión):

```bash
mp3splt -c "album.cue" "album.mp3"
```
*(Este comando divide las pistas y automáticamente les asigna los metadatos desde el archivo CUE).*
