from azure.functions import FunctionApp, TimerRequest, Context, AuthLevel
import logging

app = FunctionApp(http_auth_level=AuthLevel.ANONYMOUS)


@app.timer_trigger(schedule="*/1 * * * * *", arg_name="mytimer",
                   run_on_startup=False,
                   use_monitor=False)
@app.retry(strategy="fixed_delay", max_retry_count="1", delay_interval="5")
def mytimer(mytimer: TimerRequest, context: Context) -> None:
    logging.info(f'Current retry count: {context.retry_context.retry_count}')

    if mytimer.past_due:
        logging.info("Timer trigger is past due")

    if context.retry_context.retry_count == \
            context.retry_context.max_retry_count:
        logging.info(
            f"Max retries of {context.retry_context.max_retry_count} for "
            f"function {context.function_name} has been reached")
    raise Exception("This is a retryable exception")
