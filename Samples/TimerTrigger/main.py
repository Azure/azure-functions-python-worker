import datetime

def main(context, myTimer: dict):

    time_stamp = str(datetime.datetime.now())

    if myTimer['isPastDue']:
        context.logger.info('Python is running late!')
    
    context.logger.info(f'Python timer trigger function ran! {time_stamp}')