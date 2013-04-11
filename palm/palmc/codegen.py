import pdb
import sys
import os
from palm.palm import ProtoBase
from palm.palmc.parse import Reference, QualifiedTypeDecl
pfx = ''
o = []
def convert_proto_name(n):
    n = os.path.basename(n)
    p, last = n.rsplit(".", 1)
    assert last == "proto"
    return "%s_palm" % p

def lookup_package(qualifier, type, packages, package):
    # if qualfier begins with a ".", automatically search for
    # fully qualified package
    if qualifier.startswith(".") or package == None or len(package) == 0:
        if qualifier[1:] in packages:
            return convert_proto_name(packages[qualifier[1:]].file) + ".", type
        else:
            return None, type

    # Search for a qualifier by taking the current package
    # and appending the qualifier given to successively "outer"
    # (i.e., shorter) paths on the current package.
    idx = 0
    package_path = package
    while len(package_path) > 0:
        p = package_path + "." + qualifier
        if p in packages:
            return convert_proto_name(packages[p].file) + ".", type

        idx = package_path.rfind(".")
        if idx > -1:
            package_path = package_path[:idx]
        else:
            package_path = ""

    # The qualifier may be an actual package reference, so we
    # check here. We do this last because innermost scope must
    # searched first, and a package curr_package + qualifier may
    # have been imported.
    if qualifier in packages:
        return convert_proto_name(packages[qualifier].file) + ".", type
    else:
        return None, type

def gen_module(messages, imports, tlenums, with_slots, packages, curr_package):
    global pfx
    global o
    pfx = ''

    out('from palm.palm import ProtoBase, is_string, RepeatedSequence, ProtoValueError\n\n_PB_type = type\n_PB_finalizers = []\n\n')
    for i in imports:
        out('import %s\n' % convert_proto_name(i))

    for ename, espec in tlenums:
        write_enum(ename, espec)

    for n, (fields, subs, en) in messages:
        write_class(n, '', fields, subs, en, with_slots, packages, curr_package)

    out('''

for cname in _PB_finalizers:
    eval(cname)._pbf_finalize()

del _PB_finalizers
''')

    all = ''.join(o)

    o = []
    return all

def out(s):
    global o
    s = pfx + s.replace("\n", "\n" + pfx)
    o.append(s)

def clean(name):
    return name.rsplit('-', 1)[1]

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
    out('''
_%s__map = {%s}\n''' % (name,
                        ', '.join(("%s: '%s'" % (value, cn)) for cn, value in spec.items())))
    out('''
@classmethod
def get_%s_name(cls, v):
    return cls._%s__map[v]
''' % (name, name))

def write_class(name, scope, fields, subs, enums, with_slots, packages, curr_package):
    global pfx
    name = clean(name)
    if with_slots:
        slots = '''
    __slots__ = [
        '_data',
        '_pbf_parent_callback',
        '_cache',
        '_pbf_establish_parent_callback',
        '_evermod',
        '_mods',
        '_retains',
    ]
'''
    else:
        slots = ''
    out(
'''
class %s(ProtoBase):
    _required = [%s]
    _field_map = %r
    %s
    def __init__(self, _pbf_buf='', _pbf_parent_callback=None, **kw):
        self._pbf_parent_callback = _pbf_parent_callback
        self._cache = {}
        self._pbf_establish_parent_callback = None
        ProtoBase.__init__(self, _pbf_buf, **kw)

    @classmethod
    def _pbf_finalize(cls):
        for c in cls._pbf_finalizers:
            c(cls)
        del cls._pbf_finalizers

    @classmethod
    def fields(cls):
        return ['%s']

    def modified(self):
        return self._evermod

    def __contains__(self, item):
        try:
            return getattr(self, '%%s__exists' %% item)
        except AttributeError:
            return False

    _pbf_strings = []
    _pbf_finalizers = []

    def __str__(self):
        return '\\n'.join('%%s: %%s' %% (f, repr(getattr(self, '_get_%%s' %% f)())) for f in self.fields()
                          if getattr(self, '%%s__exists' %% f))
''' % (name,
       ", ".join(str(num) for num, (req, _, _, _) in fields.iteritems() if req == 'required'),
       dict((name, num) for num, (_, _, name, _) in fields.iteritems()),
       slots,
       "', '".join(name for _, _, name, _ in fields.values())))

    ns = {}
    for ename, espec in enums.iteritems():
        pfx += "    "
        write_enum(ename, espec)
        pfx = pfx[:-4]
        ns[ename] = 'enum'

    next_scope = name if not scope else ".".join([scope, name])
    for sn, (sf, ss, sens) in subs:
        pfx += "    "
        write_class(sn, next_scope, sf, ss, sens, with_slots, packages, curr_package)
        pfx = pfx[:-4]
        snm = clean(sn)
        ns[snm] = 'message'
        out(
'''
    TYPE_%s = %s
'''  % (snm, snm))

    # TODO -- submessages
    for num, field in fields.iteritems():
        write_field(name, scope, num, field, ns, packages, curr_package)

    out('''
TYPE_%s = %s
_PB_finalizers.append('%s%s')
''' % (name, name, scope + '.' if scope else '', name))

