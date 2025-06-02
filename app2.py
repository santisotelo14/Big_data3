import boto3
import csv
import io
import re
from datetime import datetime

# Cliente de S3
s3_client = boto3.client('s3')
BUCKET_NAME = 'publimetro333'

def clean_text(text):
    """Limpia el texto removiendo caracteres especiales y espacios extra"""
    if not text:
        return ""
    # Remover tags HTML residuales
    text = re.sub(r'<[^>]+>', '', text)
    # Remover espacios extra y caracteres especiales
    text = re.sub(r'\s+', ' ', text).strip()
    # Decodificar entidades HTML comunes
    html_entities = {
        '&': '&', '<': '<', '>': '>', '"': '"',
        ''': "'", ' ': ' ', ''': "'", '“': '"',
        '”': '"', '‘': "'", '’': "'"
    }
    for entity, char in html_entities.items():
        text = text.replace(entity, char)
    return text

def extract_el_tiempo_news(html_content):
    """Extrae noticias de El Tiempo usando regex"""
    news_items = []
    
    # Patrones para El Tiempo
    patterns = [
        r'<article[^>]*class="[^"]*article[^"]*"[^>]*>.*?<h2[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?</h2>.*?</article>',
        r'<h[1-6][^>]*>.*?<a[^>]*href="([^"]+)"[^>]*title="([^"]*)"[^>]*>([^<]*)</a>.*?</h[1-6]>',
        r'<li[^>]*class="[^"]*noticia[^"]*"[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>([^<]+)</a>.*?</li>',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, html_content, re.DOTALL | re.IGNORECASE)
        for match in matches:
            if len(match) >= 2:
                url = match[0]
                title = match[1] if len(match) == 2 else match[2]
                
                category = extract_category_from_url(url)
                title = clean_text(title)
                url = url if url.startswith('http') else f"https://www.eltiempo.com{url}"
                
                if title and len(title) > 10:
                    news_items.append({
                        'periodico': 'eltiempo',
                        'categoria': category,
                        'titular': title,
                        'enlace': url
                    })
    
    return news_items

def extract_publimetro_news(html_content):
    """Extrae noticias de Publimetro usando regex"""
    news_items = []
    
    # Patrones para Publimetro
    patterns = [
        r'<article[^>]*>.*?<h[1-6][^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>([^<]+)</a>.*?</h[1-6]>.*?</article>',
        r'<div[^>]*class="[^"]*post[^"]*"[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>([^<]+)</a>',
        r'<h[1-6][^>]*>.*?<a[^>]*href="([^"]+)"[^>]*title="([^"]*)"[^>]*>([^<]*)</a>.*?</h[1-6]>',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, html_content, re.DOTALL | re.IGNORECASE)
        for match in matches:
            if len(match) >= 2:
                url = match[0]
                title = match[1] if len(match) == 2 else (match[2] if match[2] else match[1])
                
                category = extract_category_from_url(url)
                title = clean_text(title)
                url = url if url.startswith('http') else f"https://www.publimetro.co{url}"
                
                if title and len(title) > 10:
                    news_items.append({
                        'periodico': 'publimetro',
                        'categoria': category,
                        'titular': title,
                        'enlace': url
                    })
    
    return news_items

def extract_category_from_url(url):
    """Extrae la categoría basada en la URL"""
    categories_map = {
        'politica': ['politica', 'gobierno', 'congreso', 'elecciones'],
        'economia': ['economia', 'negocios', 'finanzas', 'mercados'],
        'deportes': ['deportes', 'futbol', 'deporte', 'liga'],
        'internacional': ['mundo', 'internacional', 'exterior'],
        'tecnologia': ['tecnologia', 'tech', 'ciencia', 'innovacion'],
        'cultura': ['cultura', 'arte', 'entretenimiento', 'espectaculos'],
        'salud': ['salud', 'medicina', 'bienestar'],
        'judicial': ['justicia', 'judicial', 'crimen', 'seguridad'],
        'opinion': ['opinion', 'editorial', 'columnista'],
        'regiones': ['bogota', 'medellin', 'cali', 'barranquilla', 'regiones', 'local']
    }
    
    url_lower = url.lower()
    for category, keywords in categories_map.items():
        if any(keyword in url_lower for keyword in keywords):
            return category
    
    return 'general'

