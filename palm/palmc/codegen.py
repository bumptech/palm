try:
    import cStringIO as StringIO
except ImportError:
    import StringIO
import operator as op
import os
from palm.palm import ProtoBase


def convert_proto_name(filename):
    """Given a .proto filename, return the corresponding palm module name"""
    filename = os.path.basename(filename)
    p, last = filename.rsplit(".", 1)
    assert last == "proto"
    return "%s_palm" % p


class CodeGenerator(object):
    def __init__(self):
        self.output = StringIO.StringIO()
        self.prefix = ''

    def gen_module(self, messages, imports, tlenums):
        self.prefix = ''

        self.out("from palm.palm import "
            "ProtoBase, is_string, RepeatedSequence, ProtoValueError\n")

        for i in imports:
            self.out('from %s import *\n' % convert_proto_name(i))

        self.out("\n")
        self.out("_PB_type = type\n")
        self.out("_PB_finalizers = []\n")

        for ename, espec in tlenums:
            self.write_enum(ename, espec)

        for n, (fields, subs, en) in messages:
            self.write_class(n, '', fields, subs, en)

        self.out('''

for cname in _PB_finalizers:
    eval(cname)._pbf_finalize()

del _PB_finalizers
''')

        out = self.output.getvalue()

        self.output = StringIO.StringIO()
        return out

    def out(self, s):
        s = self.prefix + s.replace("\n", "\n" + self.prefix)
        self.output.write(s)

    def clean(self, name):
        return name.split('-', 1)[1]

    def write_enum(self, name, spec):
        self.out("\n# Enumeration: %s\n" % name)
        for cn, value in sorted(spec.items(), key=op.itemgetter(1)):
            self.out("%s = %s\n" % (cn, value))
        self.out("\nTYPE_%s = ProtoBase.TYPE_int32\n" % name)

    def write_class(self, name, scope, fields, subs, enums):
        name = self.clean(name)
        self.out(
'''
class %s(ProtoBase):
    def __init__(self, _pbf_buf='', _pbf_parent_callback=None, **kw): 
        self._pbf_parent_callback = _pbf_parent_callback
        self._cache = {}
        self._pbf_establish_parent_callback = None
        self._required = [%s]
        self._field_map = %r
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

    _pbf_strings = []
    _pbf_finalizers = []

    def __contains__(self, item):
        return getattr(self, '%%s__exists' %% item, False)

    def __str__(self):
        return '\\n'.join('%%s: %%s' %% (f, repr(getattr(self, '_get_%%s' %% f)())) for f in self.fields()
                          if getattr(self, '%%s__exists' %% f))
''' % (name,
       ", ".join(str(num) for num, (req, _, _, _) in fields.iteritems() if req == 'required'),
       dict((name, num) for num, (_, _, name, _) in fields.iteritems()),
       "', '".join(name for _, _, name, _ in fields.values())))

        ns = {}
        for ename, espec in enums.iteritems():
            self.prefix += "    "
            self.write_enum(ename, espec)
            self.prefix = self.prefix[:-4]
            ns[ename] = 'enum'

        next_scope = name if not scope else ".".join([scope, name])
        for sn, (sf, ss, sens) in subs:
            self.prefix += "    "
            self.write_class(sn, next_scope, sf, ss, sens)
            self.prefix = self.prefix[:-4]
            snm = self.clean(sn)
            ns[snm] = 'message'
            self.out(
'''
    TYPE_%s = %s
'''  % (snm, snm))

        # TODO -- submessages
        for num, field in fields.iteritems():
            self.write_field(name, scope, num, field, ns)

        self.out('''
TYPE_%s = %s
_PB_finalizers.append('%s%s')
''' % (name, name, scope + '.' if scope else '', name))

    def write_field_get(self, num, type, name, default, scope):
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

    def write_field(self, cname, parent, num, field, parent_ns):
        req, type, name, default = field
        if hasattr(ProtoBase, 'TYPE_%s' % type):
            scope = 'ProtoBase.'
        elif type in parent_ns:
            scope = '%s.' % (cname if not parent else ".".join([parent, cname]))
        else:
            scope = ''
        if req == 'repeated':
            self.out(
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
            self.out(
'''
    @property
    def %s__stream(self):
        return self._get_repeated(%s, self.TYPE_%s, "%s", lazy=True)
''' % (name, num, type, name))

        # Back to all fields...
        self.out(
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
        'name': name,
        'num': num,
        'field_get': self.write_field_get(num, type, name, default, scope),
        'type': type,
        'scope': scope,
        'scopeclass': 'cls.' + scope.split('.', 1)[-1] if scope.startswith('self.') else scope,
        })
