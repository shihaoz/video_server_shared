import logging
import sys


def log_matrix(matrix):
	for array in matrix:
		logging.info(array)
	logging.info("-- -- \n")



def log_print(msg, if_print=True, if_log=True):
	"""
	log a message
	@param if_print (default=True): print to console
	@param if_log (default=True): log the message
	@return None
	"""
	if if_print:
		print(msg)
	if if_log:
		logging.info(msg)


def log_err(msg, if_print=True, if_log=True):
	"""
	log an error
	@param if_print (default=True): print to console
	@param if_log (default=True): log the message
	@return None
	"""
	if if_print:
		print(msg, file=sys.stderr)
	if if_log:
		logging.debug(msg)
