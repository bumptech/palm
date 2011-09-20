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

def gen_module(messages, imports, tlenums):
    global pfx
    global o
    pfx = ''

    out('from palm.palm import ProtoBase, RepeatedSequence\n\n')
    for i in imports:
        out('from %s import *\n' % convert_proto_name(i))

    for ename, espec in tlenums:
        write_enum(ename, espec)

    for n, (fields, subs, en) in messages:
        write_class(n, '', fields, subs, en)

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
# Enumeration: %s
''' % name)
    for cn, value in sorted(spec.items(), key=lambda (k, v): v):
        out('''
%s = %s\n''' % (cn, value))
    out('''

TYPE_%s = ProtoBase.TYPE_int32
'''
% name)

def write_class(name, scope, fields, subs, enums):
    global pfx
    name = clean(name)
    out(
'''
class %s(ProtoBase):
    def __init__(self, _pbf_buf='', _pbf_parent_callback=None, **kw): 
        self._pbf_parent_callback = _pbf_parent_callback
        self._cache = {}
        self._pbf_establish_parent_callback = None
        self._required = [%s]
        ProtoBase.__init__(self, _pbf_buf, **kw)

    def fields(self):
        return ['%s']

    def __str__(self):
        return '\\n'.join('%%s: %%s' %% (f, repr(getattr(self, '_get_%%s' %% f)())) for f in self.fields()
                          if getattr(self, '%%s__exists' %% f))
''' % (name,
       ", ".join(str(num) for num, (req, _, _, _) in fields.iteritems() if req == 'required'),
       "', '".join(name for _, _, name, _ in fields.values())))

    ns = set()
    for ename, espec in enums.iteritems():
        pfx += "    "
        write_enum(ename, espec)
        pfx = pfx[:-4]
        ns.add(ename)

    next_scope = name if not scope else ".".join([scope, name])
    for sn, (sf, ss, sens) in subs:
        pfx += "    "
        write_class(sn, next_scope, sf, ss, sens)
        pfx = pfx[:-4]
        snm = clean(sn)
        ns.add(snm)
        out(
'''
    TYPE_%s = %s
'''  % (snm, snm))

    # TODO -- submessages
    for num, field in fields.iteritems():
        write_field(name, scope, num, field, ns)

    out('''
TYPE_%s = %s
''' % (name, name))

def write_field_get(num, type, name, default, scope):
    if default is not None:
        r = '''
            try:
                r = self._buf_get(%s, %sTYPE_%s, '%s')
            except:
                r = ''' + str(default)
    else:
        r = '''
            r = self._buf_get(%s, %sTYPE_%s, '%s')'''
    return r % (num, scope, type, name)

def write_field(cname, parent, num, field, parent_ns):
    req, type, name, default = field
    if hasattr(ProtoBase, 'TYPE_%s' % type):
        scope = 'ProtoBase.'
    elif type in parent_ns:
        scope = '%s.' % (cname if not parent else ".".join([parent, cname]))
    else:
        scope = ''
    if req == 'repeated':
        out(
'''
    class Repeated_%s(RepeatedSequence): 
        class pb_subtype(object):
            def __get__(self, instance, cls):
                return %sTYPE_%s
        pb_subtype = pb_subtype()


    TYPE_Repeated_%s = Repeated_%s
''' % (name, scope, type, name, name))
        type = 'Repeated_%s' % name
        scope = 'self.'
    out(
'''
    def _get_%(name)s(self):
        if %(num)s in self._cache:
            r = self._cache[%(num)s]
        else:%(field_get)s
            self._cache[%(num)s] = r
        return r

    def _establish_parentage_%(name)s(self, v):
        if isinstance(v, (ProtoBase, RepeatedSequence)):
            if v._pbf_parent_callback:
                assert (v._pbf_parent_callback == self._mod_%(name)s), "subobjects can only have one parent--use copy()?"
            else:
                v._pbf_parent_callback = self._mod_%(name)s
                v._pbf_establish_parent_callback = self._establish_parentage_%(name)s

    def _set_%(name)s(self, v):
        self._evermod = True
        if self._pbf_parent_callback:
            self._pbf_parent_callback()
        if isinstance(v, (ProtoBase, RepeatedSequence)):
            self._establish_parentage_%(name)s(v)
        self._cache[%(num)s] = v
        self._mods[%(num)s] = %(scope)sTYPE_%(type)s

    def _mod_%(name)s(self):
        self._evermod = True
        if self._pbf_parent_callback:
            self._pbf_parent_callback()
        self._mods[%(num)s] = %(scope)sTYPE_%(type)s

    def _del_%(name)s(self):
        self._evermod = True
        if self._pbf_parent_callback:
            self._pbf_parent_callback()
        if %(num)s in self._cache:
            del self._cache[%(num)s]
        if %(num)s in self._mods:
            del self._mods[%(num)s]
        self._buf_del(%(num)s)

    _pb_field_name_%(num)d = "%(num)s"

    %(name)s = property(_get_%(name)s, _set_%(name)s, _del_%(name)s)

    @property
    def %(name)s__exists(self):
        return %(num)s in self._mods or self._buf_exists(%(num)s)

    def __contains__(self, item):
        try:
            return getattr(self, '%%s__exists' %% item)
        except AttributeError:
            return False
''' % {
    'name':name, 
    'num':num, 
    'field_get':write_field_get(num, type, name, default, scope), 
    'type':type,
    'scope':scope})
