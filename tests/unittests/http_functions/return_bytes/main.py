def main(req):
    # This function will fail, as we don't auto-convert "bytes" to "http".
    return b'Hello World!'
