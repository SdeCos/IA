"""Ajuste visual y reconocimiento con cámara, foto o vídeo como entrada."""

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2

from configuracion import (
    BASE, RUTA_CONFIGURACION, cargar_configuracion,
    configuracion_para_imagen, guardar_configuracion, validar_configuracion,
)
from controles import ControlesPrecisos
from grabacion import Grabacion
from vision import dibujar_resultado, procesar_imagen
from reconocimiento import ReconocedorDirecto, cargar_inventario, dibujar_directo, exportar_predicciones
from reproduccion import ReproductorArchivo
from video import listar_videos, configuracion_para_video, exportar_fotograma

USAR_CAMARA = True
INDICE_CAMARA = 1
RUTA_IMAGEN = "test.jpg"
CARPETA_CAPTURAS = BASE / "capturas"


def guardar_captura(original, encuadre, valores):
    """Guarda fotos limpias y sus ajustes, evitando aplicar el zoom dos veces."""
    CARPETA_CAPTURAS.mkdir(parents=True, exist_ok=True)
    fecha = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    ruta_original = CARPETA_CAPTURAS / f"original_{fecha}.png"
    ruta_escena = CARPETA_CAPTURAS / f"escena_{fecha}.png"
    for ruta, imagen, ajustes in (
        (ruta_original, original, valores),
        (ruta_escena, encuadre, {**valores, "zoom": 100}),
    ):
        if not cv2.imwrite(str(ruta), imagen):
            raise OSError(f"No se pudo guardar {ruta}")
        guardar_configuracion(ajustes, ruta.with_suffix(".json"))
    print(f"Escena guardada: {ruta_escena}\nImagen completa: {ruta_original}", flush=True)
    print("Usa --ultima para abrir la escena con sus ajustes y sin repetir el zoom.", flush=True)
    return ruta_escena, ruta_original


def abrir_camara(indice):
    backend = cv2.CAP_AVFOUNDATION if sys.platform == "darwin" else cv2.CAP_ANY
    print(f"Abriendo cámara {indice}...", flush=True)
    cap = cv2.VideoCapture()
    for intento in range(5):
        if cap.open(indice, backend):
            print(f"Cámara abierta con {cap.getBackendName()}. Esperando imagen...", flush=True)
            return cap
        if intento < 4:
            print("Cámara todavía no disponible; reintentando en 1 segundo...", flush=True)
            time.sleep(1)
    cap.release()
    raise RuntimeError(
        f"No se pudo abrir la cámara {indice}. Prueba otro índice con --camara.\n"
        "Comprueba que el iPhone esté disponible en Photo Booth o FaceTime y revisa "
        "el permiso de Cámara de la aplicación desde la que ejecutas Python."
    )


def finalizar_grabacion(grabacion, *, interrumpida=False, motivo="Tecla R"):
    ruta = grabacion.cerrar(interrumpida=interrumpida, motivo=motivo)
    if ruta is not None:
        print(f"Vídeo guardado: {ruta}", flush=True)
        print("Incluye los ajustes iniciales y el registro de tiempos. Ábrelo en la pestaña Vídeo de la web.", flush=True)
        if grabacion.fotogramas_duplicados:
            print(f"Se repitieron {grabacion.fotogramas_duplicados} fotogramas para conservar la duración real.", flush=True)
        for mensaje in grabacion.avisos:
            print(f"Aviso de grabación: {mensaje}", flush=True)
    return ruta


