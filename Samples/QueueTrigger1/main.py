def main(context, myQueueItem: str):

    context.logger.info(f'Python queue trigger function processed a work item {myQueueItem}')