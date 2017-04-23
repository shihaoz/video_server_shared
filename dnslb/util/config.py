""" config and param setup """
import logging

log_file = "proxy.log"
log_level = logging.DEBUG
log_mode = 'w'  # overwrite existing log file
logging.basicConfig(
	filename=log_file,
	level=log_level,
	filemode=log_mode
)
server_addr = ('0.0.0.0', 5001)
