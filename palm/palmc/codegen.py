import sys
import os
from palm.palm import ProtoBase
pfx = ''
o = []
def convert_proto_name(n):
    n = os.path.basename(n)
    p, last = n.rsplit(".", 1)
    assert last == "proto"
    return "%s_palm" % p

def gen_module(messages, imports):
    global pfx
    global o
    pfx = ''

    out('from palm.palm import ProtoBase, RepeatedSequence, ProtoEnumeration\n\n')
    for i in imports:
        out('from %s import *\n' % convert_proto_name(i))
    for (n, fields, subs, en) in messages:
        write_class(n, fields, subs, en)

    all = ''.join(o)

    o = []
    return all

def out(s):
    global o
    s = pfx + s.replace("\n", "\n" + pfx)
    o.append(s)

def clean(name):
    return name.split('-', 1)[1]

def write_enum(name, spec):
    out(
'''
class %s(ProtoEnumeration):
''' % name)
    for cn, value in sorted(spec.items(), key=lambda (k, v): v):
        out('%s = %s\n' % (cn, value))
    out('''

TYPE_%s = ProtoBase.TYPE_int32
'''
% name)

def write_class(name, fields, subs, enums):
    global pfx
    name = clean(name)
    out(
'''
class %s(ProtoBase):
    def __init__(self, _pbf_buf='', _pbf_parent_callback=None, **kw): 
        ProtoBase.__init__(self, _pbf_buf, **kw)
        self._cache = {}
        self._pbf_parent_callback = _pbf_parent_callback
        self._pbf_establish_parent_callback = None

    def fields(self):
        return ['%s']

    def __str__(self):
        return '\\n'.join('%%s: %%s' %% (f, repr(getattr(self, '_get_%%s' %% f)())) for f in self.fields()
                          if getattr(self, '%%s__exists' %% f))
''' % (name,
       "', '".join(name for _, _, name, _ in fields.values())))

    for ename, espec in enums.iteritems():
        pfx += "    "
        write_enum(ename, espec)
        pfx = pfx[:-4]

    for sn, (sf, ss), ens in subs:
        pfx += "    "
        write_class(sn, sf, ss, ens)
        pfx = pfx[:-4]
        snm = clean(sn)
        out(
'''
    TYPE_%s = %s
'''  % (snm, snm))

    # TODO -- submessages
    for num, field in fields.iteritems():
        write_field(name, num, field)

def write_field_get(num, type, name, default):
    if default is not None:
        r = '''
            try:
                r = self._buf_get(%s, self.TYPE_%s, '%s')
            except:
                r = ''' + str(default)
    else:
        r = '''
            r = self._buf_get(%s, self.TYPE_%s, '%s')'''
    return r % (num, type, name)

def write_field(cname, num, field):
    req, type, name, default = field
    if req == 'repeated':
        out(
'''
    class Repeated_%s(RepeatedSequence): 
        pb_subtype = None 
    Repeated_%s.pb_subtype = %sTYPE_%s

    TYPE_Repeated_%s = Repeated_%s
''' % (name, name,
    'ProtoBase.' if hasattr(ProtoBase, 'TYPE_%s' % type) else '',
    type, name, name)
    )
        type = 'Repeated_%s' % name
    out(
'''
    def _get_%s(self):
        if %s in self._cache:
            r = self._cache[%s]
        else:%s
            self._cache[%s] = r
        return r

    def _establish_parentage_%s(self, v):
        if isinstance(v, (ProtoBase, RepeatedSequence)):
            if v._pbf_parent_callback:
                assert (v._pbf_parent_callback == self._mod_%s), "subobjects can only have one parent--use copy()?"
            else:
                v._pbf_parent_callback = self._mod_%s
                v._pbf_establish_parent_callback = self._establish_parentage_%s

    def _set_%s(self, v):
        self._evermod = True
        if self._pbf_parent_callback:
            self._pbf_parent_callback()
        if isinstance(v, (ProtoBase, RepeatedSequence)):
            self._establish_parentage_%s(v)
        self._cache[%s] = v
        self._mods[%s] = self.TYPE_%s

    def _mod_%s(self):
        self._evermod = True
        if self._pbf_parent_callback:
            self._pbf_parent_callback()
        self._mods[%s] = self.TYPE_%s

    def _del_%s(self):
        self._evermod = True
        if self._pbf_parent_callback:
            self._pbf_parent_callback()
        if %s in self._cache:
            del self._cache[%s]
        if %s in self._mods:
            del self._mods[%s]
        self._buf_del(%s)

    _pb_field_name_%d = "%s"

    %s = property(_get_%s, _set_%s, _del_%s)

    @property
    def %s__exists(self):
        return %s in self._mods or self._buf_exists(%s)

''' % (name, num, num, write_field_get(num, type, name, default), num,
    name, name, name, name,
    name, name, num, num, type,
    name, num, type,
    name, num, num, num, num, num,
    num, name,
    name, name, name, name,
    name, num, num))
