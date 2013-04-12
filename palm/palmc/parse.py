import os
from simpleparse.parser import Parser
from simpleparse.dispatchprocessor import DispatchProcessor, dispatch, dispatchList, lines

protofile = r'''
root                    := whitespace*, message_or_import+
<whitespace>            := comment / [ \t\n]
comment                 := one_line_comment / multi_line_comment
one_line_comment        := "//", -"\n"*
multi_line_comment      := "/*", -"*/"*, "*/"
package                 := "package", whitespace+, package_name, ";"!, whitespace*
package_name            := [a-zA-Z], [a-zA-Z0-9_.]*
>message_or_import<     := message / enum / import / option / package
message                 := message_start, message_label!, whitespace*, message_body, whitespace*
<message_start>         := "message", whitespace+
message_label           := [a-zA-Z], [a-z0-9A-Z_]*
section                 := [a-z]+, [ \t\n]+
message_body            := "{"!,whitespace*,field_list,whitespace*,"}"!
>field_list<            := field_opt*
>field_opt<             := message / enum / field
field                   := field_require, whitespace+!, field_type!, whitespace+!, field_name!, whitespace*, "="!, whitespace*, field_num!, whitespace*, field_default?, ";"!, whitespace*
field_require           := "repeated" / "optional" / "required"
field_type              := field_scope?, [a-zA-Z]+!, [a-zA-Z0-9]*
field_scope             := ("."?, [a-zA-Z]!, [a-zA-Z0-9]*, ".")+
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

class Scope(object):
    """Represents a given lexical scope. Automatically inherits all names from
    the given parent scope (unless none was given). New names can be added to the 
    local scope; those names can define their own scope, as well."""

    def __init__(self, name, parent):
        self.parent = parent
        self.name = name
        self.local_names = {}

    def lookup_scope(self, name):
        """Returns a Scope objected associated with a given name in this
        lexical scope. If the name is not defined at this level of
        scope, we ask the parent scope for it. Returns None if the
        name is ultimately not found."""
        if name in self.local_names.keys():
            return self
        elif self.parent is None:
            return None
        else:
            return self.parent.lookup_scope(name)

    def curr_scope(self):
        """Returns a string representation of the current scope (that can be
        used as a python module reference)."""
        if self.parent is None:
            return self.name
        else:
            parent_name = self.parent.curr_scope()
            if len(parent_name) > 0:
                return parent_name + self.name + "."
            else:
                return self.name + "."
            
    def add_name(self, name, child_scope):
        """Add a name to the current scope, including any
        lexical scope that name brings along."""
        self.local_names[name] = child_scope

    def get_child_scope(self, name):
        """Gets the scope associated with the name given, if any. 

        Returns None if no scope is associated with the name (or if the name
        is not defined in this scope."""
        if name in self.local_names.keys():
            return self.local_names[name]
        else:
            return None

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        if self.parent is None:
            return "(" + ",".join(self.local_names.keys()) + ")"
        else:
            return "(" + str(self.name) + ": " + ",".join(self.local_names.keys()) + "); " + str(self.parent)

        
class ScopeTable(object):
    """Manages scope during parsing of proto files. A single top-level
    scope will be created when the ScopeTable is built. This top-level
    scope will not go away (until the ScopeTable goes away, of course).

    The top-level scope's parent property will always be None."""

    def __init__(self):
        self.scopes = [Scope('', None)]

    def enter_scope(self, name):
        """Start a new lexical scope, maintaining a connection to
        the parent of the new scope. Return the newly created scope."""
        self.scopes.append(Scope(name, self.scopes[-1]))
        return self.scopes[-1]

    def leave_scope(self):
        """Leave a lexical scope, returning the scope object that we are
        leaving behind. Note that the top-level scope cannot be left,
        so this function will always return that scope if all other
        scopes have been left."""
        if len(self.scopes) > 1:
            return self.scopes.pop()
        else:
            return self.scopes[0]

    def current_scope(self):
        """Current lexical scope. Returns a Scope object."""
        return self.scopes[-1]

class ProtoFieldDecl:
    """Represents the type of a field declaration."""
    
    def lookup_type(self):
        """Returns the scope of the type used to define this field. The value
        returned is a string giving a dotted path prefix (representing
        the scope of the given type) for the type. When a string is
        returned, it will ALWAYS end with a trailing period.

        If the type is not found in the current lexical environment,
        None is returned.

        """
        pass

class UnqualifiedTypeDecl(ProtoFieldDecl):
    """Represents a type specified without any qualifier."""

    def __init__(self, typ, scope):
        """Create an Unqualified type with a given type name (typ) and
        lexical scope (scope). Neither value should be empty or None."""
        self.typ = typ
        self.scope = scope

    def lookup_type(self):
        scope = self.scope.lookup_scope(self.typ)
        if scope is None:
            return None
        else:
            return scope.curr_scope()

    def __str__(self):
        return "(UnqualifiedTypeDecl) " + str(self.typ)

    def __repr__(self):
        return str(self)


class QualifiedTypeDecl(ProtoFieldDecl):
    """Represents a type specified with some sort of qualifying path. The
    path can be either a package reference or a path to some type
    defined within the current lexical scope."""
    
    def __init__(self, qualifier, typ, scope):
        """Create a Qualfied type with a given path prefix (qualifier),
        type name (typ), and lexical scope (scope). The path prefix should NOT
        include a trailing period. None of the arguments should be None or
        empty."""
        self.qualifier = qualifier
        self.typ = typ
        self.scope = scope

    def lookup_type(self):
        """Returns a string giving the path to this type in the current
        module. If the value returned is None, then the type was not
        found in the current lexical scope. Otherwise, the string
        returned gives the dot-delimited path to the type. The path
        returned ALWAYS ends with a period (".").

        Note that package-qualified types (e.g., ".com.foo.Q") are
        never found in scope here, and always result in None.

        """
        # If qualifier starts with a dot, this is 
        # definitely a package reference
        if self.qualifier.startswith("."):
            return None

        # Start at outermost name on the qualifier's path 
        # and look up its scope. Then walk down child
        # scopes for each element in the path. 
        path = self.qualifier.split(".")

        # The initial scope will contain the first name 
        # in the path; it is NOT the lexical scope defined by
        # that name (which is why our for loop starts at the first
        # path element, rather than the second).
        scope = self.scope.lookup_scope(path[0])
        for i in range(len(path)):
            if not scope:
                break
            scope = scope.get_child_scope(path[i])

        # Check the final scope to make sure it contains the
        # actual type and return.
        if scope is not None and scope.get_child_scope(self.typ) is not None:
            return scope.curr_scope()

    def __str__(self):
        return "(QualifiedTypeDecl) " + str(self.qualifier) + "." + str(self.typ)

    def __repr__(self):
        return str(self)

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

class Package(object):
    """Gives the package associated with the current file (if any). 
    Use the 'name' attribute to get back the package name."""

    def __init__(self, name):
        self.name = name

    def __str__(self):
        return "(Package) " + str(self.name)

    def __repr__(self):
        return str(self)

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
        self.scope_table = ScopeTable()

    def message(self, (tag, start, stop, subtags), buffer):
        if self.current_message:
            self.message_stack.append((self.current_message, self.message_enums))
        self.message_enums = {}
        message_label = [buffer[start:end] for (tag, start, end, _) in subtags if tag == 'message_label'][0]

        if subtags:
            self.scope_table.enter_scope(message_label)
            dispatchList(self, subtags, buffer)
            message_scope = self.scope_table.leave_scope()
            # Add the new message and its associated scope to this message's lexical 
            # scope.
            self.scope_table.current_scope().add_name(message_label, message_scope)

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

    def _get_message_namespace(self):
        return '-'.join(m[0] for m in self.message_stack)

    def message_label(self, (tag, start, stop, subtags), buffer):
        self.current_message = self._get_message_namespace() + '-' + buffer[start:stop]
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
        qualifier = dispatchList(self, subtags, buffer)
        # qualifier will be the package the type is imported from, unless
        # it is zero length. buffer[start:stop] - qualifier will leave us
        # with the type name. 
        if len(qualifier) > 0 and len(qualifier[0]) > 0:
            ns = qualifier[0][:-1]
            typ = buffer[start+len(qualifier[0]):stop]
            return QualifiedTypeDecl(ns, typ, self.scope_table.current_scope())
        else:
            typ = buffer[start:stop]
            return UnqualifiedTypeDecl(typ, self.scope_table.current_scope())

    def field_scope(self, (tag, start, stop, subtags), buffer):
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
        # Fortunately, enums can't create a new lexical scope; we
        # just add this enum to the current lexical scope.
        self.scope_table.current_scope().add_name(name, None)
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

    def package(self, (tag, start, stop, subtags), buffer):
        res = dispatchList(self, subtags, buffer)
        return res[0]

    def package_name(self, (tag, start, stop, subtags), buffer):
        return Package(buffer[start:stop])
        

class ProtoParser(Parser):
    def buildProcessor(self):
        return ProtoProcessor()

def make_parser():
    return ProtoParser(protofile)
