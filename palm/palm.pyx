ctypedef int int32_t
ctypedef long long int64_t
ctypedef unsigned int uint32_t
ctypedef unsigned long long uint64_t

cdef extern from "stdlib.h":
    void free(void *)

cdef extern from "palmcore.h":
    ctypedef struct pbf_protobuf:
        pass
    pbf_protobuf * pbf_load(char *data, uint64_t size)
    void pbf_free(pbf_protobuf *pbf)
    int pbf_get_bytes(pbf_protobuf *pbf, uint64_t field_num,
        char **out, uint64_t *length)
    int pbf_get_integer(pbf_protobuf *pbf, uint64_t field_num, uint64_t *res)
    int pbf_get_signed_integer(pbf_protobuf *pbf,
        uint64_t field_num, int64_t *res,
        int32_t *res32, int use_zigzag)
    int pbf_exists(pbf_protobuf *pbf, uint64_t field_num)
    int pbf_set_bytes(pbf_protobuf *pbf, uint64_t field_num,
        char *out, uint64_t length)
    unsigned char *pbf_serialize(pbf_protobuf *pbf, int *length)

    int pbf_set_integer(pbf_protobuf *pbf, uint64_t field_num,
        uint64_t value, int fixed)
    int pbf_set_signed_integer(pbf_protobuf *pbf, uint64_t field_num,
        int64_t value, int zigzag)

    void pbf_remove(pbf_protobuf *pbf, uint64_t field_num)

    ctypedef void(*pbf_byte_stream_callback) (char *, uint64_t length, void *)
    ctypedef void(*pbf_uint_stream_callback) (uint64_t, void *)
    ctypedef void(*pbf_sint_stream_callback) (int64_t, int32_t, void *)

    int pbf_get_bytes_stream(pbf_protobuf *pbf, uint64_t field_num,
            pbf_byte_stream_callback cb, void *passthrough)

    int pbf_get_integer_stream(pbf_protobuf *pbf, uint64_t field_num, 
            pbf_uint_stream_callback cb, void *passthrough)

    int pbf_get_signed_integer_stream(pbf_protobuf *pbf,
            uint64_t field_num, int use_32, int use_zigzag,
            pbf_sint_stream_callback cb, void *passthrough)

class ProtoFieldMissing(Exception): pass
class ProtoDataError(Exception): pass

cdef void byte_string_cb(char *s, uint64_t l, void *ar):
    py_s = unicode(s[:l], "utf-8")
    (<object>ar).append(py_s)

cdef void byte_byte_cb(char *s, uint64_t l, void *ar):
    (<object>ar).append(s[:l])

cdef void signed_signed32_cb(int64_t i64, int32_t i32, void *ar):
    (<object>ar).append(i32)

cdef void signed_signed64_cb(int64_t i64, int32_t i32, void * ar):
    (<object>ar).append(i64)
    
cdef void unsigned_get(uint64_t u64, void * ar):
    (<object>ar).append(u64)

cdef void unsigned_float_get(uint64_t u64, void * ar):
    cdef float fl = (<float*>&u64)[0]
    (<object>ar).append(fl)

cdef void unsigned_double_get(uint64_t u64, void * ar):
    cdef double db = (<double*>&u64)[0]
    (<object>ar).append(db)

