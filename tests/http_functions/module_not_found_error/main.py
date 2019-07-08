import numpy as np


def main(req):
    # This function will fail, because numpy is not in site-packages folder
    np.random.seed(0)
