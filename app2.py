import boto3
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
import re

s3 = boto3.client("s3")
BUCKET_NAME = "publimetro333"

def extraer_eltiempo(html):
    soup = BeautifulSoup(html, "html.parser")
    noticias = []

    for item in soup.select("article"):
        categoria = item.get("data-seccion", "general")
        titular = item.select_one("h1, h2, h3")
        enlace = item.select_one("a[href]")

        if titular and enlace:
            noticias.append({
                "categoria": categoria.strip(),
                "titular": titular.get_text(strip=True),
                "enlace": enlace["href"] if enlace["href"].startswith("http") else "https://www.eltiempo.com" + enlace["href"]
            })
    return noticias

def extraer_publimetro(html):
    soup = BeautifulSoup(html, "html.parser")
    noticias = []

    for item in soup.select("article"):
        categoria = item.find("span", class_="category")
        titular = item.find(["h1", "h2", "h3"])
        enlace = item.find("a", href=True)

        if titular and enlace:
            noticias.append({
                "categoria": categoria.get_text(strip=True) if categoria else "general",
                "titular": titular.get_text(strip=True),
                "enlace": enlace["href"] if enlace["href"].startswith("http") else "https://www.publimetro.co" + enlace["href"]
            })
    return noticias

def procesar_archivos_existentes():
    respuesta = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix="headlines/raw/")
    archivos = [obj["Key"] for obj in respuesta.get("Contents", []) if obj["Key"].endswith(".html")]

    for archivo in archivos:
        print(f"Procesando: {archivo}")
        obj = s3.get_object(Bucket=BUCKET_NAME, Key=archivo)
        contenido = obj["Body"].read().decode("utf-8")

        fecha_match = re.search(r"contenido-(\d{4})-(\d{2})-(\d{2})\.html", archivo)
        if not fecha_match:
            continue
        year, month, day = fecha_match.groups()

        for nombre, extractor in [("eltiempo", extraer_eltiempo), ("publimetro", extraer_publimetro)]:
            noticias = extractor(contenido)
            if not noticias:
                continue

            df = pd.DataFrame(noticias)
            df["periodico"] = nombre
            df["year"] = int(year)
            df["month"] = int(month)
            df["day"] = int(day)

            # Ruta limpia
            output_key = f"headlines/final/periodico={nombre}/year={year}/month={month}/day={day}/noticias.csv"
            csv_data = df.to_csv(index=False)
            s3.put_object(Bucket=BUCKET_NAME, Key=output_key, Body=csv_data.encode("utf-8"))

            print(f"Guardado en: s3://{BUCKET_NAME}/{output_key}")

    return {"message": "Procesamiento finalizado"}

# Solo para ejecución directa (por ejemplo: python app2.py)
if __name__ == "__main__":
    resultado = procesar_archivos_existentes()
    print(resultado)