def detect_newspaper(html_content):
    """Detecta qué periódico es basándose en el contenido HTML"""
    html_lower = html_content.lower()
    
    if 'eltiempo.com' in html_lower or 'el tiempo' in html_lower:
        return 'eltiempo'
    elif 'publimetro.co' in html_lower or 'publimetro' in html_lower:
        return 'publimetro'
    return 'desconocido'

def process_html_file(html_content, file_key):
    """Procesa el contenido HTML y extrae las noticias"""
    news_items = []
    
    # Dividir el contenido por marcadores de fuente
    sections = re.split(r'<!-- INICIO DE (.*?) -->\n(.*?)<!-- FIN DE \1 -->', html_content, flags=re.DOTALL)
    for i in range(1, len(sections), 3):
        source_url = sections[i].strip()
        content = sections[i+1].strip()
        newspaper = detect_newspaper(source_url)
        
        if newspaper == 'eltiempo':
            news_items.extend(extract_el_tiempo_news(content))
        elif newspaper == 'publimetro':
            news_items.extend(extract_publimetro_news(content))
    
    # Extraer fecha del nombre del archivo
    date_match = re.search(r'contenido-(\d{4}-\d{2}-\d{2})\.html', file_key)
    date_str = date_match.group(1) if date_match else datetime.utcnow().strftime('%Y-%m-%d')
    
    # Agregar información de fecha
    for item in news_items:
        item['fecha_extraccion'] = date_str
    
    return news_items, date_str

def lambda_handler(event, context):
    """Manejador del Lambda que se activa con eventos de S3"""
    try:
        for record in event['Records']:
            bucket = record['s3']['bucket']['name']
            key = record['s3']['object']['key']
            
            if not key.startswith('headlines/raw/'):
                continue
                
            # Descargar el archivo de S3
            response = s3_client.get_object(Bucket=bucket, Key=key)
            html_content = response['Body'].read().decode('utf-8', errors='ignore')
            
            # Procesar el archivo
            news_items, date_str = process_html_file(html_content, key)
            
            if not news_items:
                print(f"No se encontraron noticias en {key}")
                return {'status': 'No se encontraron noticias'}
            
            # Crear CSV en memoria
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=['periodico', 'categoria', 'titular', 'enlace', 'fecha_extraccion'])
            writer.writeheader()
            for item in news_items:
                writer.writerow(item)
            
            # Guardar CSV en S3
            csv_key = f"headlines/processed/noticias-{date_str}.csv"
            s3_client.put_object(Bucket=BUCKET_NAME, Key=csv_key, Body=output.getvalue())
            
            print(f"CSV guardado en s3://{BUCKET_NAME}/{csv_key}")
            print(f"Extraídas {len(news_items)} noticias")
            
            # Estadísticas
            by_newspaper = {}
            by_category = {}
            for item in news_items:
                newspaper = item['periodico']
                category = item['categoria']
                by_newspaper[newspaper] = by_newspaper.get(newspaper, 0) + 1
                by_category[category] = by_category.get(category, 0) + 1
            
            print("Estadísticas por periódico:")
            for newspaper, count in by_newspaper.items():
                print(f"  {newspaper}: {count} noticias")
            
            print("Estadísticas por categoría:")
            for category, count in by_category.items():
                print(f"  {category}: {count} noticias")
            
            return {'status': f"Procesado {key} y guardado en {csv_key}"}
            
    except Exception as e:
        print(f"Error al procesar evento de S3: {str(e)}")
        raise e