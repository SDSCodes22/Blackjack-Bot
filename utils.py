import json
from io import BytesIO

import requests
from PIL import Image, ImageStat

def get_emoji(key: str):
    """When given a key in the format: "<Suit><rank>", where Suit is capitalised, and rank is abbreviated to its initial where applicable,
    it returns the emoji string to be used to represent that card

    Args:
        key (str): Card key in format "<Suit><Rank>"

    Returns:
        str: discord emoji markdown for that card
    """
    with open("config.json", 'r') as f:
        data = json.load(f)
    return str(data["bj_emojis"][key])

def get_average_avatar_color(url: str) -> str:
    """Given the avatar URL of a discord user, it computes the average colour in the profile picture and outputs a string hex code

    Args:
        url (str): The URL of the user's avatar

    Returns:
        str: The average color found in the profile picture
    """
    response = requests.get(url, timeout=10)
    response.raise_for_status()

    with Image.open(BytesIO(response.content)) as avatar:
        rgba = avatar.convert("RGBA")
        if rgba.getchannel("A").getbbox() is None:
            return "#000000"

        colors = ImageStat.Stat(
            rgba.convert("RGB"),
            mask=rgba.getchannel("A"),
        ).mean
        return int("{:02x}{:02x}{:02x}".format(*(round(color) for color in colors)), 16)