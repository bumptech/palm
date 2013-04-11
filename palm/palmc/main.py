import sys
import os
import traceback
from optparse import OptionParser

from palm.palmc.codegen import gen_module, convert_proto_name
from palm.palmc.parse import make_parser, ProtoParseError, Package

class Namespace(object):
    def __init__(self, package, file):
        self.file = file
        self.package = package

    def __str__(self):
        return "(Namespace) " + str(self.package) + " - " + str(file)

    def __repr__(self):
        return str(self)

def run():
    usage = "usage: %prog source dest [options]"

    parser = OptionParser()
    parser.add_option("-s", "--with-slots",
                      dest="with_slots",
                      action="store_true",
                      help="generate code using __slots__")
    (options, args) = parser.parse_args()

    if len(args) != 2:
        parser.error("exactly two arguments required: path to directory with .proto files and path to destination package")

    d = args[0]
    od = args[1]
    exit_status = 0
    packages_to_files = {}
    files_to_packages = {}
    parsed = []
    protos = [f for f in os.listdir(d) if f.endswith(".proto")]

    try:
        sys.stdout.write("Parsing...\n")
        for p in protos:
            sys.stdout.write(("%s..." % p).ljust(70))
            sys.stdout.flush()
            
            source = open(os.path.join(d, p)).read()
            _, res, l = make_parser().parse(source)

            if l != len(source):
                raise SyntaxError("Syntax error on line %s near %r" % (
                    source[:l].count('\n') + 1,
                    source[l:l+10]))

            package_list = [m for m in res if type(m) is Package]
            if len(package_list) == 1:
                package = package_list[0].name
                ns = Namespace(package, p)
                packages_to_files[package] = ns
                files_to_packages[p] = ns
            elif len(package_list) > 1:
                raise SyntaxError("Proto file %s declares more than 1 package." % p)
            else:
                package = None

            parsed.append((res, package, p))
            sys.stdout.write("[OKAY]\n")

        sys.stdout.write("Generating code...\n")
        for (res, package, p) in parsed:
            sys.stdout.write(("%s..." % p).ljust(70))
            sys.stdout.flush()
            # Filter the package mappings given to 
            # gen_module based on the packages 
            # imported by this proto file. 
            #
            # Fortunately, imports are not transitive (except 'import public'
            # but we aren't going to worry abou that), so we only need
            # to look for packages imported directly.
            imports = [m for m in res if type(m) is str]
            module_packages = dict([(package, file) for (package, file) 
                                   in packages_to_files.iteritems() 
                                   if package in imports])
            s = gen_module([m for m in res if type(m) is tuple],
                    imports,
                    [m for m in res if type(m) is list],
                    options.with_slots,
                    module_packages,
                    package
                    )
            open(os.path.join(od, convert_proto_name(p) + ".py"), 'wb').write(s)
            sys.stdout.write("[OKAY]\n")
    except:
        sys.stdout.write("[FAIL]\n")
        traceback.print_exc()
        exit_status = 1

    sys.stdout.flush()
    return exit_status
