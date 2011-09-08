from simpleparse.parser import Parser
from simpleparse.dispatchprocessor import DispatchProcessor, dispatch, dispatchList

protofile = r'''
root                    := whitespace*, message+
<whitespace>            := [ \t\n]
message                 := message_start, message_label!, whitespace*, message_body, whitespace*
<message_start>         := "message", whitespace+
message_label           := [a-zA-Z], [a-z0-9A-Z_]*
section                 := [a-z]+, [ \t\n]+
message_body            := "{"!,whitespace*,field_list,whitespace*,"}"!
>field_list<            := field_opt*
>field_opt<             := message / field
field                   := field_require, whitespace+!, field_type!, whitespace+!, field_name!, whitespace*, "="!, whitespace*, field_num!, whitespace*, field_default?, ";"!, whitespace*
field_require           := "optional" / "required"
field_type              := [a-zA-Z], [a-z0-9A-Z_]*
field_name              := [a-zA-Z], [a-z0-9A-Z_]*
field_num               := [0-9]+
field_default           := "[", "default", whitespace*, "=", whitespace*, field_default_value, whitespace*, "]"
field_default_value     := field_default_value_s / field_default_value_f / field_default_value_i
field_default_value_s   := '"', -'"'*, '"'
field_default_value_i   := [0-9]+
field_default_value_f   := [0-9]+, field_default_value_fd+
field_default_value_fd  := ".", [0-9]+
'''

class ProtoParseError(Exception):
    def __init__(self, start, end, buf, message):
        line = lines(start, end, buffer)
        Exception.__init__("[line %s] " ++ message)

class ProtoProcessor(DispatchProcessor):
    def __init__(self):
        self.current_message = None
        self.messages = {}
        self.message_stack = []

    def message(self, (tag, start, stop, subtags), buffer):
        if self.current_message:
            self.message_stack.append(self.current_message)

        if subtags:
            dispatchList(self, subtags, buffer)
        cm = self.current_message

        if self.message_stack:
            self.current_message = self.message_stack.pop()
            self.messages[self.current_message][1].append(cm)
        else:
            self.current_message = None

        return cm, self.messages[cm][0], [(sm, self.messages[sm]) for sm in self.messages[cm][1]]

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


class ProtoParser(Parser):
    def buildProcessor(self):
        return ProtoProcessor()

parser = ProtoParser(protofile)

from sys import stdin
r = parser.parse(stdin.read())

from codegen import gen_module

s = gen_module(r[1])
print s
