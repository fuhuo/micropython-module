#!/usr/bin/env python

# this module fork by https://github.com/kyan001/ping3

# import os
import sys
# import platform
import socket
import struct
import select
import time
# import zlib
import crc32
# import threading
import logging
# import functools

# import errors
# from enums import ICMP_DEFAULT_CODE, IcmpType, IcmpTimeExceededCode, IcmpDestinationUnreachableCode

# import enum


ICMP_DEFAULT_CODE = 0  # the code for ECHO_REPLY and ECHO_REQUEST


class IcmpType:
    """Enum for Type in ICMP Header."""
    ECHO_REPLY = 0
    DESTINATION_UNREACHABLE = 3
    REDIRECT_MESSAGE = 5
    ECHO_REQUEST = 8
    ROUTER_ADVERTISEMENT = 9
    ROUTER_SOLICITATION = 10
    TIME_EXCEEDED = 11
    BAD_IP_HEADER = 12
    TIMESTAMP = 13
    TIMESTAMP_REPLY = 14


class IcmpDestinationUnreachableCode:
    """Enum for Code in ICMP Header when type is DESTINATION_UNREACHABLE (3)"""
    DESTINATION_NETWORK_UNREACHABLE = 0
    DESTINATION_HOST_UNREACHABLE = 1
    DESTINATION_PROTOCOL_UNREACHABLE = 2
    DESTINATION_PORT_UNREACHABLE = 3
    FRAGMENTATION_REQUIRED = 4
    SOURCE_ROUTE_FAILED = 5
    DESTINATION_NETWORK_UNKNOWN = 6
    DESTINATION_HOST_UNKNOWN = 7
    SOURCE_HOST_ISOLATED = 8
    NETWORK_ADMINISTRATIVELY_PROHIBITED = 9
    HOST_ADMINISTRATIVELY_PROHIBITED = 10
    NETWORK_UNREACHABLE_FOR_TOS = 11
    HOST_UNREACHABLE_FOR_TOS = 12
    COMMUNICATION_ADMINISTRATIVELY_PROHIBITED = 13
    HOST_PRECEDENCE_VIOLATION = 14
    PRECEDENCE_CUTOFF_IN_EFFECT = 15


class IcmpTimeExceededCode:
    """Enum for Code in ICMP Header when type is TIME_EXCEEDED (11)"""
    TTL_EXPIRED = 0
    FRAGMENT_REASSEMBLY_TIME_EXCEEDED = 1

class PingError(Exception):
    pass


class TimeExceeded(PingError):
    pass


class TimeToLiveExpired(TimeExceeded):
    def __init__(self, message="Time exceeded: Time To Live expired."):
        super().__init__(message)


class DestinationUnreachable(PingError):
    pass


class DestinationHostUnreachable(DestinationUnreachable):
    def __init__(self, dest_addr=None):
        message = "Destination unreachable: Host unreachable."
        if dest_addr:
            message += " (Host='{}')".format(dest_addr)
        super().__init__(message)


class HostUnknown(PingError):
    def __init__(self, dest_addr=None):
        message = "Cannot resolve: Unknown host."
        if dest_addr:
            message += " (Host='{}')".format(dest_addr)
        super().__init__(message)


class Timeout(PingError):
    def __init__(self, timeout=None):
        message = "Request timeout for ICMP packet."
        if timeout is not None:
            message += " (Timeout={}s)".format(timeout)
        super().__init__(message)

__version__ = "2.7.0"
DEBUG = False  # DEBUG: Show debug info for developers. (default False)
EXCEPTIONS = False  # EXCEPTIONS: Raise exception when delay is not available.
LOGGER = None  # LOGGER: Record logs into console or file.

IP_HEADER_FORMAT = "!BBHHHBBHII"
ICMP_HEADER_FORMAT = "!BBHHH"  # According to netinet/ip_icmp.h. !=network byte order(big-endian), B=unsigned char, H=unsigned short
ICMP_TIME_FORMAT = "!d"  # d=double
SOCKET_SO_BINDTODEVICE = 25  # socket.SO_BINDTODEVICE


