""" config and param setup """
import logging

log_file = "proxy.log"
log_level = logging.DEBUG
logging.basicConfig(filename=log_file, level=log_level)
