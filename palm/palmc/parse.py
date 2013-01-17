from simpleparse.parser import Parser
from simpleparse.dispatchprocessor import DispatchProcessor, dispatch, dispatchList, lines

protofile = r'''
root                    := whitespace*, message_or_import+
<whitespace>            := comment / [ \t\n]
comment                 := one_line_comment / multi_line_comment / package
one_line_comment        := "//", -"\n"*
multi_line_comment      := "/*", -"*/"*, "*/"
package                 := "package", whitespace+, [a-zA-Z], [a-zA-Z0-9_.]*, ";"!, whitespace*
>message_or_import<     := message / enum / import / option
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
field_default_value     := field_default_value_s / field_default_value_b / field_default_value_f / field_default_value_i / field_default_value_l
field_default_value_s   := '"', -'"'*, '"'
field_default_value_b   := "true" / "false"
field_default_value_i   := "-"?, [0-9]+
field_default_value_f   := "-"?, [0-9]+, field_default_value_fd+
field_default_value_fd  := ".", [0-9]+
field_default_value_l   := [a-zA-Z], [a-z0-9A-Z_]*
enum                    := "enum", whitespace+!, enum_name, whitespace*, "{"!, whitespace*, enum_list, whitespace*, "}"!, whitespace*
enum_name               := [a-zA-Z], [a-z0-9A-Z_]*
>enum_list<             := enum_value*
enum_value              := enum_label, whitespace*, "=", whitespace*, enum_code, whitespace*, ";", whitespace*
enum_label              := [a-zA-Z], [a-z0-9A-Z_]*
enum_code               := [0-9]+
>import<                := "import", whitespace+!, '"'!, import_path, '"'!, whitespace*, ";"!, whitespace*
import_path             := -'"'*
<option>                := "option", -';'*, ";"!, whitespace*
'''

class Reference(object):
    """A reference to a name

    Can show up in parsed results.

    """
    def __init__(self, name):
        self.name = name

    def with_scope(self, scope):
        """Simply joins the referenced name to the given scope

        The scope must end with a "." character.

        """
        assert not scope or scope[-1] == ".", "Invalid scope: %r" % scope
        return "%s%s" % (scope, self.name)

class ProtoParseError(Exception):
    def __init__(self, start, end, buf, message):
        line = lines(start, end, buf)
        Exception.__init__(self, ("[line %s] " % line) + message)

class ProtoProcessor(DispatchProcessor):
    def __init__(self):
        self.current_message = None
        self.messages = {}
        self.message_enums = {}
        self.enum_sets = {}
        self.message_stack = []
        self.imports = set()

    def message(self, (tag, start, stop, subtags), buffer):
        if self.current_message:
            self.message_stack.append((self.current_message, self.message_enums))
        self.message_enums = {}

        if subtags:
            dispatchList(self, subtags, buffer)
        cm = self.current_message
        en = self.message_enums
        self.enum_sets[cm] = en

        if self.message_stack:
            self.current_message, self.message_enums = self.message_stack.pop()
            self.messages[self.current_message][1].append(cm)
        else:
            self.current_message = None

        self.messages[cm] = (self.messages[cm][0], 
            [(sm, self.messages[sm]) for sm in self.messages[cm][1]],
            self.enum_sets[cm])

        return cm, self.messages[cm]

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
        assert num not in self.messages[self.current_message][0], \
               'Duplicate field number %s in %s' % (num, self.current_message.split('-')[1])
        self.messages[self.current_message][0][num] = req,typ,name,default

    def field_default(self, (tag, start, stop, subtags), buffer):
        tag, start, stop, subtags = subtags[0]
        b = buffer[start:stop]
        if b == 'true':
            b = True
        elif b == 'false':
            b = False
        elif subtags and subtags[0][0] == 'field_default_value_l':
            b = Reference(b)
        return b

    def enum(self, (tag, start, stop, subtags), buffer):
        res = dispatchList(self, subtags, buffer)
        name = res[0]
        rest = res[1:]
        fields = dict(rest)
        if self.current_message:
            # Shove this enum into storage for the message that is
            # currently being parsed.
            self.message_enums[name] = fields
        return [name, fields]

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

class ProtoParser(Parser):
    def buildProcessor(self):
        return ProtoProcessor()

def make_parser():
    return ProtoParser(protofile)
