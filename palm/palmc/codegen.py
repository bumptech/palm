pfx = ''
o = []
def gen_module(messages):
    print messages
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
    name = clean(name)
    out(
'''
class %s(ProtoBase):
    def __init__(self, _pbf_buf=''): # XXX support setting
        ProtoBase.__init__(self, _pbf_buf)
        self._cache = {}
        self._mods = {}

    def dumps(self):
        self._save(self._mods, self._cache)
        self.mods = {}
        return self._serialize()

''' % name)

    # TODO -- submessages
    for num, field in fields.iteritems():
        write_field(num, field)

def write_field(num, field):
    _, type, name = field
    out(
'''
    def _get_%s(self):
        if %s in self._cache:
            r = self._cache[%s]
        else:
            r = self._buf_get(%s, ProtoBase.TYPE_%s, '%s')
            self._cache[%s] = r
        return r

    def _set_%s(self, v):
        self._cache[%s] = v
        self._mods[%s] = ProtoBase.TYPE_%s

    %s = property(_get_%s, _set_%s)

    @property
    def %s__exists(self):
        return %s in self._mods or self._buf_exists(%s)

''' % (name, num, num, num, type, name, num,
    name, num, num, type,
    name, name, name,
    name, num, num))