def _debug(*args, **kwargs):
    """Print debug info to stdout if `ping3.DEBUG` is True.
    Args:
        *args: Any. Usually are strings or objects that can be converted to str.
    """
    def get_logger():
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter('[%(levelname)s] %(message)s')
        cout_handler = logging.StreamHandler()
        cout_handler.setLevel(logging.DEBUG)
        cout_handler.setFormatter(formatter)
        logger.addHandler(cout_handler)
        logger.debug("Ping3 Version: {}".format(__version__))
        logger.debug("LOGGER: {}".format(logger))
        return logger

    if not DEBUG:
        return None
    global LOGGER
    LOGGER = LOGGER or get_logger()
    message = " ".join(str(item) for item in args)
    LOGGER.debug(message)


def _raise(err):
    """Raise exception if `ping3.EXCEPTIONS` is True.
    Args:
        err: Exception.
    Raise:
        Exception: Exception passed in args will be raised if `ping3.EXCEPTIONS` is True.
    """
    if EXCEPTIONS:
        raise err


# def _func_logger(func: callable) -> callable:
#     """Decorator that log function calls for debug
#     Args:
#         func: Function to be decorated.
#     Returns:
#         Decorated function.
#     """
#     @functools.wraps(func)
#     def wrapper(*args, **kwargs):
#         pargs = ", ".join("'{}'".format(arg) if isinstance(arg, str) else arg for arg in args)
#         kargs = str(kwargs) if kwargs else ""
#         all_args = ", ".join((pargs, kargs)) if (pargs and kargs) else (pargs or kargs)
#         _debug("Function Called:", "{func.__name__}({})".format(all_args, func=func))
#         func_return = func(*args, **kwargs)
#         _debug("Function Returned:", "{func.__name__} -> {rtrn}".format(func=func, rtrn=func_return))
#         return func_return

#     return wrapper


def ones_comp_sum16(num1: int, num2: int) -> int:
    """Calculates the 1's complement sum for 16-bit numbers.
    Args:
        num1: 16-bit number.
        num2: 16-bit number.
    Returns:
        The calculated result.
    """

    carry = 1 << 16
    result = num1 + num2
    return result if result < carry else result + 1 - carry


def checksum(source: bytes) -> int:
    """Calculates the checksum of the input bytes.
    RFC1071: https://tools.ietf.org/html/rfc1071
    RFC792: https://tools.ietf.org/html/rfc792
    Args:
        source: The input to be calculated.
    Returns:
        Calculated checksum.
    """
    if len(source) % 2:  # if the total length is odd, padding with one octet of zeros for computing the checksum
        source += b'\x00'
    sum = 0
    for i in range(0, len(source), 2):
        sum = ones_comp_sum16(sum, (source[i + 1] << 8) + source[i])
    return ~sum & 0xffff


def read_icmp_header(raw: bytes) -> dict:
    """Get information from raw ICMP header data.
    Args:
        raw: Bytes. Raw data of ICMP header.
    Returns:
        A map contains the infos from the raw header.
    """
    icmp_header_keys = ('type', 'code', 'checksum', 'id', 'seq')
    return dict(zip(icmp_header_keys, struct.unpack(ICMP_HEADER_FORMAT, raw)))


def read_ip_header(raw: bytes) -> dict:
    """Get information from raw IP header data.
    Args:
        raw: Bytes. Raw data of IP header.
    Returns:
        A map contains the infos from the raw header.
    """
    def stringify_ip(ip: int) -> str:
        return ".".join(str(ip >> offset & 0xff) for offset in (24, 16, 8, 0))  # str(ipaddress.ip_address(ip))

    ip_header_keys = ('version', 'tos', 'len', 'id', 'flags', 'ttl', 'protocol', 'checksum', 'src_addr', 'dest_addr')
    ip_header = dict(zip(ip_header_keys, struct.unpack(IP_HEADER_FORMAT, raw)))
    ip_header['src_addr'] = stringify_ip(ip_header['src_addr'])
    ip_header['dest_addr'] = stringify_ip(ip_header['dest_addr'])
    return ip_header


