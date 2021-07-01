# fork by https://github.com/slavaromanov/crc32/blob/master/src/python/crc32.py

def create_table_generater():
    for i in range(256):
        k = i
        for _ in range(8):
            if k & 1:
                k ^= 0x1db710640
            k >>= 1
        yield k
 
def get_crc_table_value(crc, k):
    # for i, v in enumerate(create_table_generater()):
    #     if i == (crc & 0xff) ^ k:
    #         return v
    return [v for i, v in enumerate(create_table_generater()) if i == (crc & 0xff) ^ k][0]

def crc_update(buf, crc):
    crc ^= 0xffffffff
    for k in buf:
        crc_table_value = get_crc_table_value(crc, k) 
        crc = (crc >> 8) ^ crc_table_value
    return crc ^ 0xffffffff
