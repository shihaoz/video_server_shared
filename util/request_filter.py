""" module for transforming request/response """
import logging
import re
import sys
import urllib.request


def readF4M(bitrate, host, port):
	""" read request from server """
	logging.info("reading f4M")
	request = b""
	try:
		res = urllib.request.urlopen(
			'http://{}:{}/vod/big_buck_bunny.f4m'
			.format(host, port)
		)
		if res.getcode() != 200:
			print(
				'f4m request failed, code {}'.format(res.getcode()),
				file=sys.stderr
			)
			logging.debug(
				'f4m request failed, code {}'.format(res.getcode())
			)
			return
		request = res.read()
	except Exception as ex:
		print('f4m request failed, exception: {}'.format(ex), file=sys.stderr)
		logging.debug('f4m request failed, exception: {}'.format(ex))
		return

	""" this is a f4m """
	logging.info("reading f4m")
	logging.info(request.decode('utf-8'))
	if len(bitrate) == 0:
		rates = re.findall(b'bitrate="([0-9]+)"', request)
		logging.info("bitrates available: {}".format(rates))
		for rate in rates:
			bitrate.append(int(rate.decode('utf-8')))
			logging.info("bitrate append:{}".format(bitrate))
			bitrate = sorted(bitrate)
	return


def modifyF4M(request):
	""" modify the f4m client request """
	if request.find(b"/big_buck_bunny.f4m") != -1:
		logging.info("this is a f4m")
		request = request.replace(
			b'big_buck_bunny.f4m',
			b'big_buck_bunny_nolist.f4m'
		)
	return request


def modifyBitrate(request, fd, bitrate, fd_to_tp):
	logging.info("modifying birate")
	if request.find(b'-Frag') != -1:
		''' this is a chunk request'''
		logging.info("this is a chunk request")
		if len(bitrate) == 0:
			logging.debug("ERROR: bitrate is not ready yet;")
			return request
		br_client = 0
		if fd in fd_to_tp:
			# maximum bitrate for this client
			br_client = fd_to_tp[fd][0] * 2 / 3
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