# @_func_logger
def send_one_ping(sock: socket, dest_addr: str, icmp_id: int, seq: int, size: int):
    """Sends one ping to the given destination.
    ICMP Header (bits): type (8), code (8), checksum (16), id (16), sequence (16)
    ICMP Payload: time (double), data
    ICMP Wikipedia: https://en.wikipedia.org/wiki/Internet_Control_Message_Protocol
    Args:
        sock: Socket.
        dest_addr: The destination address, can be an IP address or a domain name. Ex. "192.168.1.1"/"example.com"
        icmp_id: ICMP packet id. Calculated from Process ID and Thread ID.
        seq: ICMP packet sequence, usually increases from 0 in the same process.
        size: The ICMP packet payload size in bytes. Note this is only for the payload part.
    Raises:
        HostUnkown: If destination address is a domain name and cannot resolved.
    """
    _debug("Destination Address: '{}'".format(dest_addr))
    try:
        dest_addr = dest_addr # socket.gethostbyname(dest_addr)  # Domain name will translated into IP address, and IP address leaves unchanged.
    except Exception as err:
        print(str(err))
    _debug("Destination Address:", dest_addr)
    pseudo_checksum = 0  # Pseudo checksum is used to calculate the real checksum.
    icmp_header = struct.pack(ICMP_HEADER_FORMAT, IcmpType.ECHO_REQUEST, ICMP_DEFAULT_CODE, pseudo_checksum, icmp_id, seq)
    padding = (size - struct.calcsize(ICMP_TIME_FORMAT)) * "Q"  # Using double to store current time.
    icmp_payload = struct.pack(ICMP_TIME_FORMAT, time.time()) + padding.encode()
    real_checksum = checksum(icmp_header + icmp_payload)  # Calculates the checksum on the dummy header and the icmp_payload.
    # Don't know why I need socket.htons() on real_checksum since ICMP_HEADER_FORMAT already in Network Bytes Order (big-endian)
    # print(real_checksum, socket.htons(real_checksum))
    def __htons(x):
        v = '%x' % x
        vv = ''.join([v[i-2:i] for i in range(len(v), 0, -2)])
        return int(vv, 16)
    icmp_header = struct.pack(ICMP_HEADER_FORMAT, IcmpType.ECHO_REQUEST, ICMP_DEFAULT_CODE, __htons(real_checksum), icmp_id, seq)  # Put real checksum into ICMP header.
    # icmp_header = struct.pack(ICMP_HEADER_FORMAT, IcmpType.ECHO_REQUEST, ICMP_DEFAULT_CODE, real_checksum, icmp_id, seq)  # Put real checksum into ICMP header.
    _debug("Sent ICMP Header:", read_icmp_header(icmp_header))
    _debug("Sent ICMP Payload:", icmp_payload)
    packet = icmp_header + icmp_payload
    sock.sendto(packet, (dest_addr, 0))  # addr = (ip, port). Port is 0 respectively the OS default behavior will be used.


