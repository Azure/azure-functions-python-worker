from urllib.request import urlopen

import azure.functions as func


def main(req: func.HttpRequest) -> str:
    image_url = req.params.get('img')
    urlopen(image_url).read()
