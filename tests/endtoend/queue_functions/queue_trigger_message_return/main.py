import azure.functions as azf


def main(msg: azf.QueueMessage) -> bytes:
    return msg.get_body()