cdef class ProtoBase:
    (TYPE_string,
     TYPE_bytes,
     TYPE_int32,
     TYPE_int64,
     TYPE_uint32,
     TYPE_uint64,
     TYPE_sint32,
     TYPE_sint64,
     TYPE_fixed64,
     TYPE_sfixed64,
     TYPE_double,
     TYPE_fixed32,
     TYPE_sfixed32,
     TYPE_float,
     ) = range(14)

    cdef pbf_protobuf *buf

    cdef int CTYPE_string
    cdef int CTYPE_bytes
    cdef int CTYPE_int32
    cdef int CTYPE_int64
    cdef int CTYPE_uint32
    cdef int CTYPE_uint64
    cdef int CTYPE_sint32
    cdef int CTYPE_sint64
    cdef int CTYPE_fixed64
    cdef int CTYPE_sfixed64
    cdef int CTYPE_double
    cdef int CTYPE_fixed32
    cdef int CTYPE_sfixed32
    cdef int CTYPE_float

    def __init__(self, data):
        self._data = data
        self.buf = pbf_load(data, len(data))
        self._evermod = False
        if (self.buf == NULL):
            self._data = None
            raise ProtoDataError("Invalid or unsupported protobuf data")
        self.CTYPE_string = self.TYPE_string
        self.CTYPE_bytes = self.TYPE_bytes
        self.CTYPE_int32 = self.TYPE_int32
        self.CTYPE_int64 = self.TYPE_int64
        self.CTYPE_uint32 = self.TYPE_uint32
        self.CTYPE_uint64 = self.TYPE_uint64
        self.CTYPE_sint32 = self.TYPE_sint32
        self.CTYPE_sint64 = self.TYPE_sint64
        self.CTYPE_fixed64 = self.TYPE_fixed64
        self.CTYPE_sfixed64 = self.TYPE_sfixed64
        self.CTYPE_double = self.TYPE_double
        self.CTYPE_fixed32 = self.TYPE_fixed32
        self.CTYPE_sfixed32 = self.TYPE_sfixed32
        self.CTYPE_float = self.TYPE_float

    def _get_submessage(self, field, typ, name):
        cdef char *res
        cdef uint64_t rlen
        cdef int got

        got = pbf_get_bytes(self.buf, field, &res, &rlen)
        if not got:
            raise ProtoFieldMissing(name)
        bout = res[:rlen]

        inst = typ(bout, getattr(self, '_mod_%s' % name))
        return inst

    def _get_repeated(self, field, typ, name):
        cdef int ctyp

        l = []
        if type(typ.pb_subtype) is not int:
            sl = []
            assert issubclass(typ.pb_subtype, ProtoBase)
            pbf_get_bytes_stream(self.buf, field,
                    byte_byte_cb, <void *>sl)
            mod = getattr(self, '_mod_%s' % name)
            for i in sl:
                l.append(typ.pb_subtype(i, _pbf_parent_callback=mod))

        else:
            ctyp = typ.pb_subtype
            if ctyp == self.CTYPE_string:
                pbf_get_bytes_stream(self.buf, field,
                        byte_string_cb, <void *>l)
            elif ctyp == self.CTYPE_bytes:
                pbf_get_bytes_stream(self.buf, field,
                        byte_byte_cb, <void *>l)
            elif ctyp == self.CTYPE_int32 or \
                 ctyp == self.CTYPE_sfixed32:
                pbf_get_signed_integer_stream(self.buf,
                        field, 1, 0, signed_signed32_cb,
                        <void *>l)
            elif ctyp == self.CTYPE_sint32:
                pbf_get_signed_integer_stream(self.buf,
                        field, 1, 1, signed_signed32_cb,
                        <void *>l)
            elif ctyp == self.CTYPE_uint32 or \
                 ctyp == self.CTYPE_uint64 or \
                 ctyp == self.CTYPE_fixed32 or \
                 ctyp == self.CTYPE_fixed64:
                pbf_get_integer_stream(self.buf, field, 
                        unsigned_get, <void *>l)
            elif ctyp == self.CTYPE_int64 or \
                 ctyp == self.CTYPE_sfixed64:
                pbf_get_signed_integer_stream(self.buf,
                        field, 0, 0, signed_signed64_cb,
                        <void *>l)
            elif ctyp == self.CTYPE_sint64:
                pbf_get_signed_integer_stream(self.buf,
                        field, 0, 1, signed_signed64_cb,
                        <void *>l)
            elif ctyp == self.CTYPE_double:
                pbf_get_integer_stream(self.buf, field, 
                        unsigned_double_get, <void *>l)
            elif ctyp == self.CTYPE_float:
                pbf_get_integer_stream(self.buf, field, 
                        unsigned_float_get, <void *>l)
            else:
                assert 0, ("unknown type %s" % typ.pb_subtype)


        # Implied: l may be empty if there were no values
        t = typ(l)
        setattr(self, name, t) # invoke usual handlers, etc
        return t

    def _buf_get(self, field, typ, name):
        if type(typ) is not int:
            if issubclass (typ, ProtoBase):
                return self._get_submessage(field, typ, name)
            else: # repeated
                return self._get_repeated(field, typ, name)
        cdef int ctyp = typ
        cdef char *res
        cdef uint64_t rlen
        cdef int32_t si
        cdef int64_t sq
        cdef uint64_t uq
        cdef double db
        cdef float fl

        cdef int got
        if ctyp == self.CTYPE_string:
            got = pbf_get_bytes(self.buf, field, &res, &rlen)
            if not got:
                raise ProtoFieldMissing(name)
            return unicode(res[:rlen], "utf-8")
        elif ctyp == self.CTYPE_bytes:
            got = pbf_get_bytes(self.buf, field, &res, &rlen)
            if not got:
                raise ProtoFieldMissing(name)
            return res[:rlen]
        elif ctyp == self.CTYPE_int32 or \
             ctyp == self.CTYPE_sfixed32:
            got = pbf_get_signed_integer(self.buf,
                    field, NULL, &si, 0)
            if not got:
                raise ProtoFieldMissing(name)
            return si
        elif ctyp == self.CTYPE_sint32:
            got = pbf_get_signed_integer(self.buf,
                    field, NULL, &si, 1)
            if not got:
                raise ProtoFieldMissing(name)
            return si
        elif ctyp == self.CTYPE_uint32 or \
             ctyp == self.CTYPE_uint64 or \
             ctyp == self.CTYPE_fixed64 or \
             ctyp == self.CTYPE_fixed32:
            got = pbf_get_integer(self.buf,
                    field, &uq)
            if not got:
                raise ProtoFieldMissing(name)
            return uq
        elif ctyp == self.CTYPE_double:
            got = pbf_get_integer(self.buf,
                    field, <uint64_t*>&db)
            if not got:
                raise ProtoFieldMissing(name)
            return db
        elif ctyp == self.CTYPE_float:
            got = pbf_get_integer(self.buf,
                    field, &uq)
            if not got:
                raise ProtoFieldMissing(name)
            fl = (<float*>&uq)[0]
            return fl
        elif ctyp == self.CTYPE_int64 or \
             ctyp == self.CTYPE_sfixed64:
            got = pbf_get_signed_integer(self.buf,
                    field, &sq, NULL, 0)
            if not got:
                raise ProtoFieldMissing(name)
            return sq
        elif ctyp == self.CTYPE_sint64:
            got = pbf_get_signed_integer(self.buf,
                    field, &sq, NULL, 1)
            if not got:
                raise ProtoFieldMissing(name)
            return sq

        assert 0, "should not reach here!"

    def _buf_exists(self, field):
        cdef int e
        e = pbf_exists(self.buf, field)
        return bool(e)

    def _buf_del(self, field):
        pbf_remove(self.buf, field)

    def __dealloc__(self):
        if self.buf != NULL:
            pbf_free(self.buf)

    def dumps(self):
        if not self._evermod:
            return self._data
        self._save()
        self._mods = {}
        return self._serialize()

    cdef _save_item(self, f, ctyp, v):
        cdef int64_t sq
        cdef double db
        cdef float fl

        try:
            if ctyp == self.CTYPE_string:
                if type(v) is unicode:
                    v = v.encode("utf-8")
                l = len(v)
                pbf_set_bytes(self.buf,
                    f, v, l)
            elif ctyp == self.CTYPE_bytes:
                l = len(v)
                pbf_set_bytes(self.buf,
                    f, v, l)
            elif ctyp == self.CTYPE_uint32 or ctyp == self.CTYPE_uint64:
                pbf_set_integer(self.buf, f, v, 0)
            elif ctyp == self.CTYPE_int32 or ctyp == self.CTYPE_int64:
                pbf_set_signed_integer(self.buf, f, v, 0)
            elif ctyp == self.CTYPE_sint32 or ctyp == self.CTYPE_sint64:
                pbf_set_signed_integer(self.buf, f, v, 1)
            elif ctyp == self.CTYPE_fixed64:
                pbf_set_integer(self.buf, f, v, 64)
            elif ctyp == self.CTYPE_fixed32:
                pbf_set_integer(self.buf, f, v, 32)
            elif ctyp == self.CTYPE_sfixed64:
                sq = v
                pbf_set_integer(self.buf, f, (<uint64_t*>&sq)[0], 64)
            elif ctyp == self.CTYPE_sfixed32:
                sq = v
                pbf_set_integer(self.buf, f, (<uint64_t*>&sq)[0], 32)
            elif ctyp == self.CTYPE_double:
                db = v
                pbf_set_integer(self.buf, f, (<uint64_t*>&db)[0], 64)
            elif ctyp == self.CTYPE_float:
                fl = v
                pbf_set_integer(self.buf, f, (<uint32_t*>&fl)[0], 32)
            else:
                assert 0, "unimplemented"
        except Exception, e:
            raise ProtoValueError("Value exception while saving %s.%s: %s" %
                    (self.__class__.__name__,
                        getattr(self, '_pb_field_name_%d' % f), str(e)))

    def _save(self):
        cdef int ctyp

        for f, v in self._cache.iteritems():
            if f in self._mods:
                pbf_remove(self.buf, f)
                typ = self._mods[f]
                if isinstance(v, ProtoBase):
                    o = v.dumps()
                    l = len(o)
                    pbf_set_bytes(self.buf,
                        f, o, l)
                elif isinstance(v, RepeatedSequence):
                    if type(v.pb_subtype) != int:
                        assert issubclass(v.pb_subtype, ProtoBase)
                        for i in v:
                            o = i.dumps()
                            l = len(o)
                            pbf_set_bytes(self.buf,
                            f, o, l)
                    else:
                        ctyp = v.pb_subtype
                        for i in v:
                            self._save_item(f, ctyp, i)
                else:
                    ctyp = typ
                    self._save_item(f, ctyp, v)

    def _serialize(self):
        cdef unsigned char *cout
        cdef int length
        cout = pbf_serialize(self.buf, &length)
        pyout = cout[:length]
        free(cout)
        return pyout

    def copy(self):
        return self.__class__(self.dumps())

cdef class RepeatedSequence(list):
    pb_subtype = None
    def __init__(self, *args, **kw):
        list.__init__(self, *args, **kw)
        self._pbf_establish_parent_callback = None
        self._pbf_parent_callback = None

    def _pbf_child_touched(self, v=None):
        if isinstance(v, (ProtoBase, RepeatedSequence)):
            self._pbf_establish_parent_callback(v)
        self._pbf_parent_callback()

    # now--the ugly business of intercepting list modifications
    def __delitem__(self, i):
        self._pbf_child_touched()
        list.__delitem__(self, i)

    def __setitem__(self, k, v):
        self._pbf_child_touched(v)
        list.__setitem__(self, k, v)

    def append(self, v):
        self._pbf_child_touched(v)
        list.append(self, v)

    def extend(self, vs):
        for v in vs:
            self.append(v)

    def insert(self, i, v):
        self._pbf_child_touched(v)
        list.insert(self, i, v)

    def copy(self):
        '''Essentially, shed parentage
        '''
        l = list(self)
        return RepeatedSequence(l)
