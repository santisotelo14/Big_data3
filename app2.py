import boto3
import os
from datetime import datetime
from bs4 import BeautifulSoup
from io import StringIO
import csv

s3 = boto3.client('s3')
BUCKET_NAME = 'publimetro333'

def listar_archivos_raw():
    respuesta = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix='headlines/raw/')
    return [obj['Key'] for obj in respuesta.get('Contents', []) if obj['Key'].endswith('.html')]

def procesar_html(html, fuente):
    soup = BeautifulSoup(html, 'html.parser')
    noticias = []

    # Puedes personalizar los selectores según cada sitio
    if 'eltiempo.com' in fuente:
        bloques = soup.select('article a')
    elif 'publimetro' in fuente:
        bloques = soup.select('div.article-details a')
    else:
        bloques = soup.find_all('a')

    for a in bloques:
        enlace = a.get('href')
        texto = a.get_text(strip=True)
        if texto and enlace and len(texto) > 20:
            categoria = enlace.split('/')[1] if '/' in enlace else 'general'
            if not enlace.startswith('http'):
                enlace = f'https://{fuente}/{enlace.lstrip("/")}'
            noticias.append([categoria, texto, enlace])
    
    return noticias

def guardar_csv_en_s3(noticias, periodico, fecha):
    year = fecha[:4]
    month = fecha[5:7]
    day = fecha[8:10]

    csv_buffer = StringIO()
    writer = csv.writer(csv_buffer)
    writer.writerow(["categoria", "titular", "enlace"])
    writer.writerows(noticias)

    key_csv = f"headlines/final/periodico={periodico}/year={year}/month={month}/day={day}/noticias.csv"
    s3.put_object(Bucket=BUCKET_NAME, Key=key_csv, Body=csv_buffer.getvalue())
    print(f"Guardado en: s3://{BUCKET_NAME}/{key_csv}")

def lambda_handler(event, context):
    archivos = listar_archivos_raw()

    for key in archivos:
        print(f"Procesando: {key}")
        obj = s3.get_object(Bucket=BUCKET_NAME, Key=key)
        contenido = obj['Body'].read().decode('utf-8')
        fecha_str = key.split("contenido-")[-1].replace(".html", "")
        fecha = datetime.strptime(fecha_str, "%Y-%m-%d")

        if "eltiempo" in contenido:
            noticias = procesar_html(contenido, 'www.eltiempo.com')
            guardar_csv_en_s3(noticias, "eltiempo", fecha_str)
        if "publimetro" in contenido:
            noticias = procesar_html(contenido, 'www.publimetro.co')
            guardar_csv_en_s3(noticias, "publimetro", fecha_str)

    return {"message": "Procesamiento finalizado"}
    
if __name__ == '__main__':
    resultado = lambda_handler({}, {})
    print(resultado)