# @_func_logger
def receive_one_ping(sock: socket, icmp_id: int, seq: int, timeout: int) -> float:
    """Receives the ping from the socket.
    IP Header (bits): version (8), type of service (8), length (16), id (16), flags (16), time to live (8), protocol (8), checksum (16), source ip (32), destination ip (32).
    ICMP Packet (bytes): IP Header (20), ICMP Header (8), ICMP Payload (*).
    Ping Wikipedia: https://en.wikipedia.org/wiki/Ping_(networking_utility)
    ToS (Type of Service) in IP header for ICMP is 0. Protocol in IP header for ICMP is 1.
    Args:
        sock: The same socket used for send the ping.
        icmp_id: ICMP packet id. Sent packet id should be identical with received packet id.
        seq: ICMP packet sequence. Sent packet sequence should be identical with received packet sequence.
        timeout: Timeout in seconds.
    Returns:
        The delay in seconds or None on timeout.
    Raises:
        TimeToLiveExpired: If the Time-To-Live in IP Header is not large enough for destination.
        TimeExceeded: If time exceeded but Time-To-Live does not expired.
        DestinationHostUnreachable: If the destination host is unreachable.
        DestinationUnreachable: If the destination is unreachable.
    """
    # ip_header_slice = slice(0, struct.calcsize(IP_HEADER_FORMAT))  # [0:20]
    ip_header_slice_stop = struct.calcsize(IP_HEADER_FORMAT)
    # icmp_header_slice = slice(ip_header_slice.stop, ip_header_slice.stop + struct.calcsize(ICMP_HEADER_FORMAT))  # [20:28]
    icmp_header_slice_start = ip_header_slice_stop
    icmp_header_slice_stop = ip_header_slice_stop + struct.calcsize(ICMP_HEADER_FORMAT)
    timeout_time = time.time() + timeout  # Exactly time when timeout.
    _debug("Timeout time:", timeout_time)
    while True:
        timeout_left = timeout_time - time.time()  # How many seconds left until timeout.
        timeout_left = timeout_left if timeout_left > 0 else 0  # Timeout must be non-negative
        _debug("Timeout left: {:.2f}s".format(timeout_left))
        selected = select.select([sock, ], [], [], timeout_left)  # Wait until sock is ready to read or time is out.
        if selected[0] == []:  # Timeout
            raise Timeout(timeout)
        time_recv = time.time()
        recv_data, addr = sock.recvfrom(1024)
        ip_header_raw, icmp_header_raw, icmp_payload_raw = recv_data[0:ip_header_slice_stop], recv_data[icmp_header_slice_start:icmp_header_slice_stop], recv_data[icmp_header_slice_stop:]
        ip_header = read_ip_header(ip_header_raw)
        _debug("Received IP Header:", ip_header)
        icmp_header = read_icmp_header(icmp_header_raw)
        _debug("Received ICMP Header:", icmp_header)
        _debug("Received ICMP Payload:", icmp_payload_raw)
        if icmp_header['id'] and icmp_header['id'] != icmp_id:  # ECHO_REPLY should match the ID field.
            _debug("ICMP ID dismatch. Packet filtered out.")
            continue
        if icmp_header['type'] == IcmpType.TIME_EXCEEDED:  # TIME_EXCEEDED has no icmp_id and icmp_seq. Usually they are 0.
            if icmp_header['code'] == IcmpTimeExceededCode.TTL_EXPIRED:
                raise TimeToLiveExpired()  # Some router does not report TTL expired and then timeout shows.
            raise TimeExceeded()
        if icmp_header['type'] == IcmpType.DESTINATION_UNREACHABLE:  # DESTINATION_UNREACHABLE has no icmp_id and icmp_seq. Usually they are 0.
            if icmp_header['code'] == IcmpDestinationUnreachableCode.DESTINATION_HOST_UNREACHABLE:
                raise DestinationHostUnreachable()
            raise DestinationUnreachable()
        if icmp_header['id'] and icmp_header['seq'] == seq:  # ECHO_REPLY should match the SEQ field.
            if icmp_header['type'] == IcmpType.ECHO_REQUEST:  # filters out the ECHO_REQUEST itself.
                _debug("ECHO_REQUEST received. Packet filtered out.")
                continue
            if icmp_header['type'] == IcmpType.ECHO_REPLY:
                time_sent = struct.unpack(ICMP_TIME_FORMAT, icmp_payload_raw[0:struct.calcsize(ICMP_TIME_FORMAT)])[0]
                return time_recv - time_sent
        _debug("Uncatched ICMP Packet:", icmp_header)


