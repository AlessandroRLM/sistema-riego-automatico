# Riego automático con panel web

Sistema de riego con Arduino Uno: un sensor de humedad de suelo decide cuándo regar con una bomba (relé), y un panel web local permite simular la humedad, forzar la bomba y ver el sensor real.

## Integrantes

- Nicolás Salinas
- Antonia Cuba
- Alessandro Lopez

## Contenido

| Archivo | Descripción |
|---|---|
| `sensor_humedad.ino` | Sketch del Arduino (control de la bomba y comandos por serie) |
| `app.py` | Servidor web local (Python, sin dependencias externas) |
| `index.html` | Interfaz del panel (la misma que está incrustada en `app.py`) |
| `toggle.sh` | Enciende el panel si está apagado y lo apaga si está encendido |

## Hardware

| Componente | Pin |
|---|---|
| Sensor de humedad (salida analógica) | A0 |
| Relé de la bomba | D6 (activo en `LOW`) |
| LED | D8 |
| Buzzer | D9 |

## Cómo riega

La humedad se calcula con la calibración `SECO = 305` y `MOJADO = 33`, y se convierte a porcentaje.

1. Si la humedad baja de **35 %**, la bomba se enciende **5 s**.
2. Se apaga **5 s** para que el agua llegue al sensor.
3. Si la humedad sigue bajo **55 %**, da otro pulso de 5 s, y así hasta llegar a 55 %.
4. Si llega a 55 % durante un pulso, apaga de inmediato.

Mientras riega, el LED y el buzzer se activan. El buzzer se puede silenciar desde el panel.

Los valores se ajustan en las constantes del sketch: `UMBRAL_ENCENDER`, `UMBRAL_APAGAR`, `PULSO_MS` y `ESPERA_MS`. El sensor se lee y se informa cada 100 ms.

## Panel web

### Requisitos

- Python 3 (solo biblioteca estándar).
- Linux, porque el puerto serie se configura con `stty`.
- Arduino conectado por USB (`/dev/ttyACM*` o `/dev/ttyUSB*`).

### Uso

```bash
./toggle.sh
```

Enciende el panel y abre `http://localhost:8000`. Si ya está encendido, lo apaga. También se puede lanzar a mano:

```bash
python app.py [puerto_http] [/dev/ttyACM0]
```

### Controles

- **Modo simulado / real** (switch): simulado usa la humedad del slider; real usa el sensor.
- **Slider**: humedad simulada de 0 a 100 %. El Arduino aplica la lógica de riego sobre ese valor.
- **Encender / Apagar**: fuerzan la bomba. El forzado se suelta moviendo el slider o cambiando de modo.
- **Buzzer**: silencia o reactiva el buzzer.
- **Detener lectura**: libera el puerto serie para poder subir el sketch desde el IDE. **Reanudar lectura** lo vuelve a abrir.

## Subir el sketch

1. Pulsa **Detener lectura** en el panel (o apágalo con `./toggle.sh`).
2. Sube `sensor_humedad.ino` desde el Arduino IDE (placa Arduino Uno).
3. Reanuda la lectura o vuelve a encender el panel.

El Monitor Serie del IDE debe estar cerrado: ocupa el puerto y el panel no puede leerlo.

## Comandos serie

El panel manda una línea por comando a 9600 baudios:

| Comando | Efecto |
|---|---|
| `H<n>` | Usa la humedad simulada `n` (0–100) |
| `R` | Vuelve al sensor real |
| `A` | Suelta el forzado de la bomba |
| `1` / `0` | Fuerza la bomba encendida / apagada |
| `S` / `V` | Silencia / reactiva el buzzer |

El Arduino responde con líneas como:

```
raw=316  humedad=0%  estado=REGANDO  modo=REAL  silencio=0
```

## Limitaciones

- No hay autenticación: el servidor escucha solo en `127.0.0.1`.
- Los forzados de Encender y Apagar no respetan los pulsos.
- El panel no guarda historial de lecturas.
