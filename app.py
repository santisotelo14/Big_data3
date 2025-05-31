import boto3
import requests
from datetime import datetime

s3 = boto3.client('s3')
BUCKET_NAME = 'publimetro333'  # Asegúrate de que este bucket exista

# Lista de URLs a descargar
URLS = [
    'https://www.eltiempo.com/',
    'https://www.publimetro.co/'
]

def download_and_save(url):
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            fecha = datetime.utcnow().strftime('%Y-%m-%d')
            domain = url.split("//")[1].split("/")[0].replace("www.", "")
            filename = f"{fecha}-{domain}.html"
            s3.put_object(Bucket=BUCKET_NAME, Key=filename, Body=response.text)
            return f"Guardado: {filename}"
        else:
            return f"Error {response.status_code} al descargar {url}"
    except Exception as e:
        return f"Error al descargar {url}: {str(e)}"

def lambda_handler(event, context):
    resultados = [download_and_save(url) for url in URLS]
    return {'resultado': resultados}