# @_func_logger
def ping(dest_addr: str, timeout: int = 4, unit: str = "s", src_addr: str = None, ttl: int = None, seq: int = 0, size: int = 56, interface: str = None) -> float:
    """
    Send one ping to destination address with the given timeout.
    Args:
        dest_addr: The destination address, can be an IP address or a domain name. Ex. "192.168.1.1"/"example.com"
        timeout: Time to wait for a response, in seconds. Default is 4s, same as Windows CMD. (default 4)
        unit: The unit of returned value. "s" for seconds, "ms" for milliseconds. (default "s")
        src_addr: WINDOWS ONLY. The IP address to ping from. This is for multiple network interfaces. Ex. "192.168.1.20". (default None)
        interface: LINUX ONLY. The gateway network interface to ping from. Ex. "wlan0". (default None)
        ttl: The Time-To-Live of the outgoing packet. Default is None, which means using OS default ttl -- 64 onLinux and macOS, and 128 on Windows. (default None)
        seq: ICMP packet sequence, usually increases from 0 in the same process. (default 0)
        size: The ICMP packet payload size in bytes. If the input of this is less than the bytes of a double format (usually 8), the size of ICMP packet payload is 8 bytes to hold a time. The max should be the router_MTU(Usually 1480) - IP_Header(20) - ICMP_Header(8). Default is 56, same as in macOS. (default 56)
    Returns:
        The delay in seconds/milliseconds or None on timeout.
    Raises:
        PingError: Any PingError will raise again if `ping3.EXCEPTIONS` is True.
    """
    if sys.platform == "Darwin":
        socket_type = socket.SOCK_DGRAM
    else:
        socket_type = socket.SOCK_RAW
    IPPROTO_ICMP = 1
    IPPROTO_IP = 0
    SOL_IP = 0
    IP_TTL = 4
    SOL_SOCKET = 65535
    sock = socket.socket(socket.AF_INET, socket_type, IPPROTO_ICMP)
    if ttl:
        try:  # IPPROTO_IP is for Windows and BSD Linux.
            if sock.getsockopt(IPPROTO_IP, IP_TTL):
                sock.setsockopt(IPPROTO_IP, IP_TTL, ttl)
        except OSError as err:
            _debug("Set Socket Option `IP_TTL` in `IPPROTO_IP` Failed: {}".format(err))
        try:
            if sock.getsockopt(SOL_IP, IP_TTL):
                sock.setsockopt(SOL_IP, IP_TTL, ttl)
        except OSError as err:
            _debug("Set Socket Option `IP_TTL` in `SOL_IP` Failed: {}".format(err))
    if interface:
        sock.setsockopt(SOL_SOCKET, SOCKET_SO_BINDTODEVICE, interface.encode())  # packets will be sent from specified interface.
        _debug("Socket Interface Binded:", interface)
    if src_addr:
        sock.bind((src_addr, 0))  # only packets send to src_addr are received.
        _debug("Socket Source Address Binded:", src_addr)
    thread_id = 0 # threading.get_native_id() if hasattr(threading, 'get_native_id') else threading.currentThread().ident  # threading.get_native_id() is supported >= python3.8.
    process_id = 0 # os.getpid()  # If ping() run under different process, thread_id may be identical.
    icmp_id = crc32.crc_update("{}{}".format(process_id, thread_id).encode(), 0) & 0xffff  # to avoid icmp_id collision.
    try:
        send_one_ping(sock=sock, dest_addr=dest_addr, icmp_id=icmp_id, seq=seq, size=size)
        delay = receive_one_ping(sock=sock, icmp_id=icmp_id, seq=seq, timeout=timeout)  # in seconds
    except HostUnknown as err:  # Unsolved
        _debug(err)
        _raise(err)
        return False
    except PingError as err:
        _debug(err)
        _raise(err)
        return None
    finally:
        try:
            sock.close()
        except:
            pass
    if delay is None:
        return None
    if unit == "ms":
        delay *= 1000  # in milliseconds
    return delay


# @_func_logger
def verbose_ping(dest_addr: str, count: int = 4, interval: float = 0, *args, **kwargs):
    """
    Send pings to destination address with the given timeout and display the result.
    Args:
        dest_addr: The destination address. Ex. "192.168.1.1"/"example.com"
        count: How many pings should be sent. Default is 4, same as Windows CMD. (default 4)
        interval: How many seconds between two packets. Default is 0, which means send the next packet as soon as the previous one responsed. (default 0)
        *args and **kwargs: And all the other arguments available in ping() except `seq`.
    Returns:
        Formatted ping results printed.
    """
    timeout = kwargs.get("timeout")
    src = kwargs.get("src")
    unit = kwargs.setdefault("unit", "ms")
    for i in range(count):
        output_text = "ping '{}'".format(dest_addr)
        output_text += " from '{}'".format(src) if src else ""
        output_text += " ... "
        delay = ping(dest_addr, seq=i, *args, **kwargs)
        print(output_text, end="")
        if delay is None:
            print("Timeout > {}s".format(timeout) if timeout else "Timeout")
        else:
            print("{value}{unit}".format(value=int(delay), unit=unit))
        if interval > 0 and i < (count - 1):
            time.sleep(interval)


if __name__ == "__main__":
    # import command_line_ping3
    # command_line_ping3.main()
    verbose_ping('192.168.0.1')
    print(ping('192.168.0.1'))