import time
import logging
from util import common


def time1st(fd_to_tp, fd):
	# call when received client request
	if fd in fd_to_tp:
		fd_to_tp[fd] = (fd_to_tp[fd][0], time.perf_counter())
	else:
		fd_to_tp[fd] = (0, time.perf_counter())


def time2nd(fd_to_tp, fd, size_bits):
	"""call when recevied response from server"""
	T_cur, last_time = fd_to_tp[fd]
	now_time = time.perf_counter()
	T_new = size_bits/(now_time - last_time)
	logging.info(
		"chunk size_bits: {}, time1: {}, time2: {}"
	        .format(size_bits, last_time, now_time)
	)
	T_cur = common.ALPHA*(T_new) + (1 - common.ALPHA) * T_cur
	fd_to_tp[fd] = (T_cur, 0)
	logging.info("sock: {}| throughput: {}".format(fd, T_cur))

