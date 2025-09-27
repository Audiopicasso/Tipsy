import json
import logging
from openai import OpenAI, OpenAIError

import settings


logger = logging.getLogger(__name__)


def get_client(api_key: str | None = None):
    """Get an OpenAI API Client"""
    if not api_key:
        api_key = settings.OPENAI_API_KEY
    if not api_key:
        raise OpenAIError('The api_key client option must be set either by passing api_key to the client or by setting the OPENAI_API_KEY environment variable')
    return OpenAI(api_key=api_key or settings.OPENAI_API_KEY)


def generate_cocktails(pump_to_drink: dict, target_volume_ml: int = 220, requests_for_bartender: str = '', exclude_existing: bool = True, api_key: str | None = None) -> dict:
    """Generate a JSON list of cocktails using German ingredient names from pump config"""
    
    # Extrahiere deutsche Zutatennamen aus der Pumpen-Konfiguration
    available_ingredients = []
    for pump_label, config_entry in pump_to_drink.items():
        if isinstance(config_entry, dict):
            ingredient = config_entry.get('ingredient', '')
        else:
            ingredient = config_entry
        
        if ingredient:
            available_ingredients.append(ingredient)
    
    prompt = (
        'You are a creative cocktail mixologist. Based on the following pump configuration, '
        'generate a list of cocktail recipes. For each cocktail, provide a normal cocktail name, '
        'a fun cocktail name, and a dictionary of ingredients (with their measurements in ml).\n\n'
        'IMPORTANT CONSTRAINTS:\n'
        f'- Use ONLY these exact ingredient names from the pump configuration: {", ".join(available_ingredients)}\n'
        f'- Each cocktail should have a TOTAL VOLUME of approximately {target_volume_ml}ml (±20ml)\n'
        '- Balance the ingredients so the total adds up to this target volume\n'
        '- Preferrably generate recipes for common and well known cocktails, which proved to be good tasting and work with the provided ingredients.\n'
        '- All measurements must be in ml (e.g., "50 ml")\n\n'
        'Please output only valid JSON that follows this format:\n\n'
        '{\n'
        '  "cocktails": [\n'
        '    {\n'
        '      "normal_name": "Margarita",\n'
        '      "fun_name": "Citrus Snap",\n'
        '      "ingredients": {\n'
        '        "Tequila": "50 ml",\n'
        '        "Triple Sec": "25 ml",\n'
        '        "Limettensaft": "25 ml"\n'
        '      }\n'
        '    }\n'
        '  ]\n'
        '}\n\n'
        'Now, use the following pump configuration creatively to generate your cocktail recipes:\n'
        f'{json.dumps(pump_to_drink, indent=2)}\n\n'
    )
    if exclude_existing:
        from helpers import load_cocktails
        prompt += (
            'Do not include the following cocktails, which I already have recipes for:\n\n'
            f'{json.dumps(load_cocktails(), indent=2)}\n\n'
        )

    if requests_for_bartender.strip():
        prompt += f'Requests for the bartender: {requests_for_bartender.strip()}\n'

    try:
        client = get_client(api_key=api_key)
        completion = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[
                {
                    'role': 'system',
                    'content': (
                        'You are a creative cocktail mixologist. Generate cocktail recipes in JSON format. '
                        'Make sure your entire response is a valid JSON object. '
                        f'Use ONLY these ingredient names: {", ".join(available_ingredients)}'
                    )
                },
                {'role': 'user', 'content': prompt}
            ],
            response_format={'type': 'json_object'},
        )
        json_output = completion.choices[0].message.content
        data = json.loads(json_output)
        return data
    except Exception as e:
        logger.exception('Error generating cocktails')
        raise e

def generate_image(prompt: str, api_key: str | None = None, use_gpt_transparency: bool | None = None) -> str:
    """Generate an image using OpenAI"""
    if use_gpt_transparency is None:
        use_gpt_transparency = settings.USE_GPT_TRANSPARENCY
    try:
        generation_kwargs = {
            'model': 'dall-e-3',
            'prompt': prompt,
            'size': '1024x1024',
            'quality': 'standard',
            'n': 1,
        }
        if use_gpt_transparency:
            generation_kwargs.update({
                'model': 'gpt-image-1',
                'background': 'transparent',
                'output_format': 'png',
                'quality': 'auto'
            })
        else:
            generation_kwargs.update({
                'response_format': 'b64_json'
            })
        client = get_client(api_key)
        response = client.images.generate(**generation_kwargs)
        image_url = response.data[0].b64_json
        return image_url
    except Exception as e:
        raise Exception(f'Image generation error')