def write_field_get(num, type, name, default, scope):
    if default is not None:
        if isinstance(default, Reference):
            default = default.with_scope(scope)
        r = '''
            try:
                r = self._buf_get(%s, %sTYPE_%s, '%s')
            except:
                r = ''' + str(default)
    else:
        r = '''
            r = self._buf_get(%s, %sTYPE_%s, '%s')'''
    return r % (num, scope, type, name)


def write_field(cname, parent, num, field, parent_ns, packages, curr_package):
    req, type, name, default = field
    if hasattr(ProtoBase, 'TYPE_%s' % type.typ):
        scope = 'ProtoBase.'
        type = type.typ
    elif isinstance(type, QualifiedTypeDecl):
        scope, typ = type.lookup_type()
        if scope == None:
            scope, typ = lookup_package(type.qualifier, type.typ, packages, curr_package)
            if scope == None:
                scope, typ = lookup_package(type.qualifier, type.typ, packages, curr_package)


        if scope == None:
            scope = ''
        type = typ
    else:
        scope, type = type.lookup_type()
        if scope == None:
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
        custom_subtype = scope != 'ProtoBase.'
        scope = 'self.'
        if custom_subtype:
            out(
'''
    @property
    def %(name)s__stream(self):
        if %(num)s in self._cache:
            def acc(v):
                v_ = lambda: v
                return v_
            return [acc(v) for v in self._cache[%(num)s]]
        return self._get_repeated(%(num)s, self.TYPE_%(type)s, "%(name)s", lazy=True)
''' % {'name':name, 'num':num, 'type':type})

    # Back to all fields...
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

    def _set_%(name)s(self, v, modifying=True):
        self._evermod = modifying or self._evermod
        if self._pbf_parent_callback:
            self._pbf_parent_callback()
        if isinstance(v, (ProtoBase, RepeatedSequence)):
            self._establish_parentage_%(name)s(v)
        elif isinstance(v, list):
            list_assign_error = "Can't assign list to repeated field %(name)s"
            raise ProtoValueError(list_assign_error)
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

    _pb_field_name_%(num)d = "%(name)s"

    %(name)s = property(_get_%(name)s, _set_%(name)s, _del_%(name)s)

    @property
    def %(name)s__exists(self):
        return %(num)s in self._mods or self._buf_exists(%(num)s)

    @property
    def %(name)s__type(self):
        return %(scope)sTYPE_%(type)s

    def _finalize_%(name)s(cls):
        if is_string(%(scopeclass)sTYPE_%(type)s):
            cls._pbf_strings.append(%(num)s)
        elif _PB_type(%(scopeclass)sTYPE_%(type)s) is _PB_type:
            assert issubclass(%(scopeclass)sTYPE_%(type)s, RepeatedSequence)
            if is_string(%(scopeclass)sTYPE_%(type)s.pb_subtype):
                cls._pbf_strings.append(%(num)s)

    _pbf_finalizers.append(_finalize_%(name)s)

''' % {
    'name':name,
    'num':num,
    'field_get':write_field_get(num, type, name, default, scope),
    'type':type,
    'scope':scope,
    'scopeclass': 'cls.' + scope.split('.', 1)[-1] if scope.startswith('self.') else scope,
    })
