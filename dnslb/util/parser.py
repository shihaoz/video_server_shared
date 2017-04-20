import logging
import struct
import sys

""" all byte/bit->val function returns (value, nextidx) """
""" all val -> byte/bit function returns bytes """

logging.basicConfig(filename="dns.log", filemode='w')


def byte2_to_short(bytes, idx):
	""" convert 2byte to short """
	return (struct.unpack(">H", bytes[idx: idx+2])[0], idx+2)


def short_to_byte2(val, unsigned=True):
	""" val to 2 bytes"""
	if unsigned:
		return struct.pack(">H", val)
	return struct.pack(">h", val)


def byte1_to_short(bytes, idx):
	""" convert 1 byte to int """
	return (bytes[idx], idx+1)


def short_to_byte1(val):
	""" val to 1 byte """
	return struct.pack(">B", val)


def byte_to_string(bytes, idx, length):
	""" convert bytes to string using utf-8 decoding """
	return (bytes[idx:idx+length].decode('utf-8'), idx+length)


def string_to_byte(query):
	""" convert query to bytes using utf-8 encoding """
	return query.encode('utf-8')


def int_to_bit(val, length):
	""" convert integer to string of binary of length """
	a = '{:b}'.format(val)
	while len(a) < length:
		a = '0'+a
	return a


class DNSRecord:
	def __init__(self):
		""" declare variables """
		
	

class DNSQuestion:
	def __init__(self):
		""" declare variables """
		self.QNAME = ""  # target domain name x bytes
		self.QTYPE = 0  # type of query 2 bytes always 1 (A record)
		self.QCLASS = 0  # class of query 2 bytes always 1 (IP addr)

	def getQuestion(self, bytes, idx=0):
		"""
		get question info from bytes
		@return -1=Error idx=OK
		"""
		remain_length, idx = byte1_to_short(bytes, idx)
		while remain_length > 0:
			tmp, idx = byte_to_string(bytes, idx, remain_length)
			self.QNAME += tmp + "."
			remain_length, idx = byte1_to_short(bytes, idx)
		print('getQuestion:: domain name :{}'.format(self.QNAME))
		logging.info('getQuestion:: domain name :{}'.format(self.QNAME))
		# getting QTYPE
		self.QTYPE, idx = byte2_to_short(bytes, idx)
		if self.QTYPE != 1:
			print(
				"getQuestion:: wrong QTYPE:{}".format(self.QTYPE),
				file=sys.stderr
			)
			logging.debug(
				"getQuestion:: wrong QTYPE:{}".format(self.QTYPE),
				file=sys.stderr
			)
			return -1
		print("getQuestion:: QTYPE :{}".format(self.QTYPE))
		logging.info("getQuestion:: QTYPE :{}".format(self.QTYPE))
		# getting QCLASS
		self.QCLASS, idx = byte2_to_short(bytes, idx)
		if self.QCLASS != 1:
			print(
				"getQuestion:: wrong QCLASS:{}".format(self.QCLASS),
				file=sys.stderr
			)
			logging.debug(
				"getQuestion:: wrong QCLASS:{}".format(self.QCLASS),
				file=sys.stderr
			)
			return -1
		print("getQuestion:: QCLASS :{}".format(self.QCLASS))
		logging.info("getQuestion:: QCLASS :{}".format(self.QCLASS))
		return idx

	def buildQuestion(self, domain_name, qtype, qclass):
		""" build a DNS question
		  @return: None=error, byte string=OK
		"""
		questions = b''
		labels = domain_name.split('.')
		for label in labels:
			if len(label) > 255 or len(label) == 0:
				print("label length wrong: {}".format(labels), file=sys.stderr)
				logging.debug("label length wrong: {}".format(labels))
				return None
			questions += short_to_byte1(len(label))
			questions += string_to_byte(label)
		# assign the zero length octet for null label
		questions += short_to_byte1(0)
		logging.info("buildQuestion:: domain name:{}".format(questions))
		questions += short_to_byte2(qtype)
		logging.info("buildQuestion:: qtype:{}".format(qtype))
		questions += short_to_byte2(qclass)
		logging.info("buildQuestion:: qclass:{}".format(qclass))
		logging.info("buildQuestion:: DNSquestion:\n{}".format(questions))
		return questions


