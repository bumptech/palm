from simpleparse.parser import Parser
from simpleparse.dispatchprocessor import DispatchProcessor, dispatch, dispatchList

protofile = r'''
root                    := whitespace*, message_or_import+
<whitespace>            := comment / [ \t\n]
comment                 := "//", -"\n"*
>message_or_import<     := message / import
message                 := message_start, message_label!, whitespace*, message_body, whitespace*
<message_start>         := "message", whitespace+
message_label           := [a-zA-Z], [a-z0-9A-Z_]*
section                 := [a-z]+, [ \t\n]+
message_body            := "{"!,whitespace*,field_list,whitespace*,"}"!
>field_list<            := field_opt*
>field_opt<             := message / enum / field
field                   := field_require, whitespace+!, field_type!, whitespace+!, field_name!, whitespace*, "="!, whitespace*, field_num!, whitespace*, field_default?, ";"!, whitespace*
field_require           := "repeated" / "optional" / "required"
field_type              := [a-zA-Z], [a-z0-9A-Z_]*
field_name              := [a-zA-Z], [a-z0-9A-Z_]*
field_num               := [0-9]+
field_default           := "[", "default", whitespace*, "=", whitespace*, field_default_value, whitespace*, "]"
field_default_value     := field_default_value_s / field_default_value_f / field_default_value_i
field_default_value_s   := '"', -'"'*, '"'
field_default_value_i   := [0-9]+
field_default_value_f   := [0-9]+, field_default_value_fd+
field_default_value_fd  := ".", [0-9]+
enum                    := "enum", whitespace+!, enum_name, whitespace*, "{"!, whitespace*, enum_list, whitespace*, "}"!, whitespace*
enum_name               := [a-zA-Z], [a-z0-9A-Z_]*
>enum_list<             := enum_value*
enum_value              := enum_label, whitespace*, "=", whitespace*, enum_code, whitespace*, ";", whitespace*
enum_label              := [a-zA-Z], [a-z0-9A-Z_]*
enum_code               := [0-9]+
>import<                  := "import", whitespace+!, '"'!, import_path, '"'!, whitespace*, ";"!, whitespace*
import_path             := -'"'*
'''

class ProtoParseError(Exception):
    def __init__(self, start, end, buf, message):
        line = lines(start, end, buffer)
        Exception.__init__("[line %s] " ++ message)

class ProtoProcessor(DispatchProcessor):
    def __init__(self):
        self.current_message = None
        self.messages = {}
        self.enums = {}
        self.enum_sets = {}
        self.message_stack = []
        self.imports = set()

    def message(self, (tag, start, stop, subtags), buffer):
        if self.current_message:
            self.message_stack.append((self.current_message, self.enums))
            self.enums = {}

        if subtags:
            dispatchList(self, subtags, buffer)
        cm = self.current_message

        if self.message_stack:
            self.current_message, self.enums = self.message_stack.pop()
            self.messages[self.current_message][1].append(cm)
        else:
            self.current_message = None

        en = self.enums
        self.enum_sets[cm] = en
        self.enums = {}

        return cm, self.messages[cm][0], [(sm, self.messages[sm], self.enum_sets[sm]) for sm in self.messages[cm][1]], en

    def message_label(self, (tag, start, stop, subtags), buffer):
        self.current_message = str(len(self.message_stack)) + '-' +  buffer[start:stop]
        if self.current_message in self.messages:
            raise ProtoParseError(start, stop, buffer, "message %s already defined" % self.current_message)
        self.messages[self.current_message] = {}, [] # fields, submessages

    def message_body(self, (tag, start, stop, subtags), buffer):
        if subtags:
            return dispatchList(self, subtags, buffer)

    def field_require(self, (tag, start, stop, subtags), buffer):
        req = buffer[start:stop]
        return req

    def field_type(self, (tag, start, stop, subtags), buffer):
        return buffer[start:stop]

    def field_name(self, (tag, start, stop, subtags), buffer):
        return buffer[start:stop]

    def field_num(self, (tag, start, stop, subtags), buffer):
        return int(buffer[start:stop])

    def field(self, (tag, start, stop, subtags), buffer):
        res = dispatchList(self, subtags, buffer)
        if len(res) == 4:
            res.append(None)
        req,typ,name,num,default = res
        self.messages[self.current_message][0][num] = req,typ,name,default

    def field_default(self, (tag, start, stop, subtags), buffer):
        tag, start, stop, subtags = subtags[0]
        return buffer[start:stop]

    def enum(self, (tag, start, stop, subtags), buffer):
        res = dispatchList(self, subtags, buffer)
        name = res[0]
        rest = res[1:]
        fields = dict(rest)
        self.enums[name] = fields

    def enum_value(self, (tag, start, stop, subtags), buffer):
        return tuple(dispatchList(self, subtags, buffer))

    def enum_name(self, (tag, start, stop, subtags), buffer):
        return buffer[start:stop]

    def enum_label(self, (tag, start, stop, subtags), buffer):
        return buffer[start:stop]

    def enum_code(self, (tag, start, stop, subtags), buffer):
        return int(buffer[start:stop])

    def import_path(self, (tag, start, stop, subtags), buffer):
        path = buffer[start:stop]
        return path
        self.imports.add(path)

class ProtoParser(Parser):
    def buildProcessor(self):
        return ProtoProcessor()

parser = ProtoParser(protofile)

from sys import stdin
r = parser.parse(stdin.read())

from codegen import gen_module

res = r[1]
s = gen_module([m for m in res if type(m) is tuple], [m for m in res if type(m) is str])
print s
