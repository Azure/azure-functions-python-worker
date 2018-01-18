from main import main
import logging

class Context: 
    logger = logging.Logger('execution context')
    logger.setLevel(logging.INFO)

    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)


def execute():
    context = Context()

    context.logger.info('Function started.')
    main(context,queueitem) 
    context.logger.info('Function completed.')

queueitem = 'sample queue data'
execute()