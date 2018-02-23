import azure.functions as azf


def main(timer: azf.TimerRequest, pastdue: azf.Out[int]):
    pastdue.set(timer.past_due)
