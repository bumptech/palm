import sys
pfx = ''
o = []
def gen_module(messages):
    global pfx
    global o
    pfx = ''

    out('from palm import ProtoBase\n\n')
    for (n, fields, subs) in messages:
        write_class(n, fields, subs)

    all = ''.join(o)

    o = []
    return all

def out(s):
    global o
    s = pfx + s.replace("\n", "\n" + pfx)
    o.append(s)

def clean(name):
    return name.split('-', 1)[1]

def write_class(name, fields, subs):
    global pfx
    name = clean(name)
    out(
'''
class %s(ProtoBase):
    def __init__(self, _pbf_buf='', _pbf_parent_callback=None): # XXX support setting
        ProtoBase.__init__(self, _pbf_buf)
        self._cache = {}
        self._mods = {}
        self._pbf_parent_callback = _pbf_parent_callback

    def dumps(self):
        self._save(self._mods, self._cache)
        self.mods = {}
        return self._serialize()

    def fields(self):
        return ['%s']

    def __str__(self):
        return '\\n'.join('%%s: %%s' %% (f, repr(getattr(self, '_get_%%s' %% f)())) for f in self.fields()
                          if getattr(self, '%%s__exists' %% f))
''' % (name,
       "', '".join(name for _, _, name, _ in fields.values())))
    for sn, (sf, ss) in subs:
        pfx += "    "
        write_class(sn, sf, ss)
        pfx = pfx[:-4]
        snm = clean(sn)
        out(
'''
    TYPE_%s = %s
'''  % (snm, snm))

    # TODO -- submessages
    for num, field in fields.iteritems():
        write_field(num, field)

def write_field_get(num, field):
    _, type, name, default = field
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

def write_field(num, field):
    _, type, name, default = field
    out(
'''
    def _get_%s(self):
        if %s in self._cache:
            r = self._cache[%s]
        else:%s
            self._cache[%s] = r
        return r

    def _set_%s(self, v):
        if self._pbf_parent_callback:
            self._pbf_parent_callback()
        if isinstance(v, ProtoBase):
            v._pbf_parent_callback = self._mod_%s
        self._cache[%s] = v
        self._mods[%s] = self.TYPE_%s

    def _mod_%s(self):
        self._mods[%s] = self.TYPE_%s

    def _del_%s(self):
        if self._pbf_parent_callback:
            self._pbf_parent_callback()
        if %s in self._cache:
            del self._cache[%s]
        if %s in self._mods:
            del self._mods[%s]
        self._buf_del(%s)

    %s = property(_get_%s, _set_%s, _del_%s)

    @property
    def %s__exists(self):
        return %s in self._mods or self._buf_exists(%s)

''' % (name, num, num, write_field_get(num, field), num,
    name, name, num, num, type,
    name, num, type,
    name, num, num, num, num, num,
    name, name, name, name,
    name, num, num))
