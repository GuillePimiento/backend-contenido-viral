import os
import json
import base64
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

app = Flask(__name__)
CORS(app)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


def get_openai_client():
    """Retorna el cliente de OpenAI. Lanza error si no hay API key."""
    if not OPENAI_API_KEY:
        raise ValueError("Falta la variable de entorno OPENAI_API_KEY")
    return OpenAI(api_key=OPENAI_API_KEY)

LINKEDIN_PHOTO_PROMPT = """Eres un experto en imagen profesional y marca personal en LinkedIn.
Analiza la siguiente foto de perfil de LinkedIn y califica cada una de estas 4 variables con un puntaje de 1 a 10 (donde 1 es muy bajo y 10 es excelente).

Las 4 variables son:

1. **Amabilidad**: ¿La persona transmite calidez, cercanía y accesibilidad? Evalúa la sonrisa, expresión facial amigable, postura abierta y lenguaje corporal acogedor.

2. **Liderazgo**: ¿La foto proyecta autoridad, confianza y capacidad de liderazgo? Evalúa la postura firme, mirada directa, presencia ejecutiva y composición que transmita poder.

3. **Competencia**: ¿La imagen transmite profesionalismo y habilidad? Evalúa la vestimenta apropiada, fondo profesional, calidad técnica de la foto, iluminación y nitidez.

4. **Asertividad en digital**: ¿La foto está optimizada para el entorno digital de LinkedIn? Evalúa el encuadre correcto (rostro visible y centrado), resolución adecuada, fondo apropiado para redes profesionales, y si la imagen genera impacto en un feed digital.

IMPORTANTE: Responde ÚNICAMENTE con un JSON válido con este formato exacto, sin texto adicional:
{
  "amabilidad": {"puntaje": <número del 1 al 10>, "justificacion": "<breve explicación>"},
  "liderazgo": {"puntaje": <número del 1 al 10>, "justificacion": "<breve explicación>"},
  "competencia": {"puntaje": <número del 1 al 10>, "justificacion": "<breve explicación>"},
  "asertividad_digital": {"puntaje": <número del 1 al 10>, "justificacion": "<breve explicación>"},
  "puntaje_total": <número del 1 al 10>,
  "resumen": "<resumen general con recomendaciones para mejorar la foto>"
}"""


def encode_image_from_url(image_url):
    """Descarga una imagen desde URL y la convierte a base64."""
    response = requests.get(image_url, timeout=15)
    response.raise_for_status()
    return base64.b64encode(response.content).decode("utf-8")


def analyze_photo(image_source, is_url=True):
    """Envía la foto a OpenAI Vision para análisis."""
    if is_url:
        image_content = {
            "type": "image_url",
            "image_url": {"url": image_source}
        }
    else:
        image_content = {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{image_source}"}
        }

    client = get_openai_client()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": LINKEDIN_PHOTO_PROMPT},
                    image_content,
                ],
            }
        ],
        max_tokens=1000,
    )

    raw = response.choices[0].message.content.strip()

    # Limpiar posible markdown ```json ... ```
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]
    raw = raw.strip()

    return json.loads(raw)


@app.route('/')
def health():
    return jsonify({"status": "ok"})


@app.route('/gpt', methods=['POST'])
def gpt():
    data = request.get_json(force=True, silent=True)
    if data is None:
        return jsonify({"answer": "No llegaron datos al backend. Revisa el JSON del frontend."}), 400
    mensaje = data.get("message", "")
    tema = data.get("tema", "")
    return jsonify({"answer": f"Hola, recibí: '{mensaje}' en el tema '{tema}'."})


@app.route('/analyze-linkedin-photo', methods=['POST'])
def analyze_linkedin_photo():
    """
    Analiza una foto de perfil de LinkedIn.

    Acepta JSON con:
      - image_url: URL pública de la imagen
    O multipart/form-data con:
      - image: archivo de imagen subido
    """
    # Intentar obtener imagen desde JSON (URL)
    if request.is_json or request.content_type == 'application/json':
        data = request.get_json(force=True, silent=True)
        if data is None or "image_url" not in data:
            return jsonify({
                "error": "Debes enviar un JSON con 'image_url' o subir una imagen."
            }), 400

        image_url = data["image_url"]
        try:
            result = analyze_photo(image_url, is_url=True)
        except requests.exceptions.RequestException:
            return jsonify({"error": "No se pudo descargar la imagen desde la URL proporcionada."}), 400
        except json.JSONDecodeError:
            return jsonify({"error": "Error al procesar la respuesta del análisis."}), 500

    # Intentar obtener imagen desde form-data (archivo subido)
    elif 'image' in request.files:
        file = request.files['image']
        image_bytes = file.read()
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        try:
            result = analyze_photo(image_b64, is_url=False)
        except json.JSONDecodeError:
            return jsonify({"error": "Error al procesar la respuesta del análisis."}), 500
    else:
        return jsonify({
            "error": "Debes enviar 'image_url' en JSON o subir un archivo 'image' en form-data."
        }), 400

    # Calcular puntaje total ponderado (25% cada variable)
    puntajes = {
        "amabilidad": result["amabilidad"]["puntaje"],
        "liderazgo": result["liderazgo"]["puntaje"],
        "competencia": result["competencia"]["puntaje"],
        "asertividad_digital": result["asertividad_digital"]["puntaje"],
    }
    puntaje_calculado = round(sum(puntajes.values()) * 0.25, 1)

    return jsonify({
        "calificacion_total": puntaje_calculado,
        "desglose": {
            "amabilidad": {
                "puntaje": puntajes["amabilidad"],
                "peso": "25%",
                "justificacion": result["amabilidad"]["justificacion"],
            },
            "liderazgo": {
                "puntaje": puntajes["liderazgo"],
                "peso": "25%",
                "justificacion": result["liderazgo"]["justificacion"],
            },
            "competencia": {
                "puntaje": puntajes["competencia"],
                "peso": "25%",
                "justificacion": result["competencia"]["justificacion"],
            },
            "asertividad_digital": {
                "puntaje": puntajes["asertividad_digital"],
                "peso": "25%",
                "justificacion": result["asertividad_digital"]["justificacion"],
            },
        },
        "resumen": result["resumen"],
    })


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)
