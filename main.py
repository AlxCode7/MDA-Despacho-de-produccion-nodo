import requests
import pandas as pd
from datetime import datetime, timedelta , timezone
import os

# 1. Determinar la hora actual y la fecha objetivo
zona_mexico = timezone(timedelta(hours=-6))
ahora = datetime.now(zona_mexico)
hora_publicacion = 17

if ahora.hour >= hora_publicacion:
    # Si ya paso la hora de publicacion, calculamos la fecha de mañana con la prevision
    fecha_objetivo = ahora.date() + timedelta(days=1)
else:
    # calculo de hora previo a publicacion cenace, si es antes de la variable calcula el dia actual
    fecha_objetivo = ahora.date()

fecha_str = fecha_objetivo.strftime("%Y/%m/%d")

sistema = "SIN"
proceso = "MDA"
nodo = os.environ.get("NODO_CENACE")  # Clave oculta 
horas_turbinado = 12

print(f"Consultando precios del nodo {nodo} para el día {fecha_str}...")

# Consulta api cenace
url = f"https://ws01.cenace.gob.mx:8082/SWPML/SIM/{sistema}/{proceso}/{nodo}/{fecha_str}/{fecha_str}/JSON"

try:
    response = requests.get(url, timeout=30)
    data = response.json()

    # rankear precios
    registros = data["Resultados"][0]["Valores"]
    df = pd.DataFrame(registros)
    df["hora"] = df["hora"].astype(int)
    df["pml"] = df["pml"].astype(float)

    # Ordenar de mayor a menor precio
    df_ranking = df.sort_values(by="pml", ascending=False).reset_index(drop=True)

    # formato reporte para las horas
    top_horas = df_ranking.head(horas_turbinado)
    
    
    # Extrae los números de las horas y ordenarlos cronológicamente
    horas_ordenadas = sorted(top_horas['hora'].tolist())

    bloques = []
    bloque_actual = [horas_ordenadas[0]]

    for h in horas_ordenadas[1:]:
        # Si la hora actual es exactamente la anterior + 1, es continua
        if h == bloque_actual[-1] + 1:
            bloque_actual.append(h)
        else:
            bloques.append(bloque_actual)
            bloque_actual = [h]
    # Agregar el último bloque que quedó en memoria
    bloques.append(bloque_actual)
    
    # Construccion del output del mensaje
    mensaje = f"*Plan de Turbinado MDA TTS ({fecha_objetivo})*\nNodo: {nodo}\n\n"
    
    # rankeo precios
    mensaje += f"*Top {horas_turbinado} Horas más Rentables:*\n"
    for _, row in top_horas.iterrows():
        # ajuste a la hora de CENACE - 1
        hora_real = int(row['hora']) - 1
        mensaje += f"• {hora_real:02d}:00 -> ${row['pml']:.2f} MXN/MWh\n"
    
    # bloques de operacion
    mensaje += "\n*Horarios de Operación (Bloques Continuos):*\n"
    
    for b in bloques:
        hora_inicio_real = b[0] - 1
        hora_fin_real = b[-1] - 1
        
        if len(b) > 1:
            mensaje += f"• Entrada: {hora_inicio_real:02d}:00 | Salida: {hora_fin_real:02d}:59 ({len(b)} horas)\n"
        else:
            mensaje += f"• Entrada: {hora_inicio_real:02d}:00 | Salida: {hora_inicio_real:02d}:59 (1 hora aislada)\n"

    # Promedio de precio del día en esas horas
    precio_promedio = top_horas['pml'].mean()
    mensaje += f"\nPrecio Promedio ({horas_turbinado}h): ${precio_promedio:.2f} MXN/MWh\n"

    print(mensaje)

    # --- api whatsapp green-api.com ---
    id_instance = os.environ.get("GREEN_API_ID")
    api_token = os.environ.get("GREEN_API_TOKEN")
    chat_id = os.environ.get("WHATSAPP_CHAT_ID")

    url_wa = f"https://api.green-api.com/waInstance{id_instance}/sendMessage/{api_token}"
    
    payload = {
        "chatId": chat_id,
        "message": mensaje
    }
    
    # Enviamos la petición a WhatsApp
    respuesta_wa = requests.post(url_wa, json=payload)
    
    if respuesta_wa.status_code == 200:
        print("\n se envio el whatsapp")
    else:
        print(f"\n Error al enviar WhatsApp: {respuesta_wa.text}")

except Exception as e:
    print(f"\nFallo la ejecución: {e}")
