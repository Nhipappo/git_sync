import logging
import sys


def get_logger(name: str) -> logging.Logger:
    logging.basicConfig(
        level=logging.INFO,
        format='|\033[1;35m|\033[1;36m [INFO]\033[0m %(message)s',
        stream=sys.stdout
    )
    return logging.getLogger(name)
