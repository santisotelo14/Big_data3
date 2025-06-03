import boto3

# Cliente de Glue
glue = boto3.client('glue')

# Nombre del crawler (ajústalo si es diferente)
CRAWLER_NAME = 'crawler-noticias-headlines'

def lambda_handler(event, context):
    try:
        response = glue.start_crawler(Name=CRAWLER_NAME)
        return {
            "message": f"Crawler '{CRAWLER_NAME}' iniciado exitosamente.",
            "response": response
        }
    except glue.exceptions.CrawlerRunningException:
        return {
            "message": f"Crawler '{CRAWLER_NAME}' ya se está ejecutando. No se puede iniciar nuevamente."
        }
    except Exception as e:
        return {
            "error": str(e)
        }
