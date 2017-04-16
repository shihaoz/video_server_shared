""" module for transforming request/response """
import logging
import re


def readF4M(bitrate, request):
	""" read request from server """
	logging.info("reading f4M")
	if request.find(b"text/xml") != -1:
		""" this is a f4m """
		logging.info("this is a f4m")
		logging.info(request.decode('utf-8'))
		if len(bitrate) == 0:
			""" 1st time see f4m, read the available bitrate """
			rates = re.findall(b'bitrate="([0-9]+)"', request)
			logging.info("bitrates available: {}".format(rates))
			for rate in rates:
				bitrate.append(int(rate.decode('utf-8')))
			bitrate = sorted(bitrate)
		request = request.replace(b'big_buck_bunny.f4m',
		                          b'big_buck_bunny_nolist.f4m')
	return request


def modifyBitrate(request, fd, bitrate, fd_to_tp):
	logging.info("modifying birate")
	if request.find(b'-Frag') != -1:
		''' this is a chunk request'''
		logging.info("this is a chunk request")
		if len(bitrate) == 0:
			logging.debug("ERROR: bitrate is not ready yet;")
			return request
		logging.info("fd: {}, fd_to_tp: {}".format(fd, fd_to_tp))
		br_client = fd_to_tp[fd][0] * 2 / 3  # maximum bitrate for this client
		br_chosen = 0
		for br in bitrate:
			if br <= br_client and br > br_chosen:
				br_chosen = br
		if br_chosen < bitrate[0]:
			""" maintain the mininal bitrate """
			br_chosen = bitrate[0]
		logging.info("client tp: {}, chosen tp: {}".format(br_client, br_chosen))
		old_chunk = re.search(b'/[0-9]+Seg', request).group()
		new_chunk = "/{}Seg".format(br_chosen).encode('utf-8')
		logging.info("from {} to {}".format(old_chunk, new_chunk))
		request = request.replace(old_chunk, new_chunk)
	return request