class DNSHeader:
	def __init__(self):
		""" declare variables """
		self.ID = 0  # 2 byte
		self.QR = 0  # 1 bit, 0=query, 1=response
		self.Opcode = 0  # 4 bit always 0=standard query
		self.AA = 0  # 1 bit, 0=query, 1=response
		self.TC = 0  # 1 bit always 0
		self.RD = 0  # 1 bit always 0
		self.RA = 0  # 1 bit always 0
		self.Z = 0  # 3 bit always 0
		self.RCODE = 0  # 4 bit
		self.QDCOUNT = 0  # 2 byte
		self.ANCOUNT = 0  # 2 byte
		self.NSCOUNT = 0  # 2 byte always 0
		self.ARCOUNT = 0  # 2 byte always 0

	def getHeader(self, bytes, idx=0):
		"""
		get header info from bytes, used when receiving request
		@return -1=error idx=ok
		"""
		self.ID, idx = byte2_to_short(bytes, idx)
		logging.info('ID:{}'.format(self.ID))
		# deal with flags later
		flags, idx = byte2_to_short(bytes, idx)
		self.QR = (flags >> 15)  # shift 15 bits off
		self.Opcode = ((flags & int('0'+'1'*15, 2)) >> (11))
		self.AA = ((flags & int('0'*5+'1'*11, 2)) >> (10))
		self.TC = ((flags & int('0'*6+'1'*10, 2)) >> (9))
		self.RD = ((flags & int('0'*7+'1'*9, 2)) >> (8))
		self.RA = ((flags & int('0'*8+'1'*8, 2)) >> (7))
		self.Z = ((flags & int('0'*9+'1'*7, 2)) >> (4))
		self.RCODE = (flags & int('0'*12+'1'*4, 2))
		# get rest of the fields
		self.QDCOUNT, idx = byte2_to_short(bytes, idx)
		self.ANCOUNT, idx = byte2_to_short(bytes, idx)
		self.NSCOUNT, idx = byte2_to_short(bytes, idx)
		self.ARCOUNT, idx = byte2_to_short(bytes, idx)
		logging.info(
			"QDCOUNT:{}, ANCOUNT:{}, NSCOUNT:{}, ARCOUNT:{}"
			.format(self.QDCOUNT, self.ANCOUNT, self.NSCOUNT, self.ARCOUNT)
		)
		if (  # error handling
		    self.QDCOUNT != 1 or
		    self.ANCOUNT != 0 or
		    self.NSCOUNT != 0 or
		    self.ARCOUNT != 0
		):
			print('getHeader:: ERROR: count is wrong')
			logging.info('getHeader:: ERROR: count is wrong')
			print(
				"QDCOUNT:{}, ANCOUNT:{}, NSCOUNT:{}, ARCOUNT:{}"
				.format(self.QDCOUNT, self.ANCOUNT, self.NSCOUNT, self.ARCOUNT)
			)
			logging.debug(
				"QDCOUNT:{}, ANCOUNT:{}, NSCOUNT:{}, ARCOUNT:{}"
				.format(self.QDCOUNT, self.ANCOUNT, self.NSCOUNT, self.ARCOUNT)
			)
			return -1

		return idx

	def buildHeader(self, ID, flags, QDCOUNT, ANCOUNT, NSCOUNT, ARCOUNT):
		"""
		given parameter, build out the header
		@return: None=error, byte string=OK
		"""
		if (
			len(flags) != 8 or
			ID is None or
			QDCOUNT is None or
			ANCOUNT is None or
			NSCOUNT is None or
			ARCOUNT is None
		):
			print('buildHeader: ERROR in input')
			logging.debug(
				"ID:{}, flags:{}, QDCOUNT:{}, ANCOUNT:{}, NSCOUNT:{}, ARCOUNT:{}"
				.format(ID, flags, QDCOUNT, ANCOUNT, NSCOUNT, ARCOUNT)
			)
			return None
		header = b''
		header += short_to_byte2(ID)
		# number of bit for each flag
		flags_bit = [1, 4, 1, 1, 1, 1, 3, 4]
		holder = ''
		for i in range(len(flags_bit)):
			holder += int_to_bit(flags[i], flags_bit[i])
		logging.info('flags:{}'.format(holder))
		header += short_to_byte1(int(holder[:8], 2))
		header += short_to_byte1(int(holder[8:], 2))
		header += short_to_byte2(QDCOUNT)
		header += short_to_byte2(ANCOUNT)
		header += short_to_byte2(NSCOUNT)
		header += short_to_byte2(ARCOUNT)
		if len(header) != 12:
			logging.debug("buildHeader:: ERROR size != 12 bytes")
			print("buildHeader:: ERROR size != 12 bytes", file=sys.stderr)
			return None
		logging.info("buildHeader produces:{}".format(header))
		return header