def main(argv=None):
    parser = argparse.ArgumentParser(description="Captura, calibración y reconocimiento de herramientas sobre tapete.")
    parser.add_argument("--camara", type=int, default=INDICE_CAMARA, metavar="INDICE")
    parser.add_argument("--zoom", type=float, metavar="FACTOR", help="Sobrescribe el zoom guardado (1..3).")
    parser.add_argument("--config", type=Path, help="Configuración JSON; P guarda en este archivo.")
    parser.add_argument("--reconocer", action="store_true", help="Muestra nombres, pistas e inventario por reglas en directo.")
    parser.add_argument("--inventario", type=Path, help="JSON opcional con cantidades esperadas; activa el reconocimiento.")
    fuente = parser.add_mutually_exclusive_group()
    fuente.add_argument("--imagen", type=Path, metavar="RUTA", help="Trabaja sin cámara.")
    fuente.add_argument("--ultima", action="store_true", help="Abre la última escena guardada.")
    fuente.add_argument("--video", type=Path, metavar="RUTA", help="Usa un vídeo como entrada, sin abrir cámara.")
    fuente.add_argument("--ultimo-video", action="store_true", help="Usa el último vídeo guardado como entrada.")
    args = parser.parse_args(argv)
    if args.camara < 0:
        parser.error("El índice de cámara debe ser 0 o mayor.")
    if args.zoom is not None and not 1 <= args.zoom <= 3:
        parser.error("El zoom debe estar entre 1 y 3.")

    ruta_imagen = args.imagen.expanduser() if args.imagen else None
    ruta_video = args.video.expanduser().resolve() if args.video else None
    if args.ultimo_video:
        videos = listar_videos(BASE)
        if not videos:
            parser.error("No hay vídeos guardados. Indica uno con --video RUTA.")
        ruta_video = videos[0]
    if args.ultima:
        capturas = sorted(CARPETA_CAPTURAS.glob("escena_*.png"))
        if not capturas:
            parser.error("Todavía no hay capturas. Abre la cámara y pulsa G.")
        ruta_imagen = capturas[-1]
    elif not USAR_CAMARA and ruta_imagen is None and ruta_video is None:
        ruta_imagen = Path(RUTA_IMAGEN)
    cap = None
    reproductor = None
    controles = None
    grabacion = None
    grabacion_interrumpida = False
    motivo_fin = "Salida del calibrador"
    codigo_salida = 0
    try:
        reconocer = args.reconocer or args.inventario is not None
        reconocedor = ReconocedorDirecto(cargar_inventario(args.inventario)) if reconocer else None
        if ruta_video is not None:
            reproductor = ReproductorArchivo(ruta_video)
            perfil_video = BASE / "videos" / "ajustes" / f"{reproductor.info['huella']}.json"
            valores = (cargar_configuracion(args.config) if args.config else
                       cargar_configuracion(perfil_video) if perfil_video.exists() else
                       configuracion_para_video(ruta_video))
            if args.zoom is not None:
                valores["zoom"] = round(args.zoom * 100)
            valores = validar_configuracion(valores)
            print(f"Vídeo como entrada, sin cámara: {ruta_video}", flush=True)
            print("Espacio = pausar/continuar; R = volver al inicio. Al terminar queda pausado. No se graba otra copia.", flush=True)
        elif ruta_imagen is not None:
            ruta_imagen = ruta_imagen.resolve()
            valores = configuracion_para_imagen(ruta_imagen, args.config, args.zoom)
            imagen_fija = cv2.imread(str(ruta_imagen))
            if imagen_fija is None:
                raise ValueError(f"No se pudo leer la imagen: {ruta_imagen}")
            print(f"Modo foto, sin cámara: {ruta_imagen}", flush=True)
        else:
            valores = cargar_configuracion(args.config)
            if args.zoom is not None:
                valores["zoom"] = round(args.zoom * 100)
            valores = validar_configuracion(valores)
            cap = abrir_camara(args.camara)
        controles = ControlesPrecisos(valores)
        if reconocer:
            print("Reconocimiento automático activo: nombres por reglas, sin entrenamiento. Las predicciones no son etiquetas confirmadas.", flush=True)
        print("Teclas: P = guardar ajustes; E = exportar CSV; G = guardar foto; R = iniciar/parar vídeo (cámara); B = comparar máscara; Q = salir.", flush=True)
        print("Ajustes: clic en un número, escribir y pulsar Enter; botones -/+ para afinar.", flush=True)
        # Al editar una foto, P actualiza sus ajustes asociados: serán los que
        # se recuperen al volver a abrirla. --config explícito siempre prevalece.
        destino_config = args.config or (
            perfil_video if reproductor is not None else
            ruta_imagen.with_suffix(".json") if ruta_imagen is not None else RUTA_CONFIGURACION
        )
        fallo_desde = None
        aviso, aviso_hasta = "", 0.0
        mostrar_sin_limpieza = False
        avisos_anteriores = ()
        anterior_frame = None
        clave_reconocida = None
        while controles.mostrar():
            inicio_iteracion = time.monotonic() if reproductor is not None else None
            valores = controles.valores.copy()
            if reproductor is not None:
                original = reproductor.leer()
            elif cap is not None:
                ret, original = cap.read()
                if not ret:
                    if grabacion is not None:
                        grabacion.sin_imagen()
                    if fallo_desde is None:
                        fallo_desde = time.monotonic()
                        if reconocedor is not None:
                            reconocedor.reiniciar()
                        print("Sin imagen; reintentando durante 5 segundos...", flush=True)
                    if time.monotonic() - fallo_desde >= 5:
                        print("La cámara se abrió, pero no entrega imágenes. Revisa la conexión del iPhone.", flush=True)
                        grabacion_interrumpida = True
                        motivo_fin = "La cámara dejó de entregar imágenes durante 5 segundos."
                        codigo_salida = 1
                        break
                    tecla = cv2.waitKeyEx(1)
                    if not controles.manejar_tecla(tecla):
                        if tecla in (ord("q"), ord("Q")):
                            grabacion_interrumpida = True
                            motivo_fin = "Salida mientras la cámara no entregaba imágenes."
                            break
                        if tecla in (ord("r"), ord("R")) and grabacion is not None:
                            finalizar_grabacion(grabacion, interrumpida=True, motivo="Tecla R durante fallo de cámara")
                            grabacion = None
                    time.sleep(0.1)
                    continue
                fallo_desde = None
                if grabacion is not None:
                    grabacion.agregar(original)
            else:
                original = imagen_fija
            resultado = procesar_imagen(original, valores)
            avisos_actuales = tuple(resultado.get("avisos", []))
            if avisos_actuales != avisos_anteriores:
                for mensaje in avisos_actuales:
                    print(f"Aviso: {mensaje}", flush=True)
                avisos_anteriores = avisos_actuales
            if reconocedor is not None:
                clave = (reproductor.indice, tuple(sorted(valores.items()))) if reproductor is not None else None
                if reproductor is None or clave != clave_reconocida:
                    objetos, inventario = reconocedor.procesar(resultado, valores)
                    clave_reconocida = clave
                ahora = time.monotonic()
                fps = 1 / (ahora - anterior_frame) if anterior_frame is not None and ahora > anterior_frame else 0
                anterior_frame = ahora
                estado_video = None
                if reproductor is not None:
                    estado = "FIN - R reinicia" if reproductor.fin else "PAUSADO" if reproductor.pausado else "REPRODUCIENDO"
                    estado_video = (f"VIDEO SIMULADO | {reproductor.indice + 1}/{reproductor.info['fotogramas']} | "
                                    f"{reproductor.indice / reproductor.info['fps']:.2f} s | {estado}")
                vista = dibujar_directo(resultado, objetos, inventario, fps, en_vivo=cap is not None,
                                        estado_video=estado_video)
            else:
                vista = dibujar_resultado(resultado)
            cv2.putText(vista, f"Zoom digital: {valores['zoom'] / 100:.2f}x", (10, 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            if time.monotonic() < aviso_hasta:
                cv2.putText(vista, aviso, (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
            elif avisos_actuales:
                texto = "Revisa el tapete / limites. Detalles en la terminal."
                cv2.putText(vista, texto, (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
            if grabacion is not None:
                segundos = time.monotonic() - grabacion.inicio
                cv2.putText(vista, f"REC {segundos:.1f}s | R: detener y guardar", (10, 75),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            cv2.imshow("1. Mascara Binaria (Revisa si hay huecos)", resultado["mascara"])
            cv2.imshow("2. Reconocimiento en directo" if reconocer else "2. Telemetria de Caracteristicas", vista)
            if mostrar_sin_limpieza:
                cv2.imshow("0. Mascara antes de limpieza", resultado["mascara_bruta"])
            espera = reproductor.espera_ms(time.monotonic() - inicio_iteracion) if reproductor is not None else 30
            tecla = cv2.waitKeyEx(espera)
            if controles.manejar_tecla(tecla):
                continue
            if tecla in (ord("q"), ord("Q")):
                break
            try:
                if tecla == ord(" ") and reproductor is not None:
                    reproductor.alternar_pausa()
                    anterior_frame = None
                elif tecla in (ord("b"), ord("B")):
                    mostrar_sin_limpieza = not mostrar_sin_limpieza
                    if not mostrar_sin_limpieza:
                        try:
                            cv2.destroyWindow("0. Mascara antes de limpieza")
                        except cv2.error:
                            pass  # Ya pudo cerrarse con el botón de la ventana.
                elif tecla in (ord("p"), ord("P")):
                    ruta = guardar_configuracion(controles.valores, destino_config)
                    print(f"Ajustes guardados: {ruta}", flush=True)
                    aviso = "Ajustes guardados en JSON."
                    aviso_hasta = time.monotonic() + 4
                elif tecla in (ord("g"), ord("G")):
                    if reproductor is not None:
                        ruta = exportar_fotograma(ruta_video, reproductor.indice, valores, base=CARPETA_CAPTURAS)
                        print(f"Fotograma con procedencia guardado: {ruta}", flush=True)
                        aviso = "Fotograma guardado. Abre Capturas guardadas en la web."
                    else:
                        guardar_captura(original, resultado["encuadre"], valores)
                        aviso = "Foto y ajustes guardados. Puedes abrirlos con --ultima."
                    aviso_hasta = time.monotonic() + 4
                elif tecla in (ord("r"), ord("R")):
                    if reproductor is not None:
                        reproductor.reiniciar()
                        if reconocedor is not None:
                            reconocedor.reiniciar()
                        anterior_frame = None
                        clave_reconocida = None
                        aviso = "Video reiniciado."
                    elif cap is None:
                        aviso = "R graba con la camara. Abre el calibrador sin --imagen/--ultima."
                        print(aviso, flush=True)
                    elif grabacion is None:
                        grabacion = Grabacion(original, valores)
                        print("Grabando imagen original, sin audio. R detiene y guarda; Q también cierra el vídeo.", flush=True)
                        print("Se guardan los ajustes al iniciar; los cambios posteriores solo afectan a la vista del calibrador.", flush=True)
                        aviso = "Grabando original limpio. Pulsa R para detener."
                    else:
                        finalizar_grabacion(grabacion)
                        grabacion = None
                        aviso = "Video y ajustes guardados en videos."
                    aviso_hasta = time.monotonic() + 4
                elif tecla in (ord("e"), ord("E")):
                    from detector import exportar_resultado
                    origen = ruta_imagen
                    if reproductor is not None:
                        origen = exportar_fotograma(ruta_video, reproductor.indice, valores, base=CARPETA_CAPTURAS)
                    elif origen is None:
                        _, origen = guardar_captura(original, resultado["encuadre"], valores)
                    carpeta = BASE / "resultados" / f"{origen.stem}_{datetime.now():%Y%m%d_%H%M%S_%f}"
                    exportar_resultado(resultado, origen, valores, carpeta)
                    if reconocedor is not None:
                        exportar_predicciones(carpeta, objetos, inventario, vista)
                    print(f"Mediciones exportadas: {carpeta}", flush=True)
                    aviso = "CSV e imagen numerada guardados en resultados."
                    aviso_hasta = time.monotonic() + 4
            except (OSError, ValueError, cv2.error) as error:
                if grabacion is not None and grabacion.cerrada:
                    grabacion = None
                print(f"Error al guardar: {error}", flush=True)
                aviso, aviso_hasta = "No se pudo guardar. Revisa la terminal.", time.monotonic() + 4
    except (OSError, ValueError, RuntimeError, cv2.error) as error:
        grabacion_interrumpida = True
        motivo_fin = f"Error del calibrador: {error}"
        print(f"Error: {error}", file=sys.stderr)
        codigo_salida = 1
    except KeyboardInterrupt:
        grabacion_interrumpida = True
        motivo_fin = "Interrupción mediante Ctrl+C"
        codigo_salida = 130
    finally:
        # El cierre del vídeo puede tardar o recibir otro Ctrl+C. La cámara y
        # las ventanas se liberan incluso si ese cierre no llega a terminar.
        try:
            if grabacion is not None:
                try:
                    finalizar_grabacion(grabacion, interrumpida=grabacion_interrumpida, motivo=motivo_fin)
                except KeyboardInterrupt:
                    codigo_salida = 130
                    print("Cierre del vídeo interrumpido. Se conserva la carpeta incompleta para revisión.", file=sys.stderr)
                except (OSError, ValueError, RuntimeError, cv2.error) as error:
                    codigo_salida = 1
                    print(f"No se pudo finalizar el vídeo: {error}. Se conserva la carpeta incompleta para revisión.", file=sys.stderr)
        finally:
            try:
                try:
                    if cap is not None:
                        cap.release()
                finally:
                    if reproductor is not None:
                        reproductor.cerrar()
            finally:
                try:
                    if controles is not None:
                        controles.cerrar()
                finally:
                    cv2.destroyAllWindows()
    return codigo_salida


if __name__ == "__main__":
    raise SystemExit(main())
