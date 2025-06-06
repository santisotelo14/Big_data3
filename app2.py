import boto3
import pandas as pd
from bs4 import BeautifulSoup
import re
from datetime import datetime

s3 = boto3.client("s3")
BUCKET_NAME = "publimetro333"

def extraer_eltiempo(html):
    """
    Extrae noticias de HTML de El Tiempo con categorías específicas.
    """
    soup = BeautifulSoup(html, "html.parser")
    noticias = []

    # Selectores para artículos con categorías en El Tiempo
    for item in soup.select("article[data-seccion], article.category-item, article[data-category]"):
        # Intenta obtener la categoría desde atributos o elementos específicos
        categoria = item.get("data-seccion") or item.get("data-category")
        if not categoria:
            # Busca en elementos internos como spans o divs con clases relacionadas
            categoria_elem = item.select_one("span.categoria, span.section, div.tag, a.tag")
            categoria = categoria_elem.get_text(strip=True) if categoria_elem else "general"
        
        titular = item.select_one("h1, h2, h3, .title-container a, .title a")
        enlace = item.select_one("a[href]")

        if titular and enlace:
            enlace_url = enlace["href"]
            # Normaliza la URL
            if not enlace_url.startswith("http"):
                enlace_url = f"https://www.eltiempo.com{enlace_url}"
            
            noticias.append({
                "categoria": categoria.strip().capitalize() if categoria else "general",
                "titular": titular.get_text(strip=True),
                "enlace": enlace_url,
                "periodico": "eltiempo" if "eltiempo.com" in enlace_url else "publimetro"
            })
    
    return noticias

def extraer_publimetro(html):
    """
    Extrae noticias de HTML de Publimetro con categorías específicas.
    """
    soup = BeautifulSoup(html, "html.parser")
    noticias = []

    # Selectores para artículos en Publimetro
    for item in soup.select("article, .news-item, .article-item"):
        # Busca categoría en elementos específicos
        categoria_elem = item.find("span", class_=re.compile("category|section|tag|meta", re.I))
        if not categoria_elem:
            categoria_elem = item.select_one("a.category, div.section, span.tag")
        categoria = categoria_elem.get_text(strip=True) if categoria_elem else "general"

        titular = item.find(["h1", "h2", "h3", ".title", ".headline"])
        enlace = item.find("a", href=True)

        if titular and enlace:
            enlace_url = enlace["href"]
            # Normaliza la URL
            if not enlace_url.startswith("http"):
                enlace_url = f"https://www.publimetro.co{enlace_url}"
            
            noticias.append({
                "categoria": categoria.strip().capitalize() if categoria else "general",
                "titular": titular.get_text(strip=True),
                "enlace": enlace_url,
                "periodico": "publimetro" if "publimetro.co" in enlace_url else "eltiempo"
            })
    
    return noticias

def procesar_archivos_existentes():
    """
    Procesa archivos HTML desde S3 raw y guarda noticias en CSV en finalp con partición por fecha.
    """
    try:
        # Lista objetos en la carpeta raw
        respuesta = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix="headlines/raw/")
        archivos = [obj["Key"] for obj in respuesta.get("Contents", []) if obj["Key"].endswith(".html")]

        if not archivos:
            return {"message": "No se encontraron archivos HTML en s3://publimetro333/headlines/raw/"}

        for archivo in archivos:
            print(f"Procesando: {archivo}")
            
            # Extrae la fecha del nombre del archivo
            fecha_match = re.search(r"contenido-(\d{4})-(\d{2})-(\d{2})\.html", archivo)
            if not fecha_match:
                print(f"Formato de archivo inválido: {archivo}")
                continue
            year, month, day = fecha_match.groups()

            # Valida la fecha
            try:
                datetime(int(year), int(month), int(day))
            except ValueError:
                print(f"Fecha inválida en archivo: {archivo}")
                continue

            # Lee el contenido HTML desde S3
            obj = s3.get_object(Bucket=BUCKET_NAME, Key=archivo)
            contenido = obj["Body"].read().decode("utf-8", errors="ignore")

            # Determina la fuente inicial basada en el nombre del archivo
            source = "eltiempo" if "eltiempo" in archivo.lower() else "publimetro"
            extractor = extraer_eltiempo if source == "eltiempo" else extraer_publimetro

            # Extrae noticias
            noticias = extractor(contenido)
            if not noticias:
                print(f"No se encontraron noticias en: {archivo}")
                continue

            # Crea DataFrame
            df = pd.DataFrame(noticias)
            df["year"] = int(year)
            df["month"] = int(month)
            df["day"] = int(day)

            # Asegura que todas las columnas requeridas estén presentes
            required_columns = ["categoria", "titular", "enlace", "periodico", "year", "month", "day"]
            df = df[required_columns]

            # Elimina duplicados y entradas inválidas
            df = df.dropna().drop_duplicates(subset=["titular", "enlace"])

            # Corrige categorías "general" basándose en la URL
            for idx, row in df.iterrows():
                url = row["enlace"]
                if "eltiempo.com" in url:
                    # Extrae la categoría de la URL (primer segmento después del dominio)
                    match = re.search(r"eltiempo\.com/([^/]+)/", url)
                    if match and match.group(1) not in ["videos", "podcast", "mas-contenido"]:
                        df.at[idx, "categoria"] = match.group(1).replace("-", " ").capitalize()
                        df.at[idx, "periodico"] = "eltiempo"
                elif "publimetro.co" in url:
                    match = re.search(r"publimetro\.co/([^/]+)/", url)
                    if match and match.group(1) not in ["publimetro-tv", "especiales"]:
                        df.at[idx, "categoria"] = match.group(1).replace("-", " ").capitalize()
                        df.at[idx, "periodico"] = "publimetro"

            # Guarda en S3 con partición por fecha
            output_key = f"headlines/finalp/noticias-{year}-{month}-{day}.csv"
            csv_data = df.to_csv(index=False, encoding="utf-8")
            s3.put_object(Bucket=BUCKET_NAME, Key=output_key, Body=csv_data.encode("utf-8"))

            print(f"Guardado en: s3://{BUCKET_NAME}/{output_key}")

        return {"message": "Procesamiento finalizado con éxito"}

    except Exception as e:
        print(f"Error durante el procesamiento: {str(e)}")
        return {"message": f"Error durante el procesamiento: {str(e)}"}

def lambda_handler(event, context):
    """
    Manejador de la Lambda para procesar eventos de S3 o ejecución manual.
    """
    return procesar_archivos_existentes()