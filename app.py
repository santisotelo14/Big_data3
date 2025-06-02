import boto3
import requests
from datetime import datetime

# Cliente de S3
s3 = boto3.client('s3')
BUCKET_NAME = 'publimetro333'  # Nombre del bucket

# URLs de los periódicos
URLS = [
    'https://www.eltiempo.com/',
    'https://www.publimetro.co/'  #URL de las páginas
]

def download_and_save_all():
    fecha = datetime.utcnow().strftime('%Y-%m-%d')
    contenido_completo = ""

    for url in URLS:
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                contenido_completo += f"\n<!-- INICIO DE {url} -->\n"
                contenido_completo += response.text
                contenido_completo += f"\n<!-- FIN DE {url} -->\n"
            else:
                contenido_completo += f"\n<!-- ERROR {response.status_code} al descargar {url} -->\n"
        except Exception as e:
            contenido_completo += f"\n<!-- ERROR al descargar {url}: {str(e)} -->\n"

    # Ruta destino en S3
    s3_key = f"headlines/raw/contenido-{fecha}.html"

    # Subir a S3
    s3.put_object(Bucket=BUCKET_NAME, Key=s3_key, Body=contenido_completo)

    return f"Archivo guardado como: s3://{BUCKET_NAME}/{s3_key}"

def lambda_handler(event, context):
    resultado = download_and_save_all()
    return {'resultado': resultado}