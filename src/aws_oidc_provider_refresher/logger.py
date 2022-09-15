import os
import logging

if len(logging.getLogger().handlers) == 0:
    logging.basicConfig(format="%(levelname)s: %(message)s")

log = logging.getLogger()
log.setLevel(os.getenv("LOG_LEVEL", "INFO"))
